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


def patch_swap_two_steam_ids(entries, idx_a, idx_b):
    a = entries[idx_a]
    b = entries[idx_b]

    a_name = get_field(a, "name")
    b_name = get_field(b, "name")
    a_source = get_field(a, "source")
    b_source = get_field(b, "source")

    if not all([a_name, b_name, a_source, b_source]):
        raise ValueError("Missing name/source field in selected entries.")

    if a_source["value"] != "Steam" or b_source["value"] != "Steam":
        raise ValueError("Selected entries are not both Steam entries.")

    if len(a_name["value"]) != len(b_name["value"]):
        raise ValueError("Steam IDs are not same length; refusing patch.")

    a_name["value"], b_name["value"] = b_name["value"], a_name["value"]


def patch_file_same_length_swap(input_path, output_path):
    raw = Path(input_path).read_bytes()
    applied_start, applied_end, entries = parse_applied_ugcs_with_layout(raw)

    original_fragment = raw[applied_start:applied_end]

    # Example: swap entry 8 and 9 IDs
    patch_swap_two_steam_ids(entries, 8, 9)

    rebuilt_fragment = build_applied_ugcs_fragment(entries)

    print(f"Original fragment length: {len(original_fragment)}")
    print(f"New fragment length:      {len(rebuilt_fragment)}")

    if len(original_fragment) != len(rebuilt_fragment):
        raise ValueError("Refusing to patch: new fragment length differs from original.")

    patched = bytearray(raw)
    patched[applied_start:applied_end] = rebuilt_fragment

    Path(output_path).write_bytes(patched)
    print(f"Patched test file written to: {output_path}")
    print("Swapped entry 8 and 9 Steam IDs.")


if __name__ == "__main__":
    input_file = r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json"
    output_file = r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.swaptest.json"
    patch_file_same_length_swap(input_file, output_file)