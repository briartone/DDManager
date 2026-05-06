import os
import html
import json
import math
import re
import shutil
import struct
import sys
import time
import traceback
import tkinter as tk
import xml.etree.ElementTree as ET
from datetime import datetime
from tkinter import colorchooser, filedialog, messagebox, simpledialog

# =========================================================
# Darkest Dungeon Mod Manager
# =========================================================

def get_app_root():
    # Frozen builds should keep state beside the executable instead of
    # inside the temporary extraction/runtime location.
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# App data lives in one folder beside this script so saves, backups,
# caches, and exported loadouts are easy to find together.
APP_ROOT = get_app_root()
APP_DIR = os.path.join(APP_ROOT, "DD Manager Data")
STATE_FILE = os.path.join(APP_DIR, "mod_state.json")
ICON_CACHE_DIR = os.path.join(APP_DIR, "icon_cache")
STARTUP_PROFILE_LOG = os.path.join(APP_DIR, "startup_profile.log")
STARTUP_PROFILING_ENABLED = False
STEAM_APP_ID = "262060"
DD_GAME_NAME = "DarkestDungeon"

# Category colors are used in the enabled list to make load
# order groups visually scannable.
CATEGORY_COLORS = {
    "UI": "#8FA6B8",
    "Districts": "#6D9C9A",
    "Dungeons": "#B88B4A",
    "Quirks": "#B26B7B",
    "Trinkets": "#C1A85D",
    "Enemies": "#B65A4D",
    "Class Patch": "#879B5B",
    "Class": "#A4B56C",
    "Skins": "#9D7A9A",
    "Unassigned": "#82786B",
}

CATEGORY_COLOR_CYCLE = [
    "#5F8B7E",
    "#A66A4A",
    "#7D8FB3",
    "#A46D8A",
    "#9F9153",
    "#5E7A52",
    "#B46A5B",
    "#6E8C9C",
]

DEFAULT_CATEGORIES = ["UI", "Districts", "Dungeons", "Quirks", "Trinkets", "Enemies", "Class Patch", "Class", "Skins"]

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

FONT_TITLE = ("Georgia", 20, "bold")
FONT_SUBTITLE = ("Georgia", 10, "italic")
FONT_HEADING = ("Georgia", 12, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_BUTTON = ("Segoe UI", 9, "bold")

VIEW_MODES = {
    "No Icons": {
        "list_font": ("Segoe UI", 14),
        "icon_size": 0,
        "icon_strip_width": 0,
    },
    "Compact": {
        "list_font": ("Segoe UI", 12),
        "icon_size": 28,
        "icon_strip_width": 32,
    },
    "Comfortable": {
        "list_font": ("Segoe UI", 16),
        "icon_size": 40,
        "icon_strip_width": 44,
    },
    "Visual": {
        "list_font": ("Segoe UI", 24),
        "icon_size": 52,
        "icon_strip_width": 56,
    },
}


# Centers transient windows like the startup splash so they appear
# immediately in a predictable place instead of popping in later.
def center_window(window, width, height):
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


# Shows a lightweight title card while the main app finishes startup.
# This covers the several-second delay before the full Tk UI appears.
# The splash is intentionally simple and text-only so startup stays
# reliable without extra asset dependencies.
def create_startup_splash(root):
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg=THEME["bg"])
    splash.attributes("-topmost", True)
    center_window(splash, 520, 220)

    outer = tk.Frame(
        splash,
        bg=THEME["border"],
        bd=0,
        highlightthickness=0,
    )
    outer.pack(fill="both", expand=True, padx=2, pady=2)

    panel = tk.Frame(splash, bg=THEME["panel"])
    panel.place(relx=0.5, rely=0.5, anchor="center", width=512, height=212)

    top_rule = tk.Frame(panel, bg=THEME["crimson"], height=3)
    top_rule.pack(fill="x", padx=18, pady=(18, 0))

    tk.Label(
        panel,
        text="Darkest Dungeon Mod Manager",
        bg=THEME["panel"],
        fg=THEME["text_bright"],
        font=("Georgia", 22, "bold"),
    ).pack(pady=(26, 6))

    status_label = tk.Label(
        panel,
        text="Loading save tools, profiles, and mod state...",
        bg=THEME["panel"],
        fg=THEME["muted"],
        font=FONT_BODY,
    )
    status_label.pack()
    splash._status_label = status_label

    tk.Label(
        panel,
        text="The hamlet is stirring...",
        bg=THEME["panel"],
        fg=THEME["gold"],
        font=("Georgia", 11, "italic"),
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


# Detects whether a resolved mod folder lives under Steam Workshop
# content. Path-based checks are safer than guessing from numeric names,
# because local copies in DarkestDungeon\mods can also contain IDs.
def is_workshop_content_path(folder_path):
    if not folder_path:
        return False
    try:
        normalized = os.path.normcase(os.path.abspath(folder_path))
    except Exception:
        return False
    workshop_fragment = os.path.normcase(
        os.path.join("steamapps", "workshop", "content", STEAM_APP_ID)
    )
    return workshop_fragment in normalized


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
    if "tooltip" in lowered or "tray_icon" in lowered:
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

    applied_meta2_index = dson_find_meta2_by_name(raw, header, meta2_entries, "applied_ugcs_1_0")
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
            raise ValueError("No mods are loaded. Load your mods folder before patching a save.")
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
            proceed = messagebox.askyesno(
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
            messagebox.showerror(
                "Cannot Patch Save",
                "The save writer could not rebuild the mod list metadata.\n\n"
                f"{e}"
            )
            return

        self.status_label.config(
            text=f"Patched {patched_count} enabled mods. Backup: {os.path.basename(backup_path)}"
        )
        messagebox.showinfo(
            "Save Ready",
            "Patched save written to the game's default file name.\n\n"
            f"Patched file:\n{file_path}\n\n"
            f"Backup created:\n{backup_path}\n\n"
            "You can launch Darkest Dungeon now without renaming or moving the file."
        )

    def patch_latest_save_file(self):
        latest = self.detect_latest_save_file()
        if not latest:
            messagebox.showwarning(
                "No Save Found",
                "I could not auto-detect a persist.game.json save file.\n\n"
                "Use Patch Save File and pick the save manually."
            )
            return

        proceed = messagebox.askyesno(
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
            messagebox.showwarning(
                "No Profile Selected",
                "Choose a profile from the profile menu first."
            )
            return

        proceed = messagebox.askyesno(
            "Patch Selected Profile?",
            "This will create a backup, then write the patched save back to:\n\n"
            f"{save_path}\n\n"
            "Continue?"
        )
        if proceed:
            self.patch_save_file_with_metadata(save_path)

    def restore_last_backup(self):
        backup_path = self.state.get("last_backup_path", "")
        save_path = self.state.get("last_save_path", "")

        if not backup_path or not save_path or not os.path.isfile(backup_path):
            messagebox.showwarning(
                "No Backup",
                "No previous save backup was found for this session."
            )
            return

        proceed = messagebox.askyesno(
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
            self.status_label.config(text=f"Restored backup: {os.path.basename(backup_path)}")
            messagebox.showinfo("Restored", f"Backup restored to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Restore Failed", f"Could not restore backup:\n\n{e}")

    # Main save-patching entry point used by the UI.
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
        roots = []
        for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env_name)
            if base:
                candidate = os.path.join(base, "Steam")
                if os.path.isdir(candidate):
                    roots.append(candidate)

        default = r"C:\Program Files (x86)\Steam"
        if os.path.isdir(default):
            roots.append(default)

        seen = set()
        unique_roots = []
        for root in roots:
            norm = os.path.normcase(os.path.abspath(root))
            if norm not in seen:
                unique_roots.append(root)
                seen.add(norm)
        return unique_roots

    def steam_library_roots(self):
        libraries = []
        for steam_root in self.steam_install_roots():
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
                library = match.group(1).replace("\\\\", "\\")
                if os.path.isdir(library):
                    libraries.append(library)

        seen = set()
        unique_libraries = []
        for library in libraries:
            norm = os.path.normcase(os.path.abspath(library))
            if norm not in seen:
                unique_libraries.append(library)
                seen.add(norm)
        return unique_libraries

    # Finds installed Darkest Dungeon game roots across Steam libraries.
    def candidate_game_folders(self):
        candidates = []
        for library in self.steam_library_roots():
            candidate = os.path.join(library, "steamapps", "common", DD_GAME_NAME)
            if os.path.isdir(candidate):
                candidates.append(candidate)

        seen = set()
        unique = []
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                unique.append(path)
                seen.add(norm)
        return unique

    def detect_game_install_path(self):
        candidates = self.candidate_game_folders()
        if not candidates:
            return ""
        return candidates[0]

    def candidate_local_mod_folders(self):
        candidates = []
        for game_root in self.candidate_game_folders():
            candidate = os.path.join(game_root, "mods")
            if os.path.isdir(candidate):
                candidates.append(candidate)

        seen = set()
        unique = []
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                unique.append(path)
                seen.add(norm)
        return unique

    def detect_local_mod_folder(self):
        candidates = self.candidate_local_mod_folders()
        if not candidates:
            return ""
        return candidates[0]

    def candidate_workshop_mod_folders(self):
        candidates = []
        for library in self.steam_library_roots():
            candidate = os.path.join(library, "steamapps", "workshop", "content", STEAM_APP_ID)
            if os.path.isdir(candidate):
                candidates.append(candidate)

        seen = set()
        unique = []
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                unique.append(path)
                seen.add(norm)
        return unique

    def detect_workshop_mod_folder(self):
        candidates = self.candidate_workshop_mod_folders()
        if not candidates:
            return ""
        return candidates[0]

    def candidate_mod_folders(self):
        candidates = []
        for candidate in self.candidate_workshop_mod_folders():
            candidates.append(candidate)
        for candidate in self.candidate_local_mod_folders():
            candidates.append(candidate)

        current = self.mods_path.get().strip()
        if current:
            candidates.insert(0, current)

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

    def detect_best_mod_folder(self):
        candidates = self.candidate_mod_folders()
        current = self.mods_path.get().strip()
        if current and os.path.isdir(current):
            return current
        if not candidates:
            return ""

        def folder_count(path):
            try:
                return sum(1 for name in os.listdir(path) if os.path.isdir(os.path.join(path, name)))
            except Exception:
                return 0

        return max(candidates, key=folder_count)

    def companion_mod_folders(self, primary_path):
        companions = []
        primary_norm = os.path.normcase(os.path.abspath(primary_path)) if primary_path else ""

        for library in self.steam_library_roots():
            for candidate in (
                os.path.join(library, "steamapps", "workshop", "content", STEAM_APP_ID),
                os.path.join(library, "steamapps", "common", DD_GAME_NAME, "mods"),
            ):
                if not os.path.isdir(candidate):
                    continue
                norm = os.path.normcase(os.path.abspath(candidate))
                if norm != primary_norm:
                    companions.append(candidate)

        seen = set()
        unique = []
        for path in companions:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                unique.append(path)
                seen.add(norm)
        return unique

    def detect_save_files(self):
        candidates = []

        last_save = self.state.get("last_save_path", "")
        if last_save:
            candidates.append(last_save)

        for steam_root in self.steam_install_roots():
            userdata = os.path.join(steam_root, "userdata")
            if not os.path.isdir(userdata):
                continue
            try:
                steam_users = os.listdir(userdata)
            except Exception:
                continue
            for steam_user in steam_users:
                remote = os.path.join(userdata, steam_user, STEAM_APP_ID, "remote")
                if not os.path.isdir(remote):
                    continue
                for root_dir, _, files in os.walk(remote):
                    if "persist.game.json" in files:
                        candidates.append(os.path.join(root_dir, "persist.game.json"))

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

    def profile_number_from_path(self, path):
        parts = os.path.normpath(path).split(os.sep)
        for part in reversed(parts):
            match = re.fullmatch(r"profile[_ -]?(\d+)", part, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def profile_sort_key(self, slot):
        number = slot.get("number")
        if number is None:
            return (9999, slot.get("path", "").lower())
        return (number, slot.get("path", "").lower())

    def profile_label(self, path):
        number = self.profile_number_from_path(path)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            mtime = "unknown date"

        if number is None:
            base = f"Unknown Profile - {mtime}"
        else:
            base = f"Profile {number} (slot {number + 1}) - {mtime}"

        parent = os.path.basename(os.path.dirname(path))
        return f"{base} [{parent}]"

    def detect_profile_slots(self):
        slots = []
        seen = set()
        for path in self.detect_save_files():
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            slots.append({
                "path": path,
                "number": self.profile_number_from_path(path),
                "label": self.profile_label(path),
            })
            seen.add(norm)
        return sorted(slots, key=self.profile_sort_key)

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
            self.status_label.config(text=f"Selected profile save: {path}")

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
            labels = ["No profiles found"]

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
        saves = self.detect_save_files()
        if not saves:
            return ""
        return max(saves, key=lambda path: os.path.getmtime(path))

    def autodetect_summary(self):
        latest_save = self.detect_latest_save_file()
        profiles = self.detect_profile_slots()
        return {
            "game_root": self.detect_game_install_path(),
            "local_mods": self.detect_local_mod_folder(),
            "workshop_mods": self.detect_workshop_mod_folder(),
            "best_mods": self.detect_best_mod_folder(),
            "latest_save": latest_save,
            "profile_count": len(profiles),
        }

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
                save_text = latest_save if latest_save else "No save file found"
                messagebox.showinfo(
                    "Auto Detect Complete",
                    f"Game install:\n{summary['game_root'] or 'Not found'}\n\n"
                    f"Local mods:\n{summary['local_mods'] or 'Not found'}\n\n"
                    f"Workshop mods:\n{summary['workshop_mods'] or 'Not found'}\n\n"
                    f"Active mods source:\n{mod_text}\n\n"
                    f"Latest save:\n{save_text}\n\n"
                    f"Profiles found: {summary['profile_count']}"
                )
            else:
                messagebox.showwarning(
                    "Nothing Found",
                    "I could not auto-detect a Darkest Dungeon install, mods folder, or save file.\n\n"
                    "Use Browse to select your mods folder manually."
                )

    # Startup path discovery always refreshes mods and profiles from disk
    # when Darkest Dungeon paths can be detected, so the app does not rely
    # on a manual Load Mods click just to see new Workshop or local mods.
    def run_first_start_setup(self, show_popup=True):
        setup_start = time.perf_counter()
        current_mods_path = self.mods_path.get().strip()
        if current_mods_path and os.path.isdir(current_mods_path):
            self.update_startup_splash("Loading mods from the detected folder...")
            self.timed_startup_call("run_first_start_setup.load_mods", self.load_mods)
            self.update_startup_splash("Scanning profile saves...")
            self.timed_startup_call("run_first_start_setup.refresh_profile_menu", self.refresh_profile_menu)
            latest_save = self.timed_startup_call("run_first_start_setup.detect_latest_save_file", self.detect_latest_save_file)
            if latest_save:
                self.state["last_save_path"] = latest_save
                self.save_state()
            self.status_label.config(
                text=(
                    f"Loaded mods from: {current_mods_path} | "
                    f"Profiles: {len(self.profile_slots)}"
                )
            )
            self.record_startup_timing("run_first_start_setup.total", time.perf_counter() - setup_start)
            return

        summary = self.autodetect_summary()
        mod_folder = summary["best_mods"]
        if mod_folder:
            self.mods_path.set(mod_folder)
            self.update_startup_splash("Detecting mods and preparing the load order...")
            self.timed_startup_call("run_first_start_setup.load_mods", self.load_mods)
            self.update_startup_splash("Scanning profile saves...")
            self.timed_startup_call("run_first_start_setup.refresh_profile_menu", self.refresh_profile_menu)
            self.status_label.config(
                text=(
                    f"Detected game: {summary['game_root'] or 'unknown'} | "
                    f"Using mods: {mod_folder} | "
                    f"Profiles: {summary['profile_count']}"
                )
            )
            if show_popup and not self.state.get("first_run_summary_shown"):
                messagebox.showinfo(
                    "Darkest Dungeon Detected",
                    f"Game install:\n{summary['game_root'] or 'Not found'}\n\n"
                    f"Local mods folder:\n{summary['local_mods'] or 'Not found'}\n\n"
                    f"Workshop mods folder:\n{summary['workshop_mods'] or 'Not found'}\n\n"
                    f"Using mods from:\n{mod_folder}\n\n"
                    f"Latest save:\n{summary['latest_save'] or 'Not found'}\n\n"
                    f"Profiles found: {summary['profile_count']}"
                )
                self.state["first_run_summary_shown"] = True
                self.save_state()
            self.record_startup_timing("run_first_start_setup.total", time.perf_counter() - setup_start)
            return

        self.update_startup_splash("Scanning profile saves...")
        self.timed_startup_call("run_first_start_setup.refresh_profile_menu", self.refresh_profile_menu)
        self.status_label.config(
            text="No Darkest Dungeon install was auto-detected. Choose your mods folder, then click Load Mods."
        )
        self.record_startup_timing("run_first_start_setup.total", time.perf_counter() - setup_start)

    def show_setup_diagnostics(self):
        summary = self.autodetect_summary()
        mods_path = self.mods_path.get().strip()
        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})
        enabled_count = sum(1 for mod in order if enabled_map.get(mod, True))
        metadata = self.state.get("metadata", {})
        metadata_count = sum(1 for mod in order if metadata.get(mod))
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

        lines = [
            f"App data folder writable: {'Yes' if state_ok else 'No'}",
            f"Game install: {summary['game_root'] or '(not found)'}",
            f"Local mods folder: {summary['local_mods'] or '(not found)'}",
            f"Workshop mods folder: {summary['workshop_mods'] or '(not found)'}",
            f"Mods folder valid: {'Yes' if mods_ok else 'No'}",
            f"Mods folder: {mods_path or '(not set)'}",
            f"Mods loaded: {len(order)}",
            f"Enabled mods: {enabled_count}",
            f"Metadata entries: {metadata_count}",
            f"Selected profile: {self.selected_profile.get()}",
            f"Selected profile path: {selected_profile_path or '(not selected)'}",
            f"Latest detected save: {latest_save or '(not found)'}",
            f"Detected profiles: {summary['profile_count']}",
            f"Save has applied_ugcs_1_0: {save_has_mod_block}",
            f"Last backup: {self.state.get('last_backup_path') or '(none)'}",
        ]
        messagebox.showinfo("Setup Check", "\n".join(lines))

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

        return messagebox.askyesno(
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
            messagebox.showwarning(
                "No Profile Selected",
                "Choose a profile from the profile menu first."
            )
            return

        if not self.state.get("order"):
            if os.path.isdir(self.mods_path.get().strip()):
                self.load_mods()
            else:
                messagebox.showwarning(
                    "No Mods Loaded",
                    "Load your mods folder before importing a profile's mod list."
                )
                return

        try:
            save_mod_names = self.save_applied_mod_names(save_path)
        except Exception as e:
            messagebox.showerror("Could Not Read Profile", f"Could not read active mods from this save:\n\n{e}")
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
        self.status_label.config(text=status)

        if missing_names:
            preview = "\n".join(missing_names[:10])
            extra = ""
            if len(missing_names) > 10:
                extra = f"\n...and {len(missing_names) - 10} more"
            messagebox.showwarning(
                "Profile Loaded With Missing Mods",
                "The profile was loaded, but some saved active mods were not found in the current mods folder.\n\n"
                f"{preview}{extra}"
            )
        else:
            messagebox.showinfo(
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
            "metadata_path": signature["metadata_path"],
            "project_mtime": signature["project_mtime"],
            "localization_signature": signature["localization_signature"],
            "workshop_timeupdated": signature["workshop_timeupdated"],
        }

        root = parse_xml_file_forgiving(project_path) if os.path.exists(project_path) else None
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
        self.root.title("Darkest Dungeon Mod Manager")
        self.root.geometry("1400x780")

        ensure_app_storage()

        self.mods_path = tk.StringVar()
        self.selected_profile = tk.StringVar(value="No profiles found")
        self.filter_category = tk.StringVar(value="All")
        self.search_text = tk.StringVar(value="")
        self.view_mode = tk.StringVar(value="Comfortable")
        self.state = {
            "mods_path": "",
            "last_save_path": "",
            "last_backup_path": "",
            "last_output_path": "",
            "selected_profile_path": "",
            "view_mode": "Comfortable",
            "order": [],
            "categories": {},
            "category_order": list(DEFAULT_CATEGORIES),
            "category_colors": {},
            "category_memory": {},
            "custom_categories": [],
            "enabled": {},
            "nicknames": {},
            "metadata": {},
            "mod_paths": {}
        }

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
        self.drag_label = None
        self.profile_slots = []
        self.profile_label_to_path = {}
        self.startup_splash = None
        self.search_refresh_job = None
        self.icon_redraw_job = None
        self.icon_load_job = None
        self.icon_load_queue = []
        self.icon_load_pending = set()
        self.preview_icon_path_cache = {}
        self.preview_icon_image_cache = {}
        self.preview_icon_refs = {"disabled": [], "enabled": []}
        self.pending_duplicate_groups = []
        self.workshop_update_cache = None
        self.startup_profile = []

        self.enabled_visible_mods = []
        self.disabled_visible_mods = []

        self.load_state()

        if self.state.get("mods_path"):
            self.mods_path.set(self.state["mods_path"])
        if self.state.get("view_mode") in VIEW_MODES:
            self.view_mode.set(self.state["view_mode"])

        self.build_ui()

    def update_startup_splash(self, message):
        update_startup_splash(self.startup_splash, message)

    # -----------------------------------------------------
    # STARTUP PROFILING (DEBUG TOGGLE)
    # -----------------------------------------------------
    # Leave this instrumentation in place so startup timings can be
    # re-enabled quickly during future troubleshooting.

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

    # Uses the same visible naming logic for sorting so Workshop-only
    # numeric folder names do not break alphabetical ordering.
    def sort_display_name(self, mod):
        nickname = self.nickname_for_mod(mod)
        if nickname:
            return html.unescape(nickname)

        meta = self.state.get("metadata", {}).get(mod, {})
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
        if not is_workshop_content_path(mod_path):
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
        return is_workshop_content_path(self.mod_folder_path(mod))

    def display_name(self, mod):
        nickname = self.nickname_for_mod(mod)
        if nickname:
            return html.unescape(nickname)

        meta = self.state.get("metadata", {}).get(mod, {})
        title = meta.get("title", "")
        published_id = meta.get("published_file_id", "")

        if title and title != mod:
            if mod.isdigit():
                return f"{title} [{mod}]"
            if published_id and published_id not in mod:
                return f"{title} [{published_id}]"
            return html.unescape(title)

        if "_" in mod[:5]:
            prefix, remainder = mod.split("_", 1)
            if prefix.isdigit():
                return html.unescape(remainder)
        return html.unescape(mod)

    def display_suffix(self, mod):
        meta = self.state.get("metadata", {}).get(mod, {})
        version_label = str(meta.get("version_label", "")).strip()
        updated_label = str(meta.get("updated_label", "")).strip()
        if version_label:
            return version_label
        return updated_label

    def display_name_with_suffix(self, mod):
        base = self.display_name(mod)
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

    # Returns the exact name/source pair that should be written into a
    # save. This intentionally follows the app's workshop-vs-local
    # metadata rules instead of re-reading project.xml with broader
    # matching logic.
    def save_identity_for_mod(self, mod_folder):
        metadata = self.state.setdefault("metadata", {}).get(mod_folder, {})
        if not self.mod_metadata_is_fresh(mod_folder, metadata):
            metadata = self.read_mod_metadata(mod_folder)
            self.state["metadata"][mod_folder] = metadata

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

        messagebox.showwarning("Possible Duplicate Mods", "\n".join(lines))

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
        categories = []
        seen = set()

        for cat in self.state.get("category_order", []):
            if cat and cat not in ("All", "Unassigned") and cat.lower() not in seen:
                categories.append(cat)
                seen.add(cat.lower())

        for cat in self.state.get("custom_categories", []):
            if cat and cat.lower() not in seen and cat not in ("All", "Unassigned"):
                categories.append(cat)
                seen.add(cat.lower())

        for cat in self.state.get("categories", {}).values():
            if cat and cat.lower() not in seen and cat not in ("All", "Unassigned"):
                categories.append(cat)
                seen.add(cat.lower())

        return categories

    def category_color(self, category):
        saved = self.state.get("category_colors", {})
        custom = normalize_hex_color(saved.get(category, ""))
        if custom:
            return custom
        return CATEGORY_COLORS.get(category, THEME["text_bright"])

    def default_color_for_new_category(self):
        used = {
            normalize_hex_color(color)
            for color in self.state.get("category_colors", {}).values()
            if normalize_hex_color(color)
        }
        for color in CATEGORY_COLOR_CYCLE:
            normalized = normalize_hex_color(color)
            if normalized and normalized not in used:
                return normalized
        return normalize_hex_color(CATEGORY_COLOR_CYCLE[0]) or THEME["text_bright"]

    def project_tag_values(self, mod):
        project_path = os.path.join(self.mod_folder_path(mod), "project.xml")
        if not os.path.exists(project_path):
            return []

        root = parse_xml_file_forgiving(project_path)
        if root is None:
            return []

        values = []
        seen = set()
        for elem in root.iter():
            if elem.tag.split("}", 1)[-1].lower() != "tags":
                continue

            text = re.sub(r"\s+", " ", "".join(elem.itertext())).strip()
            if not text:
                continue

            for part in re.split(r"[,/|]| {2,}", text):
                cleaned = html.unescape(part).strip()
                if cleaned and cleaned.lower() not in seen:
                    values.append(cleaned)
                    seen.add(cleaned.lower())

        return values

    def auto_category_scores(self, mod):
        scores = {cat: 0 for cat in DEFAULT_CATEGORIES}
        mod_path = self.mod_folder_path(mod)
        title_bits = " ".join([
            mod,
            self.save_name(mod),
            self.display_name(mod),
            self.state.get("metadata", {}).get(mod, {}).get("title", ""),
        ]).lower()
        raw_tags = self.project_tag_values(mod)
        tags = [tag.lower() for tag in raw_tags]

        ignore_tags = {
            "english", "korean", "japanese", "chinese", "russian",
            "spanish", "german", "french", "italian", "polish",
            "pets compatible", "com", "cc", "bc", "s-purple",
        }

        tag_rules = [
            ("UI", {"ui", "interface", "tooltip", "tooltips", "qol", "quality of life", "character_ui"}),
            ("Districts", {"district", "districts", "new district"}),
            ("Dungeons", {"dungeon", "dungeons", "new dungeon", "farmstead", "courtyard", "quest", "butcher's circus", "butchers circus"}),
            ("Quirks", {"quirk", "quirks", "disease", "diseases"}),
            ("Trinkets", {"trinket", "trinkets", "new trinkets"}),
            ("Enemies", {"monster", "monster mod", "monsters", "enemy", "enemies", "boss", "bosses", "new monsters", "new boss", "modded boss", "roaming boss"}),
            ("Class Patch", {"class tweaks", "patch", "compatibility", "rework"}),
            ("Class", {"class", "new class", "class mod", "character mod", "hero", "heroes"}),
            ("Skins", {"skin", "skins", "spriteset", "sprite", "reskin"}),
        ]

        for tag in tags:
            if tag in ignore_tags:
                continue
            for category, keywords in tag_rules:
                if tag in keywords:
                    scores[category] += 4

        if os.path.isdir(mod_path):
            def has_dir(name):
                return os.path.isdir(os.path.join(mod_path, name))

            if has_dir("trinkets"):
                scores["Trinkets"] += 4
            if has_dir("monsters"):
                scores["Enemies"] += 6
            if has_dir("dungeons"):
                scores["Dungeons"] += 5
            if has_dir("quirks") or has_dir("diseases"):
                scores["Quirks"] += 5
            if has_dir("upgrades") and any("district" in tag for tag in tags):
                scores["Districts"] += 5
            if any(has_dir(name) for name in ("panels", "overlays", "fe_flow", "cursors", "scrolls")):
                scores["UI"] += 4
            if has_dir("heroes"):
                tag_blob = " ".join(tags)
                title_patch_words = (
                    "patch", "addon", "add-on", "compatibility",
                    "rebalance", "rework", "fix", "fixes", "tweak", "tweaks"
                )
                title_has_patch_words = any(word in title_bits for word in title_patch_words)
                has_class_identity = any(word in tag_blob for word in ("new class", "class mod", "character mod", " class "))
                hero_children = []
                try:
                    hero_children = [
                        name for name in os.listdir(os.path.join(mod_path, "heroes"))
                        if os.path.isdir(os.path.join(mod_path, "heroes", name))
                    ]
                except Exception:
                    hero_children = []

                if any(word in tag_blob for word in ("skin", "skins", "sprite", "spriteset", "reskin")):
                    scores["Skins"] += 7
                elif has_class_identity and hero_children and not title_has_patch_words:
                    scores["Class"] += 8
                elif "class tweaks" in tag_blob and not has_class_identity:
                    scores["Class Patch"] += 7
                elif title_has_patch_words:
                    scores["Class Patch"] += 6
                elif hero_children:
                    scores["Class"] += 6

        if "tooltip" in title_bits or "ui" in title_bits:
            scores["UI"] += 5
        if "character_ui" in title_bits:
            scores["UI"] += 6
        if "roster" in title_bits or "stack" in title_bits or "size" in title_bits:
            scores["UI"] += 5
        if "skin" in title_bits or "sprite" in title_bits:
            scores["Skins"] += 2
        if "district" in title_bits:
            scores["Districts"] += 5
        if "dungeon" in title_bits or "quest" in title_bits or "butcher" in title_bits or "circus" in title_bits:
            scores["Dungeons"] += 3
        if "trinket" in title_bits:
            scores["Trinkets"] += 2
        if "quirk" in title_bits or "quirks" in title_bits:
            scores["Quirks"] += 6
        if "vermintide" in title_bits:
            scores["Dungeons"] += 6
        if "smouldering ruin" in title_bits or "smoldering ruin" in title_bits or "kraken society" in title_bits:
            scores["Districts"] += 6
        if "monster mod" in title_bits:
            scores["Enemies"] += 6

        return scores

    # Suggests one built-in category when tag/content heuristics produce a
    # strong enough signal; otherwise returns None so the mod stays manual.
    def suggested_category_for_mod(self, mod):
        scores = self.auto_category_scores(mod)
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_category, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0

        if best_score < 4:
            return None
        if best_category == "Dungeons" and best_score >= second_score:
            return best_category
        if best_category == "Class" and best_score > second_score:
            return best_category
        if best_score - second_score < 2:
            return None
        return best_category

    def auto_categorize_mods(self, mods=None, include_already_attempted=True, show_summary=True):
        order = self.state.get("order", [])
        if not order:
            messagebox.showwarning("Warning", "Load mods before auto-categorizing.")
            return

        attempted = self.state.setdefault("auto_category_attempted", {})
        target_mods = list(mods) if mods is not None else list(order)
        changed = []
        ambiguous = []

        for mod in target_mods:
            current = self.state.get("categories", {}).get(mod, "")
            if current and current not in ("", "Unassigned", "All"):
                continue
            if not include_already_attempted and attempted.get(mod):
                continue

            suggestion = self.suggested_category_for_mod(mod)
            attempted[mod] = True
            if suggestion:
                self.state["categories"][mod] = suggestion
                self.remember_mod_category(mod, suggestion)
                changed.append((mod, suggestion))
            else:
                ambiguous.append(mod)

        self.save_state()
        self.rebuild_category_menus()
        self.refresh()

        status = f"Auto-categorized {len(changed)} mods"
        if ambiguous:
            status += f" | {len(ambiguous)} still need review"
        self.status_label.config(text=status)

        if not show_summary:
            if changed:
                self.auto_sort_silent()
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

        messagebox.showinfo(
            "Auto Categorize",
            f"Assigned {len(changed)} mods.\n\n"
            f"{preview}"
            f"{ambiguous_text}"
        )
        return changed, ambiguous

    # Builds numeric sort buckets for all categories, including
    # custom categories that were added after the original defaults.
    def get_category_priority(self, base_priority, fallback=700):
        priority = dict(base_priority)
        categories = self.get_categories()
        for index, cat in enumerate(categories):
            if cat not in priority:
                priority[cat] = 1000 + index * 100

        priority.setdefault("Unassigned", fallback)
        return priority

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
        mode = self.view_mode.get().strip()
        return VIEW_MODES.get(mode, VIEW_MODES["Comfortable"])

    def list_font(self):
        return self.current_view_config()["list_font"]

    def preview_icon_size(self):
        return self.current_view_config()["icon_size"]

    def preview_icon_strip_width(self):
        return self.current_view_config()["icon_strip_width"]

    def icons_enabled(self):
        return self.preview_icon_strip_width() > 0 and self.preview_icon_size() > 0

    # Native Tk listbox text sits slightly low inside each row, so the
    # preview icon strip uses a small per-view offset to match it better.
    def preview_icon_vertical_offset(self):
        mode = self.view_mode.get().strip()
        offsets = {
            "No Icons": 0,
            "Compact": 2,
            "Comfortable": 3,
            "Visual": 3,
        }
        return offsets.get(mode, 2)

    def set_view_mode(self, mode):
        if mode not in VIEW_MODES:
            mode = "Comfortable"
        self.view_mode.set(mode)
        self.icon_load_queue.clear()
        self.icon_load_pending.clear()
        if self.icon_load_job is not None:
            try:
                self.root.after_cancel(self.icon_load_job)
            except Exception:
                pass
            self.icon_load_job = None
        self.apply_view_mode()
        if self.icons_enabled():
            self.preload_preview_icons(self.state.get("order", []), max_size=self.preview_icon_size())
        self.save_state()
        self.refresh()

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
        self.themed_label(
            title_block,
            "Darkest Dungeon Mod Manager",
            style="title",
            anchor="w"
        ).pack(anchor="w")
        self.themed_label(
            title_block,
            "Load Order Ledger",
            style="subtitle",
            anchor="w"
        ).pack(anchor="w")

        self.themed_button(
            title_frame,
            text="Launch Darkest Dungeon",
            command=self.launch_darkest_dungeon,
            style="primary"
        ).pack(side="right")

        divider = tk.Frame(self.root, bg=THEME["crimson"], height=2)
        divider.pack(fill="x", padx=14, pady=(6, 10))

        top = self.themed_frame(self.root)
        top.pack(fill="x", padx=14, pady=(8, 10))

        path_entry = self.themed_entry(
            top,
            textvariable=self.mods_path,
            width=100,
            bd=6
        )
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.themed_button(top, text="Browse", command=self.browse).pack(side="left", padx=4)
        self.themed_button(top, text="Auto Detect", command=self.run_auto_detect).pack(side="left", padx=4)

        profile_frame = self.themed_frame(self.root)
        profile_frame.pack(fill="x", padx=14, pady=(0, 10))

        self.themed_label(
            profile_frame,
            text="Profile:",
            style="heading"
        ).pack(side="left", padx=(0, 8))

        self.profile_menu = tk.OptionMenu(
            profile_frame,
            self.selected_profile,
            "No profiles found",
            command=self.select_profile
        )
        self.configure_option_menu(self.profile_menu)
        self.profile_menu.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.themed_button(profile_frame, text="Refresh", command=self.refresh_profile_menu).pack(side="left", padx=4)
        self.themed_button(profile_frame, text="Load Profile Mods", command=self.load_selected_profile_mods, style="primary").pack(side="left", padx=4)
        self.themed_button(profile_frame, text="Patch Selected Profile", command=self.patch_selected_profile_save, style="primary").pack(side="left", padx=4)

        action_frame = self.themed_frame(self.root)
        action_frame.pack(fill="x", padx=14, pady=(0, 10))

        self.themed_button(action_frame, text="Load Mods", command=self.load_mods).pack(side="left", padx=(0, 4))
        self.themed_button(action_frame, text="Save Loadout", command=self.save_loadout).pack(side="left", padx=4)
        self.themed_button(action_frame, text="Load Loadout", command=self.load_loadout).pack(side="left", padx=4)
        self.themed_button(action_frame, text="Patch Auto-Detected Save", command=self.patch_latest_save_file, style="primary").pack(side="left", padx=4)

        self.tools_menu = tk.Menubutton(
            action_frame,
            text="Tools",
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
            cursor="hand2",
        )
        self.tools_menu.pack(side="left", padx=4)
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
        self.tools_menu.menu.add_command(label="Patch Chosen Save", command=self.patch_save_file)
        self.tools_menu.menu.add_command(label="Generate Save Code", command=self.generate_save_code)
        self.tools_menu.menu.add_command(label="Apply Order to Local Mods", command=self.apply_order)
        self.tools_menu.menu.add_command(label="Restore Last Backup", command=self.restore_last_backup)
        self.tools_menu.menu.add_command(label="Check Setup", command=self.show_setup_diagnostics)

        filter_frame = self.themed_frame(self.root)
        filter_frame.pack(fill="x", padx=14, pady=(0, 8))

        self.themed_label(
            filter_frame,
            text="Filter:",
            style="heading"
        ).pack(side="left", padx=(0, 8))

        filter_options = ["All", "Unassigned"] + self.get_categories()

        self.filter_menu = tk.OptionMenu(
            filter_frame,
            self.filter_category,
            *filter_options,
            command=lambda _: self.refresh()
        )
        self.configure_option_menu(self.filter_menu)
        self.filter_menu.pack(side="left")

        self.themed_button(filter_frame, text="Edit Categories", command=self.add_category).pack(side="left", padx=(8, 0))

        self.themed_label(
            filter_frame,
            text="Search:",
            style="heading"
        ).pack(side="left", padx=(16, 8))

        search_entry = self.themed_entry(
            filter_frame,
            textvariable=self.search_text,
            bd=4,
            width=28
        )
        search_entry.pack(side="left")
        search_entry.bind("<KeyRelease>", self.schedule_search_refresh)

        self.themed_label(
            filter_frame,
            text="View:",
            style="heading"
        ).pack(side="left", padx=(16, 8))

        self.view_mode_menu = tk.OptionMenu(
            filter_frame,
            self.view_mode,
            *VIEW_MODES.keys(),
            command=self.set_view_mode
        )
        self.configure_option_menu(self.view_mode_menu)
        self.view_mode_menu.pack(side="left")

        info_frame = self.themed_frame(self.root)
        info_frame.pack(fill="x", padx=10, pady=(0, 6))

        self.status_label = self.themed_label(
            info_frame,
            text="Choose a mods folder or click Auto Detect.",
            style="muted",
            anchor="w",
        )
        self.status_label.pack(fill="x")

        list_action_frame = self.themed_frame(self.root)
        list_action_frame.pack(fill="x", padx=14, pady=(0, 8))

        self.themed_label(
            list_action_frame,
            text="List Actions:",
            style="heading"
        ).pack(side="left", padx=(0, 8))

        self.themed_button(list_action_frame, text="Auto Sort", command=self.auto_sort).pack(side="left", padx=4)
        self.themed_button(list_action_frame, text="Auto Categorize", command=self.auto_categorize_mods).pack(side="left", padx=4)
        self.themed_button(list_action_frame, text="Nickname Mod", command=self.rename_selected_mod).pack(side="left", padx=4)

        panels_frame = self.themed_frame(self.root)
        panels_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # LEFT PANEL - DISABLED
        left_frame = self.themed_frame(panels_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.themed_label(
            left_frame,
            text="Reserve",
            style="heading"
        ).pack(anchor="w", pady=(0, 6))

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

        self.themed_button(middle_frame, text="Enable >", command=self.enable_selected_from_left).pack(pady=(120, 8))
        self.themed_button(middle_frame, text="< Reserve", command=self.disable_selected_from_right).pack(pady=8)

        # RIGHT PANEL - ENABLED
        right_frame = self.themed_frame(panels_frame)
        right_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.themed_label(
            right_frame,
            text="Load Order",
            style="heading"
        ).pack(anchor="w", pady=(0, 6))

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
                    label=cat,
                    command=lambda c=cat: self.set_filter_category(c)
                )

        self.menu.delete(0, tk.END)
        for cat in self.get_categories():
            self.menu.add_command(label=cat, command=lambda c=cat: self.set_category(c))

    def set_filter_category(self, cat):
        self.filter_category.set(cat)
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
        dialog.geometry("620x430")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        self.themed_label(
            dialog,
            text="Categories",
            style="heading"
        ).pack(anchor="w", padx=12, pady=(12, 8))

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

        def refresh_category_list():
            category_list.delete(0, tk.END)
            for index, cat in enumerate(categories):
                suffix = "" if cat in custom_categories else " (Built-in)"
                category_list.insert(tk.END, f"{cat}{suffix}")
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

        def update_color_preview():
            _, cat = current_category()
            if cat is None:
                color_preview.config(text="No category", bg=THEME["panel_deep"])
                return
            color = normalize_hex_color(category_colors.get(cat, "")) or self.category_color(cat)
            color_preview.config(text=f"Color: {color}", bg=color)

        def move_category(delta):
            index, cat = current_category()
            if cat is None:
                return
            new_index = index + delta
            if not (0 <= new_index < len(categories)):
                return
            categories[index], categories[new_index] = categories[new_index], categories[index]
            selected_index["value"] = new_index
            refresh_category_list()

        def prompt_name(title, initial=""):
            value = simpledialog.askstring(title, "Category name:", parent=dialog, initialvalue=initial)
            if value is None:
                return None
            value = " ".join(value.strip().split())
            if not value:
                messagebox.showwarning("Warning", "Category name cannot be empty.", parent=dialog)
                return None
            if value.lower() in ("all", "unassigned"):
                messagebox.showwarning("Warning", f'"{value}" is reserved.', parent=dialog)
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
                messagebox.showwarning("Warning", "That category already exists.", parent=dialog)
                return
            categories.append(name)
            custom_categories.add(name)
            chosen_color = choose_category_color()
            category_colors[name] = chosen_color or self.default_color_for_new_category()
            selected_index["value"] = len(categories) - 1
            refresh_category_list()

        def rename_category():
            index, cat = current_category()
            if cat is None:
                return
            if cat not in custom_categories:
                messagebox.showinfo("Built-in Category", "Built-in categories can be reordered, but not renamed here.", parent=dialog)
                return

            name = prompt_name("Rename Category", initial=cat)
            if not name or name == cat:
                return
            if name.lower() in {value.lower() for value in categories if value != cat}:
                messagebox.showwarning("Warning", "That category already exists.", parent=dialog)
                return

            categories[index] = name
            custom_categories.remove(cat)
            custom_categories.add(name)
            if cat in category_colors:
                category_colors[name] = category_colors.pop(cat)
            original_name = renamed_categories.pop(cat, cat)
            renamed_categories[name] = original_name
            refresh_category_list()

        def remove_category():
            index, cat = current_category()
            if cat is None:
                return
            if cat not in custom_categories:
                messagebox.showinfo("Built-in Category", "Built-in categories cannot be removed here.", parent=dialog)
                return
            confirm = messagebox.askyesno(
                "Remove Category?",
                f'Remove "{cat}" and send any mods using it to Unassigned?',
                parent=dialog
            )
            if not confirm:
                return
            categories.pop(index)
            custom_categories.remove(cat)
            category_colors.pop(cat, None)
            selected_index["value"] = min(index, len(categories) - 1) if categories else None
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
            ("Up", lambda: move_category(-1), "secondary"),
            ("Down", lambda: move_category(1), "secondary"),
            ("Add", add_new_category, "secondary"),
            ("Rename", rename_category, "secondary"),
            ("Set Color", set_category_color, "secondary"),
            ("Reset Color", reset_category_color, "secondary"),
            ("Remove", remove_category, "warning"),
        ]
        for text, command, style in button_specs:
            self.themed_button(right, text=text, command=command, style=style).pack(fill="x", pady=4)

        hint = self.themed_label(
            dialog,
            text="Built-in categories can be reordered. Custom categories can also be renamed or removed.",
            style="muted",
            anchor="w",
            justify="left",
            wraplength=480,
        )
        hint.pack(fill="x", padx=12, pady=(0, 10))

        def save_changes():
            final_categories = list(categories)
            final_custom = [cat for cat in final_categories if cat not in DEFAULT_CATEGORIES]

            removed_custom = [cat for cat in self.state.get("custom_categories", []) if cat not in final_custom]
            renamed_pairs = [
                (old_cat, new_cat)
                for new_cat, old_cat in renamed_categories.items()
                if old_cat != new_cat
            ]

            for old_cat, new_cat in renamed_pairs:
                for mod, category in list(self.state.get("categories", {}).items()):
                    if category == old_cat:
                        self.state["categories"][mod] = new_cat
                memory = self.state.get("category_memory", {})
                for key, category in list(memory.items()):
                    if category == old_cat:
                        memory[key] = new_cat

            for removed_cat in removed_custom:
                if removed_cat in renamed_categories.values():
                    continue
                for mod, category in list(self.state.get("categories", {}).items()):
                    if category == removed_cat:
                        self.state["categories"].pop(mod, None)
                memory = self.state.get("category_memory", {})
                for key, category in list(memory.items()):
                    if category == removed_cat:
                        memory.pop(key, None)

            self.state["custom_categories"] = final_custom
            self.state["category_order"] = final_categories
            self.state["category_colors"] = {
                cat: normalize_hex_color(category_colors.get(cat, ""))
                for cat in final_categories
                if normalize_hex_color(category_colors.get(cat, ""))
            }

            current_filter = self.filter_category.get()
            valid_filters = {"All", "Unassigned"} | set(final_categories)
            if current_filter not in valid_filters:
                self.filter_category.set("All")

            self.save_state()
            self.rebuild_category_menus()
            self.refresh()
            self.status_label.config(text="Categories updated.")
            dialog.destroy()

        button_row = self.themed_frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(0, 12))

        self.themed_button(button_row, text="Save", command=save_changes, style="primary").pack(side="left", padx=(0, 6))
        self.themed_button(button_row, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

        category_list.bind("<<ListboxSelect>>", sync_selection)
        refresh_category_list()

    # -----------------------------------------------------
    # SHARED UI HELPERS
    # -----------------------------------------------------

    # Used by checkbox clicks and drag/drop moves to flip a mod
    # between the enabled and disabled panels.
    def toggle_mod_enabled(self, mod):
        current = self.state["enabled"].get(mod, True)
        if current and not self.confirm_disable_active_mods([mod]):
            self.status_label.config(text="Disable cancelled for a mod active in the selected save.")
            return
        self.state["enabled"][mod] = not current
        self.save_state()
        self.refresh()

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
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception as e:
                backup_state = os.path.join(APP_DIR, "mod_state.backup.json")
                try:
                    with open(backup_state, "r", encoding="utf-8") as f:
                        self.state = json.load(f)
                    messagebox.showwarning(
                        "State Recovered",
                        "The main state file could not be read, so the app loaded the backup state.\n\n"
                        f"Main file:\n{STATE_FILE}\n\n"
                        f"Original error:\n{e}"
                    )
                except Exception:
                    messagebox.showwarning(
                        "Warning",
                        f"Could not read state file.\n\n{STATE_FILE}\n\n{e}"
                    )

        self.state.setdefault("mods_path", "")
        self.state.setdefault("last_save_path", "")
        self.state.setdefault("last_backup_path", "")
        self.state.setdefault("last_output_path", "")
        self.state.setdefault("selected_profile_path", "")
        self.state.setdefault("first_run_summary_shown", False)
        self.state.setdefault("view_mode", "Comfortable")
        self.state.setdefault("order", [])
        self.state.setdefault("categories", {})
        self.state.setdefault("category_order", list(DEFAULT_CATEGORIES))
        self.state.setdefault("category_colors", {})
        self.state.setdefault("category_memory", {})
        self.state.setdefault("auto_category_attempted", {})
        self.state.setdefault("custom_categories", [])
        self.state.setdefault("enabled", {})
        self.state.setdefault("nicknames", {})
        self.state.setdefault("metadata", {})
        self.state.setdefault("mod_paths", {})
        self.state["category_colors"] = {
            category: normalize_hex_color(color)
            for category, color in self.state.get("category_colors", {}).items()
            if normalize_hex_color(color)
        }

        ordered = []
        seen_order = set()
        for cat in self.state.get("category_order", []):
            if cat and cat not in ("All", "Unassigned") and cat.lower() not in seen_order:
                ordered.append(cat)
                seen_order.add(cat.lower())
        self.state["category_order"] = ordered

        # Older state files may contain categories that are not in
        # DEFAULT_CATEGORIES. Keep them visible instead of dropping them.
        existing = {cat.lower() for cat in DEFAULT_CATEGORIES}
        existing.update(cat.lower() for cat in self.state["custom_categories"])
        for cat in self.state["categories"].values():
            if cat and cat not in ("All", "Unassigned") and cat.lower() not in existing:
                self.state["custom_categories"].append(cat)
                existing.add(cat.lower())

        order_seen = {cat.lower() for cat in self.state["category_order"]}
        for cat in DEFAULT_CATEGORIES:
            if cat.lower() not in order_seen:
                self.state["category_order"].append(cat)
                order_seen.add(cat.lower())
        for cat in self.state["custom_categories"]:
            if cat and cat.lower() not in order_seen:
                self.state["category_order"].append(cat)
                order_seen.add(cat.lower())
        for cat in self.state["categories"].values():
            if cat and cat not in ("All", "Unassigned") and cat.lower() not in order_seen:
                self.state["category_order"].append(cat)
                order_seen.add(cat.lower())

    def save_state(self):
        self.state["mods_path"] = self.mods_path.get().strip()
        self.state["view_mode"] = self.view_mode.get().strip() or "Comfortable"
        if os.path.exists(STATE_FILE):
            try:
                shutil.copy2(STATE_FILE, os.path.join(APP_DIR, "mod_state.backup.json"))
            except Exception:
                pass
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    # -----------------------------------------------------
    # STEAM LAUNCH / LOADOUT FILES
    # -----------------------------------------------------

    # Launches Darkest Dungeon through Steam's URI handler.
    def launch_darkest_dungeon(self):
        try:
            os.startfile("steam://rungameid/262060")
        except Exception as e:
            messagebox.showerror(
                "Launch Failed",
                f"Could not launch Darkest Dungeon through Steam.\n\n{e}"
            )

    # Exports the current mod order, enabled/disabled state,
    # and categories to a portable JSON loadout.
    def save_loadout(self):
        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})

        if not order:
            messagebox.showwarning("Warning", "No mods loaded.")
            return

        default_path = os.path.join(APP_DIR, "dd_mod_loadout.json")
        file_path = filedialog.asksaveasfilename(
            title="Save Mod Loadout",
            defaultextension=".json",
            initialfile=os.path.basename(default_path),
            initialdir=APP_DIR,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not file_path:
            return

        enabled_mods = [mod for mod in order if enabled_map.get(mod, True)]
        disabled_mods = [mod for mod in order if not enabled_map.get(mod, True)]

        loadout = {
            "mods_path": self.mods_path.get().strip(),
            "order": order,
            "enabled": {mod: enabled_map.get(mod, True) for mod in order},
            "enabled_mods": enabled_mods,
            "disabled_mods": disabled_mods,
            "category_memory": self.state.get("category_memory", {}),
            "nicknames": {
                mod: self.state.get("nicknames", {}).get(mod, "")
                for mod in order
                if self.nickname_for_mod(mod)
            },
            "categories": {
                mod: self.state.get("categories", {}).get(mod, "Unassigned")
                for mod in order
            }
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(loadout, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save loadout:\n\n{e}")
            return

        self.status_label.config(
            text=f"Loadout saved: {len(enabled_mods)} enabled | {len(disabled_mods)} disabled"
        )
        messagebox.showinfo("Saved", f"Loadout saved:\n{file_path}")

    # Restores a saved loadout against the currently loaded mod list.
    # Missing mods are reported and newly discovered mods are preserved.
    def load_loadout(self):
        current_order = self.state.get("order", [])

        if not current_order:
            messagebox.showwarning("Warning", "Load mods before loading a loadout.")
            return

        file_path = filedialog.askopenfilename(
            title="Load Mod Loadout",
            initialdir=APP_DIR,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                loadout = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read loadout:\n\n{e}")
            return

        loadout_order = loadout.get("order", [])
        loadout_enabled = loadout.get("enabled", {})

        if not isinstance(loadout_order, list) or not isinstance(loadout_enabled, dict):
            messagebox.showerror("Error", "That file does not look like a valid loadout.")
            return

        current_mods = set(current_order)
        missing_mods = [mod for mod in loadout_order if mod not in current_mods]
        restored_order = [mod for mod in loadout_order if mod in current_mods]
        new_mods = [mod for mod in current_order if mod not in restored_order]

        self.state["order"] = restored_order + new_mods

        for mod in current_order:
            if mod in loadout_enabled:
                self.state["enabled"][mod] = bool(loadout_enabled[mod])

        loadout_categories = loadout.get("categories", {})
        if isinstance(loadout_categories, dict):
            for mod, cat in loadout_categories.items():
                if mod in current_mods and cat:
                    self.state["categories"][mod] = cat
                    self.remember_mod_category(mod, cat)

        loadout_memory = loadout.get("category_memory", {})
        if isinstance(loadout_memory, dict):
            self.state.setdefault("category_memory", {}).update(loadout_memory)

        loadout_nicknames = loadout.get("nicknames", {})
        if isinstance(loadout_nicknames, dict):
            nicknames = self.state.setdefault("nicknames", {})
            for mod, nickname in loadout_nicknames.items():
                if mod in current_mods and str(nickname).strip():
                    nicknames[mod] = " ".join(str(nickname).split())

        self.save_state()
        self.rebuild_category_menus()
        self.refresh()

        restored_enabled = sum(
            1 for mod in self.state["order"]
            if self.state["enabled"].get(mod, True)
        )
        restored_disabled = len(self.state["order"]) - restored_enabled

        status = f"Loadout loaded: {restored_enabled} enabled | {restored_disabled} disabled"
        if missing_mods:
            status += f" | {len(missing_mods)} missing"

        self.status_label.config(text=status)

        if missing_mods:
            preview = "\n".join(missing_mods[:10])
            extra = ""
            if len(missing_mods) > 10:
                extra = f"\n...and {len(missing_mods) - 10} more"
            messagebox.showwarning(
                "Loadout Loaded With Missing Mods",
                f"Loaded what matched your current mod list.\n\nMissing from current mods:\n{preview}{extra}"
            )
        else:
            messagebox.showinfo("Loaded", f"Loadout loaded:\n{file_path}")

    # -----------------------------------------------------
    # MOD FOLDER SELECTION
    # -----------------------------------------------------

    # Lets the user select the folder that contains Darkest Dungeon mods.
    def browse(self):
        initialdir = self.mods_path.get().strip()
        if not os.path.isdir(initialdir):
            detected = self.detect_best_mod_folder()
            initialdir = detected if detected else os.path.expanduser("~")
        path = filedialog.askdirectory(initialdir=initialdir)
        if path:
            self.mods_path.set(path)
            self.save_state()
            self.load_mods()

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

    # Syncs the saved state with the folders currently on disk.
    # Existing mods keep their order/settings; new mods are appended.
    def load_mods(self):
        load_start = time.perf_counter()
        self.update_startup_splash("Gathering local and Workshop mods...")
        stage_start = time.perf_counter()
        current_mods = self.get_current_mod_folders()
        self.record_startup_timing("load_mods.get_current_mod_folders", time.perf_counter() - stage_start)
        if current_mods is None:
            messagebox.showerror("Error", "Invalid mods folder.")
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
        self.update_startup_splash(f"Loading {len(current_mods)} mods and preview icons...")
        self.status_label.config(text=f"Loading {len(current_mods)} mods and preview icons...")
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
            )
        self.timed_startup_call("load_mods.refresh", self.refresh)

        duplicate_groups = self.timed_startup_call("load_mods.detect_local_workshop_duplicates", self.detect_local_workshop_duplicates, current_mods)

        parts = [f"{len(current_mods)} mods loaded"]
        if new_mods:
            parts.append(f"{len(new_mods)} new")
        if removed_mods:
            parts.append(f"{len(removed_mods)} removed")
        if duplicate_groups:
            parts.append(f"{len(duplicate_groups)} possible duplicates")
        self.status_label.config(text=" | ".join(parts))
        self.show_or_queue_duplicate_warning(duplicate_groups)
        self.record_startup_timing("load_mods.total", time.perf_counter() - load_start)

    # -----------------------------------------------------
    # REFRESHING THE VISIBLE LISTS
    # -----------------------------------------------------

    # Rebuilds both listboxes from current state, filter, and search text.
    # This is display-only and should not mutate load order by itself.
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
        filter_value = self.filter_category.get()
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

        for i, mod in enumerate(self.disabled_visible_mods):
            cat = categories.get(mod, "Unassigned")
            is_new_or_uncategorized = mod not in categories

            display_text = self.display_name_with_suffix(mod)
            label = f"[{cat}]  {self.truncate_name(display_text)}"
            if is_new_or_uncategorized:
                label = f"+ {label}"

            self.disabled_listbox.insert(tk.END, label)
            self.disabled_listbox.itemconfig(i, fg=THEME["disabled"])

        for i, mod in enumerate(self.enabled_visible_mods):
            cat = categories.get(mod, "Unassigned")
            is_new_or_uncategorized = mod not in categories

            display_text = self.display_name_with_suffix(mod)
            label = f"[{cat}]  {self.truncate_name(display_text)}"
            if is_new_or_uncategorized:
                label = f"+ {label}"

            self.enabled_listbox.insert(tk.END, label)
            self.enabled_listbox.itemconfig(i, fg=self.category_color(cat))

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

        self.status_label.config(
            text=(
                f"{len(self.enabled_visible_mods)} enabled | "
                f"{len(self.disabled_visible_mods)} disabled | "
                f"{uncategorized_count} uncategorized/new"
            )
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

        self.save_state()
        self.refresh()

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
            self.status_label.config(text="Disable cancelled for mods active in the selected save.")
            return

        for mod in selected_mods:
            self.state["enabled"][mod] = False

        self.save_state()
        self.refresh()

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

    # Right-click handlers select the clicked row first, then open the
    # shared category assignment menu for one or many selected mods.
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

        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def set_category(self, cat):
        if self.right_index is None:
            return

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
        for i in selected_indices:
            if 0 <= i < len(source_list):
                selected_mods.append(source_list[i])

        if not selected_mods:
            return

        for mod in selected_mods:
            self.state["categories"][mod] = cat
            self.remember_mod_category(mod, cat)

        self.save_state()
        self.refresh()

    # -----------------------------------------------------
    # DRAG STATE HELPERS
    # -----------------------------------------------------

    # These helpers keep drag/drop code shared between the enabled and
    # disabled listboxes, including multi-selection moves.
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

    def begin_drag(self, side, index, event):
        listbox = self.get_listbox_for_side(side)
        current_selection = listbox.curselection()

        if index in current_selection:
            selected_indices = list(current_selection)
        else:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            listbox.selection_anchor(index)
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

    def clear_drag_state(self):
        self.drag_source = None
        self.drag_index = None
        self.drag_mod = None
        self.drag_active = False
        self.drag_selection = []
        self.drag_selection_side = None
        self.drag_pressed_selected_index = None
        self.drag_pressed_selected_side = None

        if self.drag_label is not None:
            self.drag_label.destroy()
            self.drag_label = None

    def reorder_visible_group(self, side, moved_mods, target_index):
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

    # Shared move helper for buttons and drag/drop. Enabled -> disabled
    # moves respect the active-save warning before changing state.
    def move_selection_between_sides(self, from_side, to_side, moved_mods, target_index=None):
        if from_side == to_side:
            return

        if from_side == "enabled" and to_side == "disabled":
            if not self.confirm_disable_active_mods(moved_mods):
                self.status_label.config(text="Disable cancelled for mods active in the selected save.")
                return

        for mod in moved_mods:
            self.state["enabled"][mod] = (to_side == "enabled")

        self.refresh()

        visible_target = self.get_visible_mods_for_side(to_side)

        if target_index is None:
            target_index = len(visible_target)
        else:
            if target_index < 0:
                target_index = 0
            if target_index > len(visible_target):
                target_index = len(visible_target)

        self.reorder_visible_group(to_side, moved_mods, target_index)
        self.save_state()
        self.refresh()

        target_listbox = self.get_listbox_for_side(to_side)
        target_listbox.selection_clear(0, tk.END)
        refreshed_visible = self.get_visible_mods_for_side(to_side)

        for mod in moved_mods:
            if mod in refreshed_visible:
                idx = refreshed_visible.index(mod)
                target_listbox.selection_set(idx)
                target_listbox.activate(idx) 


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

        # SHIFT = extend from Tk's internal anchor
        if shift_held:
            try:
                anchor = self.disabled_listbox.index("anchor")
            except Exception:
                anchor = index

            if anchor is None or anchor < 0:
                anchor = index

            start = min(anchor, index)
            end = max(anchor, index)

            self.disabled_listbox.selection_clear(0, tk.END)
            for i in range(start, end + 1):
                self.disabled_listbox.selection_set(i)

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

            self.disabled_listbox.selection_anchor(index)
            self.disabled_listbox.activate(index)
            self.clear_drag_state()
            return "break"

        # Plain click keeps an existing multi-selection intact when the
        # user clicks one of its rows to drag the whole group.
        current_selection = self.disabled_listbox.curselection()
        if index not in current_selection:
            self.disabled_listbox.selection_clear(0, tk.END)
            self.disabled_listbox.selection_set(index)
            self.disabled_listbox.selection_anchor(index)
            self.drag_pressed_selected_index = None
            self.drag_pressed_selected_side = None
        else:
            self.disabled_listbox.selection_anchor(index)
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

        if self.point_in_widget(self.disabled_listbox, event.x_root, event.y_root):
            new_index = self.disabled_listbox.nearest(event.y)
            visible = self.disabled_visible_mods

            if 0 <= new_index < len(visible):
                current_positions = [visible.index(m) for m in self.drag_selection if m in visible]
                if current_positions:
                    low = min(current_positions)
                    high = max(current_positions)
                    if low <= new_index <= high:
                        return "break"

                self.reorder_visible_group("disabled", self.drag_selection, new_index)
                self.save_state()
                self.refresh()

                self.disabled_listbox.selection_clear(0, tk.END)
                for mod in self.drag_selection:
                    if mod in self.disabled_visible_mods:
                        idx = self.disabled_visible_mods.index(mod)
                        self.disabled_listbox.selection_set(idx)
                        self.disabled_listbox.activate(idx)

        return "break"

    def on_disabled_release(self, event):
        if self.drag_mod is None:
            self.clear_drag_state()
            return "break"

        if self.drag_active and self.point_in_widget(self.enabled_listbox, event.x_root, event.y_root):
            target_index = self.enabled_listbox.nearest(event.y)
            if not (0 <= target_index <= len(self.enabled_visible_mods)):
                target_index = len(self.enabled_visible_mods)

            self.move_selection_between_sides("disabled", "enabled", self.drag_selection, target_index)
        elif (
            not self.drag_active
            and self.drag_pressed_selected_side == "disabled"
            and self.drag_pressed_selected_index is not None
        ):
            index = self.drag_pressed_selected_index
            self.disabled_listbox.selection_clear(0, tk.END)
            self.disabled_listbox.selection_set(index)
            self.disabled_listbox.selection_anchor(index)
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

        # SHIFT = extend from Tk's internal anchor
        if shift_held:
            try:
                anchor = self.enabled_listbox.index("anchor")
            except Exception:
                anchor = index

            if anchor is None or anchor < 0:
                anchor = index

            start = min(anchor, index)
            end = max(anchor, index)

            self.enabled_listbox.selection_clear(0, tk.END)
            for i in range(start, end + 1):
                self.enabled_listbox.selection_set(i)

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

            self.enabled_listbox.selection_anchor(index)
            self.enabled_listbox.activate(index)
            self.clear_drag_state()
            return "break"

        # Plain click keeps an existing multi-selection intact when the
        # user clicks one of its rows to drag the whole group.
        current_selection = self.enabled_listbox.curselection()
        if index not in current_selection:
            self.enabled_listbox.selection_clear(0, tk.END)
            self.enabled_listbox.selection_set(index)
            self.enabled_listbox.selection_anchor(index)
            self.drag_pressed_selected_index = None
            self.drag_pressed_selected_side = None
        else:
            self.enabled_listbox.selection_anchor(index)
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

        if self.point_in_widget(self.enabled_listbox, event.x_root, event.y_root):
            new_index = self.enabled_listbox.nearest(event.y)
            visible = self.enabled_visible_mods

            if 0 <= new_index < len(visible):
                current_positions = [visible.index(m) for m in self.drag_selection if m in visible]
                if current_positions:
                    low = min(current_positions)
                    high = max(current_positions)
                    if low <= new_index <= high:
                        return "break"

                self.reorder_visible_group("enabled", self.drag_selection, new_index)
                self.save_state()
                self.refresh()

                self.enabled_listbox.selection_clear(0, tk.END)
                for mod in self.drag_selection:
                    if mod in self.enabled_visible_mods:
                        idx = self.enabled_visible_mods.index(mod)
                        self.enabled_listbox.selection_set(idx)
                        self.enabled_listbox.activate(idx)

        return "break"

    def on_enabled_release(self, event):
        if self.drag_mod is None:
            self.clear_drag_state()
            return "break"

        if self.drag_active and self.point_in_widget(self.disabled_listbox, event.x_root, event.y_root):
            target_index = self.disabled_listbox.nearest(event.y)
            if not (0 <= target_index <= len(self.disabled_visible_mods)):
                target_index = len(self.disabled_visible_mods)

            self.move_selection_between_sides("enabled", "disabled", self.drag_selection, target_index)
        elif (
            not self.drag_active
            and self.drag_pressed_selected_side == "enabled"
            and self.drag_pressed_selected_index is not None
        ):
            index = self.drag_pressed_selected_index
            self.enabled_listbox.selection_clear(0, tk.END)
            self.enabled_listbox.selection_set(index)
            self.enabled_listbox.selection_anchor(index)
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
        categories = self.state.get("categories", {})

        if not order:
            messagebox.showwarning("Warning", "No mods loaded.")
            return

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

        self.state["order"] = sorted(
            order,
            key=lambda mod: (
                1 if categories.get(mod, "Unassigned") == "Unassigned" else 0,
                auto_sort_priority.get(categories.get(mod, "Unassigned"), 700),
                self.sort_name(mod)
            )
        )

        self.save_state()
        self.refresh()
        self.status_label.config(text="Auto-sorted by category. You can now fine-tune manually.")

    def auto_sort_silent(self):
        order = self.state.get("order", [])
        categories = self.state.get("categories", {})

        if not order:
            return

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

        self.state["order"] = sorted(
            order,
            key=lambda mod: (
                1 if categories.get(mod, "Unassigned") == "Unassigned" else 0,
                auto_sort_priority.get(categories.get(mod, "Unassigned"), 700),
                self.sort_name(mod)
            )
        )

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
            messagebox.showwarning("Warning", "Select exactly one mod to nickname.")
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
        dialog.title("Set Nickname")
        dialog.geometry("500x140")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        self.themed_label(
            dialog,
            text="Nickname:",
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

                self.save_state()
                self.refresh()

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
                    self.status_label.config(text=f'Nickname set: {nickname}')
                else:
                    self.status_label.config(text="Nickname cleared.")

                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save nickname:\n\n{e}")

        button_row = self.themed_frame(dialog)
        button_row.pack(pady=12)

        self.themed_button(button_row, text="Save", command=do_rename, style="primary").pack(side="left", padx=6)
        self.themed_button(button_row, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

        entry.bind("<Return>", lambda event: do_rename())

    # -----------------------------------------------------
    # SAVE CODE GENERATION
    # -----------------------------------------------------

    # Builds the safer manual save snippet for applied_ugcs_1_0 only.
    def generate_save_code(self):
        order = self.state.get("order", [])
        enabled_map = self.state.get("enabled", {})

        enabled_mods = [mod for mod in order if enabled_map.get(mod, True)]

        if not enabled_mods:
            messagebox.showwarning("Warning", "No enabled mods to generate.")
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
            font=("Consolas", 10)
        )
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert("1.0", output)

        button_row = self.themed_frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(0, 12))

        def copy_all():
            dialog.clipboard_clear()
            dialog.clipboard_append(output)
            messagebox.showinfo("Copied", "Save code copied to clipboard.")

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
            messagebox.showerror("Error", "Invalid mods folder.")
            return

        order = self.state.get("order", [])
        categories = self.state.get("categories", {})

        if not order:
            messagebox.showwarning("Warning", "No mods loaded.")
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
                messagebox.showerror(
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
                messagebox.showinfo(
                    "No Local Mods To Rename",
                    "Apply Order only renames non-Workshop mods.\n\n"
                    "The currently loaded mods that were skipped are:\n\n"
                    f"{preview}{extra}"
                )
            else:
                messagebox.showwarning("Warning", "No eligible local mods were found to rename.")
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
                messagebox.showinfo(
                    "Done",
                    f"Renamed {len(rename_plan)} local mods.\n\n"
                    f"Skipped {len(skipped_mods)} Workshop mods:\n{preview}{extra}"
                )
            else:
                messagebox.showinfo("Done", f"Renamed {len(rename_plan)} local mods successfully.")

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
            messagebox.showerror("Error", f"Failed to apply order:\n\n{e}")


def main():
    process_start = time.perf_counter()
    ensure_app_storage()
    root = tk.Tk()
    # Keep the main window hidden until ModManager has built the full
    # interface so users see the splash card instead of a blank delay.
    root.withdraw()
    splash_start = time.perf_counter()
    splash = create_startup_splash(root)
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
