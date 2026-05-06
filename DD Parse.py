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


def probe_dson_file(path: str):
    p = Path(path)
    raw = p.read_bytes()

    print(f"File: {p}")
    print(f"Size: {len(raw)} bytes")
    print()

    # Strict JSON check
    first_non_ws = None
    for b in raw:
        if chr(b) not in " \t\r\n":
            first_non_ws = b
            break

    if first_non_ws == ord("{"):
        print("Looks like plain JSON text.")
    else:
        print("Does NOT look like plain JSON text.")
    print()

    # DSON doc mentions a 64-byte header.
    # We are NOT assuming exact field meanings yet — just probing.
    if len(raw) >= 64:
        print("First 64 bytes (header candidate):")
        print(raw[:64].hex(" ", 1))
        print()

        # Show first few 32-bit little-endian values for comparison
        print("Header as little-endian u32 values:")
        for i in range(0, 64, 4):
            value = read_u32_le(raw, i)
            print(f"  +0x{i:02X}: {value}")
        print()
    else:
        print("File too small to contain expected DSON header.")
        return

    # Pull printable strings to inspect likely keys/values
    strings = printable_strings(raw, min_len=4)

    print(f"Found {len(strings)} printable strings (length >= 4).")
    print("First 120 strings:")
    for off, s in strings[:120]:
        print(f"  0x{off:08X}: {s}")
    print()

    # Hunt for the keys you care about
    interesting = {
        "base_root",
        "applied_ugcs_1_0",
        "persistent_ugcs",
        "never_again",
        "presented_dlc",
        "Title",
        "PublishedFileId",
        "Steam",
        "mod_local_source",
    }

    print("Interesting strings:")
    found_any = False
    for off, s in strings:
        if s in interesting:
            found_any = True
            print(f"  0x{off:08X}: {s}")

    if not found_any:
        print("  None found.")
    print()

    # Tiny heuristic: show neighboring strings around applied_ugcs_1_0
    hits = [i for i, (_, s) in enumerate(strings) if s == "applied_ugcs_1_0"]
    if hits:
        print("Context around 'applied_ugcs_1_0':")
        for hit in hits:
            start = max(0, hit - 8)
            end = min(len(strings), hit + 20)
            print("----")
            for off, s in strings[start:end]:
                print(f"  0x{off:08X}: {s}")
    else:
        print("No 'applied_ugcs_1_0' string found in printable scan.")


if __name__ == "__main__":
    probe_dson_file(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")