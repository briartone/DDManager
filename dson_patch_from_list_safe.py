import json
import struct
from pathlib import Path

PAYLOAD_START = 0x580


def read_u32_le(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def pack_u32_le(value):
    return struct.pack("<I", value)


def read_cstring(data, offset):
    end = offset
    while end < len(data) and data[end] != 0:
        end += 1
    if end >= len(data):
        return None, offset
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def looks_like_dd_string(raw_bytes):
    if not raw_bytes:
        return False
    body = raw_bytes[:-1] if raw_bytes[-1] == 0 else raw_bytes
    if not body:
        return False
    return all(32 <= b <= 126 for b in body)


def read_len_string_with_layout(data, offset, max_len=300):
    for pad in range(0, 5):
        len_off = offset + pad
        if len_off + 4 > len(data):
            continue

        strlen = read_u32_le(data, len_off)
        if strlen <= 0 or strlen > max_len:
            continue

        str_start = len_off + 4
        str_end = str_start + strlen
        if str_end > len(data):
            continue

        raw_str = data[str_start:str_end]
        if not looks_like_dd_string(raw_str):
            continue

        if raw_str and raw_str[-1] == 0:
            value = raw_str[:-1].decode("utf-8", errors="replace")
        else:
            value = raw_str.decode("utf-8", errors="replace")

        return value, str_end, pad, strlen

    return None, offset, None, None


def is_entry_index_string(s):
    return s.isdigit() and len(s) <= 3


def find_top_level_applied_block(raw):
    i = PAYLOAD_START
    end = len(raw)

    applied_start = None
    persistent_start = None

    while i < end:
        s, new_i = read_cstring(raw, i)
        if s is None:
            i += 1
            continue

        if s == "applied_ugcs_1_0" and applied_start is None:
            applied_start = i
        elif s == "persistent_ugcs" and applied_start is not None:
            persistent_start = i
            break

        i = new_i

    if applied_start is None:
        raise ValueError("Could not find top-level applied_ugcs_1_0")
    if persistent_start is None:
        raise ValueError("Could not find persistent_ugcs after applied_ugcs_1_0")

    return applied_start, persistent_start


def parse_applied_ugcs_with_layout(raw):
    applied_start, applied_end = find_top_level_applied_block(raw)

    i = applied_start
    block_name, i = read_cstring(raw, i)
    assert block_name == "applied_ugcs_1_0"

    entries = []

    while i < applied_end:
        s, new_i = read_cstring(raw, i)

        if s == "persistent_ugcs":
            break

        if s is None:
            i += 1
            continue

        if not is_entry_index_string(s):
            i = new_i
            continue

        entry = {
            "index": s,
            "fields": []
        }
        i = new_i

        while i < applied_end:
            field_name, field_next = read_cstring(raw, i)

            if field_name is None:
                i += 1
                continue

            if field_name == "persistent_ugcs":
                entries.append(entry)
                return applied_start, applied_end, entries

            if is_entry_index_string(field_name):
                break

            if field_name in ("name", "source"):
                value, value_next, pad, stored_strlen = read_len_string_with_layout(raw, field_next)
                if value is not None:
                    entry["fields"].append({
                        "field_name": field_name,
                        "value": value,
                        "pad": pad,
                        "stored_strlen": stored_strlen,
                    })
                    i = value_next
                    continue

            i = field_next

        entries.append(entry)

    return applied_start, applied_end, entries


def build_applied_ugcs_fragment(entries):
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
            out.extend(pack_u32_le(len(value_bytes)))
            out.extend(value_bytes)

    return bytes(out)


def get_field(entry, field_name):
    for f in entry["fields"]:
        if f["field_name"] == field_name:
            return f
    return None


def apply_new_list_same_length(entries, new_list):
    if len(entries) != len(new_list):
        raise ValueError(
            f"Entry count mismatch: save has {len(entries)}, new list has {len(new_list)}"
        )

    for entry, new_item in zip(entries, new_list):
        name_field = get_field(entry, "name")
        source_field = get_field(entry, "source")

        if name_field is None or source_field is None:
            raise ValueError(f"Entry {entry['index']} missing name/source field")

        new_name = new_item["name"]
        new_source = new_item["source"]

        if len(new_name) != len(name_field["value"]):
            raise ValueError(
                f"Name length mismatch at entry {entry['index']}: "
                f"{name_field['value']!r} ({len(name_field['value'])}) -> "
                f"{new_name!r} ({len(new_name)})"
            )

        if len(new_source) != len(source_field["value"]):
            raise ValueError(
                f"Source length mismatch at entry {entry['index']}: "
                f"{source_field['value']!r} ({len(source_field['value'])}) -> "
                f"{new_source!r} ({len(new_source)})"
            )

        name_field["value"] = new_name
        source_field["value"] = new_source


def load_new_list(json_path):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Replacement list JSON must be a list.")

    cleaned = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {i} is not an object.")
        if "name" not in item or "source" not in item:
            raise ValueError(f"Entry {i} must contain 'name' and 'source'.")
        cleaned.append({
            "name": str(item["name"]),
            "source": str(item["source"]),
        })

    return cleaned


def patch_file_from_list(input_path, replacement_json_path, output_path):
    raw = Path(input_path).read_bytes()
    new_list = load_new_list(replacement_json_path)

    applied_start, applied_end, entries = parse_applied_ugcs_with_layout(raw)
    original_fragment = raw[applied_start:applied_end]

    apply_new_list_same_length(entries, new_list)
    rebuilt_fragment = build_applied_ugcs_fragment(entries)

    print(f"Original fragment length: {len(original_fragment)}")
    print(f"New fragment length:      {len(rebuilt_fragment)}")

    if len(original_fragment) != len(rebuilt_fragment):
        raise ValueError("Refusing to patch: new fragment length differs from original.")

    patched = bytearray(raw)
    patched[applied_start:applied_end] = rebuilt_fragment
    Path(output_path).write_bytes(patched)

    print(f"Patched file written to: {output_path}")


if __name__ == "__main__":
    input_file = r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json"
    replacement_json = r"C:\Users\areas\OneDrive\Documents\DD Manager\replacement_list.json"
    output_file = r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.fromlist.json"
    patch_file_from_list(input_file, replacement_json, output_file)