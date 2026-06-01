import os
import html
import json
import locale
import math
import re
import shutil
import struct
import sys
import subprocess
import time
import traceback
import tkinter as tk
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from tkinter import colorchooser, filedialog, messagebox, simpledialog

from categories import (
    CATEGORY_COLORS,
    CATEGORY_COLOR_CYCLE,
    DEFAULT_CATEGORIES,
    add_custom_category as append_custom_category,
    apply_category_editor_changes,
    auto_categorize_mods as apply_auto_categorization,
    auto_category_scores as score_mod_categories,
    category_color as resolve_category_color,
    default_color_for_new_category as pick_default_category_color,
    get_categories as build_categories,
    get_category_priority as build_category_priority,
    move_category as reposition_category,
    move_category_to_index as reposition_category_to_index,
    project_tag_values as read_project_tag_values,
    remove_custom_category as delete_custom_category,
    rename_custom_category as rename_custom_category_data,
    suggested_category_for_mod as suggest_mod_category,
)
from localization import (
    APP_VERSION,
    CATEGORY_TRANSLATION_KEYS,
    LANGUAGE_CHOICES,
    LANGUAGE_CODE_TO_LABEL,
    LANGUAGE_LABEL_TO_CODE,
    TRANSLATIONS,
    VIEW_MODE_TRANSLATION_KEYS,
    detect_default_language,
    read_saved_language,
    subtitle_with_version,
    translate_text,
)
from legacy_loadout import load_loadout as legacy_load_loadout, save_loadout as legacy_save_loadout
from paths import (
    autodetect_summary as build_autodetect_summary,
    candidate_game_folders as find_candidate_game_folders,
    candidate_local_mod_folders as find_candidate_local_mod_folders,
    candidate_mod_folders as find_candidate_mod_folders,
    candidate_workshop_mod_folders as find_candidate_workshop_mod_folders,
    companion_mod_folders as find_companion_mod_folders,
    detect_best_mod_folder as choose_best_mod_folder,
    detect_latest_save_file as choose_latest_save_file,
    detect_profile_slots as find_profile_slots,
    detect_save_files as find_save_files,
    detected_save_files_from_disk as find_save_files_from_disk,
    get_app_root,
    gog_game_roots as find_gog_game_roots,
    is_workshop_content_path,
    normalize_display_path as normalize_saved_path,
    profile_label as build_profile_label,
    profile_number_from_path as detect_profile_number_from_path,
    profile_sort_key as build_profile_sort_key,
    read_profile_week as load_profile_week,
    read_save_profile_metadata as load_save_profile_metadata,
    steam_install_roots as find_steam_install_roots,
    steam_library_roots as find_steam_library_roots,
    windows_documents_roots as find_windows_documents_roots,
    first_valid_manual_path,
)
from state import build_default_state, load_state_file, save_state_file

try:
    import ctypes
except ImportError:
    ctypes = None

try:
    import winreg
except ImportError:
    winreg = None

# =========================================================
# Darkest Dungeon Mod Manager
# =========================================================

# App data lives in one folder beside this script so saves, backups,
# caches, and exported loadouts are easy to find together.
APP_ROOT = get_app_root(sys, __file__)
APP_DIR = os.path.join(APP_ROOT, "DD Manager Data")
STATE_FILE = os.path.join(APP_DIR, "mod_state.json")
ICON_CACHE_DIR = os.path.join(APP_DIR, "icon_cache")
STARTUP_PROFILE_LOG = os.path.join(APP_DIR, "startup_profile.log")
STARTUP_PROFILING_ENABLED = False
STEAM_APP_ID = "262060"
DD_GAME_NAME = "DarkestDungeon"
DD_GAME_DIR_NAMES = ("DarkestDungeon", "Darkest Dungeon")
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

# Profile-based patching is now the default flow. Keep older save-patch and
# loadout features quarantined in legacy modules until they are needed again.
SHOW_PRIMARY_AUTO_PATCH_BUTTON = False
SHOW_START_NEW_CAMPAIGN_TOOL = False

PAYLOAD_START = 0x580

THEME = {
    "bg": "#14100F",
    "panel": "#211A18",
    "panel_deep": "#100D0C",
    "field": "#181210",
    "field_alt": "#1D1714",
    "border": "#3A2A24",
    "text": "#D8C7A3",
    "text_bright": "#E7D8B0",
    "muted": "#9D8E77",
    "gold": "#B99A45",
    "crimson": "#8F1D1D",
    "crimson_hover": "#A72A24",
    "amber": "#B56A24",
    "amber_hover": "#C47A30",
    "disabled": "#746A60",
    "select": "#5A2623",
    "select_text": "#F3E7C6",
    "ink": "#050505",
}

def platform_font(preferred, linux_fallback):
    if IS_WINDOWS:
        return preferred
    if IS_LINUX:
        return linux_fallback
    return preferred


FONT_TITLE = (platform_font("Georgia", "DejaVu Serif"), 20, "bold")
FONT_SUBTITLE = (platform_font("Georgia", "DejaVu Serif"), 10, "italic")
FONT_HEADING = (platform_font("Georgia", "DejaVu Serif"), 12, "bold")
FONT_BODY = (platform_font("Segoe UI", "DejaVu Sans"), 10)
FONT_BUTTON = (platform_font("Segoe UI", "DejaVu Sans"), 9, "bold")
FONT_MONO = (platform_font("Consolas", "DejaVu Sans Mono"), 10)

VIEW_MODES = {
    "No Icons": {
        "list_font": (platform_font("Segoe UI", "DejaVu Sans"), 14),
        "icon_size": 0,
        "icon_strip_width": 0,
    },
    "Compact": {
        "list_font": (platform_font("Segoe UI", "DejaVu Sans"), 12),
        "icon_size": 28,
        "icon_strip_width": 32,
    },
    "Comfortable": {
        "list_font": (platform_font("Segoe UI", "DejaVu Sans"), 16),
        "icon_size": 40,
        "icon_strip_width": 44,
    },
    "Visual": {
        "list_font": (platform_font("Segoe UI", "DejaVu Sans"), 24),
        "icon_size": 52,
        "icon_strip_width": 56,
    },
}

NEW_MOD_HIGHLIGHT_MS = 15000

CAMPAIGN_DLC_CHOICES = [
    ("arena_mp", "Butcher's Circus"),
    ("musketeer", "Musketeer"),
    ("crimson_court", "Crimson Court"),
    ("districts", "Districts"),
    ("flagellant", "Flagellant"),
    ("shieldbreaker", "Shieldbreaker"),
    ("color_of_madness", "Color of Madness"),
]

CAMPAIGN_READY_MAP_STATIC_OFFSETS = [
    879, 1443, 1455, 1467, 1479, 1491, 1503, 1515, 1527, 1539,
    1551, 1563, 1575, 1587, 1671, 1683, 1695, 1707, 1719, 1731,
]
CAMPAIGN_READY_ROSTER_RAW_OFFSETS = [319, 535, 571, 883, 919, 1219, 1255, 1688]


# Centers transient windows like the startup splash so they appear
# immediately in a predictable place instead of popping in later.
def center_window(window, width, height):
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def startup_splash_dimensions(language):
    sizes = {
        "en": (520, 220),
        "zh_CN": (520, 220),
        "pt_PT": (620, 220),
        "es_ES": (720, 220),
    }
    return sizes.get(language, sizes["en"])


# Simple startup card so the app doesn't sit on a blank window while
# the full UI finishes coming up.
def create_startup_splash(root, language="en"):
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg=THEME["bg"])
    splash.attributes("-topmost", True)
    splash_width, splash_height = startup_splash_dimensions(language)
    center_window(splash, splash_width, splash_height)

    outer = tk.Frame(
        splash,
        bg=THEME["border"],
        bd=0,
        highlightthickness=0,
    )
    outer.pack(fill="both", expand=True, padx=2, pady=2)

    panel = tk.Frame(splash, bg=THEME["panel"])
    panel.place(
        relx=0.5,
        rely=0.5,
        anchor="center",
        width=max(0, splash_width - 8),
        height=max(0, splash_height - 8),
    )

    top_rule = tk.Frame(panel, bg=THEME["crimson"], height=3)
    top_rule.pack(fill="x", padx=18, pady=(18, 0))

    tk.Label(
        panel,
        text=translate_text(language, "app_title"),
        bg=THEME["panel"],
        fg=THEME["text_bright"],
        font=(platform_font("Georgia", "DejaVu Serif"), 22, "bold"),
    ).pack(pady=(26, 6))

    status_label = tk.Label(
        panel,
        text=translate_text(language, "startup_loading"),
        bg=THEME["panel"],
        fg=THEME["muted"],
        font=FONT_BODY,
    )
    status_label.pack()
    splash._status_label = status_label

    tk.Label(
        panel,
        text=translate_text(language, "startup_stirring"),
        bg=THEME["panel"],
        fg=THEME["gold"],
        font=(platform_font("Georgia", "DejaVu Serif"), 11, "italic"),
    ).pack(pady=(18, 0))

    bottom_rule = tk.Frame(panel, bg=THEME["gold"], height=2)
    bottom_rule.pack(fill="x", side="bottom", padx=18, pady=(0, 18))

    splash.update()
    return splash


def update_startup_splash(splash, message):
    if splash is None:
        return
    label = getattr(splash, "_status_label", None)
    if label is None:
        return
    try:
        label.config(text=message)
        splash.update_idletasks()
        splash.update()
    except Exception:
        pass


# Ensures the project-side state/cache folders exist before the app
# starts reading or writing any saved data.
def ensure_app_storage():
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(ICON_CACHE_DIR, exist_ok=True)


def write_crash_log(summary, error):
    try:
        ensure_app_storage()
        crash_log_path = os.path.join(APP_DIR, "startup_crash.log")
        with open(crash_log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {summary}\n")
            f.write(f"{error}\n")
            f.write("-" * 80 + "\n")
        return crash_log_path
    except Exception:
        return ""


def format_duration_ms(seconds):
    return f"{seconds * 1000:.1f} ms"


def dson_read_u32_le(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def dson_pack_u32_le(value):
    return struct.pack("<I", value)


def dson_i32_from_u32_bits(value):
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"32-bit metadata value is out of range: {value}")
    if value >= 0x80000000:
        return value - 0x100000000
    return value


def dson_pack_i32_le(value):
    return struct.pack("<i", value)


def dson_string_hash(value):
    hash_value = 0
    for byte in value.encode("utf-8"):
        hash_value = (hash_value * 53 + byte) & 0xFFFFFFFF
    if hash_value >= 0x80000000:
        hash_value -= 0x100000000
    return hash_value


def dson_read_cstring(data, offset):
    end = offset
    while end < len(data) and data[end] != 0:
        end += 1
    if end >= len(data):
        return None, offset
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def dson_looks_like_string(raw_bytes):
    if not raw_bytes:
        return False
    body = raw_bytes[:-1] if raw_bytes[-1] == 0 else raw_bytes
    if not body:
        return False
    return all(32 <= b <= 126 for b in body)


def dson_read_len_string_with_layout(data, offset, max_len=300):
    for pad in range(0, 5):
        len_off = offset + pad
        if len_off + 4 > len(data):
            continue

        strlen = dson_read_u32_le(data, len_off)
        if strlen <= 0 or strlen > max_len:
            continue

        str_start = len_off + 4
        str_end = str_start + strlen
        if str_end > len(data):
            continue

        raw_str = data[str_start:str_end]
        if not dson_looks_like_string(raw_str):
            continue

        if raw_str and raw_str[-1] == 0:
            value = raw_str[:-1].decode("utf-8", errors="replace")
        else:
            value = raw_str.decode("utf-8", errors="replace")

        return value, str_end, pad, strlen

    return None, offset, None, None


def dson_is_entry_index_string(value):
    return value is not None and value.isdigit() and len(value) <= 3


def dson_find_top_level_applied_block(raw):
    try:
        header = dson_parse_header(raw)
        i = header["data_offset"]
    except Exception:
        i = PAYLOAD_START

    applied_start = None
    persistent_start = None

    while i < len(raw):
        value, new_i = dson_read_cstring(raw, i)
        if value is None:
            i += 1
            continue

        if value == "applied_ugcs_1_0" and applied_start is None:
            applied_start = i
        elif value == "persistent_ugcs" and applied_start is not None:
            persistent_start = i
            break

        i = new_i

    if applied_start is None:
        raise ValueError("Could not find top-level applied_ugcs_1_0")
    if persistent_start is None:
        raise ValueError("Could not find persistent_ugcs after applied_ugcs_1_0")

    return applied_start, persistent_start


def dson_parse_applied_ugcs_with_layout(raw):
    applied_start, applied_end = dson_find_top_level_applied_block(raw)

    i = applied_start
    block_name, i = dson_read_cstring(raw, i)
    if block_name != "applied_ugcs_1_0":
        raise ValueError("Applied UGC block starts at an unexpected value.")

    entries = []

    while i < applied_end:
        value, new_i = dson_read_cstring(raw, i)

        if value == "persistent_ugcs":
            break

        if value is None:
            i += 1
            continue

        if not dson_is_entry_index_string(value):
            i = new_i
            continue

        entry = {"index": value, "fields": []}
        i = new_i

        while i < applied_end:
            field_name, field_next = dson_read_cstring(raw, i)

            if field_name is None:
                i += 1
                continue

            if field_name == "persistent_ugcs":
                entries.append(entry)
                return applied_start, applied_end, entries

            if dson_is_entry_index_string(field_name):
                break

            if field_name in ("name", "source"):
                field_value, value_next, pad, stored_strlen = dson_read_len_string_with_layout(raw, field_next)
                if field_value is not None:
                    entry["fields"].append({
                        "field_name": field_name,
                        "value": field_value,
                        "pad": pad,
                        "stored_strlen": stored_strlen,
                    })
                    i = value_next
                    continue

            i = field_next

        entries.append(entry)

    return applied_start, applied_end, entries




def dson_build_applied_ugcs_fragment(entries):
    out = bytearray()
    out.extend(b"applied_ugcs_1_0\x00")

    for entry in entries:
        out.extend(entry["index"].encode("utf-8"))
        out.append(0)

        for field in entry["fields"]:
            out.extend(field["field_name"].encode("utf-8"))
            out.append(0)
            out.extend(b"\x00" * field["pad"])

            value_bytes = field["value"].encode("utf-8") + b"\x00"
            out.extend(dson_pack_u32_le(len(value_bytes)))
            out.extend(value_bytes)

    return bytes(out)


def dson_get_field(entry, field_name):
    for field in entry["fields"]:
        if field["field_name"] == field_name:
            return field
    return None


def dson_replacement_values(mod_manager, mod_folder):
    return mod_manager.save_identity_for_mod(mod_folder)


def app_timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def unique_path(path):
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base}-{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def persist_backup_path(file_path):
    folder = os.path.dirname(file_path)
    name = os.path.basename(file_path)
    stem, ext = os.path.splitext(name)
    if not ext:
        ext = ".json"
    return unique_path(os.path.join(folder, f"{stem}.backup.{app_timestamp()}{ext}"))


def normalize_mod_identity(value):
    if value is None:
        return ""

    text = html.unescape(str(value)).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[_\\/\-:;,.()[\]{}'\"!+]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mod_metadata_is_complete(metadata):
    if not isinstance(metadata, dict):
        return False
    required_keys = (
        "title",
        "published_file_id",
        "save_name",
        "save_source",
        "version_label",
        "updated_label",
        "black_reliquary",
        "metadata_path",
        "project_mtime",
        "localization_signature",
        "workshop_timeupdated",
    )
    return all(key in metadata for key in required_keys)


def xml_text_from_child(root, tag_name):
    for child in list(root):
        if child.tag.split("}", 1)[-1].lower() == tag_name.lower():
            if child.text:
                return child.text.strip()
            return ""
    return ""


def strip_invalid_xml_chars(text):
    return "".join(
        char for char in text
        if char in "\t\n\r" or ord(char) >= 0x20
    )


def text_has_latin(text):
    return bool(re.search(r"[A-Za-z]", text or ""))


def looks_like_numeric_id(text):
    return bool(text) and str(text).isdigit()


def is_bad_display_title(text):
    if not text:
        return True

    value = html.unescape(str(text)).strip()
    lowered = value.lower()

    if not value:
        return True
    if "{colour_" in lowered or "{color_" in lowered or "{colour" in lowered or "{color" in lowered:
        return True
    if "%" in value:
        return True
    if "<" in value or ">" in value:
        return True
    if re.search(r"\b\d+\s+combats?\b", lowered):
        return True
    if lowered in {"tooltip", "tooltips", "tray_icon"}:
        return True

    return False


def normalize_hex_color(value):
    if not value:
        return ""
    text = str(value).strip()
    if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", text):
        return ""
    if not text.startswith("#"):
        text = f"#{text}"
    return text.upper()


def parse_xml_file_forgiving(path):
    try:
        return ET.parse(path).getroot()
    except Exception:
        pass

    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return None

    for encoding in ("utf-8-sig", "utf-8", "utf-16", "gb18030", "big5"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue

        text = strip_invalid_xml_chars(text).strip()
        xml_start = text.find("<?xml")
        if xml_start > 0:
            text = text[xml_start:]
        elif xml_start < 0:
            root_start = text.find("<")
            if root_start > 0:
                text = text[root_start:]

        try:
            return ET.fromstring(text)
        except Exception:
            continue

    return None


def dson_field_info(name, object_meta1_index=None):
    name_length = len(name.encode("utf-8")) + 1
    if name_length > 0x1FF:
        raise ValueError(f"DSON field name is too long: {name!r}")

    info = name_length << 2
    if object_meta1_index is not None:
        if not 0 <= object_meta1_index <= 0xFFFFF:
            raise ValueError(f"DSON object index is out of range: {object_meta1_index}")
        info |= 1
        info |= object_meta1_index << 11
    return dson_i32_from_u32_bits(info)


def dson_parse_header(raw):
    if len(raw) < 64:
        raise ValueError("Save file is too small to contain a DSON header.")

    return {
        "magic": raw[0:4],
        "revision": raw[4:8],
        "header_length": struct.unpack_from("<i", raw, 8)[0],
        "meta1_size": struct.unpack_from("<i", raw, 16)[0],
        "meta1_count": struct.unpack_from("<i", raw, 20)[0],
        "meta1_offset": struct.unpack_from("<i", raw, 24)[0],
        "meta2_count": struct.unpack_from("<i", raw, 44)[0],
        "meta2_offset": struct.unpack_from("<i", raw, 48)[0],
        "data_length": struct.unpack_from("<i", raw, 56)[0],
        "data_offset": struct.unpack_from("<i", raw, 60)[0],
    }


def dson_parse_meta1(raw, header):
    entries = []
    offset = header["meta1_offset"]
    for index in range(header["meta1_count"]):
        entry_offset = offset + index * 16
        entries.append({
            "parent": struct.unpack_from("<i", raw, entry_offset)[0],
            "meta2_index": struct.unpack_from("<i", raw, entry_offset + 4)[0],
            "direct_children": struct.unpack_from("<i", raw, entry_offset + 8)[0],
            "all_children": struct.unpack_from("<i", raw, entry_offset + 12)[0],
        })
    return entries


def dson_parse_meta2(raw, header):
    entries = []
    offset = header["meta2_offset"]
    for index in range(header["meta2_count"]):
        entry_offset = offset + index * 12
        entries.append({
            "hash": struct.unpack_from("<i", raw, entry_offset)[0],
            "offset": struct.unpack_from("<i", raw, entry_offset + 4)[0],
            "info": struct.unpack_from("<i", raw, entry_offset + 8)[0],
        })
    return entries


def dson_meta2_name(raw, header, meta2_entry):
    offset = header["data_offset"] + meta2_entry["offset"]
    value, _ = dson_read_cstring(raw, offset)
    return value


def dson_object_index_from_info(info):
    info &= 0x7FFFFFFF
    if not (info & 1):
        return None
    return (info >> 11) & 0xFFFFF


def dson_set_object_index_in_info(info, object_index):
    if not 0 <= object_index <= 0xFFFFF:
        raise ValueError(f"DSON object index is out of range: {object_index}")

    info_bits = info & 0xFFFFFFFF
    high_bit = info_bits & 0x80000000
    name_len_bits = info_bits & 0x7FC
    return dson_i32_from_u32_bits(high_bit | 1 | name_len_bits | (object_index << 11))


def dson_find_meta2_by_name(raw, header, meta2_entries, name):
    for index, entry in enumerate(meta2_entries):
        if dson_meta2_name(raw, header, entry) == name:
            return index
    raise ValueError(f"Could not find {name!r} in save metadata.")


def dson_field_payload_layout(data, entry, next_offset):
    info = entry["info"] & 0x7FFFFFFF
    name_length = (info >> 2) & 0x1FF
    value_start = entry["offset"] + name_length
    value_end = next_offset

    if dson_object_index_from_info(entry["info"]) is not None:
        return b"", value_start, value_end

    if value_end <= value_start:
        return b"", value_start, value_end

    raw_value = data[value_start:value_end]
    if len(raw_value) == 1:
        return bytes(raw_value), value_start, value_end

    aligned_start = value_start + ((-value_start) % 4)
    if aligned_start > value_end:
        return b"", aligned_start, value_end
    return bytes(data[aligned_start:value_end]), aligned_start, value_end


def dson_decode_scalar_field(data, entry, next_offset):
    payload, _, _ = dson_field_payload_layout(data, entry, next_offset)
    if not payload:
        return None

    if len(payload) == 1:
        return bool(payload[0])

    value, _, _, _ = dson_read_len_string_with_layout(payload, 0)
    if value is not None:
        return value

    if len(payload) >= 4:
        return struct.unpack_from("<i", payload, 0)[0]

    return bytes(payload)


def dson_align_pad(relative_offset, field_name):
    after_name = relative_offset + len(field_name.encode("utf-8")) + 1
    return (-after_name) % 4


def dson_build_string_field(field_name, value, relative_offset):
    out = bytearray()
    out.extend(field_name.encode("utf-8"))
    out.append(0)
    out.extend(b"\x00" * dson_align_pad(relative_offset, field_name))

    value_bytes = value.encode("utf-8") + b"\x00"
    out.extend(dson_pack_i32_le(len(value_bytes)))
    out.extend(value_bytes)

    meta2_entry = {
        "hash": dson_string_hash(field_name),
        "offset": relative_offset,
        "info": dson_field_info(field_name),
    }
    return bytes(out), meta2_entry


def dson_parse_named_name_source_object(raw, object_name):
    header = dson_parse_header(raw)
    meta1_entries = dson_parse_meta1(raw, header)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]

    object_meta2_index = dson_find_meta2_by_name(raw, header, meta2_entries, object_name)
    object_meta2 = meta2_entries[object_meta2_index]
    object_meta1_index = dson_object_index_from_info(object_meta2["info"])
    if object_meta1_index is None:
        raise ValueError(f"{object_name!r} is not marked as an object in metadata.")

    child_meta1_indices = [
        index for index, entry in enumerate(meta1_entries)
        if entry["parent"] == object_meta1_index
    ]
    child_meta1_indices.sort(key=lambda index: meta1_entries[index]["meta2_index"])

    entries = []
    for child_meta1_index in child_meta1_indices:
        child_meta1 = meta1_entries[child_meta1_index]
        child_meta2_index = child_meta1["meta2_index"]
        child_name = dson_meta2_name(raw, header, meta2_entries[child_meta2_index]) or ""
        child_end = child_meta2_index + child_meta1["all_children"] + 1

        fields = []
        for field_index in range(child_meta2_index + 1, child_end):
            field_entry = meta2_entries[field_index]
            field_name = dson_meta2_name(raw, header, field_entry)
            next_offset = (
                meta2_entries[field_index + 1]["offset"]
                if field_index + 1 < len(meta2_entries)
                else header["data_length"]
            )
            if field_name not in ("name", "source"):
                continue
            value = dson_decode_scalar_field(data, field_entry, next_offset)
            if isinstance(value, str):
                fields.append({"field_name": field_name, "value": value})

        entries.append({"index": child_name, "fields": fields})

    return entries


def dson_build_named_name_source_object(object_name, entries, object_offset, first_meta1_index):
    data = bytearray()
    meta1_entries = []
    meta2_entries = []

    data.extend(object_name.encode("utf-8"))
    data.append(0)

    for index, entry in enumerate(entries):
        object_index_name = str(index)
        object_meta1_index = first_meta1_index + index
        object_name_offset = object_offset + len(data)

        data.extend(object_index_name.encode("utf-8"))
        data.append(0)
        meta2_entries.append({
            "hash": dson_string_hash(object_index_name),
            "offset": object_name_offset,
            "info": dson_field_info(object_index_name, object_meta1_index),
        })

        entry_name = str(entry.get("name", ""))
        entry_source = str(entry.get("source", ""))

        name_offset = object_offset + len(data)
        name_data, name_meta2 = dson_build_string_field("name", entry_name, name_offset)
        data.extend(name_data)
        meta2_entries.append(name_meta2)

        source_offset = object_offset + len(data)
        source_data, source_meta2 = dson_build_string_field("source", entry_source, source_offset)
        data.extend(source_data)
        meta2_entries.append(source_meta2)

        meta1_entries.append({
            "parent": None,
            "meta2_index": None,
            "direct_children": 2,
            "all_children": 2,
        })

    return bytes(data), meta1_entries, meta2_entries


def dson_rebuild_existing_field_block(data, entry, next_offset, new_offset):
    info = entry["info"] & 0x7FFFFFFF
    name_length = (info >> 2) & 0x1FF
    old_offset = entry["offset"]
    field_name_bytes = data[old_offset:old_offset + name_length]

    if dson_object_index_from_info(entry["info"]) is not None:
        return bytes(field_name_bytes)

    old_data_start = old_offset + name_length
    old_data_size = next_offset - old_data_start

    # Single-byte bool/char fields are written immediately after the
    # name. Multi-byte scalar/string/vector fields are 4-byte aligned.
    if old_data_size == 1:
        return bytes(field_name_bytes) + bytes(data[old_data_start:next_offset])

    old_align = (-old_data_start) % 4
    payload_start = old_data_start + old_align
    payload = data[payload_start:next_offset]

    new_data_start = new_offset + name_length
    new_align = (-new_data_start) % 4

    return bytes(field_name_bytes) + (b"\x00" * new_align) + bytes(payload)


def dson_patch_scalar_string_field(raw, field_name, new_value):
    dson_validate_editor_compatible(raw)

    header = dson_parse_header(raw)
    meta1_entries = dson_parse_meta1(raw, header)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]

    field_index = dson_find_meta2_by_name(raw, header, meta2_entries, field_name)
    field_entry = meta2_entries[field_index]
    if dson_object_index_from_info(field_entry["info"]) is not None:
        raise ValueError(f"{field_name!r} is an object field, not a scalar string field.")

    next_offset = (
        meta2_entries[field_index + 1]["offset"]
        if field_index + 1 < len(meta2_entries)
        else header["data_length"]
    )
    old_block_size = next_offset - field_entry["offset"]
    new_block, replacement_entry = dson_build_string_field(field_name, str(new_value), field_entry["offset"])
    data_delta = len(new_block) - old_block_size

    original_next_offsets = {}
    sorted_original_offsets = sorted(entry["offset"] for entry in meta2_entries)
    for index, offset in enumerate(sorted_original_offsets):
        if index + 1 < len(sorted_original_offsets):
            original_next_offsets[offset] = sorted_original_offsets[index + 1]
        else:
            original_next_offsets[offset] = len(data)

    preserved_meta2_before = [dict(entry) for entry in meta2_entries[:field_index]]
    preserved_meta2_after = [dict(entry) for entry in meta2_entries[field_index + 1:]]

    new_data_parts = [data[:field_entry["offset"]], new_block]
    next_rebuilt_offset = field_entry["offset"] + len(new_block)

    for entry in preserved_meta2_after:
        rebuilt_block = dson_rebuild_existing_field_block(
            data,
            entry,
            original_next_offsets[entry["offset"]],
            next_rebuilt_offset,
        )
        entry["offset"] = next_rebuilt_offset
        new_data_parts.append(rebuilt_block)
        next_rebuilt_offset += len(rebuilt_block)

    new_meta2_entries = preserved_meta2_before + [replacement_entry] + preserved_meta2_after
    new_data = b"".join(new_data_parts)

    new_header = bytearray(raw[:64])
    struct.pack_into("<i", new_header, 56, len(new_data))

    meta1_block = bytearray()
    for entry in meta1_entries:
        meta1_block.extend(dson_pack_i32_le(entry["parent"]))
        meta1_block.extend(dson_pack_i32_le(entry["meta2_index"]))
        meta1_block.extend(dson_pack_i32_le(entry["direct_children"]))
        meta1_block.extend(dson_pack_i32_le(entry["all_children"]))

    meta2_block = bytearray()
    for entry in new_meta2_entries:
        meta2_block.extend(dson_pack_i32_le(entry["hash"]))
        meta2_block.extend(dson_pack_i32_le(entry["offset"]))
        meta2_block.extend(dson_pack_i32_le(entry["info"]))

    patched = bytes(new_header) + bytes(meta1_block) + bytes(meta2_block) + bytes(new_data)
    check_header = dson_parse_header(patched)
    if check_header["data_offset"] + check_header["data_length"] != len(patched):
        raise ValueError("Patched save has inconsistent data offset/length metadata.")

    dson_validate_editor_compatible(patched)
    return patched


def dson_build_applied_ugcs_object(enabled_mods, mod_manager, applied_offset, first_meta1_index):
    data = bytearray()
    meta1_entries = []
    meta2_entries = []

    data.extend(b"applied_ugcs_1_0\x00")

    for index, mod in enumerate(enabled_mods):
        object_name = str(index)
        object_meta1_index = first_meta1_index + index
        object_offset = applied_offset + len(data)

        data.extend(object_name.encode("utf-8"))
        data.append(0)
        meta2_entries.append({
            "hash": dson_string_hash(object_name),
            "offset": object_offset,
            "info": dson_field_info(object_name, object_meta1_index),
        })

        new_name, new_source = dson_replacement_values(mod_manager, mod)

        name_offset = applied_offset + len(data)
        name_data, name_meta2 = dson_build_string_field("name", new_name, name_offset)
        data.extend(name_data)
        meta2_entries.append(name_meta2)

        source_offset = applied_offset + len(data)
        source_data, source_meta2 = dson_build_string_field("source", new_source, source_offset)
        data.extend(source_data)
        meta2_entries.append(source_meta2)

        meta1_entries.append({
            "parent": None,
            "meta2_index": None,
            "direct_children": 2,
            "all_children": 2,
        })

    return bytes(data), meta1_entries, meta2_entries


def dson_insert_missing_applied_ugcs(raw, enabled_mods, mod_manager):
    dson_validate_editor_compatible(raw)

    header = dson_parse_header(raw)
    if header["header_length"] != 64 or header["meta1_offset"] != 64:
        raise ValueError("Unsupported DSON header layout.")

    meta1_entries = dson_parse_meta1(raw, header)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]

    root_meta1_index = dson_object_index_from_info(meta2_entries[0]["info"])
    if root_meta1_index is None:
        raise ValueError("Save root object is missing DSON metadata.")

    persistent_meta2_index = dson_find_meta2_by_name(raw, header, meta2_entries, "persistent_ugcs")
    persistent_meta2 = meta2_entries[persistent_meta2_index]
    insertion_meta1_index = dson_object_index_from_info(persistent_meta2["info"])
    if insertion_meta1_index is None:
        raise ValueError("persistent_ugcs is not marked as an object in metadata.")

    insertion_offset = persistent_meta2["offset"]
    first_child_meta1_index = insertion_meta1_index + 1
    new_applied_data, new_child_meta1, new_child_meta2 = dson_build_applied_ugcs_object(
        enabled_mods,
        mod_manager,
        insertion_offset,
        first_child_meta1_index,
    )

    applied_meta1 = {
        "parent": root_meta1_index,
        "meta2_index": persistent_meta2_index,
        "direct_children": len(enabled_mods),
        "all_children": len(enabled_mods) * 3,
    }
    applied_meta2 = {
        "hash": dson_string_hash("applied_ugcs_1_0"),
        "offset": insertion_offset,
        "info": dson_field_info("applied_ugcs_1_0", insertion_meta1_index),
    }

    for offset, entry in enumerate(new_child_meta1):
        entry["parent"] = insertion_meta1_index
        entry["meta2_index"] = persistent_meta2_index + 1 + offset * 3

    meta1_delta = 1 + len(new_child_meta1)
    meta2_delta = 1 + len(new_child_meta2)

    adjusted_meta1_entries = []
    for entry in meta1_entries:
        adjusted = dict(entry)
        if adjusted["parent"] >= insertion_meta1_index:
            adjusted["parent"] += meta1_delta
        if adjusted["meta2_index"] >= persistent_meta2_index:
            adjusted["meta2_index"] += meta2_delta
        adjusted_meta1_entries.append(adjusted)

    new_meta1_entries = (
        adjusted_meta1_entries[:insertion_meta1_index]
        + [applied_meta1]
        + new_child_meta1
        + adjusted_meta1_entries[insertion_meta1_index:]
    )

    new_meta1_entries[root_meta1_index]["direct_children"] += 1
    new_meta1_entries[root_meta1_index]["all_children"] += meta2_delta

    original_next_offsets = {}
    sorted_original_offsets = sorted(entry["offset"] for entry in meta2_entries)
    for index, offset in enumerate(sorted_original_offsets):
        if index + 1 < len(sorted_original_offsets):
            original_next_offsets[offset] = sorted_original_offsets[index + 1]
        else:
            original_next_offsets[offset] = len(data)

    preserved_meta2_before = meta2_entries[:persistent_meta2_index]
    preserved_meta2_after = meta2_entries[persistent_meta2_index:]

    new_data_parts = [data[:insertion_offset], new_applied_data]
    next_rebuilt_offset = insertion_offset + len(new_applied_data)

    adjusted_meta2_after = []
    for entry in preserved_meta2_after:
        adjusted_entry = dict(entry)
        object_index = dson_object_index_from_info(adjusted_entry["info"])
        if object_index is not None and object_index >= insertion_meta1_index:
            adjusted_entry["info"] = dson_set_object_index_in_info(
                adjusted_entry["info"],
                object_index + meta1_delta,
            )

        rebuilt_block = dson_rebuild_existing_field_block(
            data,
            entry,
            original_next_offsets[entry["offset"]],
            next_rebuilt_offset,
        )
        adjusted_entry["offset"] = next_rebuilt_offset
        new_data_parts.append(rebuilt_block)
        next_rebuilt_offset += len(rebuilt_block)
        adjusted_meta2_after.append(adjusted_entry)

    new_meta2_entries = preserved_meta2_before + [applied_meta2] + new_child_meta2 + adjusted_meta2_after
    new_data = b"".join(new_data_parts)

    new_header = bytearray(raw[:64])
    new_meta1_count = len(new_meta1_entries)
    new_meta2_count = len(new_meta2_entries)
    new_meta1_size = new_meta1_count * 16
    new_meta2_offset = 64 + new_meta1_size
    new_data_offset = new_meta2_offset + new_meta2_count * 12

    struct.pack_into("<i", new_header, 16, new_meta1_size)
    struct.pack_into("<i", new_header, 20, new_meta1_count)
    struct.pack_into("<i", new_header, 44, new_meta2_count)
    struct.pack_into("<i", new_header, 48, new_meta2_offset)
    struct.pack_into("<i", new_header, 56, len(new_data))
    struct.pack_into("<i", new_header, 60, new_data_offset)

    meta1_block = bytearray()
    for entry in new_meta1_entries:
        meta1_block.extend(dson_pack_i32_le(entry["parent"]))
        meta1_block.extend(dson_pack_i32_le(entry["meta2_index"]))
        meta1_block.extend(dson_pack_i32_le(entry["direct_children"]))
        meta1_block.extend(dson_pack_i32_le(entry["all_children"]))

    meta2_block = bytearray()
    for entry in new_meta2_entries:
        meta2_block.extend(dson_pack_i32_le(entry["hash"]))
        meta2_block.extend(dson_pack_i32_le(entry["offset"]))
        meta2_block.extend(dson_pack_i32_le(entry["info"]))

    patched = bytes(new_header) + bytes(meta1_block) + bytes(meta2_block) + bytes(new_data)

    check_header = dson_parse_header(patched)
    if check_header["data_offset"] + check_header["data_length"] != len(patched):
        raise ValueError("Patched save has inconsistent data offset/length metadata.")

    _, _, check_entries = dson_parse_applied_ugcs_with_layout(patched)
    if len(check_entries) != len(enabled_mods):
        raise ValueError("Patched save did not roundtrip with the requested mod count.")

    dson_validate_editor_compatible(patched)

    return patched, len(check_entries)


def dson_validate_editor_compatible(raw):
    header = dson_parse_header(raw)
    meta1_entries = dson_parse_meta1(raw, header)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]

    if header["data_offset"] + header["data_length"] != len(raw):
        raise ValueError("Header data offset/length does not match the file size.")

    if header["meta1_size"] != header["meta1_count"] * 16:
        raise ValueError("Meta1 size does not match the object count.")

    if header["meta2_offset"] != header["meta1_offset"] + header["meta1_size"]:
        raise ValueError("Meta2 offset does not follow the meta1 block.")

    if header["data_offset"] != header["meta2_offset"] + header["meta2_count"] * 12:
        raise ValueError("Data offset does not follow the meta2 block.")

    offsets = [entry["offset"] for entry in meta2_entries]
    if offsets != sorted(offsets):
        raise ValueError("Meta2 field offsets are not sorted.")

    field_stack = []
    parent_stack = [-1]
    running_object_index = -1

    for field_index, entry in enumerate(meta2_entries):
        offset = entry["offset"]
        info = entry["info"] & 0x7FFFFFFF
        name_length = (info >> 2) & 0x1FF

        if name_length <= 0:
            raise ValueError(f"{offset}: Field name has invalid length.")

        name_start = offset
        name_end = offset + name_length
        if name_end > len(data):
            raise ValueError(f"{offset}: Field name extends past the data block.")

        name_bytes = data[name_start:name_end]
        if name_bytes[-1] != 0:
            raise ValueError(f"{offset}: Field name is not null-terminated.")
        if 0 in name_bytes[:-1]:
            raise ValueError(f"{offset}: Field name contains an unexpected null byte.")

        try:
            field_name = name_bytes[:-1].decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"{offset}: Field name is not valid UTF-8.") from e

        if dson_string_hash(field_name) != entry["hash"]:
            raise ValueError(f"{offset}: Field name hash mismatch for {field_name!r}.")

        object_index = dson_object_index_from_info(entry["info"])
        is_object = object_index is not None

        if is_object:
            if object_index >= len(meta1_entries):
                raise ValueError(f"{offset}: Object index {object_index} is outside meta1.")

            object_info = meta1_entries[object_index]
            if object_info["meta2_index"] != field_index:
                raise ValueError(
                    f"{offset}: Object metadata points to field {object_info['meta2_index']}, "
                    f"but this field is {field_index}."
                )
            if object_info["parent"] != parent_stack[-1]:
                raise ValueError(
                    f"{offset}: Object parent {object_info['parent']} does not match "
                    f"current parent {parent_stack[-1]}."
                )

            running_object_index += 1

        if field_stack:
            field_stack[-1]["seen_children"] += 1
            if field_stack[-1]["seen_children"] > field_stack[-1]["expected_children"]:
                raise ValueError(
                    f"{offset}: Object {field_stack[-1]['name']!r} has too many children."
                )
        elif not is_object:
            raise ValueError(f"{offset}: First field is not a root object.")

        if is_object:
            field_stack.append({
                "name": field_name,
                "object_index": object_index,
                "expected_children": meta1_entries[object_index]["direct_children"],
                "seen_children": 0,
            })
            parent_stack.append(running_object_index)

        while field_stack and field_stack[-1]["seen_children"] == field_stack[-1]["expected_children"]:
            field_stack.pop()
            parent_stack.pop()

    if field_stack:
        field = field_stack[-1]
        raise ValueError(
            f"Object {field['name']!r} has {field['seen_children']} of "
            f"{field['expected_children']} expected children."
        )

    if running_object_index + 1 != header["meta1_count"]:
        raise ValueError(
            f"Object count mismatch: parsed {running_object_index + 1}, "
            f"header says {header['meta1_count']}."
        )


def dson_patch_mod_list_resize(raw, enabled_mods, mod_manager):
    dson_validate_editor_compatible(raw)

    header = dson_parse_header(raw)
    if header["header_length"] != 64 or header["meta1_offset"] != 64:
        raise ValueError("Unsupported DSON header layout.")

    meta1_entries = dson_parse_meta1(raw, header)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]

    try:
        applied_meta2_index = dson_find_meta2_by_name(raw, header, meta2_entries, "applied_ugcs_1_0")
    except ValueError:
        return dson_insert_missing_applied_ugcs(raw, enabled_mods, mod_manager)
    applied_meta2 = meta2_entries[applied_meta2_index]
    applied_meta1_index = dson_object_index_from_info(applied_meta2["info"])
    if applied_meta1_index is None:
        raise ValueError("applied_ugcs_1_0 is not marked as an object in metadata.")

    applied_start, applied_end, old_entries = dson_parse_applied_ugcs_with_layout(raw)
    applied_start_rel = applied_start - header["data_offset"]
    applied_end_rel = applied_end - header["data_offset"]
    old_data_size = applied_end_rel - applied_start_rel

    child_meta1_indices = [
        index for index, entry in enumerate(meta1_entries)
        if entry["parent"] == applied_meta1_index
    ]
    if len(child_meta1_indices) != len(old_entries):
        raise ValueError("Save metadata does not match the parsed applied_ugcs_1_0 entries.")

    child_meta1_start = min(child_meta1_indices) if child_meta1_indices else applied_meta1_index + 1
    child_meta1_end = max(child_meta1_indices) + 1 if child_meta1_indices else child_meta1_start

    child_meta2_ranges = []
    for child_index in child_meta1_indices:
        child = meta1_entries[child_index]
        start = child["meta2_index"]
        end = start + child["all_children"] + 1
        child_meta2_ranges.append((start, end))

    if child_meta2_ranges:
        child_meta2_start = min(start for start, _ in child_meta2_ranges)
        child_meta2_end = max(end for _, end in child_meta2_ranges)
    else:
        child_meta2_start = applied_meta2_index + 1
        child_meta2_end = child_meta2_start

    first_new_child_meta1_index = child_meta1_start
    new_applied_data, new_child_meta1, new_child_meta2 = dson_build_applied_ugcs_object(
        enabled_mods,
        mod_manager,
        applied_start_rel,
        first_new_child_meta1_index,
    )
    new_data_size = len(new_applied_data)
    data_delta = new_data_size - old_data_size

    removed_meta1_count = child_meta1_end - child_meta1_start
    inserted_meta1_count = len(new_child_meta1)
    meta1_delta = inserted_meta1_count - removed_meta1_count

    removed_meta2_count = child_meta2_end - child_meta2_start
    inserted_meta2_count = len(new_child_meta2)
    meta2_delta = inserted_meta2_count - removed_meta2_count

    for offset, entry in enumerate(new_child_meta1):
        entry["parent"] = applied_meta1_index
        entry["meta2_index"] = child_meta2_start + offset * 3

    preserved_meta1_entries = meta1_entries[:child_meta1_start] + meta1_entries[child_meta1_end:]

    for entry in preserved_meta1_entries:
        if entry["parent"] >= child_meta1_end:
            entry["parent"] += meta1_delta
        if entry["meta2_index"] >= child_meta2_end:
            entry["meta2_index"] += meta2_delta

    new_meta1_entries = (
        preserved_meta1_entries[:child_meta1_start]
        + new_child_meta1
        + preserved_meta1_entries[child_meta1_start:]
    )

    new_meta1_entries[applied_meta1_index]["direct_children"] = len(enabled_mods)
    new_meta1_entries[applied_meta1_index]["all_children"] = len(enabled_mods) * 3

    parent_index = new_meta1_entries[applied_meta1_index]["parent"]
    while parent_index >= 0:
        new_meta1_entries[parent_index]["all_children"] += meta2_delta
        parent_index = new_meta1_entries[parent_index]["parent"]

    preserved_meta2_before = meta2_entries[:child_meta2_start]
    preserved_meta2_after = meta2_entries[child_meta2_end:]

    original_next_offsets = {}
    sorted_original_offsets = sorted(entry["offset"] for entry in meta2_entries)
    for index, offset in enumerate(sorted_original_offsets):
        if index + 1 < len(sorted_original_offsets):
            original_next_offsets[offset] = sorted_original_offsets[index + 1]
        else:
            original_next_offsets[offset] = len(data)

    new_data_parts = [data[:applied_start_rel], new_applied_data]
    next_rebuilt_offset = applied_start_rel + len(new_applied_data)

    for entry in preserved_meta2_after:
        object_index = dson_object_index_from_info(entry["info"])
        if object_index is not None and object_index >= child_meta1_end:
            entry["info"] = dson_set_object_index_in_info(entry["info"], object_index + meta1_delta)

        old_offset = entry["offset"]
        rebuilt_block = dson_rebuild_existing_field_block(
            data,
            entry,
            original_next_offsets[old_offset],
            next_rebuilt_offset,
        )
        entry["offset"] = next_rebuilt_offset
        new_data_parts.append(rebuilt_block)
        next_rebuilt_offset += len(rebuilt_block)

    new_meta2_entries = preserved_meta2_before + new_child_meta2 + preserved_meta2_after

    new_data = b"".join(new_data_parts)

    new_header = bytearray(raw[:64])
    new_meta1_count = len(new_meta1_entries)
    new_meta2_count = len(new_meta2_entries)
    new_meta1_size = new_meta1_count * 16
    new_meta2_offset = 64 + new_meta1_size
    new_data_offset = new_meta2_offset + new_meta2_count * 12

    struct.pack_into("<i", new_header, 16, new_meta1_size)
    struct.pack_into("<i", new_header, 20, new_meta1_count)
    struct.pack_into("<i", new_header, 44, new_meta2_count)
    struct.pack_into("<i", new_header, 48, new_meta2_offset)
    struct.pack_into("<i", new_header, 56, len(new_data))
    struct.pack_into("<i", new_header, 60, new_data_offset)

    meta1_block = bytearray()
    for entry in new_meta1_entries:
        meta1_block.extend(dson_pack_i32_le(entry["parent"]))
        meta1_block.extend(dson_pack_i32_le(entry["meta2_index"]))
        meta1_block.extend(dson_pack_i32_le(entry["direct_children"]))
        meta1_block.extend(dson_pack_i32_le(entry["all_children"]))

    meta2_block = bytearray()
    for entry in new_meta2_entries:
        meta2_block.extend(dson_pack_i32_le(entry["hash"]))
        meta2_block.extend(dson_pack_i32_le(entry["offset"]))
        meta2_block.extend(dson_pack_i32_le(entry["info"]))

    patched = bytes(new_header) + bytes(meta1_block) + bytes(meta2_block) + bytes(new_data)

    check_header = dson_parse_header(patched)
    if check_header["data_offset"] + check_header["data_length"] != len(patched):
        raise ValueError("Patched save has inconsistent data offset/length metadata.")

    _, _, check_entries = dson_parse_applied_ugcs_with_layout(patched)
    if len(check_entries) != len(enabled_mods):
        raise ValueError("Patched save did not roundtrip with the requested mod count.")

    dson_validate_editor_compatible(patched)

    return patched, len(check_entries)


def dson_patch_named_name_source_object(raw, object_name, entries):
    dson_validate_editor_compatible(raw)

    header = dson_parse_header(raw)
    if header["header_length"] != 64 or header["meta1_offset"] != 64:
        raise ValueError("Unsupported DSON header layout.")

    meta1_entries = dson_parse_meta1(raw, header)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]

    object_meta2_index = dson_find_meta2_by_name(raw, header, meta2_entries, object_name)
    object_meta2 = meta2_entries[object_meta2_index]
    object_meta1_index = dson_object_index_from_info(object_meta2["info"])
    if object_meta1_index is None:
        raise ValueError(f"{object_name!r} is not marked as an object in metadata.")

    object_meta1 = meta1_entries[object_meta1_index]
    object_start_rel = object_meta2["offset"]
    object_end_meta2_index = object_meta2_index + object_meta1["all_children"] + 1
    object_end_rel = (
        meta2_entries[object_end_meta2_index]["offset"]
        if object_end_meta2_index < len(meta2_entries)
        else header["data_length"]
    )
    old_data_size = object_end_rel - object_start_rel

    child_meta1_indices = [
        index for index, entry in enumerate(meta1_entries)
        if entry["parent"] == object_meta1_index
    ]
    child_meta1_indices.sort()
    child_meta1_start = min(child_meta1_indices) if child_meta1_indices else object_meta1_index + 1
    child_meta1_end = max(child_meta1_indices) + 1 if child_meta1_indices else child_meta1_start

    child_meta2_ranges = []
    for child_index in child_meta1_indices:
        child = meta1_entries[child_index]
        start = child["meta2_index"]
        end = start + child["all_children"] + 1
        child_meta2_ranges.append((start, end))

    if child_meta2_ranges:
        child_meta2_start = min(start for start, _ in child_meta2_ranges)
        child_meta2_end = max(end for _, end in child_meta2_ranges)
    else:
        child_meta2_start = object_meta2_index + 1
        child_meta2_end = child_meta2_start

    new_object_data, new_child_meta1, new_child_meta2 = dson_build_named_name_source_object(
        object_name,
        entries,
        object_start_rel,
        child_meta1_start,
    )

    removed_meta1_count = child_meta1_end - child_meta1_start
    inserted_meta1_count = len(new_child_meta1)
    meta1_delta = inserted_meta1_count - removed_meta1_count

    removed_meta2_count = child_meta2_end - child_meta2_start
    inserted_meta2_count = len(new_child_meta2)
    meta2_delta = inserted_meta2_count - removed_meta2_count

    for offset, entry in enumerate(new_child_meta1):
        entry["parent"] = object_meta1_index
        entry["meta2_index"] = child_meta2_start + offset * 3

    preserved_meta1_entries = meta1_entries[:child_meta1_start] + meta1_entries[child_meta1_end:]
    for entry in preserved_meta1_entries:
        if entry["parent"] >= child_meta1_end:
            entry["parent"] += meta1_delta
        if entry["meta2_index"] >= child_meta2_end:
            entry["meta2_index"] += meta2_delta

    new_meta1_entries = (
        preserved_meta1_entries[:child_meta1_start]
        + new_child_meta1
        + preserved_meta1_entries[child_meta1_start:]
    )

    new_meta1_entries[object_meta1_index]["direct_children"] = len(entries)
    new_meta1_entries[object_meta1_index]["all_children"] = len(entries) * 3

    parent_index = new_meta1_entries[object_meta1_index]["parent"]
    while parent_index >= 0:
        new_meta1_entries[parent_index]["all_children"] += meta2_delta
        parent_index = new_meta1_entries[parent_index]["parent"]

    preserved_meta2_before = meta2_entries[:child_meta2_start]
    preserved_meta2_after = meta2_entries[child_meta2_end:]

    original_next_offsets = {}
    sorted_original_offsets = sorted(entry["offset"] for entry in meta2_entries)
    for index, offset in enumerate(sorted_original_offsets):
        if index + 1 < len(sorted_original_offsets):
            original_next_offsets[offset] = sorted_original_offsets[index + 1]
        else:
            original_next_offsets[offset] = len(data)

    new_data_parts = [data[:object_start_rel], new_object_data]
    next_rebuilt_offset = object_start_rel + len(new_object_data)

    for entry in preserved_meta2_after:
        object_index = dson_object_index_from_info(entry["info"])
        if object_index is not None and object_index >= child_meta1_end:
            entry["info"] = dson_set_object_index_in_info(entry["info"], object_index + meta1_delta)

        old_offset = entry["offset"]
        rebuilt_block = dson_rebuild_existing_field_block(
            data,
            entry,
            original_next_offsets[old_offset],
            next_rebuilt_offset,
        )
        entry["offset"] = next_rebuilt_offset
        new_data_parts.append(rebuilt_block)
        next_rebuilt_offset += len(rebuilt_block)

    new_meta2_entries = preserved_meta2_before + new_child_meta2 + preserved_meta2_after
    new_data = b"".join(new_data_parts)

    new_header = bytearray(raw[:64])
    new_meta1_count = len(new_meta1_entries)
    new_meta2_count = len(new_meta2_entries)
    new_meta1_size = new_meta1_count * 16
    new_meta2_offset = 64 + new_meta1_size
    new_data_offset = new_meta2_offset + new_meta2_count * 12

    struct.pack_into("<i", new_header, 16, new_meta1_size)
    struct.pack_into("<i", new_header, 20, new_meta1_count)
    struct.pack_into("<i", new_header, 44, new_meta2_count)
    struct.pack_into("<i", new_header, 48, new_meta2_offset)
    struct.pack_into("<i", new_header, 56, len(new_data))
    struct.pack_into("<i", new_header, 60, new_data_offset)

    meta1_block = bytearray()
    for entry in new_meta1_entries:
        meta1_block.extend(dson_pack_i32_le(entry["parent"]))
        meta1_block.extend(dson_pack_i32_le(entry["meta2_index"]))
        meta1_block.extend(dson_pack_i32_le(entry["direct_children"]))
        meta1_block.extend(dson_pack_i32_le(entry["all_children"]))

    meta2_block = bytearray()
    for entry in new_meta2_entries:
        meta2_block.extend(dson_pack_i32_le(entry["hash"]))
        meta2_block.extend(dson_pack_i32_le(entry["offset"]))
        meta2_block.extend(dson_pack_i32_le(entry["info"]))

    patched = bytes(new_header) + bytes(meta1_block) + bytes(meta2_block) + bytes(new_data)

    check_header = dson_parse_header(patched)
    if check_header["data_offset"] + check_header["data_length"] != len(patched):
        raise ValueError("Patched save has inconsistent data offset/length metadata.")

    check_entries = dson_parse_named_name_source_object(patched, object_name)
    if len(check_entries) != len(entries):
        raise ValueError(f"Patched save did not roundtrip with the requested {object_name!r} count.")

    dson_validate_editor_compatible(patched)
    return patched


def dson_file_has_field_name(file_path, field_name):
    with open(file_path, "rb") as f:
        raw = f.read()

    header = dson_parse_header(raw)
    meta2_entries = dson_parse_meta2(raw, header)
    try:
        dson_find_meta2_by_name(raw, header, meta2_entries, field_name)
        return True
    except Exception:
        return False


def dson_file_contains_scalar_value(file_path, wanted_value):
    with open(file_path, "rb") as f:
        raw = f.read()

    header = dson_parse_header(raw)
    meta2_entries = dson_parse_meta2(raw, header)
    data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]
    wanted_text = str(wanted_value).strip()

    for index, entry in enumerate(meta2_entries):
        next_offset = (
            meta2_entries[index + 1]["offset"]
            if index + 1 < len(meta2_entries)
            else header["data_length"]
        )
        value = dson_decode_scalar_field(data, entry, next_offset)
        if isinstance(value, str) and value.strip() == wanted_text:
            return True
    return False


def dson_replace_scalar_payloads_from_template(target_raw, template_raw, field_name):
    target_header = dson_parse_header(target_raw)
    target_meta2 = dson_parse_meta2(target_raw, target_header)
    target_data = bytearray(target_raw[target_header["data_offset"]:target_header["data_offset"] + target_header["data_length"]])

    template_header = dson_parse_header(template_raw)
    template_meta2 = dson_parse_meta2(template_raw, template_header)
    template_data = template_raw[template_header["data_offset"]:template_header["data_offset"] + template_header["data_length"]]

    target_indices = [i for i, entry in enumerate(target_meta2) if dson_meta2_name(target_raw, target_header, entry) == field_name]
    template_indices = [i for i, entry in enumerate(template_meta2) if dson_meta2_name(template_raw, template_header, entry) == field_name]
    if len(target_indices) != len(template_indices):
        raise ValueError(f"Template field count mismatch for {field_name!r}.")

    for target_index, template_index in zip(target_indices, template_indices):
        target_entry = target_meta2[target_index]
        template_entry = template_meta2[template_index]

        target_next = target_meta2[target_index + 1]["offset"] if target_index + 1 < len(target_meta2) else target_header["data_length"]
        template_next = template_meta2[template_index + 1]["offset"] if template_index + 1 < len(template_meta2) else template_header["data_length"]

        target_payload, target_start, target_end = dson_field_payload_layout(target_data, target_entry, target_next)
        template_payload, _, _ = dson_field_payload_layout(template_data, template_entry, template_next)
        if len(target_payload) != len(template_payload):
            raise ValueError(f"Template payload size mismatch for {field_name!r}.")
        target_data[target_start:target_end] = template_payload

    return bytes(target_raw[:target_header["data_offset"]]) + bytes(target_data)


def dson_replace_scalar_payload_offsets_from_template(target_raw, template_raw, field_name, offsets):
    target_header = dson_parse_header(target_raw)
    target_meta2 = dson_parse_meta2(target_raw, target_header)
    target_data = bytearray(target_raw[target_header["data_offset"]:target_header["data_offset"] + target_header["data_length"]])

    template_header = dson_parse_header(template_raw)
    template_meta2 = dson_parse_meta2(template_raw, template_header)
    template_data = template_raw[template_header["data_offset"]:template_header["data_offset"] + template_header["data_length"]]

    target_indices = [i for i, entry in enumerate(target_meta2) if dson_meta2_name(target_raw, target_header, entry) == field_name]
    template_indices = [i for i, entry in enumerate(template_meta2) if dson_meta2_name(template_raw, template_header, entry) == field_name]
    if len(target_indices) != len(template_indices):
        raise ValueError(f"Template field count mismatch for {field_name!r}.")

    for target_index, template_index in zip(target_indices, template_indices):
        target_entry = target_meta2[target_index]
        template_entry = template_meta2[template_index]

        target_next = target_meta2[target_index + 1]["offset"] if target_index + 1 < len(target_meta2) else target_header["data_length"]
        template_next = template_meta2[template_index + 1]["offset"] if template_index + 1 < len(template_meta2) else template_header["data_length"]

        target_payload, target_start, target_end = dson_field_payload_layout(target_data, target_entry, target_next)
        template_payload, _, _ = dson_field_payload_layout(template_data, template_entry, template_next)
        if len(target_payload) != len(template_payload):
            raise ValueError(f"Template payload size mismatch for {field_name!r}.")

        mutable_payload = bytearray(target_payload)
        for offset in offsets:
            if offset < 0 or offset >= len(mutable_payload) or offset >= len(template_payload):
                raise ValueError(f"Offset {offset} is outside {field_name!r} payload.")
            mutable_payload[offset] = template_payload[offset]
        target_data[target_start:target_end] = mutable_payload

    return bytes(target_raw[:target_header["data_offset"]]) + bytes(target_data)

class ModManager:

    # Rebuilds the top-level applied_ugcs_1_0 block in a save while
    # leaving the rest of the file structure intact, then writes it
    # back in place after creating a timestamped backup.
    def patch_selected_save_file(self, file_path):
        with open(file_path, "rb") as f:
            raw = f.read()

        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})
        enabled_mods = [m for m in order if enabled_map.get(m, True)]

        if not order:
            raise ValueError("No mods are loaded. Set your mods folder and refresh mods before patching a save.")
        if not enabled_mods:
            raise ValueError("No mods are enabled. Enable at least one mod before patching a save.")

        patched, patched_count = dson_patch_mod_list_resize(raw, enabled_mods, self)
        backup_path = persist_backup_path(file_path)
        shutil.copy2(file_path, backup_path)

        temp_path = unique_path(file_path + ".tmp")
        try:
            with open(temp_path, "wb") as f:
                f.write(patched)
            with open(temp_path, "rb") as f:
                dson_validate_editor_compatible(f.read())
            os.replace(temp_path, file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

        self.state["last_save_path"] = file_path
        self.state["last_backup_path"] = backup_path
        self.state["last_output_path"] = file_path
        self.save_state()

        return patched_count, backup_path

    def patch_save_file_with_metadata(self, file_path=None):
        if file_path is None:
            initialdir = self.best_save_initialdir()
            file_path = filedialog.askopenfilename(
                title="Select persist.game.json",
                initialdir=initialdir if initialdir else None,
                filetypes=[("Darkest Dungeon save", "*persist.game.json"), ("JSON files", "*.json"), ("All files", "*.*")]
            )
        if not file_path:
            return

        if os.path.basename(file_path).lower() != "persist.game.json":
            proceed = self.ask_yes_no(
                "Patch Selected File?",
                "This does not look like the default persist.game.json file.\n\n"
                "The app will still create a backup first, then write the patched save over the selected file.\n\n"
                "Continue?"
            )
            if not proceed:
                return

        try:
            patched_count, backup_path = self.patch_selected_save_file(file_path)
        except Exception as e:
            self.show_error(
                "Cannot Patch Save",
                "The save writer could not rebuild the mod list metadata.\n\n"
                f"{e}"
            )
            return

        self.set_status_text(
            f"Patched {patched_count} enabled mods. Backup: {os.path.basename(backup_path)}"
        )
        self.show_info(
            "Save Ready",
            "Patched save written to the game's default file name.\n\n"
            f"Patched file:\n{file_path}\n\n"
            f"Backup created:\n{backup_path}\n\n"
            "You can launch Darkest Dungeon now without renaming or moving the file."
        )

    def patch_latest_save_file(self):
        latest = self.detect_latest_save_file()
        if not latest:
            self.show_warning(
                "No Save Found",
                "I could not auto-detect a persist.game.json save file.\n\n"
                "Use Patch Save File and pick the save manually."
            )
            return

        proceed = self.ask_yes_no(
            "Patch Latest Save?",
            "This will create a backup, then write the patched save back to:\n\n"
            f"{latest}\n\n"
            "Continue?"
        )
        if proceed:
            self.patch_save_file_with_metadata(latest)

    def patch_selected_profile_save(self):
        save_path = self.selected_profile_path()
        if not save_path:
            self.show_warning(
                "No Profile Selected",
                "Choose a profile from the profile menu first."
            )
            return

        proceed = self.ask_yes_no(
            "Patch Selected Profile?",
            "This will create a backup, then write the patched save back to:\n\n"
            f"{save_path}\n\n"
            "Continue?"
        )
        if proceed:
            self.patch_save_file_with_metadata(save_path)

    def profile_root_dir(self):
        candidates = []
        for save_path in self.detect_save_files():
            profile_dir = os.path.dirname(save_path)
            root_dir = os.path.dirname(profile_dir)
            if profile_dir and root_dir and os.path.isdir(root_dir):
                candidates.append(root_dir)

        seen = set()
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            return path
        return ""

    def difficulty_label_from_game_mode(self, game_mode):
        labels = {
            "radiant": "Radiant",
            "bloodmoon": "Bloodmoon",
            "base": "Darkest",
            "darkest": "Darkest",
            "stygian": "Stygian",
        }
        normalized = str(game_mode or "").strip().lower()
        if normalized in labels:
            return labels[normalized]
        if not normalized:
            return "Unknown"
        return normalized.replace("_", " ").title()

    def template_kind_for_profile(self, save_path):
        profile_dir = os.path.dirname(save_path)
        estate_path = os.path.join(profile_dir, "persist.estate.json")

        has_memory_wallet = False
        if os.path.isfile(estate_path):
            try:
                has_memory_wallet = dson_file_contains_scalar_value(estate_path, "memory")
            except Exception:
                has_memory_wallet = False

        if has_memory_wallet:
            return "campaign_ready"
        return "tutorial_seed"

    def starter_template_candidates(self):
        candidates = []
        for slot in self.detect_profile_slots():
            save_path = slot["path"]
            fields = self.read_scalar_dson_fields(
                save_path,
                wanted_names={"inraid", "raiddungeon", "game_mode", "estatename"},
            )
            if not fields.get("inraid"):
                continue
            if str(fields.get("raiddungeon", "")).strip().lower() != "tutorial":
                continue

            applied_mod_count = 0
            try:
                applied_mod_count = len(self.save_applied_mod_names(save_path))
            except Exception:
                applied_mod_count = 0

            difficulty = self.difficulty_label_from_game_mode(fields.get("game_mode", ""))
            template_kind = self.template_kind_for_profile(save_path)
            label = f"{difficulty} starter - {slot['label']}"
            if template_kind == "campaign_ready":
                label = f"{difficulty} ready template - {slot['label']}"
            if applied_mod_count:
                plural = "mod" if applied_mod_count == 1 else "mods"
                label = f"{label} | template has {applied_mod_count} saved {plural}"

            candidates.append({
                "path": save_path,
                "label": label,
                "difficulty": difficulty,
                "game_mode": str(fields.get("game_mode", "")),
                "estatename": str(fields.get("estatename", "")),
                "applied_mod_count": applied_mod_count,
                "template_kind": template_kind,
            })

        return candidates

    def preferred_starter_template(self, preferred_difficulty=None):
        templates = self.starter_template_candidates()
        if not templates:
            return None

        difficulty_rank = {
            "Darkest": 0,
            "Radiant": 1,
            "Bloodmoon": 2,
            "Stygian": 3,
            "Unknown": 4,
        }

        normalized_preferred = str(preferred_difficulty or "").strip()
        matching = [item for item in templates if item.get("difficulty") == normalized_preferred]
        if matching:
            templates = matching

        return sorted(
            templates,
            key=lambda item: (
                0 if item.get("template_kind") == "campaign_ready" else 1,
                0 if item.get("applied_mod_count", 0) == 0 else 1,
                difficulty_rank.get(item.get("difficulty", "Unknown"), 5),
                item.get("label", ""),
            ),
        )[0]

    def campaign_target_slot_choices(self):
        root_dir = self.profile_root_dir()
        if not root_dir:
            return []

        choices = []
        for index in range(0, 9):
            folder_name = f"profile_{index}"
            folder_path = os.path.join(root_dir, folder_name)
            label = f"Slot {index + 1} [{folder_name}]"
            save_path = os.path.join(folder_path, "persist.game.json")
            if os.path.isfile(save_path):
                label = f"{label} - occupied"
            else:
                label = f"{label} - empty"
            choices.append({
                "index": index,
                "folder_name": folder_name,
                "folder_path": folder_path,
                "label": label,
                "occupied": os.path.isdir(folder_path),
            })
        return choices

    def available_campaign_difficulties(self):
        seen = set()
        for template in self.starter_template_candidates():
            seen.add(template.get("difficulty", "Unknown"))

        preferred_order = ["Radiant", "Darkest", "Bloodmoon", "Stygian", "Unknown"]
        ordered = [difficulty for difficulty in preferred_order if difficulty in seen]
        extras = sorted(difficulty for difficulty in seen if difficulty not in preferred_order)
        return ordered + extras or ["Darkest"]

    def enabled_mods_for_save_patch(self):
        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})
        return [mod for mod in order if enabled_map.get(mod, True)]

    def campaign_dlc_ids(self):
        return [dlc_id for dlc_id, _label in CAMPAIGN_DLC_CHOICES]

    def campaign_dlc_label(self, dlc_id):
        for current_id, label in CAMPAIGN_DLC_CHOICES:
            if current_id == dlc_id:
                return label
        return str(dlc_id).replace("_", " ").title()

    def active_dlc_names_from_save(self, file_path):
        with open(file_path, "rb") as f:
            raw = f.read()

        active = []
        for entry in dson_parse_named_name_source_object(raw, "dlc"):
            for field in entry.get("fields", []):
                if field.get("field_name") == "name":
                    value = str(field.get("value", "")).strip()
                    if value:
                        active.append(value)
                    break
        return active

    def default_campaign_dlc_names(self, preferred_difficulty=None):
        template = self.preferred_starter_template(preferred_difficulty)
        if template is None:
            return []
        try:
            return self.active_dlc_names_from_save(template["path"])
        except Exception:
            return []

    def build_campaign_dlc_entries(self, active_dlc_names):
        active_set = {str(name).strip() for name in active_dlc_names if str(name).strip()}
        entries = []
        ordered_ids = self.campaign_dlc_ids()
        for dlc_id in ordered_ids:
            if dlc_id in active_set:
                entries.append({"name": dlc_id, "source": "dlc"})
        extras = sorted(dlc_id for dlc_id in active_set if dlc_id not in ordered_ids)
        for dlc_id in extras:
            entries.append({"name": dlc_id, "source": "dlc"})
        return entries

    def synchronize_campaign_identity_from_template(self, target_profile_dir, template_profile_dir):
        manual_template_dir = os.path.join(APP_DIR, "profile_8_manual_full")
        if not os.path.isdir(manual_template_dir):
            return

        template_game_path = os.path.join(template_profile_dir, "persist.game.json")
        with open(template_game_path, "rb") as f:
            template_game_raw = f.read()
        template_values = self.read_scalar_dson_fields(
            template_game_path,
            wanted_names={"game_mode", "inraid", "raiddungeon"},
        )

        manual_game_path = os.path.join(manual_template_dir, "persist.game.json")
        manual_values = self.read_scalar_dson_fields(
            manual_game_path,
            wanted_names={"game_mode", "inraid", "raiddungeon"},
        )
        if (
            template_values.get("game_mode") != manual_values.get("game_mode")
            or template_values.get("inraid") != manual_values.get("inraid")
            or str(template_values.get("raiddungeon", "")).strip().lower()
                != str(manual_values.get("raiddungeon", "")).strip().lower()
        ):
            return
        for filename in (
            "persist.game.json",
            "persist.estate.json",
            "persist.raid.json",
            "persist.map.json",
            "persist.roster.json",
        ):
            source_path = os.path.join(manual_template_dir, filename)
            target_path = os.path.join(target_profile_dir, filename)
            if os.path.isfile(source_path):
                shutil.copy2(source_path, target_path)

        tutorial_path = os.path.join(target_profile_dir, "persist.tutorial.json")
        if os.path.isfile(tutorial_path):
            os.remove(tutorial_path)

    def write_new_campaign_persist_game(self, file_path, campaign_name, apply_current_mods=True, active_dlc_names=None):
        with open(file_path, "rb") as f:
            raw = f.read()

        if campaign_name:
            raw = dson_patch_scalar_string_field(raw, "estatename", campaign_name)

        if active_dlc_names is not None:
            raw = dson_patch_named_name_source_object(
                raw,
                "dlc",
                self.build_campaign_dlc_entries(active_dlc_names),
            )

        enabled_mods = self.enabled_mods_for_save_patch() if apply_current_mods else []
        raw, patched_count = dson_patch_mod_list_resize(raw, enabled_mods, self)

        with open(file_path, "wb") as f:
            f.write(raw)
        return patched_count

    def create_campaign_from_template(
        self,
        template_save_path,
        target_slot_index,
        campaign_name,
        apply_current_mods=True,
        active_dlc_names=None,
    ):
        profile_root = self.profile_root_dir()
        if not profile_root:
            raise ValueError("Could not determine the Darkest Dungeon profile folder.")

        template_dir = os.path.dirname(template_save_path)
        if not os.path.isdir(template_dir):
            raise ValueError("The chosen starter template profile could not be found.")

        target_dir = os.path.join(profile_root, f"profile_{target_slot_index}")
        existing_save_path = os.path.join(target_dir, "persist.game.json")
        if os.path.isfile(existing_save_path):
            raise ValueError("The chosen target slot is already in use. Pick an empty slot instead.")
        staging_dir = unique_path(os.path.join(APP_DIR, f"profile_{target_slot_index}_staging"))

        try:
            shutil.copytree(template_dir, staging_dir)
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)

            persist_game_path = os.path.join(staging_dir, "persist.game.json")
            if not os.path.isfile(persist_game_path):
                raise ValueError("The starter template is missing persist.game.json.")

            self.synchronize_campaign_identity_from_template(staging_dir, template_dir)
            patched_count = self.write_new_campaign_persist_game(
                persist_game_path,
                campaign_name,
                apply_current_mods=apply_current_mods,
                active_dlc_names=active_dlc_names,
            )
            shutil.move(staging_dir, target_dir)
        except Exception:
            if os.path.isdir(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        target_save_path = os.path.join(target_dir, "persist.game.json")
        self.state["selected_profile_path"] = target_save_path
        self.state["last_save_path"] = target_save_path
        self.save_state()
        return target_save_path, patched_count

    def start_new_campaign(self):
        templates = self.starter_template_candidates()
        if not templates:
            self.show_warning(
                "No Starter Templates Found",
                "I could not find any tutorial-state starter profiles to clone.\n\n"
                "Create a new campaign, enter the first dungeon, then exit to desktop so the app has a starter template to work from."
            )
            return

        ready_templates = [item for item in templates if item.get("template_kind") == "campaign_ready"]
        if not ready_templates:
            self.show_warning(
                "Need a Fresh Campaign Template",
                "Start New Campaign now needs one clean in-game campaign template to clone from.\n\n"
                "Create a brand-new campaign in Darkest Dungeon, make sure it appears in the save list, then exit the game and try again.\n\n"
                "Once that template exists, the wizard can clone it into new slots and patch in the chosen DLC and mod list."
            )
            return

        slot_choices = self.campaign_target_slot_choices()
        if not slot_choices:
            self.show_warning(
                "No Profile Folder Found",
                "I could not find the Darkest Dungeon profile folder."
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Start New Campaign")
        dialog.geometry("700x520")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        empty_slot_choices = [item for item in slot_choices if not item["occupied"]]
        if not empty_slot_choices:
            self.show_warning(
                "No Empty Profile Slots",
                "All detected profile slots are already in use.\n\n"
                "Delete an unused profile in-game first, then try Start New Campaign again."
            )
            return

        first_empty = empty_slot_choices[0]
        slot_map = {item["label"]: item for item in empty_slot_choices}
        starter_reference = self.preferred_starter_template()
        default_name = "Darkest"
        template_name = (starter_reference or {}).get("estatename", "").strip()
        if template_name:
            default_name = template_name
        difficulty_choices = self.available_campaign_difficulties()
        default_difficulty = "Darkest" if "Darkest" in difficulty_choices else difficulty_choices[0]
        default_dlc_names = self.default_campaign_dlc_names(default_difficulty)

        wizard_state = {
            "slot_label": first_empty["label"],
            "campaign_name": default_name,
            "difficulty": default_difficulty,
            "active_dlc_names": list(default_dlc_names),
            "apply_mods": True,
        }
        step_index = {"value": 0}
        step_frames = []

        body = self.themed_frame(dialog)
        body.pack(fill="both", expand=True, padx=14, pady=14)

        self.themed_label(body, text="Start New Campaign", style="heading").pack(anchor="w", pady=(0, 10))
        intro_label = self.themed_label(
            body,
            text=(
                "This version creates a new campaign by cloning a clean game-created campaign template, "
                "then patching in the chosen DLC state and optionally the current enabled mods."
            ),
            style="muted",
            justify="left",
            wraplength=650,
        )
        intro_label.pack(anchor="w", pady=(0, 14))

        step_container = self.themed_frame(body)
        step_container.pack(fill="both", expand=True)

        footer = self.themed_frame(body)
        footer.pack(fill="x", pady=(14, 0))
        nav_left = self.themed_frame(footer)
        nav_left.pack(side="left")
        nav_right = self.themed_frame(footer)
        nav_right.pack(side="right")

        back_button = self.themed_button(nav_left, text="Back", command=lambda: None)
        next_button = self.themed_button(nav_right, text="Next", command=lambda: None, style="primary")
        cancel_button = self.themed_button(nav_right, text=self.tr("cancel"), command=dialog.destroy)
        back_button.pack(side="left", padx=(0, 6))
        cancel_button.pack(side="right", padx=(6, 0))
        next_button.pack(side="right")

        def add_step(title, description):
            frame = self.themed_frame(step_container)
            self.themed_label(frame, text=title, style="heading").pack(anchor="w", pady=(0, 8))
            if description:
                self.themed_label(
                    frame,
                    text=description,
                    style="muted",
                    justify="left",
                    wraplength=650,
                ).pack(anchor="w", pady=(0, 12))
            step_frames.append(frame)
            return frame

        slot_step = add_step(
            "Step 1: Choose Slot and Name",
            "Pick an empty save slot and name the new campaign.",
        )
        slot_var = tk.StringVar(value=wizard_state["slot_label"])
        campaign_name_var = tk.StringVar(value=wizard_state["campaign_name"])

        slot_row = self.themed_frame(slot_step)
        slot_row.pack(fill="x", pady=4)
        self.themed_label(slot_row, text="Target Empty Slot:", style="heading").pack(side="left", padx=(0, 8))
        slot_menu = tk.OptionMenu(slot_row, slot_var, *list(slot_map.keys()))
        self.configure_option_menu(slot_menu)
        slot_menu.config(width=28)
        slot_menu.pack(side="left", fill="x", expand=True)

        name_row = self.themed_frame(slot_step)
        name_row.pack(fill="x", pady=8)
        self.themed_label(name_row, text="Campaign Name:", style="heading").pack(side="left", padx=(0, 8))
        campaign_name_entry = self.themed_entry(name_row, textvariable=campaign_name_var, width=34)
        campaign_name_entry.pack(side="left", fill="x", expand=True)

        dlc_step = add_step(
            "Step 2: Choose DLC",
            "Choose which DLC entries should be active in the new campaign save.",
        )
        dlc_help = self.themed_label(
            dlc_step,
            text="Toggle any of the seven campaign DLC entries on or off.",
            style="muted",
            justify="left",
            wraplength=650,
        )
        dlc_help.pack(anchor="w", pady=(0, 8))
        dlc_grid = self.themed_frame(dlc_step)
        dlc_grid.pack(fill="x", pady=(0, 8))
        for column in range(2):
            dlc_grid.grid_columnconfigure(column, weight=1)
        dlc_vars = {}
        for index, (dlc_id, label) in enumerate(CAMPAIGN_DLC_CHOICES):
            var = tk.BooleanVar(value=(dlc_id in default_dlc_names))
            dlc_vars[dlc_id] = var
            checkbox = tk.Checkbutton(
                dlc_grid,
                text=label,
                variable=var,
                bg=THEME["bg"],
                fg=THEME["text"],
                activebackground=THEME["bg"],
                activeforeground=THEME["text_bright"],
                selectcolor=THEME["panel"],
                font=FONT_BODY,
                anchor="w",
                justify="left",
            )
            row = index // 2
            column = index % 2
            checkbox.grid(row=row, column=column, sticky="w", padx=(0, 20), pady=4)

        difficulty_step = add_step(
            "Step 3: Choose Difficulty",
            "This chooses the closest matching built-in starter template we have available.",
        )
        difficulty_var = tk.StringVar(value=wizard_state["difficulty"])
        difficulty_buttons = {}

        def refresh_difficulty_buttons():
            selected = difficulty_var.get()
            for difficulty, button in difficulty_buttons.items():
                if difficulty == selected:
                    button.config(
                        bg=THEME["crimson"],
                        fg=THEME["text_bright"],
                        activebackground=THEME["crimson_hover"],
                        activeforeground=THEME["text_bright"],
                        relief="sunken",
                        bd=2,
                    )
                else:
                    button.config(
                        bg=THEME["panel"],
                        fg=THEME["text"],
                        activebackground=THEME["border"],
                        activeforeground=THEME["text_bright"],
                        relief="solid",
                        bd=1,
                    )

        for difficulty in difficulty_choices:
            button = self.themed_button(
                difficulty_step,
                text=difficulty,
                command=lambda value=difficulty: (difficulty_var.set(value), refresh_difficulty_buttons()),
                style="secondary",
                width=18,
            )
            button.pack(anchor="w", pady=4)
            difficulty_buttons[difficulty] = button
        refresh_difficulty_buttons()

        current_mod_count = len(self.enabled_mods_for_save_patch())
        mods_step = add_step(
            "Step 4: Apply Current Mod List",
            "Choose whether the new campaign should immediately use the current enabled mod list.",
        )
        apply_mods_var = tk.StringVar(value="yes")
        mods_summary = self.themed_label(
            mods_step,
            text=f"Currently enabled mods: {current_mod_count}",
            style="heading",
            anchor="w",
        )
        mods_summary.pack(anchor="w", pady=(0, 10))
        mods_choice_row = self.themed_frame(mods_step)
        mods_choice_row.pack(anchor="w", pady=4)
        tk.Radiobutton(
            mods_choice_row,
            text="Yes, patch in the current enabled mods",
            variable=apply_mods_var,
            value="yes",
            bg=THEME["bg"],
            fg=THEME["text"],
            activebackground=THEME["bg"],
            activeforeground=THEME["text_bright"],
            selectcolor=THEME["panel"],
            font=FONT_BODY,
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            mods_choice_row,
            text="No, leave the new campaign with no saved mod list",
            variable=apply_mods_var,
            value="no",
            bg=THEME["bg"],
            fg=THEME["text"],
            activebackground=THEME["bg"],
            activeforeground=THEME["text_bright"],
            selectcolor=THEME["panel"],
            font=FONT_BODY,
        ).pack(anchor="w", pady=2)

        review_step = add_step(
            "Step 5: Create Campaign",
            "Review the choices below, then create the new campaign.",
        )
        review_summary = self.themed_label(review_step, text="", style="body", justify="left", wraplength=650, anchor="w")
        review_summary.pack(anchor="w")

        def sync_wizard_state():
            wizard_state["slot_label"] = slot_var.get()
            wizard_state["campaign_name"] = " ".join(campaign_name_var.get().strip().split())
            wizard_state["difficulty"] = difficulty_var.get()
            wizard_state["active_dlc_names"] = [
                dlc_id for dlc_id in self.campaign_dlc_ids()
                if dlc_vars[dlc_id].get()
            ]
            wizard_state["apply_mods"] = apply_mods_var.get() == "yes"

        def selected_template_for_current_state():
            sync_wizard_state()
            return self.preferred_starter_template(wizard_state["difficulty"])

        def require_campaign_ready_template():
            template = selected_template_for_current_state()
            if template is None:
                self.show_warning(
                    "No Matching Starter Template",
                    "I could not find a starter template for that difficulty yet.",
                    parent=dialog,
                )
                return None
            if template.get("template_kind") != "campaign_ready":
                self.show_warning(
                    "Need a Fresh Campaign Template",
                    "The best template for that difficulty is still only a raw tutorial seed.\n\n"
                    "Create one clean in-game campaign for that difficulty first, make sure it appears in the save list, then try again.",
                    parent=dialog,
                )
                return None
            return template

        def refresh_review():
            sync_wizard_state()
            mod_text = "Yes" if wizard_state["apply_mods"] else "No"
            dlc_labels = [
                self.campaign_dlc_label(dlc_id)
                for dlc_id in wizard_state["active_dlc_names"]
            ]
            dlc_text = ", ".join(dlc_labels) if dlc_labels else "None"
            template = selected_template_for_current_state()
            template_text = "ready template" if template and template.get("template_kind") == "campaign_ready" else "tutorial seed"
            review_summary.config(
                text=(
                    f"Target slot: {wizard_state['slot_label']}\n"
                    f"Campaign name: {wizard_state['campaign_name'] or '(missing)'}\n"
                    f"Active DLC: {dlc_text}\n"
                    f"Difficulty: {wizard_state['difficulty']}\n"
                    f"Apply current mod list: {mod_text}\n"
                    f"Template type: {template_text}"
                )
            )

        def validate_step(index):
            sync_wizard_state()
            if index == 0 and not wizard_state["campaign_name"]:
                self.show_warning("Missing Campaign Name", "Enter a campaign name first.", parent=dialog)
                return False
            if index == 2 and selected_template_for_current_state() is None:
                self.show_warning(
                    "No Matching Starter Template",
                    "I could not find a starter template for that difficulty yet.",
                    parent=dialog,
                )
                return False
            if index >= 2 and require_campaign_ready_template() is None:
                return False
            return True

        def show_step(index):
            step_index["value"] = index
            for current, frame in enumerate(step_frames):
                if current == index:
                    frame.pack(fill="both", expand=True)
                else:
                    frame.pack_forget()

            back_button.config(state=("normal" if index > 0 else "disabled"))
            if index == len(step_frames) - 1:
                refresh_review()
                next_button.config(text="Create Campaign")
            else:
                next_button.config(text="Next")

            if index == 0:
                campaign_name_entry.focus_set()

        def go_back():
            if step_index["value"] > 0:
                show_step(step_index["value"] - 1)

        def finish_campaign_creation():
            sync_wizard_state()
            slot_choice = slot_map.get(wizard_state["slot_label"])
            template = require_campaign_ready_template()
            if slot_choice is None or template is None:
                return

            try:
                target_save_path, patched_count = self.create_campaign_from_template(
                    template["path"],
                    slot_choice["index"],
                    wizard_state["campaign_name"],
                    apply_current_mods=wizard_state["apply_mods"],
                    active_dlc_names=wizard_state["active_dlc_names"],
                )
            except Exception as error:
                self.show_error(
                    "Could Not Create Campaign",
                    f"Failed to create the new campaign template:\n\n{error}",
                    parent=dialog,
                )
                return

            dialog.destroy()
            self.refresh_profile_menu()
            target_label = ""
            for label, path in self.profile_label_to_path.items():
                if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(target_save_path)):
                    target_label = label
                    break
            if target_label:
                self.select_profile(target_label)

            status = f"New campaign created in {slot_choice['folder_name']}"
            if wizard_state["apply_mods"]:
                status += f" | {patched_count} mods patched"
            self.set_status_text(status)

            lines = [
                f"Created new campaign profile:\n{target_save_path}",
                "",
                f"Campaign name:\n{wizard_state['campaign_name']}",
                "",
                "Active DLC:",
                ", ".join(self.campaign_dlc_label(dlc_id) for dlc_id in wizard_state["active_dlc_names"]) or "None",
                "",
                f"Difficulty: {wizard_state['difficulty']}",
                "",
                f"Applied current mod list: {'Yes' if wizard_state['apply_mods'] else 'No'}",
            ]
            if wizard_state["apply_mods"]:
                lines.extend(["", f"Patched enabled mods into the new save: {patched_count}"])
            self.show_info("New Campaign Ready", "\n".join(lines))

        def go_next():
            current = step_index["value"]
            if not validate_step(current):
                return
            if current == len(step_frames) - 1:
                finish_campaign_creation()
                return
            show_step(current + 1)

        back_button.config(command=go_back)
        next_button.config(command=go_next)
        show_step(0)

    def restore_last_backup(self):
        backup_path = self.state.get("last_backup_path", "")
        save_path = self.state.get("last_save_path", "")

        if not backup_path or not save_path or not os.path.isfile(backup_path):
            self.show_warning(
                "No Backup",
                "No previous save backup was found for this session."
            )
            return

        proceed = self.ask_yes_no(
            "Restore Backup?",
            "This will replace the current save with the last backup:\n\n"
            f"Backup:\n{backup_path}\n\n"
            f"Target:\n{save_path}\n\n"
            "Continue?"
        )
        if not proceed:
            return

        try:
            shutil.copy2(backup_path, save_path)
            self.set_status_text(f"Restored backup: {os.path.basename(backup_path)}")
            self.show_info("Restored", f"Backup restored to:\n{save_path}")
        except Exception as e:
            self.show_error("Restore Failed", f"Could not restore backup:\n\n{e}")

    # Kept as the generic button/menu entry point.
    def patch_save_file(self):
        return self.patch_save_file_with_metadata()

    def best_save_initialdir(self):
        last_save = self.state.get("last_save_path", "")
        if last_save and os.path.isdir(os.path.dirname(last_save)):
            return os.path.dirname(last_save)

        latest = self.detect_latest_save_file()
        if latest:
            return os.path.dirname(latest)

        return os.path.expanduser("~")

    def steam_install_roots(self):
        return find_steam_install_roots(IS_WINDOWS, IS_LINUX, winreg)

    def windows_documents_roots(self):
        return find_windows_documents_roots()

    def steam_library_roots(self):
        return find_steam_library_roots(self.steam_install_roots())

    def gog_game_roots(self):
        return find_gog_game_roots(IS_WINDOWS, winreg, DD_GAME_DIR_NAMES)

    # Finds installed Darkest Dungeon game roots across Steam libraries
    # and common GOG install locations.
    def candidate_game_folders(self):
        return find_candidate_game_folders(
            self.steam_library_roots(),
            self.gog_game_roots(),
            DD_GAME_DIR_NAMES,
        )

    def detect_game_install_path(self):
        return first_valid_manual_path(
            self.state.get("manual_game_root", ""),
            self.candidate_game_folders(),
        )

    def candidate_local_mod_folders(self):
        return find_candidate_local_mod_folders(self.candidate_game_folders())

    def detect_local_mod_folder(self):
        return first_valid_manual_path(
            self.state.get("manual_local_mods_path", ""),
            self.candidate_local_mod_folders(),
        )

    def candidate_workshop_mod_folders(self):
        return find_candidate_workshop_mod_folders(self.steam_library_roots(), STEAM_APP_ID)

    def detect_workshop_mod_folder(self):
        return first_valid_manual_path(
            self.state.get("manual_workshop_mods_path", ""),
            self.candidate_workshop_mod_folders(),
        )

    def raw_detect_game_install_path(self):
        candidates = self.candidate_game_folders()
        if not candidates:
            return ""
        return candidates[0]

    def raw_detect_local_mod_folder(self):
        candidates = self.candidate_local_mod_folders()
        if not candidates:
            return ""
        return candidates[0]

    def raw_detect_workshop_mod_folder(self):
        candidates = self.candidate_workshop_mod_folders()
        if not candidates:
            return ""
        return candidates[0]

    def candidate_mod_folders(self):
        return find_candidate_mod_folders(
            self.mods_path.get().strip(),
            self.candidate_workshop_mod_folders(),
            self.candidate_local_mod_folders(),
        )

    def detect_best_mod_folder(self):
        return choose_best_mod_folder(self.mods_path.get().strip(), self.candidate_mod_folders())

    def companion_mod_folders(self, primary_path):
        return find_companion_mod_folders(
            primary_path,
            self.steam_library_roots(),
            STEAM_APP_ID,
            DD_GAME_NAME,
        )

    def detected_save_files_from_disk(self):
        return find_save_files_from_disk(
            self.steam_install_roots(),
            self.steam_library_roots(),
            self.windows_documents_roots(),
            IS_WINDOWS,
            IS_LINUX,
            STEAM_APP_ID,
        )

    def detect_save_files(self):
        return find_save_files(
            self.state.get("selected_profile_path", ""),
            self.state.get("last_save_path", ""),
            self.detected_save_files_from_disk(),
        )

    def profile_number_from_path(self, path):
        return detect_profile_number_from_path(path)

    def profile_sort_key(self, slot):
        return build_profile_sort_key(slot)

    def read_scalar_dson_fields(self, path, wanted_names=None, name_predicate=None):
        values = {}
        try:
            with open(path, "rb") as f:
                raw = f.read()

            header = dson_parse_header(raw)
            meta2_entries = dson_parse_meta2(raw, header)
            data = raw[header["data_offset"]:header["data_offset"] + header["data_length"]]
            wanted = set(wanted_names or [])

            for field_index, entry in enumerate(meta2_entries):
                name = dson_meta2_name(raw, header, entry)
                if wanted:
                    if name not in wanted:
                        continue
                elif name_predicate is not None:
                    if not name_predicate(name):
                        continue
                else:
                    continue

                if dson_object_index_from_info(entry["info"]) is not None:
                    continue

                next_offset = (
                    meta2_entries[field_index + 1]["offset"]
                    if field_index + 1 < len(meta2_entries)
                    else header["data_length"]
                )
                values[name] = dson_decode_scalar_field(data, entry, next_offset)
        except Exception:
            return {}

        return values

    def read_profile_week(self, profile_save_path):
        return load_profile_week(profile_save_path, self.read_scalar_dson_fields)

    def read_save_profile_metadata(self, path):
        return load_save_profile_metadata(
            path,
            self.profile_metadata_cache,
            self.read_scalar_dson_fields,
        )

    def profile_label(self, path):
        return build_profile_label(
            path,
            self.profile_metadata_cache,
            self.read_scalar_dson_fields,
        )

    def detect_profile_slots(self):
        return find_profile_slots(
            self.detect_save_files(),
            self.profile_metadata_cache,
            self.read_scalar_dson_fields,
        )

    def selected_profile_path(self):
        label = self.selected_profile.get()
        path = self.profile_label_to_path.get(label, "")
        if path and os.path.isfile(path):
            return path

        saved_path = self.state.get("selected_profile_path", "")
        if saved_path and os.path.isfile(saved_path):
            return saved_path

        return ""

    def select_profile(self, label):
        self.selected_profile.set(label)
        path = self.profile_label_to_path.get(label, "")
        if path:
            self.state["selected_profile_path"] = path
            self.state["last_save_path"] = path
            self.save_state()
            self.set_status_translation("status_selected_profile_save", path=path)

    def refresh_profile_menu(self):
        start = time.perf_counter()
        self.profile_slots = self.detect_profile_slots()
        self.profile_label_to_path = {}

        label_counts = {}
        for slot in self.profile_slots:
            label_counts[slot["label"]] = label_counts.get(slot["label"], 0) + 1

        for slot in self.profile_slots:
            label = slot["label"]
            if label_counts[label] > 1:
                label = f"{label} - {slot['path']}"
            slot["label"] = label
            self.profile_label_to_path[label] = slot["path"]

        labels = [slot["label"] for slot in self.profile_slots]
        if not labels:
            labels = [self.empty_profile_label()]

        current_path = self.state.get("selected_profile_path") or self.state.get("last_save_path", "")
        selected_label = labels[0]
        for slot in self.profile_slots:
            if current_path and os.path.normcase(os.path.abspath(slot["path"])) == os.path.normcase(os.path.abspath(current_path)):
                selected_label = slot["label"]
                break

        self.selected_profile.set(selected_label)

        if hasattr(self, "profile_menu"):
            menu = self.profile_menu["menu"]
            menu.delete(0, tk.END)
            for label in labels:
                menu.add_command(label=label, command=lambda value=label: self.select_profile(value))

        if self.profile_slots and selected_label in self.profile_label_to_path:
            self.select_profile(selected_label)
        self.record_startup_timing("refresh_profile_menu", time.perf_counter() - start)

    def detect_latest_save_file(self):
        return choose_latest_save_file(self.detect_save_files())

    def autodetect_summary(self):
        latest_save = self.detect_latest_save_file()
        profiles = self.detect_profile_slots()
        return build_autodetect_summary(
            self.detect_game_install_path(),
            self.detect_local_mod_folder(),
            self.detect_workshop_mod_folder(),
            self.detect_best_mod_folder(),
            latest_save,
            len(profiles),
        )

    def run_auto_detect(self, show_messages=True):
        found_anything = False
        summary = self.autodetect_summary()
        mod_folder = summary["best_mods"]
        if mod_folder:
            self.mods_path.set(mod_folder)
            self.save_state()
            self.load_mods()
            found_anything = True

        latest_save = summary["latest_save"]
        if latest_save:
            self.state["last_save_path"] = latest_save
            self.save_state()
            found_anything = True

        if hasattr(self, "profile_menu"):
            self.refresh_profile_menu()

        if show_messages:
            if found_anything:
                mod_text = mod_folder if mod_folder else "No mod folder found"
                save_text = latest_save if latest_save else self.tr("no_save_file_found")
                if mod_text == "No mod folder found":
                    mod_text = self.tr("no_mod_folder_found")
                self.show_info(
                    self.tr("auto_detect_complete"),
                    self.tr(
                        "auto_detect_complete_body",
                        game_root=summary["game_root"] or self.tr("not_found"),
                        local_mods=summary["local_mods"] or self.tr("not_found"),
                        workshop_mods=summary["workshop_mods"] or self.tr("not_found"),
                        mod_text=mod_text,
                        save_text=save_text,
                        profile_count=summary["profile_count"],
                    )
                )
            else:
                self.show_warning(
                    self.tr("nothing_found"),
                    self.tr("auto_detect_nothing_found_body")
                )

    # Startup path discovery always refreshes mods and profiles from disk
    # when Darkest Dungeon paths can be detected, so the app does not rely
    # on a manual Refresh Mods click just to see new Workshop or local mods.
    def run_first_start_setup(self, show_popup=True):
        setup_start = time.perf_counter()
        current_mods_path = self.mods_path.get().strip()
        if current_mods_path and os.path.isdir(current_mods_path):
            self.update_startup_splash(self.tr("startup_loading_mods_detected"))
            self.timed_startup_call("run_first_start_setup.load_mods", self.load_mods)
            self.update_startup_splash(self.tr("startup_scanning_profiles"))
            self.timed_startup_call("run_first_start_setup.refresh_profile_menu", self.refresh_profile_menu)
            latest_save = self.timed_startup_call("run_first_start_setup.detect_latest_save_file", self.detect_latest_save_file)
            if latest_save:
                self.state["last_save_path"] = latest_save
                self.save_state()
            self.set_status_translation(
                "status_loaded_mods_profiles",
                mods_path=current_mods_path,
                profile_count=len(self.profile_slots),
            )
            self.record_startup_timing("run_first_start_setup.total", time.perf_counter() - setup_start)
            return

        summary = self.autodetect_summary()
        mod_folder = summary["best_mods"]
        if mod_folder:
            self.mods_path.set(mod_folder)
            self.update_startup_splash(self.tr("startup_detecting_mods"))
            self.timed_startup_call("run_first_start_setup.load_mods", self.load_mods)
            self.update_startup_splash(self.tr("startup_scanning_profiles"))
            self.timed_startup_call("run_first_start_setup.refresh_profile_menu", self.refresh_profile_menu)
            self.set_status_translation(
                "status_detected_game",
                game_root=summary["game_root"] or "unknown",
                mods_path=mod_folder,
                profile_count=summary["profile_count"],
            )
            if show_popup and not self.state.get("first_run_summary_shown"):
                self.show_info(
                    self.tr("dd_detected"),
                    self.tr(
                        "dd_detected_body",
                        game_root=summary["game_root"] or self.tr("not_found"),
                        local_mods=summary["local_mods"] or self.tr("not_found"),
                        workshop_mods=summary["workshop_mods"] or self.tr("not_found"),
                        mods_path=mod_folder,
                        latest_save=summary["latest_save"] or self.tr("not_found"),
                        profile_count=summary["profile_count"],
                    )
                )
                self.state["first_run_summary_shown"] = True
                self.save_state()
            self.record_startup_timing("run_first_start_setup.total", time.perf_counter() - setup_start)
            return

        self.update_startup_splash(self.tr("startup_scanning_profiles"))
        self.timed_startup_call("run_first_start_setup.refresh_profile_menu", self.refresh_profile_menu)
        self.set_status_translation("status_no_dd_detected")
        self.record_startup_timing("run_first_start_setup.total", time.perf_counter() - setup_start)

    def setup_diagnostics_lines(self):
        summary = self.autodetect_summary()
        mods_path = self.mods_path.get().strip()
        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})
        enabled_count = sum(1 for mod in order if enabled_map.get(mod, True))
        disabled_count = len(order) - enabled_count
        metadata = self.state.get("metadata", {})
        metadata_count = sum(1 for mod in order if metadata.get(mod))
        workshop_count = sum(1 for mod in order if self.mod_is_workshop(mod))
        local_count = len(order) - workshop_count
        latest_save = summary["latest_save"]

        state_ok = os.path.isdir(APP_DIR)
        mods_ok = os.path.isdir(mods_path)
        latest_save_ok = bool(latest_save)
        save_has_mod_block = "Not checked"
        selected_profile_path = self.selected_profile_path()

        if latest_save_ok:
            try:
                with open(latest_save, "rb") as f:
                    dson_find_top_level_applied_block(f.read())
                save_has_mod_block = "Yes"
            except Exception:
                save_has_mod_block = "No"

        return [
            f"DD Manager version: {APP_VERSION}",
            f"Platform: {sys.platform}",
            f"Captured: {datetime.now().isoformat(timespec='seconds')}",
            f"Language: {self.state.get('language', 'en')}",
            f"View mode: {self.current_view_mode()}",
            f"Filter: {self.current_filter_category()}",
            f"App data folder writable: {'Yes' if state_ok else 'No'}",
            f"Game install: {summary['game_root'] or '(not found)'}",
            f"Local mods folder: {summary['local_mods'] or '(not found)'}",
            f"Workshop mods folder: {summary['workshop_mods'] or '(not found)'}",
            f"Mods folder valid: {'Yes' if mods_ok else 'No'}",
            f"Mods folder: {mods_path or '(not set)'}",
            f"Mods loaded: {len(order)}",
            f"Enabled mods: {enabled_count}",
            f"Disabled mods: {disabled_count}",
            f"Workshop-backed mods: {workshop_count}",
            f"Local/manual mods: {local_count}",
            f"Metadata entries: {metadata_count}",
            f"Visible reserve rows: {len(self.disabled_visible_mods)}",
            f"Visible load-order rows: {len(self.enabled_visible_mods)}",
            f"Selected profile: {self.selected_profile.get()}",
            f"Selected profile path: {selected_profile_path or '(not selected)'}",
            f"Latest detected save: {latest_save or '(not found)'}",
            f"Detected profiles: {summary['profile_count']}",
            f"Save has applied_ugcs_1_0: {save_has_mod_block}",
            f"Last backup: {self.state.get('last_backup_path') or '(none)'}",
        ]

    def build_debug_info_text(self):
        return "\n".join(self.setup_diagnostics_lines())

    def show_setup_diagnostics(self):
        self.show_info("Setup Check", self.build_debug_info_text())

    def copy_debug_info(self):
        text = self.build_debug_info_text()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
        except Exception as e:
            self.show_error("Clipboard Error", f"Failed to copy debug info.\n\n{e}")
            return

        self.show_info(
            self.tr("debug_info_copied_title"),
            self.tr("debug_info_copied_body"),
        )

    # Reads the active applied_ugcs_1_0 names from a save so the app
    # can match that save's live mod list back to local folders.
    def save_applied_mod_names(self, save_path):
        with open(save_path, "rb") as f:
            raw = f.read()
        _, _, entries = dson_parse_applied_ugcs_with_layout(raw)

        names = []
        for entry in entries:
            name_field = dson_get_field(entry, "name")
            if name_field and name_field.get("value"):
                names.append(name_field["value"])
        return names

    # Chooses the best available save for disable warnings, preferring
    # the selected profile, then the last used save, then auto-detect.
    def best_save_for_mod_warning(self):
        candidates = [
            self.selected_profile_path(),
            self.state.get("last_save_path", ""),
            self.detect_latest_save_file(),
        ]
        seen = set()
        for path in candidates:
            if not path or not os.path.isfile(path):
                continue
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            return path
        return ""

    def mod_present_in_save_names(self, mod, save_names):
        raw_names = {str(name) for name in save_names if name}
        normalized_names = {
            normalize_mod_identity(name)
            for name in save_names
            if normalize_mod_identity(name)
        }

        for identity in self.mod_identity_values(mod):
            if identity in raw_names:
                return True
            normalized = normalize_mod_identity(identity)
            if normalized and normalized in normalized_names:
                return True

        return False

    # Warns before disabling mods that the chosen save still lists as
    # active in applied_ugcs_1_0, since that save likely depends on them.
    def confirm_disable_active_mods(self, mods):
        enabled_mods = [mod for mod in mods if self.state["enabled"].get(mod, True)]
        if not enabled_mods:
            return True

        save_path = self.best_save_for_mod_warning()
        if not save_path:
            return True

        try:
            active_names = self.save_applied_mod_names(save_path)
        except Exception:
            return True

        risky_mods = [
            mod for mod in enabled_mods
            if self.mod_present_in_save_names(mod, active_names)
        ]
        if not risky_mods:
            return True

        preview = "\n".join(self.display_name(mod) for mod in risky_mods[:8])
        extra = ""
        if len(risky_mods) > 8:
            extra = f"\n...and {len(risky_mods) - 8} more"

        return self.ask_yes_no(
            "Disable Active Save Mod?",
            "The selected save still lists these mods in applied_ugcs_1_0:\n\n"
            f"{preview}{extra}\n\n"
            f"Save checked:\n{save_path}\n\n"
            "That usually means the save is actively using them, and disabling one may break the save.\n\n"
            "Disable anyway?"
        )

    def mod_identity_values(self, mod):
        values = []
        meta = self.state.get("metadata", {}).get(mod, {})
        for key in ("published_file_id", "save_name", "title"):
            value = meta.get(key)
            if value:
                values.append(str(value))

        values.append(self.project_identity_name(mod))
        values.append(self.save_name(mod))
        values.append(mod)

        live_meta = self.read_mod_metadata(mod)
        for key in ("published_file_id", "save_name", "title"):
            value = live_meta.get(key)
            if value:
                values.append(str(value))

        normalized = []
        seen = set()
        for value in values:
            if value and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized

    def build_mod_identity_lookup(self, order):
        identity_to_mod = {}
        normalized_to_mod = {}

        for mod in order:
            for identity in self.mod_identity_values(mod):
                identity_to_mod.setdefault(identity, mod)

                normalized = normalize_mod_identity(identity)
                if normalized:
                    normalized_to_mod.setdefault(normalized, mod)

        return identity_to_mod, normalized_to_mod

    def category_memory_keys(self, mod):
        keys = []
        for identity in self.mod_identity_values(mod):
            keys.append(identity)
            normalized = normalize_mod_identity(identity)
            if normalized:
                keys.append(f"norm:{normalized}")

        unique = []
        seen = set()
        for key in keys:
            if key and key not in seen:
                unique.append(key)
                seen.add(key)
        return unique

    def remember_mod_category(self, mod, category):
        if not category or category in ("All", "Unassigned"):
            return

        memory = self.state.setdefault("category_memory", {})
        for key in self.category_memory_keys(mod):
            memory[key] = category

    def recalled_mod_category(self, mod):
        memory = self.state.get("category_memory", {})
        for key in self.category_memory_keys(mod):
            category = memory.get(key)
            if category:
                return category
        return None

    def rebuild_category_memory_from_current(self):
        for mod, category in list(self.state.get("categories", {}).items()):
            if category and category not in ("All", "Unassigned"):
                self.remember_mod_category(mod, category)

    def load_selected_profile_mods(self):
        save_path = self.selected_profile_path()
        if not save_path:
            self.show_warning(
                "No Profile Selected",
                "Choose a profile from the profile menu first."
            )
            return

        if not self.state.get("order"):
            if os.path.isdir(self.mods_path.get().strip()):
                self.load_mods()
            else:
                self.show_warning(
                    "No Mods Loaded",
                    "Set your mods folder and refresh mods before importing a profile's mod list."
                )
                return

        try:
            save_mod_names = self.save_applied_mod_names(save_path)
        except Exception as e:
            self.show_error("Could Not Read Profile", f"Could not read active mods from this save:\n\n{e}")
            return

        order = self.state.get("order", [])
        self.refresh_missing_mod_metadata(order)
        identity_to_mod, normalized_to_mod = self.build_mod_identity_lookup(order)

        matched_mods = []
        missing_names = []
        seen_mods = set()
        for save_name in save_mod_names:
            mod = identity_to_mod.get(save_name)
            if mod is None:
                mod = normalized_to_mod.get(normalize_mod_identity(save_name))
            if mod and mod not in seen_mods:
                matched_mods.append(mod)
                seen_mods.add(mod)
            elif not mod:
                missing_names.append(save_name)

        remaining_mods = [mod for mod in order if mod not in seen_mods]

        self.state["order"] = matched_mods + remaining_mods
        self.state["enabled"] = {
            mod: mod in seen_mods
            for mod in self.state["order"]
        }
        self.state["selected_profile_path"] = save_path
        self.state["last_save_path"] = save_path
        self.save_state()
        self.refresh()

        status = f"Loaded profile mods: {len(matched_mods)} active"
        if missing_names:
            status += f" | {len(missing_names)} missing"
        self.set_status_text(status)

        if missing_names:
            preview = "\n".join(missing_names[:10])
            extra = ""
            if len(missing_names) > 10:
                extra = f"\n...and {len(missing_names) - 10} more"
            self.show_warning(
                "Profile Loaded With Missing Mods",
                "The profile was loaded, but some saved active mods were not found in the current mods folder.\n\n"
                f"{preview}{extra}"
            )
        else:
            self.show_info(
                "Profile Mods Loaded",
                f"Loaded {len(matched_mods)} active mods from:\n{save_path}"
            )

    # -----------------------------------------------------
    # MOD METADATA
    # -----------------------------------------------------

    def workshop_manifest_paths(self):
        paths = []
        for library in self.steam_library_roots():
            candidate = os.path.join(
                library,
                "steamapps",
                "workshop",
                f"appworkshop_{STEAM_APP_ID}.acf",
            )
            if os.path.isfile(candidate):
                paths.append(candidate)

        seen = set()
        unique = []
        for path in paths:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                unique.append(path)
                seen.add(norm)
        return unique

    def workshop_update_times(self):
        if self.workshop_update_cache is not None:
            return self.workshop_update_cache

        updates = {}
        pattern = re.compile(
            r'"(?P<id>\d+)"\s*\{[^{}]*?"timeupdated"\s*"(?P<ts>\d+)"',
            re.S,
        )
        for manifest_path in self.workshop_manifest_paths():
            try:
                with open(manifest_path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except Exception:
                continue

            for match in pattern.finditer(raw):
                item_id = match.group("id")
                if item_id not in updates:
                    updates[item_id] = match.group("ts")

        self.workshop_update_cache = updates
        return updates

    def format_month_year(self, timestamp):
        try:
            dt = datetime.fromtimestamp(float(timestamp))
        except Exception:
            return ""
        return dt.strftime("%m/%y")

    def safe_getmtime(self, path):
        try:
            if path and os.path.exists(path):
                return os.path.getmtime(path)
        except Exception:
            pass
        return None

    def localization_signature_for_mod(self, mod_folder):
        localization_path = os.path.join(self.mod_folder_path(mod_folder), "localization")
        if not os.path.isdir(localization_path):
            return ""

        count = 0
        newest = 0.0
        try:
            filenames = os.listdir(localization_path)
        except Exception:
            return ""

        for filename in filenames:
            if not filename.lower().endswith(".xml"):
                continue
            count += 1
            file_path = os.path.join(localization_path, filename)
            mtime = self.safe_getmtime(file_path)
            if mtime and mtime > newest:
                newest = mtime

        if count == 0:
            return ""
        return f"{count}:{int(newest)}"

    def metadata_signature_for_mod(self, mod_folder, workshop_id=""):
        mod_path = self.mod_folder_path(mod_folder)
        project_path = os.path.join(mod_path, "project.xml")
        workshop_timeupdated = ""
        workshop_id = str(workshop_id or "").strip()
        if workshop_id:
            workshop_timeupdated = str(self.workshop_update_times().get(workshop_id, "") or "")

        return {
            "metadata_path": os.path.normcase(os.path.abspath(mod_path)) if mod_path else "",
            "project_mtime": self.safe_getmtime(project_path),
            "localization_signature": self.localization_signature_for_mod(mod_folder),
            "workshop_timeupdated": workshop_timeupdated,
        }

    def mod_metadata_is_fresh(self, mod_folder, metadata):
        if not mod_metadata_is_complete(metadata):
            return False

        workshop_id = metadata.get("published_file_id", "")
        current_signature = self.metadata_signature_for_mod(mod_folder, workshop_id)
        return all(metadata.get(key) == value for key, value in current_signature.items())

    def version_label_from_project(self, root):
        if root is None:
            return ""

        major = xml_text_from_child(root, "VersionMajor")
        minor = xml_text_from_child(root, "VersionMinor")
        if not major and not minor:
            return ""

        if (major or "").strip().isdigit() and (minor or "").strip().isdigit():
            if int(major) == 0 and int(minor) == 0:
                return ""
            return f"{int(major)}.{int(minor)}"

        parts = [part for part in (major, minor) if str(part).strip()]
        return ".".join(parts)

    def is_black_reliquary_tagged(self, tags):
        for tag in tags:
            normalized = re.sub(r"[_\\/\-:;,.()[\]{}'\"!+]+", " ", html.unescape(str(tag)).lower())
            normalized = re.sub(r"\s+", " ", normalized).strip()
            compact = normalized.replace(" ", "")
            if normalized == "black reliquary" or compact == "blackreliquary":
                return True
        return False

    def newest_mod_file_timestamp(self, mod_folder):
        mod_path = self.mod_folder_path(mod_folder)
        newest = None

        for root, _, filenames in os.walk(mod_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                try:
                    mtime = os.path.getmtime(file_path)
                except Exception:
                    continue
                if newest is None or mtime > newest:
                    newest = mtime

        return newest

    def updated_label_for_mod(self, mod_folder, workshop_id=""):
        workshop_id = str(workshop_id or "").strip()
        if workshop_id:
            workshop_updates = self.workshop_update_times()
            workshop_timestamp = workshop_updates.get(workshop_id)
            if workshop_timestamp:
                label = self.format_month_year(workshop_timestamp)
                if label:
                    return label

        newest_file_timestamp = self.newest_mod_file_timestamp(mod_folder)
        if newest_file_timestamp is not None:
            label = self.format_month_year(newest_file_timestamp)
            if label:
                return label

        project_path = os.path.join(self.mod_folder_path(mod_folder), "project.xml")
        try:
            if os.path.exists(project_path):
                label = self.format_month_year(os.path.getmtime(project_path))
                if label:
                    return label
        except Exception:
            pass

        return ""

    # Reads project.xml when available so save patching and UI labels can
    # distinguish Workshop identity from local-folder identity.
    def read_mod_metadata(self, mod_folder):
        project_path = os.path.join(self.mod_folder_path(mod_folder), "project.xml")
        is_workshop = self.mod_is_workshop(mod_folder)
        workshop_id = self.workshop_id_for_mod(mod_folder) if is_workshop else ""
        fallback_title = self.save_name(mod_folder)
        code_title = self.internal_code_title_for_mod(mod_folder)
        signature = self.metadata_signature_for_mod(mod_folder, workshop_id)

        metadata = {
            "title": fallback_title,
            "published_file_id": workshop_id,
            "save_name": workshop_id or fallback_title,
            "save_source": "Steam" if is_workshop and workshop_id else "mod_local_source",
            "version_label": "",
            "updated_label": "",
            "black_reliquary": False,
            "metadata_path": signature["metadata_path"],
            "project_mtime": signature["project_mtime"],
            "localization_signature": signature["localization_signature"],
            "workshop_timeupdated": signature["workshop_timeupdated"],
        }

        root = parse_xml_file_forgiving(project_path) if os.path.exists(project_path) else None
        metadata["black_reliquary"] = self.is_black_reliquary_tagged(self.project_tag_values(mod_folder))
        metadata["version_label"] = self.version_label_from_project(root)
        if root is None:
            title = self.localization_title_for_mod(mod_folder)
            if title and text_has_latin(title) and not is_bad_display_title(title):
                metadata["title"] = title
            elif looks_like_numeric_id(fallback_title) and code_title:
                metadata["title"] = code_title
            metadata["updated_label"] = self.updated_label_for_mod(mod_folder, metadata["published_file_id"])
            return metadata

        title = xml_text_from_child(root, "Title")
        published_id = xml_text_from_child(root, "PublishedFileId")

        if (
            title
            and not is_bad_display_title(title)
            and (text_has_latin(title) or not text_has_latin(fallback_title) or looks_like_numeric_id(fallback_title))
        ):
            metadata["title"] = title

        if is_workshop and published_id:
            metadata["published_file_id"] = published_id

        if is_workshop and metadata["published_file_id"]:
            metadata["save_name"] = metadata["published_file_id"]
            metadata["save_source"] = "Steam"
        else:
            metadata["save_name"] = metadata["title"]
            metadata["save_source"] = "mod_local_source"

        if metadata["title"] == fallback_title or not text_has_latin(metadata["title"]):
            title = self.localization_title_for_mod(mod_folder)
            if title and text_has_latin(title) and not is_bad_display_title(title):
                metadata["title"] = title
            elif looks_like_numeric_id(fallback_title) and code_title and not text_has_latin(metadata["title"]):
                metadata["title"] = code_title

        metadata["updated_label"] = self.updated_label_for_mod(mod_folder, metadata["published_file_id"])

        return metadata

    def localization_title_for_mod(self, mod_folder):
        localization_path = os.path.join(self.mod_folder_path(mod_folder), "localization")
        if not os.path.isdir(localization_path):
            return ""

        candidates = []
        try:
            filenames = os.listdir(localization_path)
        except Exception:
            return ""

        for filename in filenames:
            if not filename.lower().endswith(".xml"):
                continue

            root = parse_xml_file_forgiving(os.path.join(localization_path, filename))
            if root is None:
                continue

            for elem in root.iter():
                if elem.tag.split("}", 1)[-1].lower() != "entry":
                    continue

                entry_id = elem.attrib.get("id", "").lower()
                text = "".join(elem.itertext()).strip()
                text = re.sub(r"\s+", " ", html.unescape(text))
                if not text or len(text) > 80 or is_bad_display_title(text):
                    continue

                if entry_id.startswith("hero_class_name_"):
                    priority = 0
                elif "class_name" in entry_id:
                    priority = 1
                elif "mod_name" in entry_id or "title" in entry_id:
                    priority = 2
                elif entry_id.endswith("_name") or "_name_" in entry_id:
                    priority = 3
                else:
                    continue

                candidates.append((priority, len(text), text))

        if not candidates:
            return ""

        candidates.sort()
        return candidates[0][2]

    def internal_code_title_for_mod(self, mod_folder):
        mod_path = self.mod_folder_path(mod_folder)
        for subfolder in ("heroes", "monsters", "dungeons", "raid"):
            root = os.path.join(mod_path, subfolder)
            if not os.path.isdir(root):
                continue

            try:
                names = sorted(
                    name for name in os.listdir(root)
                    if os.path.isdir(os.path.join(root, name))
                )
            except Exception:
                continue

            for name in names:
                cleaned = re.sub(r"[_\-]+", " ", name).strip()
                cleaned = re.sub(r"\s+", " ", cleaned)
                if cleaned and text_has_latin(cleaned):
                    words = []
                    for part in cleaned.split():
                        if part.islower() and len(part) <= 3:
                            words.append(part.upper())
                        else:
                            words.append(part[:1].upper() + part[1:])
                    return " ".join(words)

        return ""

    def refresh_missing_mod_metadata(self, mods=None):
        if mods is None:
            mods = self.state.get("order", [])

        metadata = self.state.setdefault("metadata", {})
        changed = False

        for mod in mods:
            current = metadata.get(mod, {})
            if not self.mod_metadata_is_fresh(mod, current):
                metadata[mod] = self.read_mod_metadata(mod)
                changed = True

        return changed



    # -----------------------------------------------------
    # APP STARTUP / SESSION STATE
    # -----------------------------------------------------

    # Creates Tk variables, the in-memory state dictionary, icon caches,
    # and drag/drop bookkeeping before loading saved state and drawing
    # the main interface.
    def __init__(self, root):
        self.root = root
        detected_language = detect_default_language(IS_WINDOWS, ctypes)
        self.root.title(translate_text(detected_language, "app_title"))
        self.root.geometry("1400x780")

        ensure_app_storage()

        self.mods_path = tk.StringVar()
        self.language = tk.StringVar(value=LANGUAGE_CODE_TO_LABEL.get(detected_language, LANGUAGE_CODE_TO_LABEL["en"]))
        self.selected_profile = tk.StringVar(value=translate_text(detected_language, "profile_none"))
        self.filter_category = tk.StringVar(value=translate_text(detected_language, CATEGORY_TRANSLATION_KEYS["All"]))
        self.search_text = tk.StringVar(value="")
        self.view_mode = tk.StringVar(value=translate_text(detected_language, VIEW_MODE_TRANSLATION_KEYS["Comfortable"]))
        self.state = build_default_state(detected_language, DEFAULT_CATEGORIES)

        self.right_index = None
        self.drag_index = None
        self.enabled_visible_mods = []
        self.disabled_visible_mods = []
        self.drag_source = None
        self.drag_mod = None
        self.drag_start_x = None
        self.drag_start_y = None
        self.drag_pressed_selected_index = None
        self.drag_pressed_selected_side = None
        self.disabled_selection_anchor_index = None
        self.enabled_selection_anchor_index = None
        self.drag_label = None
        self.drag_indicator = None
        self.profile_slots = []
        self.profile_label_to_path = {}
        self.profile_metadata_cache = {}
        self.startup_splash = None
        self.search_refresh_job = None
        self.view_mode_job = None
        self.new_mod_highlight_job = None
        self.icon_redraw_job = None
        self.icon_load_job = None
        self.icon_load_queue = []
        self.icon_load_pending = set()
        self.preview_icon_path_cache = {}
        self.preview_icon_image_cache = {}
        self.preview_icon_refs = {"disabled": [], "enabled": []}
        self.status_translation = None
        self.pending_duplicate_groups = []
        self.workshop_update_cache = None
        self.context_menu_workshop_index = None
        self.deferred_save_job = None
        self.startup_profile = []
        self.recent_new_mods = set()

        self.enabled_visible_mods = []
        self.disabled_visible_mods = []

        self.load_state()

        if self.state.get("mods_path"):
            self.mods_path.set(self.state["mods_path"])
        if self.state.get("view_mode") in VIEW_MODES:
            self.view_mode.set(self.view_mode_label(self.state["view_mode"]))
        self.language.set(LANGUAGE_CODE_TO_LABEL.get(self.state.get("language", "en"), LANGUAGE_CODE_TO_LABEL["en"]))
        self.selected_profile.set(self.empty_profile_label())
        self.root.title(self.tr("app_title"))

        self.build_ui()

    def update_startup_splash(self, message):
        update_startup_splash(self.startup_splash, message)

    def current_language(self):
        return self.state.get("language", "en")

    def tr(self, key, **kwargs):
        return translate_text(self.current_language(), key, **kwargs)

    def empty_profile_label(self):
        return self.tr("profile_none")

    def category_label(self, category):
        key = CATEGORY_TRANSLATION_KEYS.get(category)
        if key:
            return self.tr(key)
        return category

    def category_from_label(self, label):
        for category, key in CATEGORY_TRANSLATION_KEYS.items():
            if label == category:
                return category
            for language_code in TRANSLATIONS.keys():
                if label == translate_text(language_code, key):
                    return category
        return label

    def current_filter_category(self):
        return self.category_from_label(self.filter_category.get().strip())

    def view_mode_label(self, mode):
        key = VIEW_MODE_TRANSLATION_KEYS.get(mode)
        if key:
            return self.tr(key)
        return mode

    def view_mode_from_label(self, label):
        for mode, key in VIEW_MODE_TRANSLATION_KEYS.items():
            if label == mode:
                return mode
            for language_code in TRANSLATIONS.keys():
                if label == translate_text(language_code, key):
                    return mode
        return label

    def current_view_mode(self):
        mode = self.view_mode_from_label(self.view_mode.get().strip())
        return mode if mode in VIEW_MODES else "Comfortable"

    def set_language(self, language_label):
        language_code = LANGUAGE_LABEL_TO_CODE.get(language_label, "en")
        self.language.set(LANGUAGE_CODE_TO_LABEL.get(language_code, LANGUAGE_CODE_TO_LABEL["en"]))
        if self.state.get("language") == language_code:
            return
        self.state["language"] = language_code
        self.save_state()
        self.refresh_localized_texts()

    def set_status_text(self, text):
        self.status_translation = None
        if hasattr(self, "status_label"):
            self.status_label.config(text=text)

    def set_status_translation(self, key, **kwargs):
        self.status_translation = (key, dict(kwargs))
        if hasattr(self, "status_label"):
            self.status_label.config(text=self.tr(key, **kwargs))

    def show_info(self, title, message, **kwargs):
        return messagebox.showinfo(title, message, **kwargs)

    def show_warning(self, title, message, **kwargs):
        return messagebox.showwarning(title, message, **kwargs)

    def show_error(self, title, message, **kwargs):
        return messagebox.showerror(title, message, **kwargs)

    def ask_yes_no(self, title, message, **kwargs):
        return messagebox.askyesno(title, message, **kwargs)

    def rebuild_tools_menu(self):
        if not hasattr(self, "tools_menu"):
            return
        self.tools_menu.menu.delete(0, tk.END)
        if SHOW_START_NEW_CAMPAIGN_TOOL:
            self.tools_menu.menu.add_command(label=self.tr("tool_start_new_campaign"), command=self.start_new_campaign)
        self.tools_menu.menu.add_command(label=self.tr("tool_patch_save"), command=self.patch_save_file)
        self.tools_menu.menu.add_command(label=self.tr("tool_patch_autodetected_legacy"), command=self.patch_latest_save_file)
        self.tools_menu.menu.add_command(label=self.tr("tool_generate_save_code"), command=self.generate_save_code)
        self.tools_menu.menu.add_separator()
        self.tools_menu.menu.add_command(label=self.tr("tool_apply_order"), command=self.apply_order)
        self.tools_menu.menu.add_command(label=self.tr("tool_restore_backup"), command=self.restore_last_backup)
        self.tools_menu.menu.add_separator()
        self.tools_menu.menu.add_command(label=self.tr("tool_check_setup"), command=self.show_setup_diagnostics)
        self.tools_menu.menu.add_command(label=self.tr("tool_copy_debug_info"), command=self.copy_debug_info)

    def refresh_localized_texts(self):
        self.root.title(self.tr("app_title"))
        for attr_name, key in (
            ("title_label", "app_title"),
            ("launch_button", "launch_game"),
            ("open_local_mods_button", "open_local_mods"),
            ("file_paths_button", "file_paths"),
            ("auto_detect_button", "auto_detect"),
            ("language_label", "language"),
            ("profile_heading_label", "profile"),
            ("refresh_profile_button", "refresh"),
            ("load_profile_button", "load_profile_mods"),
            ("patch_profile_button", "patch_selected_profile"),
            ("refresh_mods_button", "refresh_mods"),
            ("filter_heading_label", "filter"),
            ("edit_categories_button", "edit_categories"),
            ("search_heading_label", "search"),
            ("view_heading_label", "view"),
            ("list_actions_heading_label", "list_actions"),
            ("auto_sort_button", "auto_sort"),
            ("auto_categorize_button", "auto_categorize"),
            ("nickname_button", "nickname_mod"),
            ("reserve_heading_label", "reserve"),
            ("enable_button", "enable_selected"),
            ("disable_button", "disable_selected"),
            ("load_order_heading_label", "load_order"),
        ):
            widget = getattr(self, attr_name, None)
            if widget is not None:
                widget.config(text=self.tr(key))

        if hasattr(self, "subtitle_label"):
            self.subtitle_label.config(text=subtitle_with_version(self.tr("app_subtitle")))

        if hasattr(self, "tools_menu"):
            self.tools_menu.config(text=self.tr("tools"))
            self.rebuild_tools_menu()

        if hasattr(self, "filter_menu"):
            self.filter_category.set(self.category_label(self.current_filter_category()))
            self.rebuild_category_menus()

        if hasattr(self, "view_mode_menu"):
            self.view_mode.set(self.view_mode_label(self.current_view_mode()))
            self.rebuild_view_mode_menu()

        if hasattr(self, "status_label"):
            if self.status_translation is not None:
                key, kwargs = self.status_translation
                self.set_status_translation(key, **kwargs)
            else:
                current_text = self.status_label.cget("text")
                default_texts = {
                    translate_text(language_code, "status_choose_mods")
                    for language_code in TRANSLATIONS.keys()
                }
                if current_text in default_texts:
                    self.set_status_translation("status_choose_mods")

        if hasattr(self, "profile_menu") and not self.profile_slots:
            self.selected_profile.set(self.empty_profile_label())
            menu = self.profile_menu["menu"]
            menu.delete(0, tk.END)
            label = self.empty_profile_label()
            menu.add_command(label=label, command=lambda value=label: self.select_profile(value))

        category_editor_refresh = getattr(self, "category_editor_refresh", None)
        if category_editor_refresh is not None:
            category_editor_refresh()

        if hasattr(self, "disabled_listbox") and hasattr(self, "enabled_listbox"):
            self.refresh()

    # -----------------------------------------------------
    # STARTUP PROFILING (DEBUG TOGGLE)
    # -----------------------------------------------------
    # Handy when startup gets weird again.

    def record_startup_timing(self, label, seconds):
        if not STARTUP_PROFILING_ENABLED:
            return
        self.startup_profile.append((str(label), float(seconds)))

    def timed_startup_call(self, label, func, *args, **kwargs):
        if not STARTUP_PROFILING_ENABLED:
            return func(*args, **kwargs)
        start = time.perf_counter()
        result = func(*args, **kwargs)
        self.record_startup_timing(label, time.perf_counter() - start)
        return result

    def write_startup_profile(self):
        if not STARTUP_PROFILING_ENABLED:
            return
        if not self.startup_profile:
            return

        total = sum(seconds for _, seconds in self.startup_profile)
        lines = [
            f"Startup profile - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total tracked time: {format_duration_ms(total)}",
            "",
        ]
        for label, seconds in self.startup_profile:
            lines.append(f"{label}: {format_duration_ms(seconds)}")
        lines.append("")

        try:
            with open(STARTUP_PROFILE_LOG, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
                f.write("\n")
        except Exception:
            pass

    # -----------------------------------------------------
    # DISPLAY / IDENTITY HELPERS
    # -----------------------------------------------------

    def sort_name(self, mod):
        name = self.sort_display_name(mod).strip()
        if name.lower().startswith("the "):
            name = name[4:]
        return name.lower()

    def current_metadata_for_mod(self, mod, force_title_refresh=False):
        metadata = self.state.setdefault("metadata", {}).get(mod, {})
        needs_refresh = not self.mod_metadata_is_fresh(mod, metadata)

        if not needs_refresh and force_title_refresh:
            title = str(metadata.get("title", "")).strip()
            project_path = os.path.join(self.mod_folder_path(mod), "project.xml")
            if title == mod and mod.isdigit() and os.path.isfile(project_path):
                needs_refresh = True

        if needs_refresh:
            metadata = self.read_mod_metadata(mod)
            self.state["metadata"][mod] = metadata

        return metadata

    # Uses the same visible naming logic for sorting so Workshop-only
    # numeric folder names do not break alphabetical ordering.
    def sort_display_name(self, mod):
        nickname = self.nickname_for_mod(mod)
        if nickname:
            return html.unescape(nickname)

        meta = self.current_metadata_for_mod(mod, force_title_refresh=True)
        title = str(meta.get("title", "")).strip()
        if title and title != mod:
            return html.unescape(title)

        return self.save_name(mod)

    def save_name(self, mod):
        parts = mod.split("_")
        while parts and parts[0].isdigit():
            parts.pop(0)
        return "_".join(parts) if parts else mod

    # Resolves a Steam Workshop ID only when the backing folder actually
    # lives under Steam's workshop content path.
    def workshop_id_for_mod(self, mod):
        mod_path = self.mod_folder_path(mod)
        if not is_workshop_content_path(mod_path, STEAM_APP_ID):
            return ""

        if mod.isdigit():
            return mod

        parts = mod.split("_")
        for part in parts[:2]:
            if part.isdigit() and len(part) >= 7:
                return part

        path_id = os.path.basename(self.mod_folder_path(mod))
        if path_id.isdigit():
            return path_id

        return ""

    # Convenience wrapper used by metadata and UI logic that need to know
    # whether a mod is Workshop-backed or a local manual copy.
    def mod_is_workshop(self, mod):
        return is_workshop_content_path(self.mod_folder_path(mod), STEAM_APP_ID)

    def apply_name_prefixes(self, mod, text):
        value = html.unescape(str(text or "")).strip()
        if not value:
            return value

        meta = self.current_metadata_for_mod(mod)
        if meta.get("black_reliquary") and not value.startswith("[BR] "):
            value = f"[BR] {value}"
        return value

    def display_name(self, mod, force_title_refresh=False):
        nickname = self.nickname_for_mod(mod)
        if nickname:
            return self.apply_name_prefixes(mod, nickname)

        meta = self.current_metadata_for_mod(mod, force_title_refresh=force_title_refresh)
        title = meta.get("title", "")
        published_id = meta.get("published_file_id", "")

        if title and title != mod:
            if mod.isdigit():
                return self.apply_name_prefixes(mod, f"{title} [{mod}]")
            if published_id and published_id not in mod:
                return self.apply_name_prefixes(mod, f"{title} [{published_id}]")
            return self.apply_name_prefixes(mod, title)

        if "_" in mod[:5]:
            prefix, remainder = mod.split("_", 1)
            if prefix.isdigit():
                return self.apply_name_prefixes(mod, remainder)
        return self.apply_name_prefixes(mod, mod)

    def display_suffix(self, mod):
        meta = self.current_metadata_for_mod(mod)
        version_label = str(meta.get("version_label", "")).strip()
        updated_label = str(meta.get("updated_label", "")).strip()
        if version_label:
            return version_label
        return updated_label

    def display_name_with_suffix(self, mod, force_title_refresh=False):
        base = self.display_name(mod, force_title_refresh=force_title_refresh)
        suffix = self.display_suffix(mod)
        if suffix:
            return f"{base} ({suffix})"
        return base

    def nickname_for_mod(self, mod):
        nicknames = self.state.get("nicknames", {})
        value = nicknames.get(mod, "")
        if not value:
            return ""
        return " ".join(str(value).split())

    def schedule_search_refresh(self, event=None):
        if self.search_refresh_job is not None:
            try:
                self.root.after_cancel(self.search_refresh_job)
            except Exception:
                pass
        self.search_refresh_job = self.root.after(120, self.run_scheduled_search_refresh)

    def run_scheduled_search_refresh(self):
        self.search_refresh_job = None
        self.refresh()

    def truncate_name(self, text, max_length=42):
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def project_identity_name(self, mod_folder):
        project_path = os.path.join(self.mod_folder_path(mod_folder), "project.xml")

        fallback = self.save_name(mod_folder)

        if not os.path.exists(project_path):
            return self.workshop_id_for_mod(mod_folder) or fallback

        root = parse_xml_file_forgiving(project_path)
        if root is None:
            return self.workshop_id_for_mod(mod_folder) or fallback

        published_id = xml_text_from_child(root, "PublishedFileId")
        if published_id:
            return published_id

        title = xml_text_from_child(root, "Title")
        if title:
            return title

        return self.workshop_id_for_mod(mod_folder) or fallback

    # Returns the name/source pair we actually want written into the save.
    def save_identity_for_mod(self, mod_folder):
        metadata = self.current_metadata_for_mod(mod_folder, force_title_refresh=True)
        name = str(metadata.get("save_name") or self.save_name(mod_folder))
        source = str(metadata.get("save_source") or ("Steam" if name.isdigit() else "mod_local_source"))
        return name, source

    def duplicate_detection_keys(self, mod):
        keys = []
        meta = self.state.get("metadata", {}).get(mod, {})
        for value in (
            meta.get("published_file_id"),
            meta.get("title"),
            meta.get("save_name"),
            self.save_name(mod),
            mod,
        ):
            normalized = normalize_mod_identity(value)
            if not normalized:
                continue
            if normalized.isdigit():
                keys.append(f"id:{normalized}")
            elif len(normalized) >= 5:
                keys.append(f"name:{normalized}")

        unique = []
        seen = set()
        for key in keys:
            if key not in seen:
                unique.append(key)
                seen.add(key)
        return unique

    def detect_local_workshop_duplicates(self, mods):
        workshop_by_key = {}
        local_by_key = {}

        for mod in mods:
            keys = self.duplicate_detection_keys(mod)
            if not keys:
                continue

            target = workshop_by_key if self.mod_is_workshop(mod) else local_by_key
            for key in keys:
                target.setdefault(key, []).append(mod)

        duplicate_groups = []
        seen_pairs = set()

        for key, local_mods in local_by_key.items():
            workshop_mods = workshop_by_key.get(key, [])
            if not workshop_mods:
                continue

            local_unique = sorted(set(local_mods), key=str.lower)
            workshop_unique = sorted(set(workshop_mods), key=str.lower)
            pair_signature = (tuple(local_unique), tuple(workshop_unique))
            if pair_signature in seen_pairs:
                continue

            seen_pairs.add(pair_signature)
            duplicate_groups.append({
                "key": key,
                "locals": local_unique,
                "workshop": workshop_unique,
            })

        duplicate_groups.sort(
            key=lambda group: (
                self.sort_name(group["locals"][0]) if group["locals"] else "",
                self.sort_name(group["workshop"][0]) if group["workshop"] else "",
            )
        )
        return duplicate_groups

    def warn_about_duplicate_mods(self, duplicate_groups):
        if not duplicate_groups:
            return

        lines = [
            "Possible duplicate local and Workshop copies were detected.",
            "",
            "These pairs often cause confusion because both versions appear to be the same mod:",
            "",
        ]

        preview_groups = duplicate_groups[:10]
        for group in preview_groups:
            local_names = ", ".join(self.display_name(mod) for mod in group["locals"])
            workshop_names = ", ".join(self.display_name(mod) for mod in group["workshop"])
            lines.append(f"Local: {local_names}")
            lines.append(f"Workshop: {workshop_names}")
            lines.append("")

        if len(duplicate_groups) > len(preview_groups):
            lines.append(f"...and {len(duplicate_groups) - len(preview_groups)} more possible duplicate matches.")
            lines.append("")

        lines.append("If both copies are intentional, you can ignore this warning.")

        self.show_warning("Possible Duplicate Mods", "\n".join(lines))

    def show_or_queue_duplicate_warning(self, duplicate_groups):
        if not duplicate_groups:
            return

        splash_exists = False
        try:
            splash_exists = self.startup_splash is not None and self.startup_splash.winfo_exists()
        except Exception:
            splash_exists = False

        if splash_exists:
            self.pending_duplicate_groups = duplicate_groups
            return

        self.warn_about_duplicate_mods(duplicate_groups)

    def flush_startup_notifications(self):
        duplicate_groups = list(self.pending_duplicate_groups)
        self.pending_duplicate_groups = []
        if duplicate_groups:
            self.root.after(50, lambda groups=duplicate_groups: self.warn_about_duplicate_mods(groups))

    # -----------------------------------------------------
    # CATEGORY HELPERS
    # -----------------------------------------------------

    # Combines built-in categories, saved custom categories, and
    # categories found on existing mods so old loadouts still work.
    def get_categories(self):
        return build_categories(self.state)

    def category_color(self, category):
        return resolve_category_color(
            self.state,
            category,
            normalize_hex_color,
            THEME["text_bright"],
        )

    def default_color_for_new_category(self):
        return pick_default_category_color(
            self.state,
            normalize_hex_color,
            THEME["text_bright"],
        )

    def project_tag_values(self, mod):
        return read_project_tag_values(
            self.mod_folder_path,
            mod,
            parse_xml_file_forgiving,
        )

    def auto_category_scores(self, mod):
        return score_mod_categories(
            self.state,
            mod,
            self.mod_folder_path,
            self.save_name,
            self.display_name,
            parse_xml_file_forgiving,
        )

    # Suggests one built-in category when tag/content heuristics produce a
    # strong enough signal; otherwise returns None so the mod stays manual.
    def suggested_category_for_mod(self, mod):
        return suggest_mod_category(
            self.state,
            mod,
            self.mod_folder_path,
            self.save_name,
            self.display_name,
            parse_xml_file_forgiving,
        )

    def auto_categorize_mods(self, mods=None, include_already_attempted=True, show_summary=True, refresh_ui=True):
        order = self.state.get("order", [])
        if not order:
            self.show_warning("Warning", "Load mods before auto-categorizing.")
            return

        target_mods = list(mods) if mods is not None else list(order)
        changed, ambiguous = apply_auto_categorization(
            self.state,
            target_mods,
            self.suggested_category_for_mod,
            self.remember_mod_category,
            include_already_attempted=include_already_attempted,
        )

        if not show_summary and changed:
            self.state["order"] = self.sorted_order_by_category()

        if not refresh_ui:
            self.save_state()
            return changed, ambiguous

        self.save_state()
        self.rebuild_category_menus()
        self.refresh()

        status = f"Auto-categorized {len(changed)} mods"
        if ambiguous:
            status += f" | {len(ambiguous)} still need review"
        self.set_status_text(status)

        if not show_summary:
            return changed, ambiguous

        preview = "\n".join(
            f"{self.display_name(mod)} -> {category}"
            for mod, category in changed[:12]
        )
        if not preview:
            preview = "(No confident matches)"

        ambiguous_text = ""
        if ambiguous:
            ambiguous_preview = "\n".join(self.display_name(mod) for mod in ambiguous[:10])
            extra = ""
            if len(ambiguous) > 10:
                extra = f"\n...and {len(ambiguous) - 10} more"
            ambiguous_text = (
                "\n\nStill Unassigned:\n"
                f"{ambiguous_preview}{extra}"
            )

        self.show_info(
            "Auto Categorize",
            f"Assigned {len(changed)} mods.\n\n"
            f"{preview}"
            f"{ambiguous_text}"
        )
        return changed, ambiguous

    # Builds numeric sort buckets for all categories, including
    # custom categories that were added after the original defaults.
    def get_category_priority(self, base_priority, fallback=700):
        return build_category_priority(self.state, base_priority, fallback)

    def sorted_order_by_category(self, order=None, categories=None):
        if order is None:
            order = self.state.get("order", [])
        if categories is None:
            categories = self.state.get("categories", {})

        auto_sort_priority = self.get_category_priority({
            "UI": 0,
            "Districts": 100,
            "Dungeons": 200,
            "Quirks": 250,
            "Trinkets": 300,
            "Enemies": 400,
            "Class Patch": 450,
            "Class": 500,
            "Skins": 600,
            "Unassigned": 700
        })

        return sorted(
            order,
            key=lambda mod: (
                1 if categories.get(mod, "Unassigned") == "Unassigned" else 0,
                auto_sort_priority.get(categories.get(mod, "Unassigned"), 700),
                self.sort_name(mod)
            )
        )

    # -----------------------------------------------------
    # THEME HELPERS
    # -----------------------------------------------------

    def themed_frame(self, parent, bg=None, **kwargs):
        return tk.Frame(parent, bg=bg or THEME["bg"], **kwargs)

    def themed_label(self, parent, text, style="body", **kwargs):
        styles = {
            "title": {"bg": THEME["bg"], "fg": THEME["text_bright"], "font": FONT_TITLE},
            "subtitle": {"bg": THEME["bg"], "fg": THEME["muted"], "font": FONT_SUBTITLE},
            "heading": {"bg": THEME["bg"], "fg": THEME["gold"], "font": FONT_HEADING},
            "body": {"bg": THEME["bg"], "fg": THEME["text"], "font": FONT_BODY},
            "muted": {"bg": THEME["bg"], "fg": THEME["muted"], "font": FONT_BODY},
        }
        config = dict(styles.get(style, styles["body"]))
        config.update(kwargs)
        return tk.Label(parent, text=text, **config)

    def themed_button(self, parent, text, command, style="secondary", **kwargs):
        styles = {
            "primary": {
                "bg": THEME["crimson"],
                "fg": THEME["text_bright"],
                "activebackground": THEME["crimson_hover"],
                "activeforeground": THEME["text_bright"],
            },
            "secondary": {
                "bg": THEME["panel"],
                "fg": THEME["text"],
                "activebackground": THEME["border"],
                "activeforeground": THEME["text_bright"],
            },
            "warning": {
                "bg": THEME["amber"],
                "fg": THEME["ink"],
                "activebackground": THEME["amber_hover"],
                "activeforeground": THEME["ink"],
            },
        }
        config = {
            "font": FONT_BUTTON,
            "relief": "solid",
            "bd": 1,
            "highlightthickness": 1,
            "highlightbackground": THEME["border"],
            "padx": 8,
            "pady": 4,
            "cursor": "hand2",
        }
        config.update(styles.get(style, styles["secondary"]))
        config.update(kwargs)
        return tk.Button(parent, text=text, command=command, **config)

    def themed_entry(self, parent, **kwargs):
        config = {
            "bg": THEME["field"],
            "fg": THEME["text_bright"],
            "insertbackground": THEME["gold"],
            "font": FONT_BODY,
            "relief": "solid",
            "bd": 1,
            "highlightthickness": 1,
            "highlightbackground": THEME["border"],
        }
        config.update(kwargs)
        return tk.Entry(parent, **config)

    def configure_option_menu(self, option_menu):
        option_menu.config(
            bg=THEME["panel"],
            fg=THEME["text"],
            activebackground=THEME["border"],
            activeforeground=THEME["text_bright"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            relief="solid",
            bd=1,
            font=FONT_BODY,
        )
        option_menu["menu"].config(
            bg=THEME["panel"],
            fg=THEME["text"],
            activebackground=THEME["crimson"],
            activeforeground=THEME["text_bright"],
            font=FONT_BODY,
            tearoff=0,
        )

    def current_view_config(self):
        return VIEW_MODES.get(self.current_view_mode(), VIEW_MODES["Comfortable"])

    def list_font(self):
        return self.current_view_config()["list_font"]

    def set_recent_new_mods(self, mods):
        self.recent_new_mods = set(mods)
        if self.new_mod_highlight_job is not None:
            try:
                self.root.after_cancel(self.new_mod_highlight_job)
            except Exception:
                pass
            self.new_mod_highlight_job = None

        if self.recent_new_mods:
            self.new_mod_highlight_job = self.root.after(
                NEW_MOD_HIGHLIGHT_MS,
                self.clear_recent_new_mods,
            )

    def clear_recent_new_mods(self):
        self.new_mod_highlight_job = None
        if not self.recent_new_mods:
            return
        self.recent_new_mods.clear()
        self.refresh()

    def preview_icon_size(self):
        return self.current_view_config()["icon_size"]

    def preview_icon_strip_width(self):
        return self.current_view_config()["icon_strip_width"]

    def icons_enabled(self):
        return self.preview_icon_strip_width() > 0 and self.preview_icon_size() > 0

    # Native Tk listbox text sits slightly low inside each row, so the
    # preview icon strip uses a small per-view offset to match it better.
    def preview_icon_vertical_offset(self):
        mode = self.current_view_mode()
        offsets = {
            "No Icons": 0,
            "Compact": 2,
            "Comfortable": 3,
            "Visual": 3,
        }
        return offsets.get(mode, 2)

    def visible_mods_in_display_order(self):
        return list(self.disabled_visible_mods) + list(self.enabled_visible_mods)

    def visible_mods_for_side_from_state(self, side, order=None):
        if order is None:
            order = self.state.get("order", [])

        categories = self.state.get("categories", {})
        enabled_map = self.state.get("enabled", {})
        filter_value = self.current_filter_category()
        search_value = self.search_text.get().strip().lower()

        visible_mods = []
        for mod in order:
            is_enabled = enabled_map.get(mod, True)
            if side == "enabled" and not is_enabled:
                continue
            if side == "disabled" and is_enabled:
                continue

            cat = categories.get(mod, "Unassigned")
            if filter_value != "All" and cat != filter_value:
                continue

            if search_value:
                display_text = self.display_name_with_suffix(mod)
                display = display_text.lower()
                save_display = self.save_name(mod).lower()
                raw_name = mod.lower()
                meta = self.state.get("metadata", {}).get(mod, {})
                meta_title = str(meta.get("title", "")).lower()
                meta_id = str(meta.get("published_file_id", "")).lower()

                if (
                    search_value not in display
                    and search_value not in save_display
                    and search_value not in raw_name
                    and search_value not in meta_title
                    and search_value not in meta_id
                ):
                    continue

            visible_mods.append(mod)

        recent_new_mods = self.recent_new_mods
        if recent_new_mods:
            order_positions = {mod: index for index, mod in enumerate(order)}
            visible_mods.sort(
                key=lambda mod: (
                    mod not in recent_new_mods,
                    order_positions.get(mod, len(order)),
                )
            )

        return visible_mods

    def set_view_mode(self, mode):
        mode = self.view_mode_from_label(mode)
        if mode not in VIEW_MODES:
            mode = "Comfortable"
        self.view_mode.set(self.view_mode_label(mode))
        if self.view_mode_job is not None:
            try:
                self.root.after_cancel(self.view_mode_job)
            except Exception:
                pass
        self.view_mode_job = self.root.after(90, self.apply_pending_view_mode)

    def apply_pending_view_mode(self):
        self.view_mode_job = None
        self.icon_load_queue.clear()
        self.icon_load_pending.clear()
        if self.icon_load_job is not None:
            try:
                self.root.after_cancel(self.icon_load_job)
            except Exception:
                pass
            self.icon_load_job = None
        self.apply_view_mode()
        self.save_state()
        self.root.update_idletasks()
        if self.icons_enabled():
            self.queue_preview_icon_loads(self.visible_mods_in_display_order(), max_size=self.preview_icon_size())

    def apply_view_mode(self):
        list_font = self.list_font()
        strip_width = self.preview_icon_strip_width()

        if hasattr(self, "disabled_listbox"):
            self.disabled_listbox.config(font=list_font)
        if hasattr(self, "enabled_listbox"):
            self.enabled_listbox.config(font=list_font)
        if hasattr(self, "disabled_icon_canvas"):
            self.disabled_icon_canvas.config(width=strip_width)
        if hasattr(self, "enabled_icon_canvas"):
            self.enabled_icon_canvas.config(width=strip_width)

        if hasattr(self, "disabled_icon_canvas"):
            if self.icons_enabled():
                if not self.disabled_icon_canvas.winfo_manager():
                    self.disabled_icon_canvas.pack(side="left", fill="y", padx=(0, 3), before=self.disabled_listbox)
            else:
                if self.disabled_icon_canvas.winfo_manager():
                    self.disabled_icon_canvas.pack_forget()
        if hasattr(self, "enabled_icon_canvas"):
            if self.icons_enabled():
                if not self.enabled_icon_canvas.winfo_manager():
                    self.enabled_icon_canvas.pack(side="left", fill="y", padx=(0, 3), before=self.enabled_listbox)
            else:
                if self.enabled_icon_canvas.winfo_manager():
                    self.enabled_icon_canvas.pack_forget()

        self.schedule_icon_redraw()

    def preview_icon_path_for_mod(self, mod):
        cached = self.preview_icon_path_cache.get(mod)
        if cached is not None:
            return cached

        mod_path = self.mod_folder_path(mod)
        candidates = [
            os.path.join(mod_path, "preview_icon.png"),
            os.path.join(mod_path, "preview_icon.gif"),
            os.path.join(mod_path, "preview_icon.jpg"),
        ]

        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                self.preview_icon_path_cache[mod] = candidate
                return candidate

        project_path = os.path.join(mod_path, "project.xml")
        root = parse_xml_file_forgiving(project_path) if os.path.exists(project_path) else None
        if root is not None:
            preview_file = xml_text_from_child(root, "PreviewIconFile")
            if preview_file:
                candidates.insert(0, os.path.join(mod_path, preview_file))

        resolved = ""
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                resolved = candidate
                break

        self.preview_icon_path_cache[mod] = resolved
        return resolved

    def preview_icon_cache_path(self, mod, source_path, max_size):
        if not source_path:
            return ""

        try:
            stat = os.stat(source_path)
        except OSError:
            return ""

        safe_mod = re.sub(r"[^A-Za-z0-9._-]+", "_", mod).strip("._") or "mod"
        base = os.path.splitext(os.path.basename(source_path))[0]
        filename = (
            f"{safe_mod}_{base}_{max_size}_"
            f"{int(stat.st_mtime)}_{stat.st_size}.png"
        )
        return os.path.join(ICON_CACHE_DIR, filename)

    def preview_icon_image_for_mod(self, mod, max_size=None, allow_load=True):
        if max_size is None:
            max_size = self.preview_icon_size()
        cache_key = (mod, max_size)
        if cache_key in self.preview_icon_image_cache:
            return self.preview_icon_image_cache[cache_key]

        if not allow_load:
            return None

        path = self.preview_icon_path_for_mod(mod)
        if not path:
            self.preview_icon_image_cache[cache_key] = None
            return None

        cache_path = self.preview_icon_cache_path(mod, path, max_size)
        if cache_path and os.path.isfile(cache_path):
            try:
                image = tk.PhotoImage(file=cache_path)
                self.preview_icon_image_cache[cache_key] = image
                return image
            except Exception:
                pass

        try:
            image = tk.PhotoImage(file=path)
        except Exception:
            self.preview_icon_image_cache[cache_key] = None
            return None

        width = max(1, int(image.width()))
        height = max(1, int(image.height()))
        factor = max(1, math.ceil(max(width, height) / max_size))
        if factor > 1:
            image = image.subsample(factor, factor)

        if cache_path:
            try:
                os.makedirs(ICON_CACHE_DIR, exist_ok=True)
                image.write(cache_path, format="png")
            except Exception:
                pass

        self.preview_icon_image_cache[cache_key] = image
        return image

    # Eagerly resolves preview icon paths and current-size images so a
    # freshly loaded mod list does not fill icons in only when scrolled.
    def preload_preview_icons(self, mods=None, max_size=None):
        start = time.perf_counter()
        if mods is None:
            mods = self.state.get("order", [])
        if max_size is None:
            max_size = self.preview_icon_size()

        mods = list(mods)
        if not mods:
            self.record_startup_timing("preload_preview_icons", time.perf_counter() - start)
            return

        self.icon_load_queue.clear()
        self.icon_load_pending.clear()
        if self.icon_load_job is not None:
            try:
                self.root.after_cancel(self.icon_load_job)
            except Exception:
                pass
            self.icon_load_job = None

        for index, mod in enumerate(mods, start=1):
            self.preview_icon_path_for_mod(mod)
            self.preview_icon_image_for_mod(mod, max_size=max_size, allow_load=True)

            if index % 25 == 0:
                self.root.update_idletasks()
        self.record_startup_timing("preload_preview_icons", time.perf_counter() - start)

    def queue_preview_icon_loads(self, mods=None, max_size=None):
        if mods is None:
            mods = self.state.get("order", [])
        if max_size is None:
            max_size = self.preview_icon_size()

        for mod in mods:
            self.preview_icon_path_for_mod(mod)
            self.queue_icon_load(mod, max_size=max_size)

    def queue_icon_load(self, mod, max_size=None):
        if max_size is None:
            max_size = self.preview_icon_size()

        item = (mod, max_size)
        if item in self.preview_icon_image_cache:
            return
        if item in self.icon_load_pending:
            return

        self.icon_load_pending.add(item)
        self.icon_load_queue.append(item)

        if self.icon_load_job is None:
            self.icon_load_job = self.root.after(1, self.process_icon_load_queue)

    def process_icon_load_queue(self):
        self.icon_load_job = None
        loaded_any = False

        for _ in range(4):
            if not self.icon_load_queue:
                break

            mod, max_size = self.icon_load_queue.pop(0)
            self.icon_load_pending.discard((mod, max_size))
            if (mod, max_size) in self.preview_icon_image_cache:
                continue

            image = self.preview_icon_image_for_mod(mod, max_size=max_size, allow_load=True)
            if image is not None:
                loaded_any = True

        if loaded_any:
            self.schedule_icon_redraw()

        if self.icon_load_queue:
            self.icon_load_job = self.root.after(1, self.process_icon_load_queue)

    def schedule_icon_redraw(self):
        if self.icon_redraw_job is not None:
            try:
                self.root.after_cancel(self.icon_redraw_job)
            except Exception:
                pass
        self.icon_redraw_job = self.root.after_idle(self.redraw_icon_canvases)

    def redraw_icon_canvases(self):
        self.icon_redraw_job = None
        self.redraw_icon_canvas("disabled")
        self.redraw_icon_canvas("enabled")

    # Mirrors the listbox rows onto the neighboring icon canvas so each
    # mod can show a preview image without switching to a custom row UI.
    def redraw_icon_canvas(self, side):
        if not self.icons_enabled():
            return

        if side == "disabled":
            canvas = getattr(self, "disabled_icon_canvas", None)
            listbox = getattr(self, "disabled_listbox", None)
            visible_mods = self.disabled_visible_mods
        else:
            canvas = getattr(self, "enabled_icon_canvas", None)
            listbox = getattr(self, "enabled_listbox", None)
            visible_mods = self.enabled_visible_mods

        if canvas is None or listbox is None:
            return

        canvas.delete("all")
        self.preview_icon_refs[side] = []

        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        canvas.create_rectangle(0, 0, width, height, fill=THEME["panel_deep"], outline="")

        for index, mod in enumerate(visible_mods):
            bbox = listbox.bbox(index)
            if not bbox:
                continue

            _, y, _, row_height = bbox
            center_y = y + row_height // 2 + self.preview_icon_vertical_offset()
            image = self.preview_icon_image_for_mod(mod, allow_load=False)
            if image is not None:
                canvas.create_image(width // 2, center_y, image=image)
                self.preview_icon_refs[side].append(image)
            else:
                self.queue_icon_load(mod)
                icon_size = self.preview_icon_size()
                inset = max(4, (width - icon_size) // 2)
                tile_height = min(icon_size, max(12, row_height - 8))
                top = center_y - tile_height // 2
                min_top = y + 4
                max_top = y + row_height - tile_height - 4
                if max_top < min_top:
                    top = y + max(2, (row_height - tile_height) // 2)
                else:
                    top = max(min_top, min(top, max_top))
                bottom = top + tile_height
                canvas.create_rectangle(
                    inset,
                    top,
                    width - inset,
                    bottom,
                    fill=THEME["field_alt"],
                    outline=THEME["border"],
                )

    def on_icon_canvas_click(self, side, event):
        if side == "disabled":
            listbox = self.disabled_listbox
            visible = self.disabled_visible_mods
        else:
            listbox = self.enabled_listbox
            visible = self.enabled_visible_mods

        if not visible:
            return "break"

        index = listbox.nearest(event.y)
        if not (0 <= index < len(visible)):
            return "break"

        listbox.selection_clear(0, tk.END)
        listbox.selection_set(index)
        listbox.selection_anchor(index)
        listbox.activate(index)
        listbox.focus_set()
        return "break"

    def on_disabled_yview(self, first, last):
        if hasattr(self, "disabled_scrollbar"):
            self.disabled_scrollbar.set(first, last)
        self.schedule_icon_redraw()

    def on_enabled_yview(self, first, last):
        if hasattr(self, "enabled_scrollbar"):
            self.enabled_scrollbar.set(first, last)
        self.schedule_icon_redraw()

    def scroll_disabled_list(self, *args):
        self.disabled_listbox.yview(*args)
        self.schedule_icon_redraw()

    def scroll_enabled_list(self, *args):
        self.enabled_listbox.yview(*args)
        self.schedule_icon_redraw()

    # -----------------------------------------------------
    # USER INTERFACE SETUP
    # -----------------------------------------------------

    def build_ui(self):
        build_start = time.perf_counter()
        self.root.configure(bg=THEME["bg"])

        title_frame = self.themed_frame(self.root)
        title_frame.pack(fill="x", padx=14, pady=(12, 4))

        title_block = self.themed_frame(title_frame)
        title_block.pack(side="left")
        self.title_label = self.themed_label(
            title_block,
            self.tr("app_title"),
            style="title",
            anchor="w"
        )
        self.title_label.pack(anchor="w")
        self.subtitle_label = self.themed_label(
            title_block,
            subtitle_with_version(self.tr("app_subtitle")),
            style="subtitle",
            anchor="w"
        )
        self.subtitle_label.pack(anchor="w")

        self.launch_button = self.themed_button(
            title_frame,
            text=self.tr("launch_game"),
            command=self.launch_darkest_dungeon,
            style="primary"
        )
        self.launch_button.pack(side="right")

        language_frame = self.themed_frame(title_frame)
        language_frame.pack(side="right", padx=(0, 12))
        self.language_label = self.themed_label(
            language_frame,
            text=self.tr("language"),
            style="heading"
        )
        self.language_label.pack(side="left", padx=(0, 6))
        self.language_menu = tk.OptionMenu(
            language_frame,
            self.language,
            *LANGUAGE_CODE_TO_LABEL.values(),
            command=self.set_language
        )
        self.configure_option_menu(self.language_menu)
        self.language_menu.pack(side="left")

        divider = tk.Frame(self.root, bg=THEME["crimson"], height=2)
        divider.pack(fill="x", padx=14, pady=(6, 10))

        top = self.themed_frame(self.root)
        top.pack(fill="x", padx=14, pady=(8, 10))

        top_left_actions = self.themed_frame(top)
        top_left_actions.pack(side="left")

        top_right_actions = self.themed_frame(top)
        top_right_actions.pack(side="right")

        self.open_local_mods_button = self.themed_button(top_left_actions, text=self.tr("open_local_mods"), command=self.open_assigned_local_mods_folder)
        self.open_local_mods_button.pack(side="left", padx=(0, 4))
        self.file_paths_button = self.themed_button(top_left_actions, text=self.tr("file_paths"), command=self.browse)
        self.file_paths_button.pack(side="left", padx=4)
        self.auto_detect_button = self.themed_button(top_left_actions, text=self.tr("auto_detect"), command=self.run_auto_detect)
        self.auto_detect_button.pack(side="left", padx=(4, 0))

        self.refresh_mods_button = self.themed_button(top_right_actions, text=self.tr("refresh_mods"), command=self.load_mods)
        self.refresh_mods_button.pack(side="left", padx=(0, 4))
        self.tools_menu = tk.Menubutton(
            top_right_actions,
            text=self.tr("tools"),
            bg=THEME["panel"],
            fg=THEME["text"],
            activebackground=THEME["border"],
            activeforeground=THEME["text_bright"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            relief="solid",
            bd=1,
            font=FONT_BUTTON,
            padx=8,
            pady=4,
            anchor="w",
            cursor="hand2",
        )
        self.tools_menu.pack(side="left", padx=(4, 0))
        self.tools_menu.menu = tk.Menu(
            self.tools_menu,
            tearoff=0,
            bg=THEME["panel"],
            fg=THEME["text"],
            activebackground=THEME["crimson"],
            activeforeground=THEME["text_bright"],
            font=FONT_BODY,
        )
        self.tools_menu["menu"] = self.tools_menu.menu
        self.rebuild_tools_menu()

        profile_frame = self.themed_frame(self.root)
        profile_frame.pack(fill="x", padx=14, pady=(0, 10))

        self.profile_heading_label = self.themed_label(
            profile_frame,
            text=self.tr("profile"),
            style="heading"
        )
        self.profile_heading_label.pack(side="left", padx=(0, 8))

        self.profile_menu = tk.OptionMenu(
            profile_frame,
            self.selected_profile,
            self.empty_profile_label(),
            command=self.select_profile
        )
        self.configure_option_menu(self.profile_menu)
        self.profile_menu.config(width=42)
        self.profile_menu.pack(side="left", padx=(0, 8))

        self.refresh_profile_button = self.themed_button(profile_frame, text=self.tr("refresh"), command=self.refresh_profile_menu)
        self.refresh_profile_button.pack(side="left", padx=(0, 8))
        self.load_profile_button = self.themed_button(profile_frame, text=self.tr("load_profile_mods"), command=self.load_selected_profile_mods, style="primary")
        self.load_profile_button.pack(side="left", padx=(0, 4))
        self.patch_profile_button = self.themed_button(profile_frame, text=self.tr("patch_selected_profile"), command=self.patch_selected_profile_save, style="primary")
        self.patch_profile_button.pack(side="left", padx=(4, 0))

        # Auto-detected save patching is now a legacy fallback because profile
        # patching covers the main workflow more reliably.
        if SHOW_PRIMARY_AUTO_PATCH_BUTTON:
            action_frame = self.themed_frame(self.root)
            action_frame.pack(fill="x", padx=14, pady=(0, 10))
            self.themed_button(
                action_frame,
                text="Patch Auto-Detected Save",
                command=self.patch_latest_save_file,
                style="primary"
            ).pack(side="left", padx=4)

        filter_frame = self.themed_frame(self.root)
        filter_frame.pack(fill="x", padx=14, pady=(0, 8))

        self.filter_heading_label = self.themed_label(
            filter_frame,
            text=self.tr("filter"),
            style="heading"
        )
        self.filter_heading_label.pack(side="left", padx=(0, 8))

        filter_options = [self.category_label("All"), self.category_label("Unassigned")] + [
            self.category_label(cat) for cat in self.get_categories()
        ]

        self.filter_menu = tk.OptionMenu(
            filter_frame,
            self.filter_category,
            *filter_options,
            command=lambda _: self.refresh()
        )
        self.configure_option_menu(self.filter_menu)
        self.filter_menu.pack(side="left")

        self.edit_categories_button = self.themed_button(filter_frame, text=self.tr("edit_categories"), command=self.add_category)
        self.edit_categories_button.pack(side="left", padx=(8, 0))

        self.search_heading_label = self.themed_label(
            filter_frame,
            text=self.tr("search"),
            style="heading"
        )
        self.search_heading_label.pack(side="left", padx=(16, 8))

        search_entry = self.themed_entry(
            filter_frame,
            textvariable=self.search_text,
            bd=4,
            width=28
        )
        search_entry.pack(side="left")
        search_entry.bind("<KeyRelease>", self.schedule_search_refresh)

        self.view_heading_label = self.themed_label(
            filter_frame,
            text=self.tr("view"),
            style="heading"
        )
        self.view_heading_label.pack(side="left", padx=(16, 8))

        self.view_mode_menu = tk.OptionMenu(
            filter_frame,
            self.view_mode,
            *(self.view_mode_label(mode) for mode in VIEW_MODES.keys()),
            command=self.set_view_mode
        )
        self.configure_option_menu(self.view_mode_menu)
        self.view_mode_menu.pack(side="left")

        info_frame = self.themed_frame(self.root)
        info_frame.pack(fill="x", padx=10, pady=(0, 6))

        self.status_label = self.themed_label(
            info_frame,
            text=self.tr("status_choose_mods"),
            style="muted",
            anchor="w",
        )
        self.status_label.pack(fill="x")
        self.status_translation = ("status_choose_mods", {})

        list_action_frame = self.themed_frame(self.root)
        list_action_frame.pack(fill="x", padx=14, pady=(0, 8))

        self.list_actions_heading_label = self.themed_label(
            list_action_frame,
            text=self.tr("list_actions"),
            style="heading"
        )
        self.list_actions_heading_label.pack(side="left", padx=(0, 8))

        self.auto_sort_button = self.themed_button(list_action_frame, text=self.tr("auto_sort"), command=self.auto_sort)
        self.auto_sort_button.pack(side="left", padx=4)
        self.auto_categorize_button = self.themed_button(list_action_frame, text=self.tr("auto_categorize"), command=self.auto_categorize_mods)
        self.auto_categorize_button.pack(side="left", padx=4)
        self.nickname_button = self.themed_button(list_action_frame, text=self.tr("nickname_mod"), command=self.rename_selected_mod)
        self.nickname_button.pack(side="left", padx=4)

        panels_frame = self.themed_frame(self.root)
        panels_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # LEFT PANEL - DISABLED
        left_frame = self.themed_frame(panels_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.reserve_heading_label = self.themed_label(
            left_frame,
            text=self.tr("reserve"),
            style="heading"
        )
        self.reserve_heading_label.pack(anchor="w", pady=(0, 6))

        left_scroll = tk.Scrollbar(left_frame)
        left_scroll.pack(side="right", fill="y")
        self.disabled_scrollbar = left_scroll

        self.disabled_icon_canvas = tk.Canvas(
            left_frame,
            width=self.preview_icon_strip_width(),
            bg=THEME["panel_deep"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            bd=0,
            relief="flat",
        )
        self.disabled_icon_canvas.pack(side="left", fill="y", padx=(0, 3))
        self.disabled_icon_canvas.bind("<ButtonPress-1>", lambda event: self.on_icon_canvas_click("disabled", event))

        self.disabled_listbox = tk.Listbox(
            left_frame,
            width=50,
            bg=THEME["panel_deep"],
            fg=THEME["disabled"],
            selectbackground=THEME["select"],
            selectforeground=THEME["select_text"],
            font=self.list_font(),
            activestyle="none",
            selectmode=tk.MULTIPLE,
            yscrollcommand=self.on_disabled_yview,
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            relief="flat"
        )
        self.disabled_listbox.pack(side="left", fill="both", expand=True)
        left_scroll.config(command=self.scroll_disabled_list)

        # MIDDLE BUTTONS
        middle_frame = self.themed_frame(panels_frame)
        middle_frame.pack(side="left", fill="y", padx=8)

        self.enable_button = self.themed_button(middle_frame, text=self.tr("enable_selected"), command=self.enable_selected_from_left)
        self.enable_button.pack(pady=(120, 8))
        self.disable_button = self.themed_button(middle_frame, text=self.tr("disable_selected"), command=self.disable_selected_from_right)
        self.disable_button.pack(pady=8)

        # RIGHT PANEL - ENABLED
        right_frame = self.themed_frame(panels_frame)
        right_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.load_order_heading_label = self.themed_label(
            right_frame,
            text=self.tr("load_order"),
            style="heading"
        )
        self.load_order_heading_label.pack(anchor="w", pady=(0, 6))

        right_scroll = tk.Scrollbar(right_frame)
        right_scroll.pack(side="right", fill="y")
        self.enabled_scrollbar = right_scroll

        self.enabled_icon_canvas = tk.Canvas(
            right_frame,
            width=self.preview_icon_strip_width(),
            bg=THEME["panel_deep"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            bd=0,
            relief="flat",
        )
        self.enabled_icon_canvas.pack(side="left", fill="y", padx=(0, 3))
        self.enabled_icon_canvas.bind("<ButtonPress-1>", lambda event: self.on_icon_canvas_click("enabled", event))

        self.enabled_listbox = tk.Listbox(
            right_frame,
            width=50,
            bg=THEME["panel_deep"],
            fg=THEME["text_bright"],
            selectbackground=THEME["select"],
            selectforeground=THEME["select_text"],
            font=self.list_font(),
            activestyle="none",
            selectmode=tk.MULTIPLE,
            yscrollcommand=self.on_enabled_yview,
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            relief="flat"
        )
        self.enabled_listbox.pack(side="left", fill="both", expand=True)
        right_scroll.config(command=self.scroll_enabled_list)


        # Custom mouse handling so plain left-drag moves items,
        # while Ctrl/Shift still do multi-select.
        self.disabled_listbox.bind("<ButtonPress-1>", self.on_disabled_click)
        self.disabled_listbox.bind("<B1-Motion>", self.on_disabled_drag)
        self.disabled_listbox.bind("<ButtonRelease-1>", self.on_disabled_release)
        self.disabled_listbox.bind("<Configure>", lambda event: self.schedule_icon_redraw())

        self.enabled_listbox.bind("<ButtonPress-1>", self.on_enabled_click)
        self.enabled_listbox.bind("<B1-Motion>", self.on_enabled_drag)
        self.enabled_listbox.bind("<ButtonRelease-1>", self.on_enabled_release)
        self.enabled_listbox.bind("<Configure>", lambda event: self.schedule_icon_redraw())


        # Keyboard toggle shortcuts
        self.disabled_listbox.bind("<space>", self.toggle_disabled_selected)
        self.enabled_listbox.bind("<space>", self.toggle_enabled_selected)

        # Right-click category menu on both
        self.disabled_listbox.bind("<Button-3>", self.show_disabled_menu)
        self.enabled_listbox.bind("<Button-3>", self.show_enabled_menu)
        self.disabled_listbox.bind("<Button-2>", self.show_disabled_menu)
        self.enabled_listbox.bind("<Button-2>", self.show_enabled_menu)

        self.menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=THEME["panel"],
            fg=THEME["text"],
            activebackground=THEME["crimson"],
            activeforeground=THEME["text_bright"],
            font=FONT_BODY,
        )
        self.rebuild_category_menus()
        self.rebuild_view_mode_menu()
        self.refresh_profile_menu()
        self.apply_view_mode()

        self.refresh()
        self.record_startup_timing("build_ui", time.perf_counter() - build_start)

    # -----------------------------------------------------
    # FILTER / CATEGORY UI
    # -----------------------------------------------------

    # Rebuilds both the filter dropdown and right-click category menu
    # whenever categories are added or discovered from saved state.
    def rebuild_category_menus(self):
        if hasattr(self, "filter_menu"):
            filter_menu = self.filter_menu["menu"]
            filter_menu.delete(0, tk.END)
            for cat in ["All", "Unassigned"] + self.get_categories():
                filter_menu.add_command(
                    label=self.category_label(cat),
                    command=lambda c=cat: self.set_filter_category(c)
                )

        self.menu.delete(0, tk.END)
        for cat in self.get_categories():
            self.menu.add_command(label=self.category_label(cat), command=lambda c=cat: self.set_category(c))
        self.menu.add_separator()
        self.menu.add_command(label=self.tr("open_workshop_page"), command=self.open_workshop_page_for_menu_selection)
        self.context_menu_workshop_index = self.menu.index(tk.END)

    def rebuild_view_mode_menu(self):
        if not hasattr(self, "view_mode_menu"):
            return
        menu = self.view_mode_menu["menu"]
        menu.delete(0, tk.END)
        for mode in VIEW_MODES.keys():
            menu.add_command(
                label=self.view_mode_label(mode),
                command=lambda value=mode: self.set_view_mode(value)
            )

    def set_filter_category(self, cat):
        self.filter_category.set(self.category_label(cat))
        self.refresh()

    def add_category(self):
        categories = list(self.get_categories())
        custom_categories = set(self.state.get("custom_categories", []))
        renamed_categories = {}
        category_colors = {
            category: normalize_hex_color(color)
            for category, color in self.state.get("category_colors", {}).items()
            if normalize_hex_color(color)
        }

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Categories")
        dialog.geometry("620x470")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        self.themed_label(
            dialog,
            text="Categories",
            style="heading"
        ).pack(anchor="w", padx=12, pady=(12, 8))

        footer = self.themed_frame(dialog)
        footer.pack(side="bottom", fill="x", padx=12, pady=(0, 12))

        body = self.themed_frame(dialog)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = self.themed_frame(body)
        left.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(left)
        scroll.pack(side="right", fill="y")

        category_list = tk.Listbox(
            left,
            width=34,
            bg=THEME["panel_deep"],
            fg=THEME["text_bright"],
            selectbackground=THEME["select"],
            selectforeground=THEME["select_text"],
            font=FONT_BODY,
            activestyle="none",
            yscrollcommand=scroll.set,
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            relief="flat",
        )
        category_list.pack(side="left", fill="both", expand=True)
        scroll.config(command=category_list.yview)

        right = self.themed_frame(body)
        right.pack(side="left", fill="y", padx=(10, 0))

        selected_index = {"value": None}
        drag_category_index = {"value": None}
        drag_category_y = {"value": None}
        drag_category_active = {"value": False}
        color_preview = tk.Label(
            right,
            text="",
            bg=THEME["panel_deep"],
            fg=THEME["text_bright"],
            font=FONT_BODY,
            width=14,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            padx=6,
            pady=6,
        )
        color_preview.pack(fill="x", pady=(0, 8))

        def close_dialog():
            self.category_editor_refresh = None
            dialog.destroy()

        def refresh_category_list():
            category_list.delete(0, tk.END)
            for index, cat in enumerate(categories):
                display_name = cat if cat in custom_categories else self.category_label(cat)
                suffix = "" if cat in custom_categories else f" ({self.tr('category_builtin_suffix')})"
                category_list.insert(tk.END, f"{display_name}{suffix}")
                category_list.itemconfig(index, fg=self.category_color(cat))

            if categories:
                index = selected_index["value"]
                if index is None:
                    index = 0
                index = max(0, min(index, len(categories) - 1))
                selected_index["value"] = index
                category_list.selection_clear(0, tk.END)
                category_list.selection_set(index)
                category_list.activate(index)
                category_list.see(index)
            else:
                selected_index["value"] = None
            update_color_preview()

        def current_category():
            index = selected_index["value"]
            if index is None or not (0 <= index < len(categories)):
                return None, None
            return index, categories[index]

        def sync_selection(event=None):
            selection = category_list.curselection()
            if selection:
                selected_index["value"] = selection[0]
            update_color_preview()

        def begin_category_drag(event):
            if not categories:
                return "break"
            index = category_list.nearest(event.y)
            if not (0 <= index < len(categories)):
                return "break"
            selected_index["value"] = index
            drag_category_index["value"] = index
            drag_category_y["value"] = event.y_root
            drag_category_active["value"] = False
            refresh_category_list()
            return "break"

        def drag_category(event):
            if drag_category_index["value"] is None or not categories:
                return "break"

            if drag_category_y["value"] is not None and not drag_category_active["value"]:
                if abs(event.y_root - drag_category_y["value"]) < 4:
                    return "break"
                drag_category_active["value"] = True

            target_index = category_list.nearest(event.y)
            target_index = max(0, min(target_index, len(categories) - 1))
            current_index = drag_category_index["value"]
            if target_index == current_index:
                return "break"

            new_index = reposition_category_to_index(categories, current_index, target_index)
            if new_index is None:
                return "break"
            drag_category_index["value"] = new_index
            selected_index["value"] = new_index
            refresh_category_list()
            return "break"

        def end_category_drag(event=None):
            drag_category_index["value"] = None
            drag_category_y["value"] = None
            drag_category_active["value"] = False
            return "break"

        def update_color_preview():
            _, cat = current_category()
            if cat is None:
                color_preview.config(text=self.tr("category_editor_no_category"), bg=THEME["panel_deep"])
                return
            color = normalize_hex_color(category_colors.get(cat, "")) or self.category_color(cat)
            color_preview.config(text=self.tr("category_editor_color", color=color), bg=color)

        def move_category(delta):
            index, cat = current_category()
            if cat is None:
                return
            new_index = reposition_category(categories, index, delta)
            if new_index is None:
                return
            selected_index["value"] = new_index
            refresh_category_list()

        def prompt_name(title, initial=""):
            value = simpledialog.askstring(title, "Category name:", parent=dialog, initialvalue=initial)
            if value is None:
                return None
            value = " ".join(value.strip().split())
            if not value:
                self.show_warning("Warning", "Category name cannot be empty.", parent=dialog)
                return None
            if value.lower() in ("all", "unassigned"):
                self.show_warning("Warning", f'"{value}" is reserved.', parent=dialog)
                return None
            return value

        def choose_category_color(initial=""):
            start_color = normalize_hex_color(initial) or self.default_color_for_new_category()
            _, chosen = colorchooser.askcolor(color=start_color, parent=dialog, title="Choose Category Color")
            return normalize_hex_color(chosen)

        def add_new_category():
            name = prompt_name("Add Category")
            if not name:
                return
            if name.lower() in {cat.lower() for cat in categories}:
                self.show_warning("Warning", "That category already exists.", parent=dialog)
                return
            chosen_color = choose_category_color()
            selected_index["value"] = append_custom_category(
                categories,
                custom_categories,
                category_colors,
                name,
                chosen_color or self.default_color_for_new_category(),
            )
            refresh_category_list()

        def rename_category():
            index, cat = current_category()
            if cat is None:
                return
            if cat not in custom_categories:
                self.show_info("Built-in Category", "Built-in categories can be reordered, but not renamed here.", parent=dialog)
                return

            name = prompt_name("Rename Category", initial=cat)
            if not name or name == cat:
                return
            if name.lower() in {value.lower() for value in categories if value != cat}:
                self.show_warning("Warning", "That category already exists.", parent=dialog)
                return

            rename_custom_category_data(
                categories,
                custom_categories,
                category_colors,
                renamed_categories,
                index,
                cat,
                name,
            )
            refresh_category_list()

        def remove_category():
            index, cat = current_category()
            if cat is None:
                return
            if cat not in custom_categories:
                self.show_info("Built-in Category", "Built-in categories cannot be removed here.", parent=dialog)
                return
            confirm = self.ask_yes_no(
                "Remove Category?",
                f'Remove "{cat}" and send any mods using it to Unassigned?',
                parent=dialog
            )
            if not confirm:
                return
            selected_index["value"] = delete_custom_category(
                categories,
                custom_categories,
                category_colors,
                index,
                cat,
            )
            refresh_category_list()

        def set_category_color():
            _, cat = current_category()
            if cat is None:
                return
            chosen_color = choose_category_color(category_colors.get(cat, self.category_color(cat)))
            if not chosen_color:
                return
            category_colors[cat] = chosen_color
            refresh_category_list()

        def reset_category_color():
            _, cat = current_category()
            if cat is None:
                return
            category_colors.pop(cat, None)
            refresh_category_list()

        button_specs = [
            ("category_editor_up", lambda: move_category(-1), "secondary"),
            ("category_editor_down", lambda: move_category(1), "secondary"),
            ("category_editor_add", add_new_category, "secondary"),
            ("category_editor_rename", rename_category, "secondary"),
            ("category_editor_set_color", set_category_color, "secondary"),
            ("category_editor_reset_color", reset_category_color, "secondary"),
            ("category_editor_remove", remove_category, "warning"),
        ]
        editor_buttons = []
        for key, command, style in button_specs:
            button = self.themed_button(right, text=self.tr(key), command=command, style=style, width=16)
            button.pack(fill="x", pady=3, ipady=2)
            editor_buttons.append((button, key))

        hint = self.themed_label(
            footer,
            text=self.tr("category_editor_hint"),
            style="muted",
            anchor="w",
            justify="left",
            wraplength=480,
        )
        hint.pack(fill="x", pady=(0, 10))

        def save_changes():
            final_categories = apply_category_editor_changes(
                self.state,
                categories,
                category_colors,
                renamed_categories,
                normalize_hex_color,
            )

            current_filter = self.current_filter_category()
            valid_filters = {"All", "Unassigned"} | set(final_categories)
            if current_filter not in valid_filters:
                self.filter_category.set(self.category_label("All"))

            self.save_state()
            self.rebuild_category_menus()
            self.refresh()
            self.set_status_text("Categories updated.")
            close_dialog()

        button_row = self.themed_frame(footer)
        button_row.pack(fill="x")

        save_button = self.themed_button(
            button_row,
            text=self.tr("save"),
            command=save_changes,
            style="primary",
            width=12,
        )
        save_button.pack(side="left", padx=(0, 6))
        cancel_button = self.themed_button(
            button_row,
            text=self.tr("cancel"),
            command=close_dialog,
            width=12,
        )
        cancel_button.pack(side="left", padx=6)

        def refresh_category_editor_texts():
            dialog.title(self.tr("edit_categories"))
            hint.config(text=self.tr("category_editor_hint"))
            save_button.config(text=self.tr("save"))
            cancel_button.config(text=self.tr("cancel"))
            for button, key in editor_buttons:
                button.config(text=self.tr(key))
            refresh_category_list()

        category_list.bind("<<ListboxSelect>>", sync_selection)
        category_list.bind("<ButtonPress-1>", begin_category_drag)
        category_list.bind("<B1-Motion>", drag_category)
        category_list.bind("<ButtonRelease-1>", end_category_drag)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        self.category_editor_refresh = refresh_category_editor_texts
        refresh_category_editor_texts()

    # -----------------------------------------------------
    # SHARED UI HELPERS
    # -----------------------------------------------------

    # Used by checkbox clicks and drag/drop moves to flip a mod
    # between the enabled and disabled panels.
    def toggle_mod_enabled(self, mod):
        current = self.state["enabled"].get(mod, True)
        if current and not self.confirm_disable_active_mods([mod]):
            self.set_status_text("Disable cancelled for a mod active in the selected save.")
            return
        self.state["enabled"][mod] = not current
        self.refresh()
        self.schedule_save_state()

    def point_in_widget(self, widget, x_root, y_root):
        x1 = widget.winfo_rootx()
        y1 = widget.winfo_rooty()
        x2 = x1 + widget.winfo_width()
        y2 = y1 + widget.winfo_height()
        return x1 <= x_root <= x2 and y1 <= y_root <= y2

    # -----------------------------------------------------
    # SAVED APP STATE
    # -----------------------------------------------------

    def load_state(self):
        self.state, notices = load_state_file(
            STATE_FILE,
            APP_DIR,
            detect_default_language(IS_WINDOWS, ctypes),
            DEFAULT_CATEGORIES,
            normalize_hex_color,
        )
        for level, title, message in notices:
            if level == "warning":
                self.show_warning(title, message)

    def save_state(self):
        self.state["mods_path"] = self.mods_path.get().strip()
        self.state["view_mode"] = self.current_view_mode()
        save_state_file(self.state, STATE_FILE, APP_DIR)

    def schedule_save_state(self):
        if self.deferred_save_job is not None:
            return
        self.deferred_save_job = self.root.after_idle(self.flush_scheduled_save_state)

    def flush_scheduled_save_state(self):
        self.deferred_save_job = None
        self.save_state()

    def restore_drag_selection(self, side, mods):
        listbox = self.get_listbox_for_side(side)
        visible_mods = self.get_visible_mods_for_side(side)
        listbox.selection_clear(0, tk.END)
        first_selected_index = None

        for mod in mods:
            if mod in visible_mods:
                idx = visible_mods.index(mod)
                if first_selected_index is None:
                    first_selected_index = idx
                listbox.selection_set(idx)
                listbox.activate(idx)

        if first_selected_index is not None:
            self.set_selection_anchor_for_side(side, first_selected_index)

    # -----------------------------------------------------
    # PATH OVERRIDES / LAUNCH / LOADOUT FILES
    # -----------------------------------------------------

    def manual_path_entries(self):
        return [
            {
                "key": "manual_game_root",
                "label": "Game install folder",
                "kind": "dir",
                "current": self.detect_game_install_path,
                "detected": self.raw_detect_game_install_path,
            },
            {
                "key": "mods_path",
                "label": "Active mods folder",
                "kind": "dir",
                "current": lambda: self.mods_path.get().strip() or self.detect_best_mod_folder(),
                "detected": self.detect_best_mod_folder,
            },
            {
                "key": "manual_local_mods_path",
                "label": "Local mods folder",
                "kind": "dir",
                "current": self.detect_local_mod_folder,
                "detected": self.raw_detect_local_mod_folder,
            },
            {
                "key": "manual_workshop_mods_path",
                "label": "Workshop mods folder",
                "kind": "dir",
                "current": self.detect_workshop_mod_folder,
                "detected": self.raw_detect_workshop_mod_folder,
            },
            {
                "key": "selected_profile_path",
                "label": "Profile save file",
                "kind": "file",
                "current": lambda: self.selected_profile_path() or self.detect_latest_save_file(),
                "detected": lambda: max(
                    self.detected_save_files_from_disk(),
                    key=lambda path: os.path.getmtime(path),
                    default="",
                ),
            },
        ]

    def normalize_display_path(self, path):
        return normalize_saved_path(path)

    def browse_path_value(self, var, kind):
        current = self.normalize_display_path(var.get())
        initialdir = current
        if kind == "file" and current:
            parent = os.path.dirname(current)
            if os.path.isdir(parent):
                initialdir = parent
        if not os.path.isdir(initialdir):
            initialdir = os.path.expanduser("~")

        if kind == "file":
            path = filedialog.askopenfilename(
                title=self.tr("select_persist_game"),
                initialdir=initialdir,
                filetypes=[
                    (self.tr("darkest_dungeon_save"), "*persist.game.json"),
                    (self.tr("json_files"), "*.json"),
                    (self.tr("all_files"), "*.*"),
                ]
            )
        else:
            path = filedialog.askdirectory(initialdir=initialdir)

        if path:
            var.set(self.normalize_display_path(path))

    def save_manual_paths(self, values, dialog):
        self.state["manual_game_root"] = self.normalize_display_path(values["manual_game_root"].get())
        self.state["manual_local_mods_path"] = self.normalize_display_path(values["manual_local_mods_path"].get())
        self.state["manual_workshop_mods_path"] = self.normalize_display_path(values["manual_workshop_mods_path"].get())

        mods_path = self.normalize_display_path(values["mods_path"].get())
        self.mods_path.set(mods_path)

        selected_profile_path = self.normalize_display_path(values["selected_profile_path"].get())
        self.state["selected_profile_path"] = selected_profile_path
        if selected_profile_path:
            self.state["last_save_path"] = selected_profile_path

        self.save_state()
        self.refresh_profile_menu()

        if os.path.isdir(mods_path):
            self.load_mods()
        else:
            self.refresh()

        if selected_profile_path and os.path.isfile(selected_profile_path):
            self.set_status_translation("status_manual_paths_profile", path=selected_profile_path)
        elif mods_path:
            self.set_status_translation("status_manual_paths_mods", path=mods_path)
        else:
            self.set_status_translation("status_manual_paths")

        dialog.destroy()

    def open_paths_editor(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr("dialog_file_paths"))
        dialog.geometry("1020x380")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        self.themed_label(
            dialog,
            text=self.tr("paths_editor_heading"),
            style="heading"
        ).pack(anchor="w", padx=14, pady=(14, 4))
        self.themed_label(
            dialog,
            text=self.tr("paths_editor_hint"),
            style="muted"
        ).pack(anchor="w", padx=14, pady=(0, 12))

        values = {}
        grid = self.themed_frame(dialog)
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        grid.grid_columnconfigure(1, weight=1)

        for row_index, entry in enumerate(self.manual_path_entries()):
            self.themed_label(grid, text=entry["label"]).grid(row=row_index, column=0, sticky="w", padx=(0, 10), pady=6)
            var = tk.StringVar(value=self.normalize_display_path(entry["current"]()))
            values[entry["key"]] = var
            self.themed_entry(grid, textvariable=var).grid(row=row_index, column=1, sticky="ew", pady=6)
            self.themed_button(
                grid,
                text=self.tr("browse"),
                command=lambda current_var=var, current_kind=entry["kind"]: self.browse_path_value(current_var, current_kind)
            ).grid(row=row_index, column=2, padx=6, pady=6)
            self.themed_button(
                grid,
                text=self.tr("auto"),
                command=lambda current_var=var, detected=entry["detected"]: current_var.set(self.normalize_display_path(detected()))
            ).grid(row=row_index, column=3, padx=6, pady=6)
            self.themed_button(
                grid,
                text=self.tr("clear"),
                command=lambda current_var=var: current_var.set("")
            ).grid(row=row_index, column=4, padx=(6, 0), pady=6)

        button_row = self.themed_frame(dialog)
        button_row.pack(fill="x", padx=14, pady=(0, 14))
        self.themed_button(
            button_row,
            text=self.tr("save_file_paths"),
            command=lambda: self.save_manual_paths(values, dialog),
            style="primary"
        ).pack(side="left", padx=(0, 6))
        self.themed_button(button_row, text=self.tr("cancel"), command=dialog.destroy).pack(side="left", padx=6)

    def open_folder_in_file_manager(self, folder_path, title="Open Folder"):
        normalized_path = self.normalize_display_path(folder_path)
        if not normalized_path or not os.path.isdir(normalized_path):
            self.show_warning(title, "That folder is not set or no longer exists.")
            return False

        try:
            if IS_WINDOWS:
                os.startfile(normalized_path)
                return True

            commands = []
            if IS_LINUX:
                commands.append(["xdg-open", normalized_path])

            for command in commands:
                try:
                    subprocess.Popen(command)
                    return True
                except FileNotFoundError:
                    continue

            raise RuntimeError("No supported file manager launcher was found on this platform.")
        except Exception as e:
            self.show_error(title, f"Could not open this folder.\n\n{e}")
            return False

    def open_assigned_local_mods_folder(self):
        local_mods_path = self.detect_local_mod_folder()
        if self.open_folder_in_file_manager(local_mods_path, title="Open Local Mods"):
            self.set_status_text(f"Opened local mods folder: {local_mods_path}")

    # Launches Darkest Dungeon through Steam's URI handler.
    def launch_darkest_dungeon(self):
        steam_uri = "steam://rungameid/262060"
        try:
            if IS_WINDOWS:
                try:
                    os.startfile(steam_uri)
                    return
                except OSError:
                    pass

                game_root = self.detect_game_install_path()
                for executable_name in ("Darkest.exe", "DarkestDungeon.exe"):
                    candidate = os.path.join(game_root, executable_name)
                    if os.path.isfile(candidate):
                        os.startfile(candidate)
                        return

                raise RuntimeError(
                    "No Steam launcher or local Darkest Dungeon executable was found."
                )

            launch_commands = []
            if IS_LINUX:
                launch_commands.extend((
                    ["xdg-open", steam_uri],
                    ["steam", steam_uri],
                ))

            for command in launch_commands:
                try:
                    subprocess.Popen(command)
                    return
                except FileNotFoundError:
                    continue

            raise RuntimeError("No supported Steam launcher was found on this platform.")
        except Exception as e:
            self.show_error(
                "Launch Failed",
                f"Could not launch Darkest Dungeon through Steam.\n\n{e}"
            )

    # Exports the current mod order, enabled/disabled state,
    # and categories to a portable JSON loadout.
    def save_loadout(self):
        legacy_save_loadout(self, APP_DIR, filedialog)

    # Restores a saved loadout against the currently loaded mod list.
    # Missing mods are reported and newly discovered mods are preserved.
    def load_loadout(self):
        legacy_load_loadout(self, APP_DIR, filedialog)

    # -----------------------------------------------------
    # MOD FOLDER SELECTION
    # -----------------------------------------------------

    # Opens the manual path editor so users can override auto-detected
    # game, mods, Workshop, and profile-save paths when needed.
    def browse(self):
        self.open_paths_editor()

    def mod_folder_path(self, mod):
        mod_paths = self.state.get("mod_paths", {})
        path = mod_paths.get(mod)
        if path and os.path.isdir(path):
            return path
        return os.path.join(self.mods_path.get().strip(), mod)

    def get_current_mod_folders(self):
        path = self.mods_path.get().strip()
        if not os.path.isdir(path):
            return None

        roots = [path] + self.companion_mod_folders(path)
        mods = []
        mod_paths = {}
        seen = set()

        for root in roots:
            try:
                names = os.listdir(root)
            except Exception:
                continue

            for name in names:
                folder_path = os.path.join(root, name)
                if not os.path.isdir(folder_path):
                    continue
                if name in seen:
                    continue
                mods.append(name)
                mod_paths[name] = folder_path
                seen.add(name)

        self.state["mod_paths"] = mod_paths
        return sorted(mods, key=str.lower)

    # -----------------------------------------------------
    # LOADING MODS INTO THE APP
    # -----------------------------------------------------

    # Syncs saved state with what is actually on disk. Existing mods keep
    # their order/settings and brand-new ones get appended.
    def load_mods(self):
        load_start = time.perf_counter()
        self.update_startup_splash(self.tr("startup_gathering_mods"))
        stage_start = time.perf_counter()
        current_mods = self.get_current_mod_folders()
        self.record_startup_timing("load_mods.get_current_mod_folders", time.perf_counter() - stage_start)
        if current_mods is None:
            self.show_error("Error", "Invalid mods folder.")
            return

        saved_order = self.state.get("order", [])
        saved_categories = self.state.get("categories", {})
        saved_enabled = self.state.get("enabled", {})
        saved_metadata = self.state.get("metadata", {})

        new_mods = [m for m in current_mods if m not in saved_order]
        removed_mods = [m for m in saved_order if m not in current_mods]

        # Preserve saved ordering for existing mods, then append newly
        # discovered folders so they are easy to spot and categorize.
        merged_order = [m for m in saved_order if m in current_mods]
        merged_order.extend(new_mods)

        cleaned_categories = {
            mod: cat for mod, cat in saved_categories.items()
            if mod in current_mods
        }

        cleaned_enabled = {
            mod: enabled for mod, enabled in saved_enabled.items()
            if mod in current_mods
        }

        cleaned_metadata = {
            mod: meta for mod, meta in saved_metadata.items()
            if mod in current_mods
        }
        cleaned_nicknames = {
            mod: nickname for mod, nickname in self.state.get("nicknames", {}).items()
            if mod in current_mods and str(nickname).strip()
        }
        cleaned_mod_paths = {
            mod: path for mod, path in self.state.get("mod_paths", {}).items()
            if mod in current_mods
        }

        stage_start = time.perf_counter()
        for mod in current_mods:
            if mod not in cleaned_enabled:
                cleaned_enabled[mod] = False

            if not self.mod_metadata_is_fresh(mod, cleaned_metadata.get(mod, {})):
                cleaned_metadata[mod] = self.read_mod_metadata(mod)

            if mod not in cleaned_categories:
                recalled_category = self.recalled_mod_category(mod)
                if recalled_category:
                    cleaned_categories[mod] = recalled_category

            category = cleaned_categories.get(mod)
            if category:
                self.remember_mod_category(mod, category)
        self.record_startup_timing("load_mods.metadata_and_category_sync", time.perf_counter() - stage_start)

        self.state["order"] = merged_order
        self.state["categories"] = cleaned_categories
        self.state["enabled"] = cleaned_enabled
        self.state["nicknames"] = cleaned_nicknames
        self.state["metadata"] = cleaned_metadata
        self.state["mod_paths"] = cleaned_mod_paths
        self.preview_icon_path_cache = {
            mod: path for mod, path in self.preview_icon_path_cache.items()
            if mod in current_mods
        }
        self.preview_icon_image_cache = {
            key: image for key, image in self.preview_icon_image_cache.items()
            if key[0] in current_mods
        }
        stage_start = time.perf_counter()
        self.save_state()
        self.record_startup_timing("load_mods.save_state", time.perf_counter() - stage_start)
        self.update_startup_splash(self.tr("startup_loading_mod_icons", count=len(current_mods)))
        self.set_status_translation("startup_loading_mod_icons", count=len(current_mods))
        self.root.update_idletasks()
        if self.icons_enabled():
            self.timed_startup_call("load_mods.preload_preview_icons", self.preload_preview_icons, merged_order, max_size=self.preview_icon_size())
        auto_category_targets = [
            mod for mod in current_mods
            if mod in new_mods or cleaned_categories.get(mod, "Unassigned") in ("", "Unassigned", "All")
        ]
        if auto_category_targets:
            self.timed_startup_call(
                "load_mods.auto_categorize_mods",
                self.auto_categorize_mods,
                mods=auto_category_targets,
                include_already_attempted=False,
                show_summary=False,
                refresh_ui=False,
            )
        self.set_recent_new_mods(new_mods)
        self.rebuild_category_menus()
        self.timed_startup_call("load_mods.refresh", self.refresh)

        duplicate_groups = self.timed_startup_call("load_mods.detect_local_workshop_duplicates", self.detect_local_workshop_duplicates, current_mods)

        parts = [f"{len(current_mods)} mods loaded"]
        if new_mods:
            parts.append(f"{len(new_mods)} new")
        if removed_mods:
            parts.append(f"{len(removed_mods)} removed")
        if duplicate_groups:
            parts.append(f"{len(duplicate_groups)} possible duplicates")
        self.set_status_text(" | ".join(parts))
        self.show_or_queue_duplicate_warning(duplicate_groups)
        self.record_startup_timing("load_mods.total", time.perf_counter() - load_start)

    # -----------------------------------------------------
    # REFRESHING THE VISIBLE LISTS
    # -----------------------------------------------------

    # Rebuild both visible lists from current state, filter, and search text.
    def refresh(self):
        left_yview = self.disabled_listbox.yview() if hasattr(self, "disabled_listbox") else (0.0, 1.0)
        right_yview = self.enabled_listbox.yview() if hasattr(self, "enabled_listbox") else (0.0, 1.0)

        disabled_selection = self.disabled_listbox.curselection() if hasattr(self, "disabled_listbox") else ()
        enabled_selection = self.enabled_listbox.curselection() if hasattr(self, "enabled_listbox") else ()

        selected_disabled_mods = []
        selected_enabled_mods = []

        for index in disabled_selection:
            if 0 <= index < len(self.disabled_visible_mods):
                selected_disabled_mods.append(self.disabled_visible_mods[index])

        for index in enabled_selection:
            if 0 <= index < len(self.enabled_visible_mods):
                selected_enabled_mods.append(self.enabled_visible_mods[index])

        self.disabled_listbox.delete(0, tk.END)
        self.enabled_listbox.delete(0, tk.END)

        order = self.state.get("order", [])
        categories = self.state.get("categories", {})
        enabled_map = self.state.get("enabled", {})
        filter_value = self.current_filter_category()
        search_value = self.search_text.get().strip().lower()

        self.enabled_visible_mods = []
        self.disabled_visible_mods = []

        # Build the visible enabled/disabled lists from the single saved
        # order list so filtering never mutates the real load order.
        for mod in order:
            cat = categories.get(mod, "Unassigned")
            display_text = self.display_name_with_suffix(mod)
            display = display_text.lower()
            save_display = self.save_name(mod).lower()
            raw_name = mod.lower()
            meta = self.state.get("metadata", {}).get(mod, {})
            meta_title = str(meta.get("title", "")).lower()
            meta_id = str(meta.get("published_file_id", "")).lower()

            if filter_value != "All" and cat != filter_value:
                continue

            if search_value:
                if (
                    search_value not in display
                    and search_value not in save_display
                    and search_value not in raw_name
                    and search_value not in meta_title
                    and search_value not in meta_id
                ):
                    continue

            if enabled_map.get(mod, True):
                self.enabled_visible_mods.append(mod)
            else:
                self.disabled_visible_mods.append(mod)

        recent_new_mods = self.recent_new_mods
        if recent_new_mods:
            order_positions = {mod: index for index, mod in enumerate(order)}
            self.disabled_visible_mods.sort(key=lambda mod: (mod not in recent_new_mods, order_positions.get(mod, len(order))))
            self.enabled_visible_mods.sort(key=lambda mod: (mod not in recent_new_mods, order_positions.get(mod, len(order))))

        for i, mod in enumerate(self.disabled_visible_mods):
            cat = categories.get(mod, "Unassigned")
            is_new_or_uncategorized = mod not in categories
            is_recent_new = mod in recent_new_mods

            display_text = self.display_name_with_suffix(mod)
            label = f"[{self.category_label(cat)}]  {self.truncate_name(display_text)}"
            if is_new_or_uncategorized:
                label = f"+ {label}"
            if is_recent_new:
                label = f"NEW  {label}"

            self.disabled_listbox.insert(tk.END, label)
            self.disabled_listbox.itemconfig(i, fg=THEME["disabled"])
            if is_recent_new:
                self.disabled_listbox.itemconfig(i, bg=THEME["field"])

        for i, mod in enumerate(self.enabled_visible_mods):
            cat = categories.get(mod, "Unassigned")
            is_new_or_uncategorized = mod not in categories
            is_recent_new = mod in recent_new_mods

            display_text = self.display_name_with_suffix(mod)
            label = f"[{self.category_label(cat)}]  {self.truncate_name(display_text)}"
            if is_new_or_uncategorized:
                label = f"+ {label}"
            if is_recent_new:
                label = f"NEW  {label}"

            self.enabled_listbox.insert(tk.END, label)
            self.enabled_listbox.itemconfig(i, fg=self.category_color(cat))
            if is_recent_new:
                self.enabled_listbox.itemconfig(i, bg=THEME["field"])

        for i, mod in enumerate(self.disabled_visible_mods):
            if mod in selected_disabled_mods:
                self.disabled_listbox.selection_set(i)

        for i, mod in enumerate(self.enabled_visible_mods):
            if mod in selected_enabled_mods:
                self.enabled_listbox.selection_set(i)

        if self.disabled_listbox.size() > 0:
            self.disabled_listbox.yview_moveto(left_yview[0])

        if self.enabled_listbox.size() > 0:
            self.enabled_listbox.yview_moveto(right_yview[0])

        uncategorized_count = sum(1 for mod in order if mod not in categories)

        self.set_status_translation(
            "status_mod_summary",
            enabled=len(self.enabled_visible_mods),
            disabled=len(self.disabled_visible_mods),
            uncategorized=uncategorized_count,
        )
        self.schedule_icon_redraw()

    # -----------------------------------------------------
    # ENABLE / DISABLE PANEL ACTIONS
    # -----------------------------------------------------

    # Button and keyboard actions for moving selected mods between panels.
    # Disabling goes through the active-save warning before it commits.
    def enable_selected_from_left(self):
        selected_indices = self.disabled_listbox.curselection()
        if not selected_indices:
            return

        selected_mods = []
        for index in selected_indices:
            if 0 <= index < len(self.disabled_visible_mods):
                selected_mods.append(self.disabled_visible_mods[index])

        for mod in selected_mods:
            self.state["enabled"][mod] = True

        self.refresh()
        self.schedule_save_state()

        for mod in selected_mods:
            if mod in self.enabled_visible_mods:
                self.enabled_listbox.selection_set(self.enabled_visible_mods.index(mod))

    def disable_selected_from_right(self):
        selected_indices = self.enabled_listbox.curselection()
        if not selected_indices:
            return

        selected_mods = []
        for index in selected_indices:
            if 0 <= index < len(self.enabled_visible_mods):
                selected_mods.append(self.enabled_visible_mods[index])

        if not self.confirm_disable_active_mods(selected_mods):
            self.set_status_text("Disable cancelled for mods active in the selected save.")
            return

        for mod in selected_mods:
            self.state["enabled"][mod] = False

        self.refresh()
        self.schedule_save_state()

        for mod in selected_mods:
            if mod in self.disabled_visible_mods:
                self.disabled_listbox.selection_set(self.disabled_visible_mods.index(mod))

    def toggle_disabled_selected(self, event=None):
        self.enable_selected_from_left()

    def toggle_enabled_selected(self, event=None):
        self.disable_selected_from_right()

    # -----------------------------------------------------
    # CATEGORY MENU SUPPORT
    # -----------------------------------------------------

    # Right-click should grab the row under the mouse before opening the
    # category menu, even if it was not already selected.
    def show_disabled_menu(self, event):
        if not self.disabled_visible_mods:
            return

        index = self.disabled_listbox.nearest(event.y)
        if index < 0 or index >= len(self.disabled_visible_mods):
            return

        self.right_index = ("disabled", index)

        current_selection = self.disabled_listbox.curselection()
        if index not in current_selection:
            self.disabled_listbox.selection_clear(0, tk.END)
            self.disabled_listbox.selection_set(index)
            self.disabled_listbox.activate(index)

        self.prepare_mod_context_menu()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def show_enabled_menu(self, event):
        if not self.enabled_visible_mods:
            return

        index = self.enabled_listbox.nearest(event.y)
        if index < 0 or index >= len(self.enabled_visible_mods):
            return

        self.right_index = ("enabled", index)

        current_selection = self.enabled_listbox.curselection()
        if index not in current_selection:
            self.enabled_listbox.selection_clear(0, tk.END)
            self.enabled_listbox.selection_set(index)
            self.enabled_listbox.activate(index)

        self.prepare_mod_context_menu()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def prepare_mod_context_menu(self):
        if not hasattr(self, "menu"):
            return

        selected_mods = self.selected_mods_for_right_click_menu()
        can_open_workshop_page = (
            len(selected_mods) == 1
            and bool(self.workshop_id_for_mod(selected_mods[0]))
        )
        state = tk.NORMAL if can_open_workshop_page else tk.DISABLED
        self.menu.entryconfig(self.context_menu_workshop_index, state=state)

    def selected_mods_for_right_click_menu(self):
        if self.right_index is None:
            return []

        side, index = self.right_index
        if side == "enabled":
            selected_indices = self.enabled_listbox.curselection()
            source_list = self.enabled_visible_mods
        else:
            selected_indices = self.disabled_listbox.curselection()
            source_list = self.disabled_visible_mods

        if not selected_indices:
            selected_indices = (index,)

        selected_mods = []
        for current_index in selected_indices:
            if 0 <= current_index < len(source_list):
                selected_mods.append(source_list[current_index])
        return selected_mods

    def open_workshop_page_for_menu_selection(self):
        selected_mods = self.selected_mods_for_right_click_menu()
        if not selected_mods:
            return

        mod = selected_mods[0]
        workshop_id = self.workshop_id_for_mod(mod)
        if not workshop_id:
            self.show_warning(
                self.tr("no_workshop_page_title"),
                self.tr("no_workshop_page_body"),
            )
            return

        url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
        try:
            opened = webbrowser.open(url)
            if not opened and IS_WINDOWS and hasattr(os, "startfile"):
                os.startfile(url)
        except Exception as e:
            self.show_error(
                self.tr("open_workshop_page_error_title"),
                self.tr("open_workshop_page_error_body", error=e),
            )

    def set_category(self, cat):
        selected_mods = self.selected_mods_for_right_click_menu()

        if not selected_mods:
            return

        for mod in selected_mods:
            self.state["categories"][mod] = cat
            self.remember_mod_category(mod, cat)

        self.refresh()
        self.schedule_save_state()

    # -----------------------------------------------------
    # DRAG STATE HELPERS
    # -----------------------------------------------------

    # Shared drag/drop helpers for both listboxes.
    def get_mods_from_indices(self, side, indices):
        source = self.enabled_visible_mods if side == "enabled" else self.disabled_visible_mods
        mods = []
        for i in indices:
            if 0 <= i < len(source):
                mods.append(source[i])
        return mods

    def get_listbox_for_side(self, side):
        return self.enabled_listbox if side == "enabled" else self.disabled_listbox

    def get_visible_mods_for_side(self, side):
        return self.enabled_visible_mods if side == "enabled" else self.disabled_visible_mods

    def set_selection_anchor_for_side(self, side, index):
        listbox = self.get_listbox_for_side(side)
        visible = self.get_visible_mods_for_side(side)

        if not (0 <= index < len(visible)):
            return

        if side == "enabled":
            self.enabled_selection_anchor_index = index
        else:
            self.disabled_selection_anchor_index = index

        listbox.selection_anchor(index)

    def get_selection_anchor_for_side(self, side, fallback_index):
        visible = self.get_visible_mods_for_side(side)
        listbox = self.get_listbox_for_side(side)
        anchor = (
            self.enabled_selection_anchor_index
            if side == "enabled"
            else self.disabled_selection_anchor_index
        )

        if anchor is not None and 0 <= anchor < len(visible):
            return anchor

        selection = listbox.curselection()
        if selection:
            anchor = selection[0]
        else:
            anchor = fallback_index

        self.set_selection_anchor_for_side(side, anchor)
        return anchor

    def begin_drag(self, side, index, event):
        listbox = self.get_listbox_for_side(side)
        current_selection = listbox.curselection()

        if index in current_selection:
            selected_indices = list(current_selection)
        else:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            self.set_selection_anchor_for_side(side, index)
            listbox.activate(index)
            selected_indices = [index]

        self.drag_source = side
        self.drag_index = index
        self.drag_mod = self.get_visible_mods_for_side(side)[index]
        self.drag_selection = self.get_mods_from_indices(side, selected_indices)
        self.drag_selection_side = side
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.drag_active = False

    def ensure_drag_label(self, event):
        if self.drag_label is not None:
            return

        count = len(self.drag_selection)
        if count == 1:
            text = self.display_name(self.drag_selection[0])
        else:
            text = f"{count} mods"

        self.drag_label = tk.Label(
            self.root,
            text=text,
            bg=THEME["crimson"],
            fg=THEME["text_bright"],
            relief="solid",
            bd=1,
            padx=8,
            pady=4,
            font=FONT_BUTTON
        )
        self.drag_label.place(x=event.x_root - self.root.winfo_rootx() + 12,
                              y=event.y_root - self.root.winfo_rooty() + 12)

    def move_drag_label(self, event):
        if self.drag_label is not None:
            self.drag_label.place(
                x=event.x_root - self.root.winfo_rootx() + 12,
                y=event.y_root - self.root.winfo_rooty() + 12
            )

    def ensure_drag_indicator(self):
        if self.drag_indicator is not None:
            return
        self.drag_indicator = tk.Frame(
            self.root,
            bg=THEME["gold"],
            height=3,
            bd=0,
            highlightthickness=0,
        )

    def hide_drag_indicator(self):
        self.drag_target_side = None
        self.drag_target_index = None
        if self.drag_indicator is not None:
            self.drag_indicator.place_forget()

    def clear_drag_visuals(self):
        self.hide_drag_indicator()
        if self.drag_label is not None:
            self.drag_label.destroy()
            self.drag_label = None
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def drag_target_index_for_pointer(self, side, event):
        listbox = self.get_listbox_for_side(side)
        visible = self.get_visible_mods_for_side(side)

        if not self.point_in_widget(listbox, event.x_root, event.y_root):
            return None
        if not visible:
            return 0

        target_index = listbox.nearest(event.y)
        if not (0 <= target_index < len(visible)):
            return len(visible)

        bbox = listbox.bbox(target_index)
        if bbox:
            _, row_y, _, row_height = bbox
            if event.y >= row_y + row_height:
                return min(len(visible), target_index + 1)

        return target_index

    def show_drag_indicator_for_target(self, side, target_index):
        listbox = self.get_listbox_for_side(side)
        visible = self.get_visible_mods_for_side(side)

        self.ensure_drag_indicator()

        if not visible:
            indicator_y = 2
        elif target_index >= len(visible):
            bbox = listbox.bbox(len(visible) - 1)
            if not bbox:
                self.hide_drag_indicator()
                return
            _, row_y, _, row_height = bbox
            indicator_y = row_y + row_height - 1
        else:
            bbox = listbox.bbox(target_index)
            if not bbox:
                self.hide_drag_indicator()
                return
            _, row_y, _, _ = bbox
            indicator_y = row_y - 1

        self.drag_target_side = side
        self.drag_target_index = target_index
        self.drag_indicator.place(
            in_=listbox,
            x=2,
            y=max(1, indicator_y),
            width=max(10, listbox.winfo_width() - 4),
            height=3,
        )

    def update_drag_feedback(self, event):
        target_side = None
        if self.point_in_widget(self.disabled_listbox, event.x_root, event.y_root):
            target_side = "disabled"
        elif self.point_in_widget(self.enabled_listbox, event.x_root, event.y_root):
            target_side = "enabled"

        if target_side is None:
            self.hide_drag_indicator()
            return

        target_index = self.drag_target_index_for_pointer(target_side, event)
        if target_index is None:
            self.hide_drag_indicator()
            return

        if target_side == self.drag_source:
            visible = self.get_visible_mods_for_side(target_side)
            current_positions = [visible.index(m) for m in self.drag_selection if m in visible]
            if current_positions:
                low = min(current_positions)
                high = max(current_positions)
                if low <= target_index <= high:
                    self.hide_drag_indicator()
                    return

        self.show_drag_indicator_for_target(target_side, target_index)

    def clear_drag_state(self):
        self.drag_source = None
        self.drag_index = None
        self.drag_mod = None
        self.drag_active = False
        self.drag_selection = []
        self.drag_target_side = None
        self.drag_target_index = None
        self.drag_selection_side = None
        self.drag_pressed_selected_index = None
        self.drag_pressed_selected_side = None

        self.clear_drag_visuals()
        if self.drag_indicator is not None:
            self.drag_indicator.destroy()
            self.drag_indicator = None

    def reorder_visible_group(self, side, moved_mods, target_index, visible_mods=None):
        if visible_mods is None:
            visible_mods = self.get_visible_mods_for_side(side)
        side_set = set(visible_mods)

        remaining_visible = [m for m in visible_mods if m not in moved_mods]

        if target_index < 0:
            target_index = 0
        if target_index > len(remaining_visible):
            target_index = len(remaining_visible)

        new_visible = remaining_visible[:]
        for offset, mod in enumerate(moved_mods):
            new_visible.insert(target_index + offset, mod)

        full_order = self.state["order"][:]
        new_full = []
        vis_iter = iter(new_visible)

        # Replace only the visible slice for this side while preserving
        # relative positions for filtered-out or opposite-side mods.
        for mod in full_order:
            if mod in side_set:
                new_full.append(next(vis_iter))
            else:
                new_full.append(mod)

        self.state["order"] = new_full

    def finish_same_side_drag(self, side, event):
        visible = self.get_visible_mods_for_side(side)
        if self.drag_target_side == side and self.drag_target_index is not None:
            new_index = self.drag_target_index
        else:
            listbox = self.get_listbox_for_side(side)
            if not self.point_in_widget(listbox, event.x_root, event.y_root):
                return False
            new_index = self.drag_target_index_for_pointer(side, event)

        if new_index is None:
            return False

        current_positions = [visible.index(m) for m in self.drag_selection if m in visible]
        if current_positions:
            low = min(current_positions)
            high = max(current_positions)
            if low <= new_index <= high:
                return False

        self.reorder_visible_group(side, self.drag_selection, new_index)
        self.refresh()
        self.schedule_save_state()
        self.restore_drag_selection(side, self.drag_selection)
        return True

    # Shared move helper for buttons and drag/drop. Enabled -> disabled
    # moves respect the active-save warning before changing state.
    def move_selection_between_sides(self, from_side, to_side, moved_mods, target_index=None):
        if from_side == to_side:
            return

        if from_side == "enabled" and to_side == "disabled":
            if not self.confirm_disable_active_mods(moved_mods):
                self.set_status_text("Disable cancelled for mods active in the selected save.")
                return

        for mod in moved_mods:
            self.state["enabled"][mod] = (to_side == "enabled")
        visible_target = self.visible_mods_for_side_from_state(to_side)

        if target_index is None:
            target_index = len(visible_target)
        else:
            if target_index < 0:
                target_index = 0
            if target_index > len(visible_target):
                target_index = len(visible_target)

        self.reorder_visible_group(to_side, moved_mods, target_index, visible_mods=visible_target)
        self.refresh()
        self.schedule_save_state()

        self.restore_drag_selection(to_side, moved_mods)


    # -----------------------------------------------------
    # DRAG REORDERING / CROSS-PANEL DRAG
    # -----------------------------------------------------

    # Disabled-list mouse handlers mirror the enabled-list handlers below.
    # A click near the left edge toggles enablement; dragging reorders or
    # moves selected mods across panels.
    def on_disabled_click(self, event):
        index = self.disabled_listbox.nearest(event.y)
        if not (0 <= index < len(self.disabled_visible_mods)):
            self.clear_drag_state()
            return "break"

        mod = self.disabled_visible_mods[index]

        if event.x < 28:
            self.toggle_mod_enabled(mod)
            self.clear_drag_state()
            return "break"

        shift_held = bool(event.state & 0x0001)
        ctrl_held = bool(event.state & 0x0004)

        # SHIFT = grow the current highlighted span upward or downward
        # without dropping the rows that were already selected.
        if shift_held:
            anchor = self.get_selection_anchor_for_side("disabled", index)
            current_selection = list(self.disabled_listbox.curselection())

            if current_selection:
                start = min(current_selection[0], index)
                end = max(current_selection[-1], index)
            else:
                start = min(anchor, index)
                end = max(anchor, index)

            self.disabled_listbox.selection_clear(0, tk.END)
            for i in range(start, end + 1):
                self.disabled_listbox.selection_set(i)

            self.set_selection_anchor_for_side("disabled", anchor)
            self.disabled_listbox.activate(index)
            self.disabled_listbox.see(index)
            self.clear_drag_state()
            return "break"

        # CTRL = toggle item, and make it the new anchor
        if ctrl_held:
            if index in self.disabled_listbox.curselection():
                self.disabled_listbox.selection_clear(index)
            else:
                self.disabled_listbox.selection_set(index)

            self.set_selection_anchor_for_side("disabled", index)
            self.disabled_listbox.activate(index)
            self.clear_drag_state()
            return "break"

        # Plain click keeps an existing multi-selection intact when the
        # user clicks one of its rows to drag the whole group.
        current_selection = self.disabled_listbox.curselection()
        if index not in current_selection:
            self.disabled_listbox.selection_clear(0, tk.END)
            self.disabled_listbox.selection_set(index)
            self.set_selection_anchor_for_side("disabled", index)
            self.drag_pressed_selected_index = None
            self.drag_pressed_selected_side = None
        else:
            self.set_selection_anchor_for_side("disabled", index)
            self.drag_pressed_selected_index = index
            self.drag_pressed_selected_side = "disabled"
        self.disabled_listbox.activate(index)

        self.begin_drag("disabled", index, event)
        return "break"

    def on_disabled_drag(self, event):
        if self.drag_source != "disabled" or self.drag_mod is None:
            return "break"

        dx = abs(event.x_root - self.drag_start_x)
        dy = abs(event.y_root - self.drag_start_y)

        if not self.drag_active:
            if dx < 6 and dy < 6:
                return "break"
            self.drag_active = True
            self.ensure_drag_label(event)

        self.move_drag_label(event)
        self.update_drag_feedback(event)

        return "break"

    def on_disabled_release(self, event):
        if self.drag_mod is None:
            self.clear_drag_state()
            return "break"

        self.clear_drag_visuals()
        if self.drag_active:
            if self.drag_target_side == "enabled" and self.drag_target_index is not None:
                self.move_selection_between_sides("disabled", "enabled", self.drag_selection, self.drag_target_index)
            else:
                self.finish_same_side_drag("disabled", event)
        elif (
            not self.drag_active
            and self.drag_pressed_selected_side == "disabled"
            and self.drag_pressed_selected_index is not None
        ):
            index = self.drag_pressed_selected_index
            self.disabled_listbox.selection_clear(0, tk.END)
            self.disabled_listbox.selection_set(index)
            self.set_selection_anchor_for_side("disabled", index)
            self.disabled_listbox.activate(index)
            self.disabled_listbox.see(index)

        self.clear_drag_state()
        return "break"

    # Enabled-list handlers support Shift/Ctrl selection plus plain-click
    # dragging for reorder and cross-panel moves.
    def on_enabled_click(self, event):
        index = self.enabled_listbox.nearest(event.y)
        if not (0 <= index < len(self.enabled_visible_mods)):
            self.clear_drag_state()
            return "break"

        mod = self.enabled_visible_mods[index]

        if event.x < 28:
            self.toggle_mod_enabled(mod)
            self.clear_drag_state()
            return "break"

        shift_held = bool(event.state & 0x0001)
        ctrl_held = bool(event.state & 0x0004)

        # SHIFT = grow the current highlighted span upward or downward
        # without dropping the rows that were already selected.
        if shift_held:
            anchor = self.get_selection_anchor_for_side("enabled", index)
            current_selection = list(self.enabled_listbox.curselection())

            if current_selection:
                start = min(current_selection[0], index)
                end = max(current_selection[-1], index)
            else:
                start = min(anchor, index)
                end = max(anchor, index)

            self.enabled_listbox.selection_clear(0, tk.END)
            for i in range(start, end + 1):
                self.enabled_listbox.selection_set(i)

            self.set_selection_anchor_for_side("enabled", anchor)
            self.enabled_listbox.activate(index)
            self.enabled_listbox.see(index)
            self.clear_drag_state()
            return "break"

        # CTRL = toggle item, and make it the new anchor
        if ctrl_held:
            if index in self.enabled_listbox.curselection():
                self.enabled_listbox.selection_clear(index)
            else:
                self.enabled_listbox.selection_set(index)

            self.set_selection_anchor_for_side("enabled", index)
            self.enabled_listbox.activate(index)
            self.clear_drag_state()
            return "break"

        # Plain click keeps an existing multi-selection intact when the
        # user clicks one of its rows to drag the whole group.
        current_selection = self.enabled_listbox.curselection()
        if index not in current_selection:
            self.enabled_listbox.selection_clear(0, tk.END)
            self.enabled_listbox.selection_set(index)
            self.set_selection_anchor_for_side("enabled", index)
            self.drag_pressed_selected_index = None
            self.drag_pressed_selected_side = None
        else:
            self.set_selection_anchor_for_side("enabled", index)
            self.drag_pressed_selected_index = index
            self.drag_pressed_selected_side = "enabled"
        self.enabled_listbox.activate(index)

        self.begin_drag("enabled", index, event)
        return "break"

    def on_enabled_drag(self, event):
        if self.drag_source != "enabled" or self.drag_mod is None:
            return "break"

        dx = abs(event.x_root - self.drag_start_x)
        dy = abs(event.y_root - self.drag_start_y)

        if not self.drag_active:
            if dx < 6 and dy < 6:
                return "break"
            self.drag_active = True
            self.ensure_drag_label(event)

        self.move_drag_label(event)
        self.update_drag_feedback(event)

        return "break"

    def on_enabled_release(self, event):
        if self.drag_mod is None:
            self.clear_drag_state()
            return "break"

        self.clear_drag_visuals()
        if self.drag_active:
            if self.drag_target_side == "disabled" and self.drag_target_index is not None:
                self.move_selection_between_sides("enabled", "disabled", self.drag_selection, self.drag_target_index)
            else:
                self.finish_same_side_drag("enabled", event)
        elif (
            not self.drag_active
            and self.drag_pressed_selected_side == "enabled"
            and self.drag_pressed_selected_index is not None
        ):
            index = self.drag_pressed_selected_index
            self.enabled_listbox.selection_clear(0, tk.END)
            self.enabled_listbox.selection_set(index)
            self.set_selection_anchor_for_side("enabled", index)
            self.enabled_listbox.activate(index)
            self.enabled_listbox.see(index)

        self.clear_drag_state()
        return "break"

    # -----------------------------------------------------
    # AUTO SORT
    # -----------------------------------------------------

    # Sorts the saved order by category priority, then alphabetically
    # inside each category using sort_name().
    def auto_sort(self):
        order = self.state.get("order", [])

        if not order:
            self.show_warning("Warning", "No mods loaded.")
            return

        self.state["order"] = self.sorted_order_by_category(order)

        self.save_state()
        self.refresh()
        self.set_status_text("Auto-sorted by category. You can now fine-tune manually.")

    def auto_sort_silent(self):
        order = self.state.get("order", [])

        if not order:
            return

        self.state["order"] = self.sorted_order_by_category(order)

        self.save_state()
        self.refresh()

    # -----------------------------------------------------
    # MOD NICKNAMES
    # -----------------------------------------------------

    # Stores a UI-only nickname for one selected mod without changing
    # the mod folder, save identity, or metadata on disk.
    def rename_selected_mod(self):
        selected_enabled = self.enabled_listbox.curselection()
        selected_disabled = self.disabled_listbox.curselection()

        if len(selected_enabled) + len(selected_disabled) != 1:
            self.show_warning(self.tr("warning"), self.tr("select_one_mod_to_nickname"))
            return

        if selected_enabled:
            visible_index = selected_enabled[0]
            source_list = self.enabled_visible_mods
        else:
            visible_index = selected_disabled[0]
            source_list = self.disabled_visible_mods

        if not (0 <= visible_index < len(source_list)):
            return

        mod = source_list[visible_index]

        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr("dialog_set_nickname"))
        dialog.geometry("500x140")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        self.themed_label(
            dialog,
            text=self.tr("nickname"),
            style="heading"
        ).pack(pady=(15, 5))

        current_nickname = self.nickname_for_mod(mod)
        initial_text = current_nickname or self.display_name(mod)
        name_var = tk.StringVar(value=initial_text)
        entry = self.themed_entry(
            dialog,
            textvariable=name_var,
            width=50,
        )
        entry.pack(pady=5)
        entry.focus_set()
        entry.select_range(0, tk.END)

        def do_rename():
            nickname = " ".join(name_var.get().split())
            saved_nickname = self.nickname_for_mod(mod)
            default_display = self.display_name(mod)

            if nickname == initial_text:
                dialog.destroy()
                return

            if nickname == default_display and not saved_nickname:
                dialog.destroy()
                return

            if nickname == default_display:
                nickname = ""

            if nickname == saved_nickname:
                dialog.destroy()
                return

            try:
                nicknames = self.state.setdefault("nicknames", {})
                if nickname:
                    nicknames[mod] = nickname
                else:
                    nicknames.pop(mod, None)

                self.refresh()
                self.schedule_save_state()

                if self.state["enabled"].get(mod, True):
                    if mod in self.enabled_visible_mods:
                        new_index = self.enabled_visible_mods.index(mod)
                        self.enabled_listbox.selection_clear(0, tk.END)
                        self.enabled_listbox.selection_set(new_index)
                        self.enabled_listbox.activate(new_index)
                        self.enabled_listbox.see(new_index)
                else:
                    if mod in self.disabled_visible_mods:
                        new_index = self.disabled_visible_mods.index(mod)
                        self.disabled_listbox.selection_clear(0, tk.END)
                        self.disabled_listbox.selection_set(new_index)
                        self.disabled_listbox.activate(new_index)
                        self.disabled_listbox.see(new_index)

                if nickname:
                    self.set_status_translation("status_nickname_set", nickname=nickname)
                else:
                    self.set_status_translation("status_nickname_cleared")

                dialog.destroy()

            except Exception as e:
                self.show_error(self.tr("error"), self.tr("failed_save_nickname", error=e))

        button_row = self.themed_frame(dialog)
        button_row.pack(pady=12)

        self.themed_button(button_row, text=self.tr("save"), command=do_rename, style="primary").pack(side="left", padx=6)
        self.themed_button(button_row, text=self.tr("cancel"), command=dialog.destroy).pack(side="left", padx=6)

        entry.bind("<Return>", lambda event: do_rename())

    # -----------------------------------------------------
    # SAVE CODE GENERATION
    # -----------------------------------------------------

    # Builds a manual applied_ugcs_1_0 block for copy/paste fixes.
    def generate_save_code(self):
        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})

        enabled_mods = [mod for mod in order if enabled_map.get(mod, True)]

        if not enabled_mods:
            self.show_warning("Warning", "No enabled mods to generate.")
            return

        indent1 = "        "
        indent2 = "            "
        indent3 = "                "
        lines = []

        lines.append(f'{indent1}"applied_ugcs_1_0" : {{')
        for i, mod in enumerate(enabled_mods):
            mod_name, mod_source = self.save_identity_for_mod(mod)

            lines.append(f'{indent2}"{i}" : {{')
            lines.append(f'{indent3}"name" : "{mod_name}",')
            lines.append(f'{indent3}"source" : "{mod_source}"')
            if i == len(enabled_mods) - 1:
                lines.append(f'{indent2}}}')
            else:
                lines.append(f'{indent2}}},')
        lines.append(f'{indent1}}},')

        output = "\n".join(lines)

        dialog = tk.Toplevel(self.root)
        dialog.title("Generated Save Code")
        dialog.geometry("900x650")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)

        self.themed_label(
            dialog,
            text='Paste this applied_ugcs_1_0 block after "never_again".',
            style="heading"
        ).pack(anchor="w", padx=12, pady=(12, 6))

        text = tk.Text(
            dialog,
            wrap="none",
            bg=THEME["panel_deep"],
            fg=THEME["text_bright"],
            insertbackground=THEME["gold"],
            font=FONT_MONO
        )
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert("1.0", output)

        button_row = self.themed_frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(0, 12))

        def copy_all():
            dialog.clipboard_clear()
            dialog.clipboard_append(output)
            self.show_info("Copied", "Save code copied to clipboard.")

        self.themed_button(button_row, text="Copy to Clipboard", command=copy_all, style="primary").pack(side="left", padx=4)
        self.themed_button(button_row, text="Close", command=dialog.destroy).pack(side="left", padx=4)

    # -----------------------------------------------------
    # APPLYING LOAD ORDER TO FOLDERS
    # -----------------------------------------------------

    # Renames only non-Workshop mod folders with numeric prefixes that
    # reflect the current category priority and manual order. Workshop
    # mods keep their saved order inside this app, but are left alone on
    # disk so Steam-managed folders are not renamed or disconnected.
    def apply_order(self):
        path = self.mods_path.get().strip()
        if not os.path.isdir(path):
            self.show_error("Error", "Invalid mods folder.")
            return

        order = self.state.get("order", [])
        categories = self.state.get("categories", {})

        if not order:
            self.show_warning("Warning", "No mods loaded.")
            return

        priority = self.get_category_priority({
            "UI": 0,
            "Class Patch": 100,
            "Class": 200,
            "Skins": 300,
            "Quirks": 350,
            "Dungeons": 400,
            "Districts": 450,
            "Enemies": 500,
            "Trinkets": 600,
            "Unassigned": 700,
        }, fallback=600)

        rename_plan = []
        skipped_mods = []
        used_names = set()
        original_categories = dict(self.state.get("categories", {}))
        original_enabled = dict(self.state.get("enabled", {}))
        original_metadata = dict(self.state.get("metadata", {}))
        original_mod_paths = dict(self.state.get("mod_paths", {}))

        def is_workshop_mod_path(folder_path):
            if not folder_path:
                return False
            normalized = os.path.normcase(os.path.abspath(folder_path))
            workshop_fragment = os.path.normcase(
                os.path.join("steamapps", "workshop", "content", STEAM_APP_ID)
            )
            return workshop_fragment in normalized

        for i, mod in enumerate(order):
            current_path = self.mod_folder_path(mod)
            if not os.path.isdir(current_path):
                raise_path = current_path or os.path.join(path, mod)
                self.show_error(
                    "Error",
                    "Cannot apply order because a loaded mod folder is missing:\n\n"
                    f"{raise_path}\n\n"
                    "Reload mods and try again."
                )
                return

            if is_workshop_mod_path(current_path):
                skipped_mods.append(mod)
                continue

            cat = categories.get(mod, "Unassigned")
            base = priority.get(cat, 600)
            parent_dir = os.path.dirname(current_path)

            stripped_name = mod
            if "_" in mod[:5]:
                prefix, remainder = mod.split("_", 1)
                if prefix.isdigit():
                    stripped_name = remainder

            new_name = f"{base + i:04d}_{stripped_name}"

            candidate = new_name
            suffix = 1
            used_key = candidate.lower()
            while used_key in used_names:
                candidate = f"{base + i:04d}_{suffix}_{stripped_name}"
                used_key = candidate.lower()
                suffix += 1

            used_names.add(used_key)
            rename_plan.append({
                "old_name": mod,
                "final_name": candidate,
                "parent_dir": parent_dir,
                "old_path": current_path,
            })

        if not rename_plan:
            if skipped_mods:
                preview = "\n".join(self.display_name(mod) for mod in skipped_mods[:10])
                extra = ""
                if len(skipped_mods) > 10:
                    extra = f"\n...and {len(skipped_mods) - 10} more"
                self.show_info(
                    "No Local Mods To Rename",
                    "Apply Order only renames non-Workshop mods.\n\n"
                    "The currently loaded mods that were skipped are:\n\n"
                    f"{preview}{extra}"
                )
            else:
                self.show_warning("Warning", "No eligible local mods were found to rename.")
            return

        temp_pairs = []
        rename_token = app_timestamp()
        try:
            for item in rename_plan:
                old_name = item["old_name"]
                old_path = item["old_path"]
                parent_dir = item["parent_dir"]

                temp_name = f"__temp__{rename_token}__{old_name}"
                temp_path = os.path.join(parent_dir, temp_name)
                temp_counter = 2
                while os.path.exists(temp_path):
                    temp_name = f"__temp__{rename_token}__{temp_counter}__{old_name}"
                    temp_path = os.path.join(parent_dir, temp_name)
                    temp_counter += 1

                os.rename(old_path, temp_path)
                temp_pairs.append({
                    "old_path": old_path,
                    "temp_name": temp_name,
                    "temp_path": temp_path,
                    "parent_dir": parent_dir,
                })

            for i, item in enumerate(rename_plan):
                final_path = os.path.join(item["parent_dir"], item["final_name"])
                os.rename(temp_pairs[i]["temp_path"], final_path)

            rename_lookup = {
                item["old_name"]: {
                    "new_name": item["final_name"],
                    "new_path": os.path.join(item["parent_dir"], item["final_name"]),
                }
                for item in rename_plan
            }

            updated_categories = {}
            updated_enabled = {}
            updated_metadata = {}
            updated_mod_paths = {}
            updated_order = []

            for mod in order:
                rename_info = rename_lookup.get(mod)
                final_name = rename_info["new_name"] if rename_info else mod
                final_path = rename_info["new_path"] if rename_info else self.mod_folder_path(mod)

                if mod in original_categories:
                    updated_categories[final_name] = original_categories[mod]
                if mod in original_enabled:
                    updated_enabled[final_name] = original_enabled[mod]
                if mod in original_metadata:
                    updated_metadata[final_name] = original_metadata[mod]
                if final_path and os.path.isdir(final_path):
                    updated_mod_paths[final_name] = final_path
                updated_order.append(final_name)

            self.state["categories"] = updated_categories
            self.state["enabled"] = updated_enabled
            self.state["metadata"] = updated_metadata
            self.state["mod_paths"] = updated_mod_paths
            self.state["order"] = updated_order
            self.preview_icon_path_cache.clear()
            self.preview_icon_image_cache.clear()
            for mod, category in updated_categories.items():
                self.remember_mod_category(mod, category)
            self.save_state()
            self.refresh()

            if skipped_mods:
                preview = "\n".join(self.display_name(mod) for mod in skipped_mods[:10])
                extra = ""
                if len(skipped_mods) > 10:
                    extra = f"\n...and {len(skipped_mods) - 10} more"
                self.show_info(
                    "Done",
                    f"Renamed {len(rename_plan)} local mods.\n\n"
                    f"Skipped {len(skipped_mods)} Workshop mods:\n{preview}{extra}"
                )
            else:
                self.show_info("Done", f"Renamed {len(rename_plan)} local mods successfully.")

        except Exception as e:
            # Roll back any half-finished rename so the mods folder is not
            # left stranded in __temp__ names if one rename fails midway.
            for item in reversed(temp_pairs):
                temp_path = item["temp_path"]
                old_path = item["old_path"]
                if os.path.exists(temp_path) and not os.path.exists(old_path):
                    try:
                        os.rename(temp_path, old_path)
                    except Exception:
                        pass
            self.show_error("Error", f"Failed to apply order:\n\n{e}")


def main():
    process_start = time.perf_counter()
    ensure_app_storage()
    root = tk.Tk()
    # Keep the main window hidden until ModManager has built the full
    # interface so users see the splash card instead of a blank delay.
    root.withdraw()
    splash_start = time.perf_counter()
    splash = create_startup_splash(root, read_saved_language(STATE_FILE, IS_WINDOWS, ctypes))
    splash_time = time.perf_counter() - splash_start
    app_start = time.perf_counter()
    app = ModManager(root)
    app.record_startup_timing("main.create_startup_splash", splash_time)
    app.record_startup_timing("main.ModManager_init", time.perf_counter() - app_start)
    app.startup_splash = splash
    app.timed_startup_call("main.run_first_start_setup", app.run_first_start_setup, show_popup=False)
    update_start = time.perf_counter()
    root.update_idletasks()
    app.record_startup_timing("main.root.update_idletasks", time.perf_counter() - update_start)
    destroy_start = time.perf_counter()
    splash.destroy()
    app.record_startup_timing("main.splash.destroy", time.perf_counter() - destroy_start)
    deiconify_start = time.perf_counter()
    root.deiconify()
    app.record_startup_timing("main.root.deiconify", time.perf_counter() - deiconify_start)
    app.flush_startup_notifications()
    app.record_startup_timing("main.total_before_mainloop", time.perf_counter() - process_start)
    app.write_startup_profile()
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error = traceback.format_exc()
        crash_log_path = write_crash_log("Application startup failed.", error)
        detail = "Darkest Dungeon Mod Manager could not start.\n\n"
        if crash_log_path:
            detail += f"A crash log was written to:\n{crash_log_path}\n\n"
        detail += error
        try:
            messagebox.showerror("Startup Failed", detail)
        except Exception:
            pass
        raise
