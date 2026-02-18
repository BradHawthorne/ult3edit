"""Ultima III: Exodus - Game Text Viewer.

TEXT file: 1024 bytes of high-bit ASCII strings, null-terminated records.
Contains in-game text strings used by the engine.
"""

import argparse
import json
import os
import sys

from .constants import TEXT_FILE_SIZE
from .fileutil import decode_high_ascii, encode_high_ascii, backup_file
from .json_export import export_json


def load_text_records(path: str) -> list[str]:
    """Load TEXT file and split into null-terminated string records."""
    with open(path, 'rb') as f:
        data = f.read()

    records = []
    parts = data.split(b'\x00')
    for part in parts:
        if not part:
            continue
        text = decode_high_ascii(part)
        records.append(text)
    return records


def cmd_view(args) -> None:
    records = load_text_records(args.file)
    filename = os.path.basename(args.file)

    if args.json:
        result = {
            'file': filename,
            'records': [{'index': i, 'text': rec} for i, rec in enumerate(records)],
        }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Game Text: {filename} ({len(records)} strings) ===\n")
    for i, rec in enumerate(records):
        print(f"  [{i:3d}] {rec}")
    print()


def cmd_edit(args) -> None:
    """Launch TUI text editor."""
    from .tui import require_prompt_toolkit
    require_prompt_toolkit()
    from .tui.text_editor import TextEditor

    with open(args.file, 'rb') as f:
        data = f.read()

    editor = TextEditor(args.file, data)
    editor.run()


def cmd_import(args) -> None:
    """Import game text from JSON."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    do_backup = getattr(args, 'backup', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    records = jdata if isinstance(jdata, list) else jdata.get('records', [])

    # Rebuild file: pack strings sequentially
    offset = 0
    for entry in records:
        text = entry.get('text', '') if isinstance(entry, dict) else str(entry)
        encoded = encode_high_ascii(text, len(text))
        end = offset + len(encoded) + 1  # +1 for null terminator
        if end > len(data):
            break
        data[offset:offset + len(encoded)] = encoded
        data[offset + len(encoded)] = 0x00
        offset = end

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Imported {len(records)} text records to {output}")


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('text', help='Game text viewer/editor')
    sub = p.add_subparsers(dest='text_command')

    p_view = sub.add_parser('view', help='View game text strings')
    p_view.add_argument('file', help='TEXT file path')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit game text (TUI)')
    p_edit.add_argument('file', help='TEXT file path')

    p_import = sub.add_parser('import', help='Import game text from JSON')
    p_import.add_argument('file', help='TEXT file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')


def dispatch(args) -> None:
    cmd = args.text_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit text {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Game Text Viewer')
    sub = parser.add_subparsers(dest='text_command')

    p_view = sub.add_parser('view', help='View game text strings')
    p_view.add_argument('file', help='TEXT file path')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
