import struct
from pathlib import Path

PAYLOAD_START = 0x580


def read_u32_le(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def read_f32_le(data, offset):
    return struct.unpack_from("<f", data, offset)[0]


def is_printable_ascii(b):
    return 32 <= b <= 126


def read_cstring(data, offset):
    end = offset
    while end < len(data) and data[end] != 0:
        if not is_printable_ascii(data[end]):
            return None, offset
        end += 1

    if end >= len(data):
        return None, offset

    text = data[offset:end].decode("utf-8", errors="replace")
    return text, end + 1


def tokenize_payload(raw, start=PAYLOAD_START, max_steps=500):
    i = start
    step = 0
    tokens = []

    while i < len(raw) and step < max_steps:
        b = raw[i]

        if is_printable_ascii(b):
            text, new_i = read_cstring(raw, i)
            if text is not None and len(text) >= 1:
                tokens.append({
                    "offset": i,
                    "type": "STRING",
                    "value": text
                })
                i = new_i
                step += 1
                continue

        if i + 4 <= len(raw):
            u32 = read_u32_le(raw, i)
            f32 = read_f32_le(raw, i)

            if 0 <= u32 <= 100000:
                tokens.append({
                    "offset": i,
                    "type": "U32",
                    "value": u32
                })
                i += 4
                step += 1
                continue

            elif abs(f32) > 0 and abs(f32) < 1e10:
                tokens.append({
                    "offset": i,
                    "type": "F32",
                    "value": f32
                })
                i += 4
                step += 1
                continue

        tokens.append({
            "offset": i,
            "type": "BYTE",
            "value": raw[i]
        })
        i += 1
        step += 1

    return tokens


def hex_dump_line(raw, start, count=32):
    chunk = raw[start:start + count]
    hex_part = " ".join(f"{b:02X}" for b in chunk)
    ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    return f"0x{start:08X}  {hex_part:<95}  {ascii_part}"


def dump_window(raw, center, before=16, after=48):
    start = max(0, center - before)
    end = min(len(raw), center + after)

    line_start = start - (start % 16)
    while line_start < end:
        print(hex_dump_line(raw, line_start, 16))
        line_start += 16


def find_applied_ugcs_indices(tokens):
    indices = []
    in_block = False

    for idx, t in enumerate(tokens):
        if t["type"] == "STRING" and t["value"] == "applied_ugcs_1_0":
            in_block = True
            continue

        if in_block and t["type"] == "STRING" and t["value"] == "persistent_ugcs":
            break

        if in_block and t["type"] == "STRING" and t["value"] in ("name", "source"):
            indices.append(idx)

    return indices


def main(path_str):
    path = Path(path_str)
    raw = path.read_bytes()
    tokens = tokenize_payload(raw)

    print(f"File: {path}")
    print(f"Token count: {len(tokens)}")
    print()

    field_indices = find_applied_ugcs_indices(tokens)

    for idx in field_indices:
        tok = tokens[idx]
        print("=" * 80)
        print(f"FIELD TOKEN: {tok['value']!r} at 0x{tok['offset']:08X}")

        # Show nearby tokens
        print("\nNearby tokens:")
        for j in range(max(0, idx - 3), min(len(tokens), idx + 8)):
            t = tokens[j]
            marker = ">>" if j == idx else "  "
            print(f"{marker} 0x{t['offset']:08X}  {t['type']:<6}  {t['value']}")

        # Show raw bytes around that field
        print("\nRaw bytes around field:")
        dump_window(raw, tok["offset"], before=16, after=64)
        print()

    print("=" * 80)
    print("Done.")


if __name__ == "__main__":
    main(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")