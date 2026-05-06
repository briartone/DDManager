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


def find_first_index(strings, target, start=0):
    for i in range(start, len(strings)):
        if strings[i][1] == target:
            return i
    return None


def extract_name_source_entries(block):
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

    return entries


def extract_applied_ugcs(strings):
    start_idx = find_first_index(strings, "applied_ugcs_1_0")
    end_idx = find_first_index(strings, "persistent_ugcs")

    if start_idx is None or end_idx is None or end_idx <= start_idx:
        raise ValueError("Could not isolate top-level applied_ugcs_1_0 block.")

    block = strings[start_idx + 1:end_idx]
    return extract_name_source_entries(block), start_idx, end_idx


def extract_persistent_ugcs(strings):
    persistent_idx = find_first_index(strings, "persistent_ugcs")
    presented_idx = find_first_index(strings, "presented_dlc", start=persistent_idx or 0)

    if persistent_idx is None or presented_idx is None or presented_idx <= persistent_idx:
        raise ValueError("Could not isolate persistent_ugcs block.")

    nested_applied_idx = find_first_index(strings, "applied_ugcs_1_0", start=persistent_idx + 1)
    if nested_applied_idx is None or nested_applied_idx >= presented_idx:
        # If there is no nested applied_ugcs_1_0, treat as empty
        return [], persistent_idx, presented_idx

    block = strings[nested_applied_idx + 1:presented_idx]
    return extract_name_source_entries(block), nested_applied_idx, presented_idx


def print_entries(title, entries):
    print(title)
    if not entries:
        print("  <none>")
        print()
        return

    for idx, entry in enumerate(entries):
        print(f'  {idx:>3}: name="{entry["name"]}" | source="{entry["source"]}"')
    print()
    print(f"  Total: {len(entries)}")
    print()


def main(path_str):
    path = Path(path_str)
    raw = path.read_bytes()
    strings = printable_strings(raw, min_len=4)

    applied_entries, applied_start, applied_end = extract_applied_ugcs(strings)
    persistent_entries, persistent_start, persistent_end = extract_persistent_ugcs(strings)

    print(f"File: {path}")
    print(f"Total printable strings: {len(strings)}")
    print()

    print(f"Top-level applied_ugcs_1_0 range: {applied_start} -> {applied_end}")
    print(f"Persistent nested applied_ugcs_1_0 range: {persistent_start} -> {persistent_end}")
    print()

    print_entries("Top-level applied_ugcs_1_0:", applied_entries)
    print_entries("Persistent nested applied_ugcs_1_0:", persistent_entries)

    if applied_entries == persistent_entries:
        print("Blocks match exactly.")
    else:
        print("Blocks differ.")


if __name__ == "__main__":
    main(r"C:\Users\areas\OneDrive\Documents\DD Manager\persist.game.json")