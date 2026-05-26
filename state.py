"""State defaults, persistence, and migration helpers for DD Manager."""

import json
import os
import shutil


def build_default_state(default_language, default_categories):
    return {
        "language": default_language,
        "mods_path": "",
        "last_save_path": "",
        "last_backup_path": "",
        "last_output_path": "",
        "selected_profile_path": "",
        "manual_game_root": "",
        "manual_local_mods_path": "",
        "manual_workshop_mods_path": "",
        "first_run_summary_shown": False,
        "view_mode": "Comfortable",
        "order": [],
        "categories": {},
        "category_order": list(default_categories),
        "category_colors": {},
        "category_memory": {},
        "auto_category_attempted": {},
        "custom_categories": [],
        "enabled": {},
        "nicknames": {},
        "metadata": {},
        "mod_paths": {},
    }


def migrate_state_data(state, default_language, default_categories, normalize_hex_color):
    state = dict(state or {})
    defaults = build_default_state(default_language, default_categories)
    for key, value in defaults.items():
        state.setdefault(key, value if not isinstance(value, (list, dict)) else value.copy())

    state["category_colors"] = {
        category: normalize_hex_color(color)
        for category, color in state.get("category_colors", {}).items()
        if normalize_hex_color(color)
    }

    ordered = []
    seen_order = set()
    for cat in state.get("category_order", []):
        if cat and cat not in ("All", "Unassigned") and cat.lower() not in seen_order:
            ordered.append(cat)
            seen_order.add(cat.lower())
    state["category_order"] = ordered

    existing = {cat.lower() for cat in default_categories}
    existing.update(cat.lower() for cat in state["custom_categories"])
    for cat in state["categories"].values():
        if cat and cat not in ("All", "Unassigned") and cat.lower() not in existing:
            state["custom_categories"].append(cat)
            existing.add(cat.lower())

    order_seen = {cat.lower() for cat in state["category_order"]}
    for cat in default_categories:
        if cat.lower() not in order_seen:
            state["category_order"].append(cat)
            order_seen.add(cat.lower())
    for cat in state["custom_categories"]:
        if cat and cat.lower() not in order_seen:
            state["category_order"].append(cat)
            order_seen.add(cat.lower())
    for cat in state["categories"].values():
        if cat and cat not in ("All", "Unassigned") and cat.lower() not in order_seen:
            state["category_order"].append(cat)
            order_seen.add(cat.lower())

    return state


def load_state_file(state_file, app_dir, default_language, default_categories, normalize_hex_color):
    backup_state = os.path.join(app_dir, "mod_state.backup.json")
    raw_state = None
    notices = []

    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                raw_state = json.load(f)
        except Exception as error:
            try:
                with open(backup_state, "r", encoding="utf-8") as f:
                    raw_state = json.load(f)
                notices.append((
                    "warning",
                    "State Recovered",
                    "The main state file could not be read, so the app loaded the backup state.\n\n"
                    f"Main file:\n{state_file}\n\n"
                    f"Original error:\n{error}",
                ))
            except Exception:
                notices.append((
                    "warning",
                    "Warning",
                    f"Could not read state file.\n\n{state_file}\n\n{error}",
                ))

    state = migrate_state_data(
        raw_state,
        default_language,
        default_categories,
        normalize_hex_color,
    )
    return state, notices


def save_state_file(state, state_file, app_dir):
    backup_state = os.path.join(app_dir, "mod_state.backup.json")
    if os.path.exists(state_file):
        try:
            shutil.copy2(state_file, backup_state)
        except Exception:
            pass

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
