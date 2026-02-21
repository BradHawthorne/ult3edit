"""Extract and catalog all JSR $46BA inline strings from engine binaries.

Scans for the 3-byte pattern $20 $BA $46 (JSR $46BA) and extracts the
following inline high-ASCII text (terminated by $00). This is the same
technique used by shapes.py:extract_overlay_strings() but applied to the
full engine binaries.

Usage:
    python engine/tools/string_catalog.py engine/originals/ULT3.bin
    python engine/tools/string_catalog.py engine/originals/ULT3.bin --json -o strings.json
    python engine/tools/string_catalog.py engine/originals/ULT3.bin --org 0x5000
"""

import argparse
import json
import os
import sys

# JSR $46BA = $20 $BA $46
_JSR_46BA = bytes([0x20, 0xBA, 0x46])


def extract_inline_strings(data: bytes, org: int = 0) -> list[dict]:
    """Extract all JSR $46BA inline strings from binary data.

    Args:
        data: Raw binary data to scan.
        org: Origin address (added to offsets for absolute addresses).

    Returns:
        List of dicts with keys: index, file_offset, address, text_offset,
        text_end, text, raw_bytes, byte_count.
    """
    strings = []
    i = 0
    idx = 0
    while i < len(data) - 3:
        if data[i:i + 3] == _JSR_46BA:
            text_start = i + 3
            chars = []
            raw = bytearray()
            j = text_start
            while j < len(data) and data[j] != 0x00:
                b = data[j]
                raw.append(b)
                if b == 0xFF:
                    chars.append('\n')
                else:
                    ch = b & 0x7F
                    if 0x20 <= ch < 0x7F:
                        chars.append(chr(ch))
                j += 1
            if chars:
                text = ''.join(chars)
                strings.append({
                    'index': idx,
                    'file_offset': i,
                    'address': org + i,
                    'text_offset': text_start,
                    'text_end': j,
                    'text': text,
                    'raw_hex': raw.hex(),
                    'byte_count': j - text_start + 1,  # including null terminator
                    'jsr_plus_text': (j - i) + 1,  # total bytes (JSR + text + null)
                })
                idx += 1
            i = j + 1
        else:
            i += 1
    return strings


def categorize_string(text: str) -> str:
    """Auto-categorize a string based on content keywords."""
    t = text.upper().strip()

    if any(w in t for w in ['CARD OF', 'MARK OF', 'SHARD', 'SIGIL']):
        return 'quest-item'
    if any(w in t for w in ['CARD', 'MARK', 'STRANGE']):
        return 'quest-message'
    if any(w in t for w in ['KILLED', 'HIT', 'MISSED', 'CONFLICT', 'VICTORY',
                             'PILFERED', 'CHEST', 'RETREAT']):
        return 'combat'
    if any(w in t for w in ['NORTH', 'SOUTH', 'EAST', 'WEST', 'BOARD',
                             'KLIMB', 'DESCEND', 'ENTER']):
        return 'movement'
    if any(w in t for w in ['TRAP', 'ACID', 'POISON', 'BOMB', 'GAS', 'EVADE']):
        return 'trap'
    if any(w in t for w in ['FOUNTAIN', 'DRINK', 'GREMLIN', 'WIND']):
        return 'fountain'
    if any(w in t for w in ['SPELL', 'CAST', 'MAGE', 'CLERIC', 'WIZARD',
                             'M.P.', 'CURE', 'RESURECT', 'RECALL']):
        return 'magic'
    if any(w in t for w in ['ARMOUR', 'WEAPON', 'GOLD', 'TORCH', 'KEY',
                             'WEAR', 'READY', 'EXOTIC']):
        return 'equipment'
    if any(w in t for w in ['DUNGEON', 'TOWN', 'CASTLE', 'SHRINE', 'EXIT',
                             'SOSARIA', 'WHIRLPOOL', 'DARK', 'MISTY']):
        return 'location'
    if any(w in t for w in ['EVOCARE', 'ABERIA', 'EXODUS', 'YELL']):
        return 'story'
    if any(w in t for w in ['DONE', 'EXCHANGED', 'ABORTED', 'WELCOME',
                             'GOOD DAY', 'TRANSACT']):
        return 'shop'
    if any(w in t for w in ['INCAPACITATED', 'STARVING', 'NOT ENOUGH',
                             'FAILED', 'NO EFFECT', 'INVALID', 'NOT HERE',
                             'NOT ALLOWED', 'NOT OWNED']):
        return 'status'
    if any(w in t for w in ['AMOUNT', 'ACTION', 'CMD', 'PLAYER', 'WAIT',
                             'WHO', 'WHICH', 'WHOSE', 'DIRECT']):
        return 'ui-prompt'
    if any(w in t for w in ['DROWN', 'GRAVE', 'SWIRL', 'ENGULF']):
        return 'death'

    return 'other'


def print_catalog(strings: list[dict], org: int):
    """Print formatted string catalog to stdout."""
    total_bytes = sum(s['jsr_plus_text'] for s in strings)

    print(f"\n=== Inline String Catalog ===")
    print(f"Total strings: {len(strings)}")
    print(f"Total bytes (JSR + text + null): {total_bytes:,}")
    print(f"Origin: ${org:04X}\n")

    # Group by category
    categories = {}
    for s in strings:
        cat = categorize_string(s['text'])
        categories.setdefault(cat, []).append(s)

    for cat in sorted(categories.keys()):
        cat_strings = categories[cat]
        cat_bytes = sum(s['jsr_plus_text'] for s in cat_strings)
        print(f"--- {cat} ({len(cat_strings)} strings, {cat_bytes} bytes) ---")
        for s in cat_strings:
            addr = f"${s['address']:04X}"
            text = s['text'].replace('\n', '\\n')
            print(f"  [{s['index']:3d}] {addr}  {s['byte_count']:3d}B  {text}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Extract JSR $46BA inline strings from engine binaries')
    parser.add_argument('binary', help='Binary file to scan')
    parser.add_argument('--org', type=lambda x: int(x, 0), default=0,
                        help='Origin address (e.g., 0x5000 for ULT3)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    args = parser.parse_args()

    # Auto-detect origin from filename
    org = args.org
    basename = os.path.basename(args.binary).upper()
    if org == 0:
        if 'ULT3' in basename:
            org = 0x5000
        elif 'EXOD' in basename:
            org = 0x2000
        elif 'SUBS' in basename:
            org = 0x4100

    with open(args.binary, 'rb') as f:
        data = f.read()

    strings = extract_inline_strings(data, org)

    if args.json:
        # Add category to each string
        for s in strings:
            s['category'] = categorize_string(s['text'])

        result = {
            'binary': os.path.basename(args.binary),
            'org': f'${org:04X}',
            'size': len(data),
            'total_strings': len(strings),
            'total_bytes': sum(s['jsr_plus_text'] for s in strings),
            'strings': strings,
        }

        output = json.dumps(result, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Wrote {len(strings)} strings to {args.output}")
        else:
            print(output)
    else:
        print_catalog(strings, org)


if __name__ == '__main__':
    main()
