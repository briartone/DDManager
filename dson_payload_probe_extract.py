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


def extract_applied_ugcs_tokens(tokens):
    results = []
    i = 0

    while i < len(tokens):
        t = tokens[i]

        if t["type"] == "STRING" and t["value"] == "applied_ugcs_1_0":
            i += 1

            while i < len(tokens):
                # expect "0", "1", "2", ...
                if tokens[i]["type"] != "STRING":
                    break

                entry_index = tokens[i]["value"]
                if not entry_index.isdigit():
                    break

                i += 1
                entry = {"index": entry_index}

                while i < len(tokens):
                    if tokens[i]["type"] == "STRING" and tokens[i]["value"] in ("name", "source"):
                        key = tokens[i]["value"]
                        i += 1

                        # skip non-STRING tokens until the next STRING value
                        while i < len(tokens) and tokens[i]["type"] != "STRING":
                            i += 1

                        if i < len(tokens):
                            entry[key] = tokens[i]["value"]
                            i += 1
                    else:
                        break

                results.append(entry)

        else:
            i += 1

    return results


def probe_payload(path_str, start=PAYLOAD_START, max_steps=260):
    raw = Path(path_str).read_bytes()

    print(f"File size: {len(raw)} bytes")
    print(f"Payload probe start: 0x{start:08X}")
    print()

    i = start
    step = 0
    tokens = []

    while i < len(raw) and step < max_steps:
        b = raw[i]

        # Try STRING first
        if is_printable_ascii(b):
            text, new_i = read_cstring(raw, i)
            if text is not None and len(text) >= 1:
                print(f"{step:03}  0x{i:08X}  STRING   {text!r}")
                tokens.append({
                    "offset": i,
                    "type": "STRING",
                    "value": text
                })
                i = new_i
                step += 1
                continue

        # Try U32 / F32
        if i + 4 <= len(raw):
            u32 = read_u32_le(raw, i)
            f32 = read_f32_le(raw, i)

            printed = False

            if 0 <= u32 <= 100000:
                print(f"{step:03}  0x{i:08X}  U32      {u32}")
                tokens.append({
                    "offset": i,
                    "type": "U32",
                    "value": u32
                })
                i += 4
                step += 1
                printed = True

            elif abs(f32) > 0 and abs(f32) < 1e10:
                print(f"{step:03}  0x{i:08X}  F32      {f32}")
                tokens.append({
                    "offset": i,
                    "type": "F32",
                    "value": f32
                })
                i += 4
                step += 1
                printed = True

            if printed:
                continue

        # fallback single byte
        print(f"{step:03}  0x{i:08X}  BYTE     0x{raw[i]:02X}")
        tokens.append({
            "offset": i,
            "type": "BYTE",
            "value": raw[i]
        })
        i += 1
        step += 1

    print()
    print("Extracted applied_ugcs_1_0 entries:")
    entries = extract_applied_ugcs_tokens(tokens)

    if not entries:
        print("  <none>")
    else:
        for entry in entries:
            idx = entry.get("index", "?")
            name = entry.get("name", "<missing>")
            source = entry.get("source", "<missing>")
            print(f'  {idx}: name="{name}" | source="{source}"')

    print()
    print(f"Total extracted entries: {len(entries)}")


if __name__ == "__main__":
    probe_payload(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")