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


def probe_payload(path_str, start=PAYLOAD_START, max_steps=220):
    raw = Path(path_str).read_bytes()

    print(f"File size: {len(raw)} bytes")
    print(f"Payload probe start: 0x{start:08X}")
    print()

    i = start
    step = 0

    while i < len(raw) and step < max_steps:
        b = raw[i]

        # Try string first
        if is_printable_ascii(b):
            text, new_i = read_cstring(raw, i)
            if text is not None and len(text) >= 1:
                print(f"{step:03}  0x{i:08X}  STRING   {text!r}")
                i = new_i
                step += 1
                continue

        # Try u32
        if i + 4 <= len(raw):
            u32 = read_u32_le(raw, i)
            f32 = read_f32_le(raw, i)

            # Heuristic display
            printed = False

            # Small integers / lengths / flags
            if 0 <= u32 <= 100000:
                print(f"{step:03}  0x{i:08X}  U32      {u32}")
                i += 4
                step += 1
                printed = True

            # Float-ish values in a sane range
            elif abs(f32) > 0 and abs(f32) < 1e10:
                print(f"{step:03}  0x{i:08X}  F32      {f32}")
                i += 4
                step += 1
                printed = True

            if printed:
                continue

        # Single-byte fallback
        print(f"{step:03}  0x{i:08X}  BYTE     0x{raw[i]:02X}")
        i += 1
        step += 1


if __name__ == "__main__":
    probe_payload(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")