import struct
from pathlib import Path

PAYLOAD_START = 0x580


def read_u32_le(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


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

    # allow trailing null terminator inside stored length
    body = raw_bytes[:-1] if raw_bytes[-1] == 0 else raw_bytes

    if not body:
        return False

    return all(32 <= b <= 126 for b in body)


def read_len_string_flexible(data, offset, max_len=200):
    """
    Try:
      [pad zeros 0..4][u32 length][ascii bytes, possibly including trailing null]
    """
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
            raw_str = raw_str[:-1]

        value = raw_str.decode("utf-8", errors="replace")
        return value, str_end

    return None, offset


def is_entry_index_string(s):
    return s.isdigit() and len(s) <= 3


def extract_applied_ugcs_structured(raw):
    i = PAYLOAD_START
    end = len(raw)

    # Find applied_ugcs_1_0
    while i < end:
        s, new_i = read_cstring(raw, i)
        if s == "applied_ugcs_1_0":
            i = new_i
            break
        if s is None:
            i += 1
        else:
            i = new_i
    else:
        raise ValueError("Could not find applied_ugcs_1_0")

    entries = []

    while i < end:
        s, new_i = read_cstring(raw, i)

        if s == "persistent_ugcs":
            break

        if s is None:
            i += 1
            continue

        if not is_entry_index_string(s):
            i = new_i
            continue

        entry = {"index": s}
        i = new_i

        while i < end:
            field_name, field_next = read_cstring(raw, i)

            if field_name is None:
                i += 1
                continue

            if field_name == "persistent_ugcs":
                entries.append(entry)
                return entries

            if is_entry_index_string(field_name):
                break

            if field_name in ("name", "source"):
                value, value_next = read_len_string_flexible(raw, field_next)
                if value is not None:
                    entry[field_name] = value
                    i = value_next
                    continue

            i = field_next

        entries.append(entry)

    return entries


def main(path_str):
    raw = Path(path_str).read_bytes()
    entries = extract_applied_ugcs_structured(raw)

    print("Structured applied_ugcs_1_0 entries:")
    for e in entries:
        print(
            f'  {e.get("index", "?")}: '
            f'name="{e.get("name", "<missing>")}" | '
            f'source="{e.get("source", "<missing>")}"'
        )

    print()
    print(f"Total extracted entries: {len(entries)}")


if __name__ == "__main__":
    main(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")