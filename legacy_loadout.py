"""Legacy loadout import/export helpers kept outside the main app flow."""

import json
import os


def save_loadout(app, app_dir, filedialog_module):
    order = app.state.get("order", [])
    enabled_map = app.state.get("enabled", {})

    if not order:
        app.show_warning("Warning", "No mods loaded.")
        return

    default_path = os.path.join(app_dir, "dd_mod_loadout.json")
    file_path = filedialog_module.asksaveasfilename(
        title="Save Mod Loadout",
        defaultextension=".json",
        initialfile=os.path.basename(default_path),
        initialdir=app_dir,
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )

    if not file_path:
        return

    enabled_mods = [mod for mod in order if enabled_map.get(mod, True)]
    disabled_mods = [mod for mod in order if not enabled_map.get(mod, True)]

    loadout = {
        "mods_path": app.mods_path.get().strip(),
        "order": order,
        "enabled": {mod: enabled_map.get(mod, True) for mod in order},
        "enabled_mods": enabled_mods,
        "disabled_mods": disabled_mods,
        "category_memory": app.state.get("category_memory", {}),
        "nicknames": {
            mod: app.state.get("nicknames", {}).get(mod, "")
            for mod in order
            if app.nickname_for_mod(mod)
        },
        "categories": {
            mod: app.state.get("categories", {}).get(mod, "Unassigned")
            for mod in order
        },
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(loadout, f, indent=2)
    except Exception as error:
        app.show_error("Error", f"Failed to save loadout:\n\n{error}")
        return

    app.set_status_text(
        f"Loadout saved: {len(enabled_mods)} enabled | {len(disabled_mods)} disabled"
    )
    app.show_info("Saved", f"Loadout saved:\n{file_path}")


def load_loadout(app, app_dir, filedialog_module):
    current_order = app.state.get("order", [])

    if not current_order:
        app.show_warning("Warning", "Load mods before loading a loadout.")
        return

    file_path = filedialog_module.askopenfilename(
        title="Load Mod Loadout",
        initialdir=app_dir,
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )

    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            loadout = json.load(f)
    except Exception as error:
        app.show_error("Error", f"Failed to read loadout:\n\n{error}")
        return

    loadout_order = loadout.get("order", [])
    loadout_enabled = loadout.get("enabled", {})

    if not isinstance(loadout_order, list) or not isinstance(loadout_enabled, dict):
        app.show_error("Error", "That file does not look like a valid loadout.")
        return

    current_mods = set(current_order)
    missing_mods = [mod for mod in loadout_order if mod not in current_mods]
    restored_order = [mod for mod in loadout_order if mod in current_mods]
    new_mods = [mod for mod in current_order if mod not in restored_order]

    app.state["order"] = restored_order + new_mods

    for mod in current_order:
        if mod in loadout_enabled:
            app.state["enabled"][mod] = bool(loadout_enabled[mod])

    loadout_categories = loadout.get("categories", {})
    if isinstance(loadout_categories, dict):
        for mod, cat in loadout_categories.items():
            if mod in current_mods and cat:
                app.state["categories"][mod] = cat
                app.remember_mod_category(mod, cat)

    loadout_memory = loadout.get("category_memory", {})
    if isinstance(loadout_memory, dict):
        app.state.setdefault("category_memory", {}).update(loadout_memory)

    loadout_nicknames = loadout.get("nicknames", {})
    if isinstance(loadout_nicknames, dict):
        nicknames = app.state.setdefault("nicknames", {})
        for mod, nickname in loadout_nicknames.items():
            if mod in current_mods and str(nickname).strip():
                nicknames[mod] = " ".join(str(nickname).split())

    app.save_state()
    app.rebuild_category_menus()
    app.refresh()

    restored_enabled = sum(
        1 for mod in app.state["order"]
        if app.state["enabled"].get(mod, True)
    )
    restored_disabled = len(app.state["order"]) - restored_enabled

    status = f"Loadout loaded: {restored_enabled} enabled | {restored_disabled} disabled"
    if missing_mods:
        status += f" | {len(missing_mods)} missing"

    app.set_status_text(status)

    if missing_mods:
        preview = "\n".join(missing_mods[:10])
        extra = ""
        if len(missing_mods) > 10:
            extra = f"\n...and {len(missing_mods) - 10} more"
        app.show_warning(
            "Loadout Loaded With Missing Mods",
            f"Loaded what matched your current mod list.\n\nMissing from current mods:\n{preview}{extra}"
        )
    else:
        app.show_info("Loaded", f"Loadout loaded:\n{file_path}")
