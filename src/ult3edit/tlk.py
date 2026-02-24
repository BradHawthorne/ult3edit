"""Ultima III: Exodus - TLK Dialog Extractor/Builder/Viewer.

TLK files contain NPC dialog text in high-bit ASCII.
Format: 0xFF = line break within record, 0x00 = record terminator.
19 TLK files (A-S) correspond to game locations.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .constants import TLK_LETTERS, TLK_NAMES, TLK_LINE_BREAK, TLK_RECORD_END
from .fileutil import resolve_game_file, backup_file
from .json_export import export_json


def is_text_record(data: bytes) -> bool:
    """Check if a binary record looks like valid high-ASCII text (not code).

    Real TLK text uses high-bit ASCII (0xA0-0xFE = printable chars with bit 7).
    Code sections have many bytes below 0x80. We check that most content bytes
    are in the high-ASCII printable range.
    """
    if not data:
        return False
    content_bytes = 0
    high_ascii_printable = 0
    for b in data:
        if b == TLK_LINE_BREAK or b == TLK_RECORD_END:
            continue
        content_bytes += 1
        if 0xA0 <= b <= 0xFE:
            high_ascii_printable += 1
    if content_bytes == 0:
        return False
    # 70% threshold: real TLK text is nearly all high-ASCII; binary/code
    # sections typically have <50% high-ASCII bytes.  70% cleanly separates
    # the two in all known game files (vanilla + total conversions).
    return high_ascii_printable / content_bytes > 0.7


def decode_record(data: bytes) -> list[str]:
    """Decode a single TLK record into a list of text lines."""
    lines: list[str] = []
    cur: list[str] = []
    for b in data:
        if b == TLK_LINE_BREAK:
            lines.append(''.join(cur))
            cur = []
            continue
        if b == TLK_RECORD_END:
            break
        ch = b & 0x7F
        if 0x20 <= ch < 0x7F:
            cur.append(chr(ch))
        # Skip non-printable bytes
    if cur or not lines:
        lines.append(''.join(cur))
    return lines


def encode_record(lines: list[str]) -> bytes:
    """Encode text lines into a TLK binary record."""
    out = bytearray()
    for idx, line in enumerate(lines):
        if idx > 0:
            out.append(TLK_LINE_BREAK)
        for ch in line:
            out.append((ord(ch.upper()) & 0x7F) | 0x80)
    out.append(TLK_RECORD_END)
    return bytes(out)


def parse_tlk_data(data: bytes, skip_binary: bool = True) -> list[list[str]]:
    """Parse raw TLK data and return list of decoded records."""
    records = []
    parts = data.split(bytes([TLK_RECORD_END]))
    for part in parts:
        if not part:
            continue
        if skip_binary and not is_text_record(part):
            continue
        records.append(decode_record(part + bytes([TLK_RECORD_END])))
    return records


def load_tlk_records(path: str, skip_binary: bool = True) -> list[list[str]]:
    """Load a TLK file and return list of decoded records."""
    with open(path, 'rb') as f:
        data = f.read()
    return parse_tlk_data(data, skip_binary)


def cmd_view(args) -> None:
    """View TLK dialog records."""
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        # Batch view all TLK files
        tlk_files = []
        for letter in TLK_LETTERS:
            path = resolve_game_file(path_or_dir, 'TLK', letter)
            if path:
                tlk_files.append((letter, path))

        if not tlk_files:
            print(f"Error: No TLK files found in {path_or_dir}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for letter, path in tlk_files:
                records = load_tlk_records(path)
                result[f'TLK{letter}'] = {
                    'location': TLK_NAMES.get(letter, 'Unknown'),
                    'records': [{'index': i, 'lines': rec} for i, rec in enumerate(records)],
                }
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Dialogs ({len(tlk_files)} files) ===\n")
        for letter, path in tlk_files:
            location = TLK_NAMES.get(letter, 'Unknown')
            records = load_tlk_records(path)
            print(f"  TLK{letter} - {location} ({len(records)} records)")
            for i, rec in enumerate(records):
                text = ' / '.join(rec)
                if len(text) > 72:
                    text = text[:69] + '...'
                print(f"    [{i:2d}] {text}")
            print()
    else:
        # Single file view
        records = load_tlk_records(path_or_dir)
        filename = os.path.basename(path_or_dir)

        if args.json:
            result = {'file': filename, 'records': [
                {'index': i, 'lines': rec} for i, rec in enumerate(records)
            ]}
            export_json(result, args.output)
            return

        print(f"\n=== TLK Dialog: {filename} ({len(records)} records) ===\n")
        for i, rec in enumerate(records):
            print(f"  Record {i}:")
            for line in rec:
                print(f"    {line}")
            print()


def cmd_extract(args) -> None:
    """Extract TLK binary to editable text file."""
    records = load_tlk_records(args.input)
    lines: list[str] = []
    for i, rec in enumerate(records):
        lines.append(f'# Record {i}')
        lines.extend(rec)
        lines.append('---')

    if lines and lines[-1] == '---':
        lines.pop()

    output = args.output
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"Extracted {len(records)} records to {output}")


def cmd_build(args) -> None:
    """Build TLK binary from editable text file."""
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()

    blocks = [b.strip() for b in text.split('\n---\n')]
    out = bytearray()

    for block in blocks:
        if not block:
            continue
        lines = []
        for line in block.splitlines():
            if line.strip().startswith('#'):
                continue
            lines.append(line.rstrip('\n'))
        out.extend(encode_record(lines))

    output = args.output
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'wb') as f:
        f.write(bytes(out))
    print(f"Built TLK ({len(out)} bytes) to {output}")


def cmd_edit(args) -> None:
    """Edit a specific record in-place, or find-replace across all records."""
    find_text = getattr(args, 'find', None)
    replace_text = getattr(args, 'replace', None)
    record = getattr(args, 'record', None)
    text = getattr(args, 'text', None)

    if find_text is not None and replace_text is not None:
        _cmd_find_replace(args, find_text, replace_text)
        return

    if find_text is not None or replace_text is not None:
        print("Error: --find and --replace must be used together",
              file=sys.stderr)
        sys.exit(1)

    if record is None or text is None:
        print("Error: Either --record/--text or --find/--replace required",
              file=sys.stderr)
        sys.exit(1)

    with open(args.file, 'rb') as f:
        raw = f.read()
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    # Split into raw parts, track which are text
    raw_parts = raw.split(bytes([TLK_RECORD_END]))
    text_index = 0
    target_part = None
    for i, part in enumerate(raw_parts):
        if not part:
            continue
        if is_text_record(part):
            if text_index == record:
                target_part = i
                break
            text_index += 1

    text_count = sum(1 for p in raw_parts if p and is_text_record(p))
    if target_part is None:
        print(f"Error: Record {record} out of range (0-{text_count-1})",
              file=sys.stderr)
        sys.exit(1)

    # Replace only the target text record, preserve everything else
    new_lines = text.split('\\n')
    new_encoded = encode_record(new_lines)
    # encode_record appends TLK_RECORD_END; strip it since split removed them
    raw_parts[target_part] = new_encoded[:-1]

    # Rebuild: rejoin with TLK_RECORD_END separator
    out = bytes([TLK_RECORD_END]).join(raw_parts)

    if dry_run:
        print(f"Would update record {record}")
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(out)
    print(f"Updated record {record} in {output}")


def _cmd_find_replace(args, find_text: str, replace_text: str) -> None:
    """Find and replace text across all text records in a TLK file."""
    with open(args.file, 'rb') as f:
        raw = f.read()
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)
    ignore_case = getattr(args, 'ignore_case', False)

    raw_parts = raw.split(bytes([TLK_RECORD_END]))
    total_replacements = 0
    records_changed = 0

    for i, part in enumerate(raw_parts):
        if not part or not is_text_record(part):
            continue
        lines = decode_record(part + bytes([TLK_RECORD_END]))
        changed = False
        new_lines = []
        for line in lines:
            if ignore_case:
                # Case-insensitive find, preserve replacement case
                pattern = re.compile(re.escape(find_text), re.IGNORECASE)
                count = len(pattern.findall(line))
                new_line = pattern.sub(replace_text, line)
            else:
                count = line.count(find_text)
                new_line = line.replace(find_text, replace_text)
            if count > 0:
                changed = True
                total_replacements += count
            new_lines.append(new_line)
        if changed:
            records_changed += 1
            new_encoded = encode_record(new_lines)
            raw_parts[i] = new_encoded[:-1]

    out = bytes([TLK_RECORD_END]).join(raw_parts)

    print(f"Find '{find_text}' -> '{replace_text}': "
          f"{total_replacements} replacement(s) in {records_changed} record(s)")

    if total_replacements == 0:
        return

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(out)
    print(f"Written to {output}")


def _match_line(line: str, pattern: str, use_regex: bool) -> bool:
    """Check if a line matches a search pattern."""
    if use_regex:
        return bool(re.search(pattern, line, re.IGNORECASE))
    return pattern.lower() in line.lower()


def cmd_search(args) -> None:
    """Search dialog text across TLK files."""
    use_regex = getattr(args, 'regex', False)
    path_or_dir = args.path

    if use_regex:
        try:
            re.compile(args.pattern)
        except re.error as e:
            print(f"Error: Invalid regex: {e}", file=sys.stderr)
            sys.exit(1)

    results = []

    if os.path.isdir(path_or_dir):
        for letter in TLK_LETTERS:
            path = resolve_game_file(path_or_dir, 'TLK', letter)
            if not path:
                continue
            records = load_tlk_records(path)
            location = TLK_NAMES.get(letter, 'Unknown')
            for i, rec in enumerate(records):
                for line in rec:
                    if _match_line(line, args.pattern, use_regex):
                        results.append({
                            'file': f'TLK{letter}',
                            'location': location,
                            'record': i,
                            'line': line,
                        })
    else:
        records = load_tlk_records(path_or_dir)
        filename = os.path.basename(path_or_dir)
        for i, rec in enumerate(records):
            for line in rec:
                if _match_line(line, args.pattern, use_regex):
                    results.append({
                        'file': filename,
                        'record': i,
                        'line': line,
                    })

    if getattr(args, 'json', False):
        export_json(results, getattr(args, 'output', None))
        return

    if not results:
        print(f"No matches for '{args.pattern}'")
        return

    print(f"\n=== Search: '{args.pattern}' ({len(results)} matches) ===\n")
    for r in results:
        loc = f" ({r['location']})" if 'location' in r else ''
        print(f"  {r['file']}{loc} record {r['record']}: {r['line']}")
    print()


def cmd_import(args) -> None:
    """Import dialog records from JSON."""
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    # Accept either a list of records or a dict with 'records' key
    records = jdata if isinstance(jdata, list) else jdata.get('records', [])

    out = bytearray()
    for entry in records:
        lines = entry.get('lines', []) if isinstance(entry, dict) else entry
        out.extend(encode_record(lines))

    print(f"Import: {len(records)} record(s)")

    if dry_run:
        print("Dry run - no changes written.")
        return

    if do_backup and os.path.exists(args.file) and (not args.output or args.output == args.file):
        backup_file(args.file)

    output = args.output if args.output else args.file
    with open(output, 'wb') as f:
        f.write(bytes(out))
    print(f"Imported {len(records)} records to {output}")


def register_parser(subparsers) -> None:
    """Register tlk subcommands on a CLI subparser group."""
    p = subparsers.add_parser('tlk', help='Dialog text viewer/editor')
    sub = p.add_subparsers(dest='tlk_command')

    p_view = sub.add_parser('view', help='View dialog records')
    p_view.add_argument('path', help='TLK file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_extract = sub.add_parser('extract', help='Extract TLK to text')
    p_extract.add_argument('input', help='TLK binary file')
    p_extract.add_argument('output', help='Output text file')

    p_build = sub.add_parser('build', help='Build TLK from text')
    p_build.add_argument('input', help='Input text file')
    p_build.add_argument('output', help='Output TLK binary file')

    p_edit = sub.add_parser('edit', help='Edit a record in-place')
    p_edit.add_argument('file', help='TLK file')
    p_edit.add_argument('--record', type=int, help='Record index (with --text)')
    p_edit.add_argument('--text', help='New text (use \\n for line breaks, with --record)')
    p_edit.add_argument('--find', help='Text to find (with --replace)')
    p_edit.add_argument('--replace', help='Replacement text (with --find)')
    p_edit.add_argument('--ignore-case', action='store_true', help='Case-insensitive find/replace')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true', help='Show changes without writing')

    p_search = sub.add_parser('search', help='Search dialog text')
    p_search.add_argument('path', help='TLK file or GAME directory')
    p_search.add_argument('pattern', help='Text to search for (case-insensitive)')
    p_search.add_argument('--regex', action='store_true', help='Treat pattern as a regular expression')
    p_search.add_argument('--json', action='store_true', help='Output as JSON')
    p_search.add_argument('--output', '-o', help='Output file (for --json)')

    p_import = sub.add_parser('import', help='Import dialog from JSON')
    p_import.add_argument('file', help='TLK file path (output target)')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def dispatch(args) -> None:
    """Dispatch tlk subcommand."""
    cmd = args.tlk_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'extract':
        cmd_extract(args)
    elif cmd == 'build':
        cmd_build(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'search':
        cmd_search(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: ult3edit tlk {view|extract|build|edit|search|import} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Dialog Text Viewer/Editor')
    sub = parser.add_subparsers(dest='tlk_command')

    p_view = sub.add_parser('view', help='View dialog records')
    p_view.add_argument('path', help='TLK file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_extract = sub.add_parser('extract', help='Extract TLK to text')
    p_extract.add_argument('input', help='TLK binary file')
    p_extract.add_argument('output', help='Output text file')

    p_build = sub.add_parser('build', help='Build TLK from text')
    p_build.add_argument('input', help='Input text file')
    p_build.add_argument('output', help='Output TLK binary file')

    p_edit = sub.add_parser('edit', help='Edit a record in-place')
    p_edit.add_argument('file', help='TLK file')
    p_edit.add_argument('--record', type=int, help='Record index (with --text)')
    p_edit.add_argument('--text', help='New text (use \\n for line breaks, with --record)')
    p_edit.add_argument('--find', help='Text to find (with --replace)')
    p_edit.add_argument('--replace', help='Replacement text (with --find)')
    p_edit.add_argument('--ignore-case', action='store_true',
                        help='Case-insensitive find/replace')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_search = sub.add_parser('search', help='Search dialog text')
    p_search.add_argument('path', help='TLK file or GAME directory')
    p_search.add_argument('pattern', help='Text to search for (case-insensitive)')
    p_search.add_argument('--regex', action='store_true',
                          help='Treat pattern as a regular expression')
    p_search.add_argument('--json', action='store_true', help='Output as JSON')
    p_search.add_argument('--output', '-o', help='Output file (for --json)')

    p_import = sub.add_parser('import', help='Import dialog from JSON')
    p_import.add_argument('file', help='TLK file path (output target)')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
