"""Ultima III: Exodus - Combat Battlefield Viewer.

CON files: 192 bytes (0xC0), loaded at $9900. Layout verified via engine
code tracing (ULT3.s lookup_add at $7E18, spawn loop, PC init loop):
  0x00-0x78: 11x11 battlefield tiles (121 bytes)
  0x79-0x7F: Unused padding (7 bytes, never read by engine)
  0x80-0x87: Monster start X positions [0-7]
  0x88-0x8F: Monster start Y positions [0-7]
  0x90-0x97: Runtime: saved tile under monster (overwritten at combat init)
  0x98-0x9F: Runtime: monster type/status (overwritten at combat init)
  0xA0-0xA3: PC start X positions [0-3]
  0xA4-0xA7: PC start Y positions [0-3]
  0xA8-0xAB: Runtime: saved tile under PC (overwritten at init)
  0xAC-0xAF: Runtime: PC appearance tile (overwritten by JSR $7F5D)
  0xB0-0xBF: Unused tail padding (16 bytes, never read by engine)
"""

import argparse
import json
import os
import sys

from .constants import (
    CON_NAMES, CON_LETTERS, CON_FILE_SIZE,
    CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_MAP_TILES,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_MONSTER_COUNT,
    CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CON_PC_COUNT,
    CON_PADDING1_OFFSET, CON_PADDING1_SIZE,
    CON_RUNTIME_MONSAVE_OFFSET, CON_RUNTIME_MONSTATUS_OFFSET,
    CON_RUNTIME_PCSAVE_OFFSET, CON_RUNTIME_PCTILE_OFFSET,
    CON_PADDING2_OFFSET, CON_PADDING2_SIZE,
    tile_char, TILE_CHARS_REVERSE,
)
from .fileutil import resolve_game_file, backup_file
from .json_export import export_json


class CombatMap:
    """A single combat battlefield."""

    def __init__(self, data: bytes):
        self.tiles = data[:CON_MAP_TILES]
        self.monster_x = [data[CON_MONSTER_X_OFFSET + i] if CON_MONSTER_X_OFFSET + i < len(data) else 0
                          for i in range(CON_MONSTER_COUNT)]
        self.monster_y = [data[CON_MONSTER_Y_OFFSET + i] if CON_MONSTER_Y_OFFSET + i < len(data) else 0
                          for i in range(CON_MONSTER_COUNT)]
        self.pc_x = [data[CON_PC_X_OFFSET + i] if CON_PC_X_OFFSET + i < len(data) else 0
                     for i in range(CON_PC_COUNT)]
        self.pc_y = [data[CON_PC_Y_OFFSET + i] if CON_PC_Y_OFFSET + i < len(data) else 0
                     for i in range(CON_PC_COUNT)]
        # Padding and runtime arrays — preserved for round-trip fidelity
        # padding1: 7 bytes between tile grid and monster positions (unused)
        self.padding1 = list(data[CON_PADDING1_OFFSET:CON_PADDING1_OFFSET + CON_PADDING1_SIZE]) \
            if len(data) > CON_PADDING1_OFFSET else [0] * CON_PADDING1_SIZE
        # runtime_data: 16 bytes of runtime arrays (saved-tile + status, overwritten at init)
        self.runtime_monster = list(data[CON_RUNTIME_MONSAVE_OFFSET:CON_RUNTIME_MONSTATUS_OFFSET + 8]) \
            if len(data) > CON_RUNTIME_MONSAVE_OFFSET else [0] * 16
        # runtime_pc: 8 bytes of runtime arrays (saved-tile + appearance, overwritten at init)
        self.runtime_pc = list(data[CON_RUNTIME_PCSAVE_OFFSET:CON_RUNTIME_PCTILE_OFFSET + 4]) \
            if len(data) > CON_RUNTIME_PCSAVE_OFFSET else [0] * 8
        # padding2: 16 bytes of unused tail padding
        self.padding2 = list(data[CON_PADDING2_OFFSET:CON_PADDING2_OFFSET + CON_PADDING2_SIZE]) \
            if len(data) > CON_PADDING2_OFFSET else [0] * CON_PADDING2_SIZE

    def render(self) -> str:
        """Render 11x11 battlefield with position overlays."""
        # Build base grid
        grid = []
        for y in range(CON_MAP_HEIGHT):
            row = []
            for x in range(CON_MAP_WIDTH):
                offset = y * CON_MAP_WIDTH + x
                if offset < len(self.tiles):
                    row.append(tile_char(self.tiles[offset]))
                else:
                    row.append(' ')
            grid.append(row)

        # Overlay monster positions
        for i in range(CON_MONSTER_COUNT):
            mx, my = self.monster_x[i], self.monster_y[i]
            if 0 <= mx < CON_MAP_WIDTH and 0 <= my < CON_MAP_HEIGHT:
                grid[my][mx] = 'm'

        # Overlay PC positions
        for i in range(CON_PC_COUNT):
            px, py = self.pc_x[i], self.pc_y[i]
            if 0 <= px < CON_MAP_WIDTH and 0 <= py < CON_MAP_HEIGHT:
                grid[py][px] = '@'

        lines = ['     ' + ''.join(f'{x % 10}' for x in range(CON_MAP_WIDTH))]
        for y, row in enumerate(grid):
            lines.append(f'  {y:2d}  {"".join(row)}')

        # Show padding/runtime data if non-zero (for debugging/analysis)
        has_extra = any(self.padding1) or any(self.runtime_monster) or any(self.padding2)
        if has_extra:
            lines.append('')
            if any(self.padding1):
                lines.append(f'  Padding (0x79): {" ".join(f"{b:02X}" for b in self.padding1)}')
            if any(self.runtime_monster):
                lines.append(f'  Runtime monster (0x90): {" ".join(f"{b:02X}" for b in self.runtime_monster)}')
            if any(self.padding2):
                lines.append(f'  Padding (0xB0): {" ".join(f"{b:02X}" for b in self.padding2)}')

        return '\n'.join(lines)

    def to_dict(self) -> dict:
        result = {
            'tiles': [[tile_char(self.tiles[y * CON_MAP_WIDTH + x])
                        for x in range(CON_MAP_WIDTH)
                        if y * CON_MAP_WIDTH + x < len(self.tiles)]
                       for y in range(CON_MAP_HEIGHT)
                       if y * CON_MAP_WIDTH < len(self.tiles)],
            'monsters': [{'x': self.monster_x[i], 'y': self.monster_y[i]}
                         for i in range(CON_MONSTER_COUNT)
                         if self.monster_x[i] or self.monster_y[i]],
            'pcs': [{'x': self.pc_x[i], 'y': self.pc_y[i]}
                    for i in range(CON_PC_COUNT)],
            'padding': {
                'pre_monster': self.padding1,
                'tail': self.padding2,
            },
            'runtime': {
                'monster_save_and_status': self.runtime_monster,
                'pc_save_and_tile': self.runtime_pc,
            },
        }
        return result


def cmd_view(args) -> None:
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        con_files = []
        for letter in CON_LETTERS:
            path = resolve_game_file(path_or_dir, 'CON', letter)
            if path:
                con_files.append((letter, path))

        if not con_files:
            print(f"Error: No CON files found in {path_or_dir}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for letter, path in con_files:
                with open(path, 'rb') as f:
                    data = f.read()
                cm = CombatMap(data)
                result[f'CON{letter}'] = {
                    'name': CON_NAMES.get(letter, 'Unknown'),
                    **cm.to_dict(),
                }
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Combat Maps ({len(con_files)} arenas) ===\n")
        for letter, path in con_files:
            name = CON_NAMES.get(letter, 'Unknown')
            with open(path, 'rb') as f:
                data = f.read()
            cm = CombatMap(data)
            print(f"  CON{letter} - {name}")
            print(cm.render())
            print(f"  Legend: @ = PC start, m = monster start")
            print()
    else:
        with open(path_or_dir, 'rb') as f:
            data = f.read()

        filename = os.path.basename(path_or_dir)

        if args.json:
            cm = CombatMap(data)
            result = {'file': filename, **cm.to_dict()}
            export_json(result, args.output)
            return

        cm = CombatMap(data)
        print(f"\n=== Combat Map: {filename} ({len(data)} bytes) ===\n")
        print(cm.render())
        print(f"\n  Legend: @ = PC start, m = monster start")
        print()


def cmd_edit(args) -> None:
    """Launch TUI combat map editor."""
    from .tui import require_prompt_toolkit
    require_prompt_toolkit()
    from .tui.combat_editor import CombatEditor

    with open(args.file, 'rb') as f:
        data = f.read()

    editor = CombatEditor(args.file, data)
    editor.run()


def cmd_import(args) -> None:
    """Import a combat map from JSON."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    do_backup = getattr(args, 'backup', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    # Import tiles
    tiles = jdata.get('tiles', [])
    for y, row in enumerate(tiles[:CON_MAP_HEIGHT]):
        for x, ch in enumerate(row[:CON_MAP_WIDTH]):
            offset = y * CON_MAP_WIDTH + x
            data[offset] = TILE_CHARS_REVERSE.get(ch, 0x20)

    # Import monster positions
    for i, m in enumerate(jdata.get('monsters', [])[:CON_MONSTER_COUNT]):
        data[CON_MONSTER_X_OFFSET + i] = m.get('x', 0)
        data[CON_MONSTER_Y_OFFSET + i] = m.get('y', 0)

    # Import PC positions
    for i, p in enumerate(jdata.get('pcs', [])[:CON_PC_COUNT]):
        data[CON_PC_X_OFFSET + i] = p.get('x', 0)
        data[CON_PC_Y_OFFSET + i] = p.get('y', 0)

    # Import padding/runtime data for round-trip fidelity
    padding = jdata.get('padding', {})
    for i, b in enumerate(padding.get('pre_monster', [])[:CON_PADDING1_SIZE]):
        if CON_PADDING1_OFFSET + i < len(data):
            data[CON_PADDING1_OFFSET + i] = b
    for i, b in enumerate(padding.get('tail', [])[:CON_PADDING2_SIZE]):
        if CON_PADDING2_OFFSET + i < len(data):
            data[CON_PADDING2_OFFSET + i] = b
    runtime = jdata.get('runtime', {})
    for i, b in enumerate(runtime.get('monster_save_and_status', [])[:16]):
        if CON_RUNTIME_MONSAVE_OFFSET + i < len(data):
            data[CON_RUNTIME_MONSAVE_OFFSET + i] = b
    for i, b in enumerate(runtime.get('pc_save_and_tile', [])[:8]):
        if CON_RUNTIME_PCSAVE_OFFSET + i < len(data):
            data[CON_RUNTIME_PCSAVE_OFFSET + i] = b
    # Backward compat: accept old 'descriptor' key
    desc = jdata.get('descriptor', {})
    if desc:
        for i, b in enumerate(desc.get('block1', [])[:CON_PADDING1_SIZE]):
            if CON_PADDING1_OFFSET + i < len(data):
                data[CON_PADDING1_OFFSET + i] = b

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Imported combat map to {output}")


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('combat', help='Combat battlefield viewer/editor')
    sub = p.add_subparsers(dest='combat_command')

    p_view = sub.add_parser('view', help='View combat maps')
    p_view.add_argument('path', help='CON file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit a combat map (TUI)')
    p_edit.add_argument('file', help='CON file path')

    p_import = sub.add_parser('import', help='Import combat map from JSON')
    p_import.add_argument('file', help='CON file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')


def dispatch(args) -> None:
    cmd = args.combat_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit combat {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Combat Battlefield Viewer')
    sub = parser.add_subparsers(dest='combat_command')

    p_view = sub.add_parser('view', help='View combat maps')
    p_view.add_argument('path', help='CON file or GAME directory')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
