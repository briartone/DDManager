import struct
from pathlib import Path


def read_u32_le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def printable_strings(data: bytes, min_len: int = 4):
    results = []
    current = bytearray()
    start = None

    for i, b in enumerate(data):
        if 32 <= b <= 126:
            if start is None:
                start = i
            current.append(b)
        else:
            if current and len(current) >= min_len:
                results.append((start, current.decode("utf-8", errors="replace")))
            current = bytearray()
            start = None

    if current and len(current) >= min_len:
        results.append((start, current.decode("utf-8", errors="replace")))

    return results


def hex_preview(data: bytes, max_len: int = 64):
    snippet = data[:max_len]
    return snippet.hex(" ", 1)


def parse_header_u32s(raw: bytes):
    if len(raw) < 64:
        raise ValueError("File too small for 64-byte DSON header.")
    return [read_u32_le(raw, i) for i in range(0, 64, 4)]


def candidate_offsets_from_header(values, file_size):
    candidates = set()

    # Always include header end as a known structural boundary
    candidates.add(64)

    for v in values:
        if 0 < v < file_size:
            candidates.add(v)

    candidates.add(file_size)
    return sorted(candidates)


def region_report(raw: bytes, start: int, end: int, label: str):
    block = raw[start:end]
    strings = printable_strings(block, min_len=4)

    print(f"{label}")
    print(f"  start: 0x{start:08X} ({start})")
    print(f"  end:   0x{end:08X} ({end})")
    print(f"  size:  {end - start} bytes")
    print(f"  hex:   {hex_preview(block, 64)}")

    if strings:
        print("  strings:")
        for rel_off, s in strings[:12]:
            abs_off = start + rel_off
            print(f"    0x{abs_off:08X}: {s}")
        if len(strings) > 12:
            print(f"    ... ({len(strings) - 12} more)")
    else:
        print("  strings: <none>")
    print()


def main(path_str):
    path = Path(path_str)
    raw = path.read_bytes()
    file_size = len(raw)

    print(f"File: {path}")
    print(f"Size: {file_size} bytes")
    print()

    header_values = parse_header_u32s(raw)

    print("Header u32 values:")
    for i, value in enumerate(header_values):
        print(f"  +0x{i*4:02X}: {value}")
    print()

    offsets = candidate_offsets_from_header(header_values, file_size)

    print("Candidate structural boundaries:")
    for off in offsets:
        print(f"  0x{off:08X} ({off})")
    print()

    # Report header separately
    region_report(raw, 0, 64, "Region 0: Header")

    # Report each candidate region between offsets
    for idx in range(len(offsets) - 1):
        start = offsets[idx]
        end = offsets[idx + 1]
        if start >= end:
            continue
        region_report(raw, start, end, f"Region {idx + 1}")

    # Bonus: report where your important strings live
    all_strings = printable_strings(raw, min_len=4)
    interesting = {
        "base_root",
        "applied_ugcs_1_0",
        "persistent_ugcs",
        "presented_dlc",
        "name",
        "source",
        "Steam",
        "mod_local_source",
    }

    print("Interesting strings in full file:")
    found = False
    for off, s in all_strings:
        if s in interesting:
            found = True
            print(f"  0x{off:08X}: {s}")

    if not found:
        print("  <none>")
    print()


if __name__ == "__main__":
    main(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")