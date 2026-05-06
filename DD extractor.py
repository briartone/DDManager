import struct
from pathlib import Path


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


def find_first_index(strings, target):
    for i, (_, s) in enumerate(strings):
        if s == target:
            return i
    return None


def extract_applied_ugcs_entries(strings):
    start_idx = find_first_index(strings, "applied_ugcs_1_0")
    end_idx = find_first_index(strings, "persistent_ugcs")

    if start_idx is None:
        raise ValueError("Could not find 'applied_ugcs_1_0' in printable strings.")

    if end_idx is None:
        raise ValueError("Could not find 'persistent_ugcs' in printable strings.")

    if end_idx <= start_idx:
        raise ValueError("'persistent_ugcs' appears before 'applied_ugcs_1_0'.")

    block = strings[start_idx + 1:end_idx]

    entries = []
    current_name = None
    current_source = None

    i = 0
    while i < len(block):
        _, s = block[i]

        if s == "name" and i + 1 < len(block):
            current_name = block[i + 1][1]
            i += 2
            continue

        if s == "source" and i + 1 < len(block):
            current_source = block[i + 1][1]
            i += 2

            if current_name is not None:
                entries.append({
                    "name": current_name,
                    "source": current_source
                })
                current_name = None
                current_source = None
            continue

        i += 1

    return entries, start_idx, end_idx


def main(path_str):
    path = Path(path_str)
    raw = path.read_bytes()
    strings = printable_strings(raw, min_len=4)

    entries, start_idx, end_idx = extract_applied_ugcs_entries(strings)

    print(f"File: {path}")
    print(f"Total printable strings: {len(strings)}")
    print(f"'applied_ugcs_1_0' string index: {start_idx}")
    print(f"'persistent_ugcs' string index: {end_idx}")
    print()

    print("Extracted applied_ugcs_1_0 entries:")
    for idx, entry in enumerate(entries):
        print(f'{idx:>3}: name="{entry["name"]}" | source="{entry["source"]}"')

    print()
    print(f"Total extracted entries: {len(entries)}")


if __name__ == "__main__":
    main(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")