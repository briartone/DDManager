"""Filesystem, install, and profile discovery helpers for DD Manager."""

import os
import re
from datetime import datetime


def get_app_root(sys_module, file_path):
    if getattr(sys_module, "frozen", False):
        return os.path.dirname(os.path.abspath(sys_module.executable))
    return os.path.dirname(os.path.abspath(file_path))


def is_workshop_content_path(folder_path, steam_app_id):
    if not folder_path:
        return False
    try:
        normalized = os.path.normcase(os.path.abspath(folder_path))
    except Exception:
        return False
    workshop_fragment = os.path.normcase(
        os.path.join("steamapps", "workshop", "content", steam_app_id)
    )
    return workshop_fragment in normalized


def _unique_paths(paths):
    seen = set()
    unique = []
    for path in paths:
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen:
            unique.append(path)
            seen.add(norm)
    return unique


def steam_install_roots(is_windows, is_linux, winreg_module):
    roots = []
    if is_windows:
        if winreg_module is not None:
            for hive, subkey, value_name in (
                (winreg_module.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg_module.HKEY_CURRENT_USER, r"Software\Valve\Steam", "InstallPath"),
                (winreg_module.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam", "InstallPath"),
                (winreg_module.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam", "InstallPath"),
            ):
                try:
                    with winreg_module.OpenKey(hive, subkey) as key:
                        value, _ = winreg_module.QueryValueEx(key, value_name)
                except Exception:
                    continue
                if value and os.path.isdir(value):
                    roots.append(value)

        for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env_name)
            if base:
                candidate = os.path.join(base, "Steam")
                if os.path.isdir(candidate):
                    roots.append(candidate)

        default = r"C:\Program Files (x86)\Steam"
        if os.path.isdir(default):
            roots.append(default)
    elif is_linux:
        home = os.path.expanduser("~")
        linux_candidates = [
            os.path.join(home, ".steam", "steam"),
            os.path.join(home, ".steam", "root"),
            os.path.join(home, ".local", "share", "Steam"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", "data", "Steam"),
        ]
        for candidate in linux_candidates:
            if os.path.isdir(candidate):
                roots.append(candidate)

    return _unique_paths(roots)


def windows_documents_roots():
    roots = []
    for env_name in (
        "USERPROFILE",
        "OneDrive",
        "OneDriveConsumer",
        "OneDriveCommercial",
    ):
        base = os.environ.get(env_name)
        if not base:
            continue
        candidate = os.path.join(base, "Documents")
        if os.path.isdir(candidate):
            roots.append(candidate)

    expanded = os.path.expanduser("~/Documents")
    if os.path.isdir(expanded):
        roots.append(expanded)

    return _unique_paths(roots)


def steam_library_roots(steam_roots):
    libraries = []
    for steam_root in steam_roots:
        libraries.append(steam_root)
        vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
        if not os.path.exists(vdf_path):
            continue
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            library = os.path.expanduser(match.group(1).replace("\\\\", "\\"))
            if os.path.isdir(library):
                libraries.append(library)

    return _unique_paths(libraries)


def gog_game_roots(is_windows, winreg_module, dd_game_dir_names):
    roots = []
    if not is_windows:
        return roots

    if winreg_module is not None:
        registry_keys = (
            (winreg_module.HKEY_LOCAL_MACHINE, r"Software\GOG.com\Games"),
            (winreg_module.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\GOG.com\Games"),
            (winreg_module.HKEY_CURRENT_USER, r"Software\GOG.com\Games"),
        )
        for hive, subkey in registry_keys:
            try:
                with winreg_module.OpenKey(hive, subkey) as games_key:
                    index = 0
                    while True:
                        try:
                            child_name = winreg_module.EnumKey(games_key, index)
                        except OSError:
                            break
                        index += 1

                        try:
                            with winreg_module.OpenKey(games_key, child_name) as child_key:
                                value, _ = winreg_module.QueryValueEx(child_key, "path")
                        except Exception:
                            continue

                        if value and os.path.isdir(value):
                            roots.append(value)
            except Exception:
                continue

    for base in (
        r"C:\GOG Games",
        r"C:\Program Files (x86)\GOG Galaxy\Games",
        r"C:\Program Files\GOG Galaxy\Games",
    ):
        if not os.path.isdir(base):
            continue
        for folder_name in dd_game_dir_names:
            candidate = os.path.join(base, folder_name)
            if os.path.isdir(candidate):
                roots.append(candidate)

    return _unique_paths(roots)


def candidate_game_folders(steam_libraries, gog_roots, dd_game_dir_names):
    candidates = []
    for library in steam_libraries:
        for folder_name in dd_game_dir_names:
            candidate = os.path.join(library, "steamapps", "common", folder_name)
            if os.path.isdir(candidate):
                candidates.append(candidate)
    for candidate in gog_roots:
        if os.path.isdir(candidate):
            candidates.append(candidate)
    return _unique_paths(candidates)


def candidate_local_mod_folders(game_folders):
    candidates = []
    for game_root in game_folders:
        candidate = os.path.join(game_root, "mods")
        if os.path.isdir(candidate):
            candidates.append(candidate)
    return _unique_paths(candidates)


def candidate_workshop_mod_folders(steam_libraries, steam_app_id):
    candidates = []
    for library in steam_libraries:
        candidate = os.path.join(library, "steamapps", "workshop", "content", steam_app_id)
        if os.path.isdir(candidate):
            candidates.append(candidate)
    return _unique_paths(candidates)


def first_valid_manual_path(manual_path, candidates):
    if manual_path and os.path.isdir(manual_path):
        return manual_path
    if not candidates:
        return ""
    return candidates[0]


def candidate_mod_folders(current_path, workshop_folders, local_folders):
    candidates = []
    candidates.extend(workshop_folders)
    candidates.extend(local_folders)
    if current_path:
        candidates.insert(0, current_path)

    valid = []
    seen = set()
    for path in candidates:
        if not path or not os.path.isdir(path):
            continue
        try:
            has_mods = any(os.path.isdir(os.path.join(path, name)) for name in os.listdir(path))
        except Exception:
            has_mods = False
        norm = os.path.normcase(os.path.abspath(path))
        if has_mods and norm not in seen:
            valid.append(path)
            seen.add(norm)
    return valid


def detect_best_mod_folder(current_path, candidates):
    if current_path and os.path.isdir(current_path):
        return current_path
    if not candidates:
        return ""

    def folder_count(path):
        try:
            return sum(1 for name in os.listdir(path) if os.path.isdir(os.path.join(path, name)))
        except Exception:
            return 0

    return max(candidates, key=folder_count)


def companion_mod_folders(primary_path, steam_libraries, steam_app_id, dd_game_name):
    companions = []
    primary_norm = os.path.normcase(os.path.abspath(primary_path)) if primary_path else ""

    for library in steam_libraries:
        for candidate in (
            os.path.join(library, "steamapps", "workshop", "content", steam_app_id),
            os.path.join(library, "steamapps", "common", dd_game_name, "mods"),
        ):
            if not os.path.isdir(candidate):
                continue
            norm = os.path.normcase(os.path.abspath(candidate))
            if norm != primary_norm:
                companions.append(candidate)

    return _unique_paths(companions)


def detected_save_files_from_disk(
    steam_roots,
    steam_libraries,
    windows_documents,
    is_windows,
    is_linux,
    steam_app_id,
):
    candidates = []
    for steam_root in steam_roots:
        userdata = os.path.join(steam_root, "userdata")
        if not os.path.isdir(userdata):
            continue
        try:
            steam_users = os.listdir(userdata)
        except Exception:
            continue
        for steam_user in steam_users:
            remote = os.path.join(userdata, steam_user, steam_app_id, "remote")
            if not os.path.isdir(remote):
                continue
            for root_dir, _, files in os.walk(remote):
                if "persist.game.json" in files:
                    candidates.append(os.path.join(root_dir, "persist.game.json"))

    if is_linux:
        for library in steam_libraries:
            compat_root = os.path.join(
                library,
                "steamapps",
                "compatdata",
                steam_app_id,
                "pfx",
                "drive_c",
                "users",
                "steamuser",
                "Documents",
                "Darkest",
            )
            if not os.path.isdir(compat_root):
                continue
            for root_dir, _, files in os.walk(compat_root):
                if "persist.game.json" in files:
                    candidates.append(os.path.join(root_dir, "persist.game.json"))

        linux_local_root = os.path.join(
            os.path.expanduser("~"),
            ".local",
            "share",
            "Red Hook Studios",
            "Darkest",
        )
        if os.path.isdir(linux_local_root):
            for root_dir, _, files in os.walk(linux_local_root):
                if "persist.game.json" in files:
                    candidates.append(os.path.join(root_dir, "persist.game.json"))

    if is_windows:
        for documents_root in windows_documents:
            darkest_root = os.path.join(documents_root, "Darkest")
            if not os.path.isdir(darkest_root):
                continue
            for root_dir, _, files in os.walk(darkest_root):
                if "persist.game.json" in files:
                    candidates.append(os.path.join(root_dir, "persist.game.json"))

    return candidates


def detect_save_files(selected_save, last_save, detected_save_files):
    candidates = []
    if selected_save:
        candidates.append(selected_save)
    if last_save:
        candidates.append(last_save)
    candidates.extend(detected_save_files)

    valid = []
    seen = set()
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen:
            valid.append(path)
            seen.add(norm)
    return valid


def profile_number_from_path(path):
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        match = re.fullmatch(r"profile[_ -]?(\d+)", part, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def profile_sort_key(slot):
    number = slot.get("number")
    if number is None:
        return (9999, slot.get("path", "").lower())
    return (number, slot.get("path", "").lower())


def read_profile_week(profile_save_path, read_scalar_dson_fields):
    profile_dir = os.path.dirname(profile_save_path)
    game_path = os.path.join(profile_dir, "persist.game.json")
    game_values = {}
    if os.path.isfile(game_path):
        game_values = read_scalar_dson_fields(game_path, wanted_names={"inraid"})

    if game_values.get("inraid") is True:
        inraid_candidates = [
            ("persist.campaign_log.json", "current_week", 0),
            ("persist.campaign_log.json", "total_weeks", 0),
            ("persist.estate.json", "week", 0),
        ]
        for filename, field_name, adjustment in inraid_candidates:
            candidate_path = os.path.join(profile_dir, filename)
            if not os.path.isfile(candidate_path):
                continue

            values = read_scalar_dson_fields(candidate_path, wanted_names={field_name})
            if field_name not in values:
                continue

            try:
                week_number = int(values[field_name]) + adjustment
            except Exception:
                continue

            if week_number >= 0:
                return week_number

    exact_candidates = [
        ("persist.town_event.json", "last_town_event_week", 0),
        ("persist.estate.json", "week", 0),
        ("persist.campaign_log.json", "current_week", 0),
        ("persist.campaign_log.json", "total_weeks", -1),
    ]

    for filename, field_name, adjustment in exact_candidates:
        candidate_path = os.path.join(profile_dir, filename)
        if not os.path.isfile(candidate_path):
            continue

        values = read_scalar_dson_fields(candidate_path, wanted_names={field_name})
        if field_name not in values:
            continue

        try:
            week_number = int(values[field_name]) + adjustment
        except Exception:
            continue

        if week_number >= 0:
            return week_number

    try:
        filenames = sorted(os.listdir(profile_dir))
    except Exception:
        return None

    for filename in filenames:
        lower = filename.lower()
        if not lower.startswith("persist.") or not lower.endswith(".json"):
            continue
        if lower.endswith(".decoded.json"):
            continue

        candidate_path = os.path.join(profile_dir, filename)
        values = read_scalar_dson_fields(
            candidate_path,
            name_predicate=lambda name: "week" in str(name).lower(),
        )
        for name, value in values.items():
            lowered_name = str(name).lower()
            if lowered_name.startswith("number_of_weeks_"):
                continue
            try:
                week_number = int(value)
            except Exception:
                continue
            if week_number >= 0:
                return week_number

    return None


def read_save_profile_metadata(path, cache, read_scalar_dson_fields):
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None

    cached = cache.get(path)
    if cached and cached.get("mtime") == mtime:
        return dict(cached["metadata"])

    metadata = read_scalar_dson_fields(path, wanted_names={"date_time"})
    metadata["week"] = read_profile_week(path, read_scalar_dson_fields)

    cache[path] = {
        "mtime": mtime,
        "metadata": dict(metadata),
    }
    return metadata


def profile_label(path, cache, read_scalar_dson_fields):
    number = profile_number_from_path(path)
    metadata = read_save_profile_metadata(path, cache, read_scalar_dson_fields)

    save_date = str(metadata.get("date_time") or "").strip()
    if not save_date:
        try:
            save_date = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            save_date = "unknown date"

    week_number = metadata.get("week")

    if number is None:
        base = f"Unknown Profile - {save_date}"
    else:
        base = f"Profile {number} (slot {number + 1}) - {save_date}"

    if week_number is not None:
        base = f"{base} - Week {week_number}"

    parent = os.path.basename(os.path.dirname(path))
    return f"{base} [{parent}]"


def detect_profile_slots(paths, cache, read_scalar_dson_fields):
    slots = []
    seen = set()
    for path in paths:
        norm = os.path.normcase(os.path.abspath(path))
        if norm in seen:
            continue
        slots.append({
            "path": path,
            "number": profile_number_from_path(path),
            "label": profile_label(path, cache, read_scalar_dson_fields),
        })
        seen.add(norm)
    return sorted(slots, key=profile_sort_key)


def detect_latest_save_file(save_files):
    if not save_files:
        return ""
    return max(save_files, key=lambda path: os.path.getmtime(path))


def autodetect_summary(game_root, local_mods, workshop_mods, best_mods, latest_save, profile_count):
    return {
        "game_root": game_root,
        "local_mods": local_mods,
        "workshop_mods": workshop_mods,
        "best_mods": best_mods,
        "latest_save": latest_save,
        "profile_count": profile_count,
    }


def normalize_display_path(path):
    path = str(path or "").strip()
    if not path:
        return ""
    return os.path.normpath(path)
