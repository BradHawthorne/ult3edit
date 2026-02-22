"""Source-level inline string patcher for engine assembly files.

Modifies ASC directives in .s source files, enabling string replacements
with NO LENGTH CONSTRAINTS (unlike binary patching). The assembler handles
all byte counting.

Inline strings in CIDAR disassembly appear as:
    DB      $20,$BA,$46,$FF        ; JSR $46BA + newline
    ASC     "CARD OF DEATH"        ; text
    DB      $00 ; null terminator  ; terminator

This tool replaces the text inside ASC directives, matching by content.
After patching, reassemble with asmiigs to produce the modified binary.

Usage:
    python source_patcher.py engine/ult3/ult3.s patches.json -o patched_ult3.s
    python source_patcher.py engine/ult3/ult3.s patches.json --dry-run

Patch file format:
    {
      "patches": [
        {"vanilla": "CARD OF DEATH", "text": "SHARD OF VOID"},
        {"vanilla": "MARK OF KINGS", "text": "SIGIL: KINGS"},
        {"index": 5, "text": "REPLACEMENT"}
      ]
    }

Patches match by vanilla text (case-insensitive) or by ASC directive index.
"""

import argparse
import json
import os
import re
import sys


# Pattern matching ASC "..." directives
_ASC_PATTERN = re.compile(r'^(\s+ASC\s+)"(.*)"(.*)$')


def extract_asc_strings(lines):
    """Extract all ASC directive strings from source lines.

    Returns list of dicts with keys: index, line_number, text, full_line.
    """
    strings = []
    idx = 0
    for line_num, line in enumerate(lines):
        m = _ASC_PATTERN.match(line)
        if m:
            text = m.group(2)
            strings.append({
                'index': idx,
                'line_number': line_num,
                'text': text,
                'prefix': m.group(1),
                'suffix': m.group(3),
            })
            idx += 1
    return strings


def is_inline_string(lines, asc_info):
    """Check if an ASC directive is part of a JSR $46BA inline string.

    Looks for $20,$BA,$46 (JSR $46BA) pattern in preceding DB lines,
    and $00 null terminator in following DB line.
    """
    line_num = asc_info['line_number']

    # Check for null terminator after
    has_null_after = False
    if line_num + 1 < len(lines):
        next_line = lines[line_num + 1].strip()
        if next_line.startswith('DB') and '$00' in next_line:
            has_null_after = True

    # Check for JSR $46BA before (in preceding DB lines)
    has_jsr_before = False
    # The JSR pattern might be split across DB lines, or the ASC might be
    # preceded by another ASC (multi-line string). Check up to 5 lines back.
    for i in range(1, 6):
        if line_num - i < 0:
            break
        prev = lines[line_num - i].strip()
        if '$20,$BA,$46' in prev or '$BA,$46' in prev:
            has_jsr_before = True
            break
        # Skip blank lines and comments, keep looking
        if not prev or prev.startswith(';'):
            continue
        # Stop searching if we hit a non-DB/non-ASC line
        if not prev.startswith('DB') and not prev.startswith('ASC'):
            break

    return has_jsr_before and has_null_after


def resolve_source_patches(asc_strings, patches):
    """Match patches to ASC strings.

    Returns list of (asc_info, new_text) pairs.
    """
    resolved = []

    # Build lookup by text (case-insensitive, whitespace-normalized)
    by_text = {}
    for s in asc_strings:
        key = s['text'].strip().upper()
        by_text.setdefault(key, []).append(s)

    by_index = {s['index']: s for s in asc_strings}

    for patch in patches:
        new_text = patch.get('text', '')

        if 'vanilla' in patch:
            # Strip leading/trailing newline markers and whitespace
            key = patch['vanilla'].strip().strip('\n').upper()
            matches = by_text.get(key, [])
            if matches:
                for m in matches:
                    resolved.append((m, new_text.strip('\n')))
            else:
                print(f"  Warning: vanilla text '{patch['vanilla']}' not found "
                      f"in ASC directives", file=sys.stderr)

        elif 'index' in patch:
            idx = patch['index']
            if idx in by_index:
                resolved.append((by_index[idx], new_text.strip('\n')))
            else:
                print(f"  Warning: ASC index {idx} not found", file=sys.stderr)

        else:
            print(f"  Warning: patch has no vanilla/index key: {patch}",
                  file=sys.stderr)

    return resolved


def apply_source_patches(lines, resolved):
    """Apply resolved patches to source lines.

    Returns (modified_lines, count_applied).
    """
    modified = list(lines)
    applied = 0

    for asc_info, new_text in resolved:
        line_num = asc_info['line_number']
        prefix = asc_info['prefix']
        suffix = asc_info['suffix']
        old_text = asc_info['text']

        # Handle newlines in replacement text: split into multiple ASC + DB $FF lines
        if '\n' in new_text:
            parts = new_text.split('\n')
            new_lines = []
            for i, part in enumerate(parts):
                if i > 0:
                    # Add $FF newline byte between parts
                    new_lines.append(f'{prefix.rstrip():<16s}DB      $FF\n')
                if part:
                    new_lines.append(f'{prefix}"{part}"{suffix}\n')
            modified[line_num] = ''.join(new_lines)
        else:
            modified[line_num] = f'{prefix}"{new_text}"{suffix}\n'

        print(f'  [{asc_info["index"]:3d}] Line {line_num + 1}: '
              f'"{old_text}" -> "{new_text}"')
        applied += 1

    return modified, applied


def main():
    parser = argparse.ArgumentParser(
        description='Patch ASC inline strings in engine assembly source')
    parser.add_argument('source', help='Assembly source file (.s)')
    parser.add_argument('patches', help='JSON patch file')
    parser.add_argument('-o', '--output', help='Output file (default: overwrite)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')
    parser.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwriting')
    parser.add_argument('--inline-only', action='store_true',
                        help='Only patch ASC directives that are JSR $46BA inline strings')
    args = parser.parse_args()

    # Load source
    with open(args.source, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Load patches
    with open(args.patches, 'r', encoding='utf-8') as f:
        patch_data = json.load(f)

    patches = patch_data.get('patches', [])
    if not patches:
        print("No patches found in JSON file", file=sys.stderr)
        sys.exit(1)

    # Extract ASC strings
    asc_strings = extract_asc_strings(lines)
    print(f"Found {len(asc_strings)} ASC directives in {args.source}")

    # Optionally filter to inline strings only
    if args.inline_only:
        asc_strings = [s for s in asc_strings if is_inline_string(lines, s)]
        print(f"  ({len(asc_strings)} are JSR $46BA inline strings)")

    # Resolve patches
    resolved = resolve_source_patches(asc_strings, patches)
    if not resolved:
        print("No patches matched any ASC strings", file=sys.stderr)
        sys.exit(1)

    # Apply patches
    modified, applied = apply_source_patches(lines, resolved)
    print(f"\nPatched {applied} ASC directive(s)")

    if args.dry_run:
        print("Dry run -- no changes written.")
        return

    output = args.output or args.source
    if args.backup and output == args.source:
        import shutil
        shutil.copy2(args.source, args.source + '.bak')
        print(f"Backup: {args.source}.bak")

    with open(output, 'w', encoding='utf-8') as f:
        f.writelines(modified)
    print(f"Wrote patched source to {output}")


if __name__ == '__main__':
    main()
