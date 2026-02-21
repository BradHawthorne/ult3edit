"""Patch inline JSR $46BA strings in engine binaries.

Takes a JSON patch file mapping string indices to replacement text,
and produces a patched binary. Strings that fit in the original space
are patched in-place. Strings that are too long are reported as errors.

Usage:
    python engine/tools/string_patcher.py engine/originals/ULT3.bin patches.json -o patched_ULT3.bin
    python engine/tools/string_patcher.py engine/originals/ULT3.bin patches.json --dry-run

Patch file format:
    {
      "patches": [
        {"index": 142, "text": "SHARD OF VOID"},
        {"index": 143, "text": "SHARD OF FLUX"},
        {"vanilla": "CARD OF DEATH", "text": "SHARD OF VOID"},
        {"address": "0x6C48", "text": "SHARD OF VOID"}
      ]
    }

Patches can match by index, vanilla text, or address. Vanilla text matching
is case-insensitive and ignores leading/trailing whitespace and newlines.
"""

import argparse
import json
import os
import sys

from string_catalog import extract_inline_strings


def encode_high_ascii(text: str) -> bytearray:
    """Encode text as high-ASCII bytes with $FF for newlines."""
    result = bytearray()
    for ch in text:
        if ch == '\n':
            result.append(0xFF)
        else:
            result.append(ord(ch.upper()) | 0x80)
    return result


def patch_string(data: bytearray, string_info: dict, new_text: str) -> tuple[bool, str]:
    """Patch a single inline string in-place.

    Returns (success, message).
    """
    text_offset = string_info['text_offset']
    text_end = string_info['text_end']
    max_bytes = text_end - text_offset  # space before null terminator

    encoded = encode_high_ascii(new_text)

    if len(encoded) > max_bytes:
        return False, (f"String too long: '{new_text}' needs {len(encoded)} bytes, "
                       f"only {max_bytes} available (original: '{string_info['text']}')")

    # Write encoded text
    for i, b in enumerate(encoded):
        data[text_offset + i] = b

    # Null-fill remaining space (including the original null terminator position)
    for i in range(len(encoded), max_bytes + 1):
        data[text_offset + i] = 0x00

    return True, f"Patched [{string_info['index']}] '{string_info['text']}' -> '{new_text}'"


def resolve_patches(strings: list[dict], patches: list[dict]) -> list[tuple[dict, str]]:
    """Resolve patch entries to (string_info, new_text) pairs.

    Supports matching by index, vanilla text, or address.
    """
    resolved = []
    # Build lookup tables
    by_index = {s['index']: s for s in strings}
    by_text = {}
    for s in strings:
        key = s['text'].strip().strip('\n').upper()
        by_text.setdefault(key, []).append(s)
    by_addr = {s['address']: s for s in strings}

    for patch in patches:
        new_text = patch.get('text', '')

        if 'index' in patch:
            idx = patch['index']
            if idx in by_index:
                resolved.append((by_index[idx], new_text))
            else:
                print(f"  Warning: index {idx} not found", file=sys.stderr)

        elif 'vanilla' in patch:
            key = patch['vanilla'].strip().strip('\n').upper()
            matches = by_text.get(key, [])
            if matches:
                for m in matches:
                    resolved.append((m, new_text))
            else:
                print(f"  Warning: vanilla text '{patch['vanilla']}' not found",
                      file=sys.stderr)

        elif 'address' in patch:
            addr = int(patch['address'], 0) if isinstance(patch['address'], str) else patch['address']
            if addr in by_addr:
                resolved.append((by_addr[addr], new_text))
            else:
                print(f"  Warning: address ${addr:04X} not found", file=sys.stderr)

        else:
            print(f"  Warning: patch has no index/vanilla/address key: {patch}",
                  file=sys.stderr)

    return resolved


def main():
    parser = argparse.ArgumentParser(
        description='Patch inline JSR $46BA strings in engine binaries')
    parser.add_argument('binary', help='Binary file to patch')
    parser.add_argument('patches', help='JSON patch file')
    parser.add_argument('-o', '--output', help='Output file (default: overwrite)')
    parser.add_argument('--org', type=lambda x: int(x, 0), default=0,
                        help='Origin address (auto-detected from filename)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')
    parser.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwriting')
    args = parser.parse_args()

    # Auto-detect origin
    org = args.org
    basename = os.path.basename(args.binary).upper()
    if org == 0:
        if 'ULT3' in basename:
            org = 0x5000
        elif 'EXOD' in basename:
            org = 0x2000
        elif 'SUBS' in basename:
            org = 0x4100

    # Load binary
    with open(args.binary, 'rb') as f:
        data = bytearray(f.read())

    # Load patches
    with open(args.patches, 'r', encoding='utf-8') as f:
        patch_data = json.load(f)

    patches = patch_data.get('patches', [])
    if not patches:
        print("No patches found in JSON file", file=sys.stderr)
        sys.exit(1)

    # Extract current strings
    strings = extract_inline_strings(bytes(data), org)

    # Resolve patches to string targets
    resolved = resolve_patches(strings, patches)

    if not resolved:
        print("No patches matched any strings", file=sys.stderr)
        sys.exit(1)

    # Apply patches
    success_count = 0
    error_count = 0
    for string_info, new_text in resolved:
        ok, msg = patch_string(data, string_info, new_text)
        if ok:
            print(f"  {msg}")
            success_count += 1
        else:
            print(f"  ERROR: {msg}", file=sys.stderr)
            error_count += 1

    print(f"\nPatched {success_count} string(s), {error_count} error(s)")

    if args.dry_run:
        print("Dry run — no changes written.")
        return

    if error_count > 0:
        print("Errors detected — not writing output.", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.binary
    if args.backup and output == args.binary:
        import shutil
        shutil.copy2(args.binary, args.binary + '.bak')
        print(f"Backup: {args.binary}.bak")

    with open(output, 'wb') as f:
        f.write(data)
    print(f"Wrote patched binary to {output}")


if __name__ == '__main__':
    main()
