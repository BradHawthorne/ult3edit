"""Ultima III: Exodus - Save State Viewer/Editor.

Reads multiple save files from a GAME directory:
  SOSA (4096 bytes) - Overworld map state (64x64 tiles)
  PRTY (16 bytes) - Party state at zero-page $E0-$EF:
    $E0: transport mode, $E1: party size (0-4), $E2: location type,
    $E3: saved overworld X, $E4: saved overworld Y, $E5: sentinel,
    $E6-$E9: roster slot IDs
  PLRS (256 bytes) - 4 active character records (4x64 bytes)
  SOSM (256 bytes) - Overworld monster positions
"""

import argparse
import json
import os
import sys

from .constants import (
    PRTY_TRANSPORT, PRTY_TRANSPORT_CODES, PRTY_LOCATION_TYPE,
    PRTY_OFF_TRANSPORT, PRTY_OFF_PARTY_SIZE, PRTY_OFF_LOCATION,
    PRTY_OFF_SAVED_X, PRTY_OFF_SAVED_Y, PRTY_OFF_SENTINEL,
    PRTY_OFF_SLOT_IDS,
    PRTY_FILE_SIZE, PLRS_FILE_SIZE, SOSA_FILE_SIZE, SOSM_FILE_SIZE,
    CHAR_RECORD_SIZE, tile_char,
)
from .fileutil import resolve_single_file, backup_file
from .roster import Character
from .json_export import export_json


class PartyState:
    """Party state from PRTY file (16 bytes)."""

    def __init__(self, data: bytes):
        if len(data) < PRTY_FILE_SIZE:
            raise ValueError(f"PRTY data too small: {len(data)} bytes (need {PRTY_FILE_SIZE})")
        self.raw = bytearray(data[:PRTY_FILE_SIZE])

    @property
    def transport(self) -> str:
        return PRTY_TRANSPORT.get(self.raw[PRTY_OFF_TRANSPORT],
                                  f'Unknown(${self.raw[PRTY_OFF_TRANSPORT]:02X})')

    @transport.setter
    def transport(self, name: str) -> None:
        code = PRTY_TRANSPORT_CODES.get(name.lower())
        if code is not None:
            self.raw[PRTY_OFF_TRANSPORT] = code

    @property
    def party_size(self) -> int:
        return self.raw[PRTY_OFF_PARTY_SIZE]

    @party_size.setter
    def party_size(self, val: int) -> None:
        self.raw[PRTY_OFF_PARTY_SIZE] = max(0, min(4, val))

    @property
    def location_type(self) -> str:
        return PRTY_LOCATION_TYPE.get(self.raw[PRTY_OFF_LOCATION],
                                      f'Unknown(${self.raw[PRTY_OFF_LOCATION]:02X})')

    @property
    def location_code(self) -> int:
        return self.raw[PRTY_OFF_LOCATION]

    @location_code.setter
    def location_code(self, val: int) -> None:
        self.raw[PRTY_OFF_LOCATION] = val & 0xFF

    @property
    def x(self) -> int:
        return self.raw[PRTY_OFF_SAVED_X]

    @x.setter
    def x(self, val: int) -> None:
        self.raw[PRTY_OFF_SAVED_X] = max(0, min(63, val))

    @property
    def y(self) -> int:
        return self.raw[PRTY_OFF_SAVED_Y]

    @y.setter
    def y(self, val: int) -> None:
        self.raw[PRTY_OFF_SAVED_Y] = max(0, min(63, val))

    @property
    def sentinel(self) -> int:
        return self.raw[PRTY_OFF_SENTINEL]

    @property
    def slot_ids(self) -> list[int]:
        return [self.raw[PRTY_OFF_SLOT_IDS + i] for i in range(4)]

    @slot_ids.setter
    def slot_ids(self, ids: list[int]) -> None:
        for i, sid in enumerate(ids[:4]):
            self.raw[PRTY_OFF_SLOT_IDS + i] = max(0, min(19, sid))

    def to_dict(self) -> dict:
        return {
            'transport': self.transport,
            'party_size': self.party_size,
            'location_type': self.location_type,
            'x': self.x, 'y': self.y,
            'slot_ids': self.slot_ids,
        }

    def display(self) -> None:
        print(f"  Transport:     {self.transport}")
        print(f"  Party size:    {self.party_size}")
        print(f"  Location:      {self.location_type}")
        print(f"  Coordinates:   ({self.x}, {self.y})")
        print(f"  Roster slots:  {self.slot_ids}")


def cmd_view(args) -> None:
    game_dir = args.game_dir

    prty_path = resolve_single_file(game_dir, 'PRTY')
    if not prty_path:
        print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    with open(prty_path, 'rb') as f:
        prty_data = f.read()
    party = PartyState(prty_data)

    plrs_path = resolve_single_file(game_dir, 'PLRS')

    active_chars = []
    if plrs_path:
        with open(plrs_path, 'rb') as f:
            plrs_data = f.read()
        for i in range(min(4, len(plrs_data) // CHAR_RECORD_SIZE)):
            offset = i * CHAR_RECORD_SIZE
            active_chars.append(Character(plrs_data[offset:offset + CHAR_RECORD_SIZE]))

    if args.json:
        result = {
            'party': party.to_dict(),
            'active_characters': [c.to_dict() for c in active_chars if not c.is_empty],
        }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Save State ===\n")
    print(f"  --- Party Info (PRTY) ---")
    party.display()

    if active_chars:
        print(f"\n  --- Active Characters (PLRS) ---\n")
        for i, char in enumerate(active_chars):
            if not char.is_empty:
                char.display(i)

    # Load SOSA for mini-map if available
    sosa_path = resolve_single_file(game_dir, 'SOSA')

    if sosa_path and not args.brief:
        with open(sosa_path, 'rb') as f:
            sosa_data = f.read()
        print(f"  --- Overworld State (SOSA, scaled 4:1) ---\n")
        for y in range(0, 64, 4):
            row = '  '
            for x in range(0, 64, 2):
                offset = y * 64 + x
                if offset < len(sosa_data):
                    ch = tile_char(sosa_data[offset])
                    # Mark party position
                    if abs(x - party.x) <= 1 and abs(y - party.y) <= 1:
                        ch = '@'
                    row += ch
                else:
                    row += ' '
            print(row)

    print()


def cmd_edit(args) -> None:
    game_dir = args.game_dir
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    prty_path = resolve_single_file(game_dir, 'PRTY')
    if not prty_path:
        print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    with open(prty_path, 'rb') as f:
        data = bytearray(f.read())
    party = PartyState(data)

    prty_modified = False
    if args.transport is not None:
        party.transport = args.transport; prty_modified = True
    if args.x is not None:
        party.x = args.x; prty_modified = True
    if args.y is not None:
        party.y = args.y; prty_modified = True
    if args.party_size is not None:
        party.party_size = args.party_size; prty_modified = True
    if args.slot_ids is not None:
        party.slot_ids = args.slot_ids; prty_modified = True

    # PLRS character editing
    plrs_modified = False
    plrs_slot = getattr(args, 'plrs_slot', None)
    if plrs_slot is not None:
        plrs_path = resolve_single_file(game_dir, 'PLRS')
        if not plrs_path:
            print(f"Error: PLRS file not found in {game_dir}", file=sys.stderr)
            sys.exit(1)
        with open(plrs_path, 'rb') as f:
            plrs_data = bytearray(f.read())

        if plrs_slot < 0 or plrs_slot >= min(4, len(plrs_data) // CHAR_RECORD_SIZE):
            print(f"Error: PLRS slot {plrs_slot} out of range", file=sys.stderr)
            sys.exit(1)

        offset = plrs_slot * CHAR_RECORD_SIZE
        char = Character(plrs_data[offset:offset + CHAR_RECORD_SIZE])

        if getattr(args, 'name', None) is not None:
            char.name = args.name; plrs_modified = True
        if getattr(args, 'str', None) is not None:
            char.strength = args.str; plrs_modified = True
        if getattr(args, 'dex', None) is not None:
            char.dexterity = args.dex; plrs_modified = True
        if getattr(args, 'int_', None) is not None:
            char.intelligence = args.int_; plrs_modified = True
        if getattr(args, 'wis', None) is not None:
            char.wisdom = args.wis; plrs_modified = True
        if getattr(args, 'hp', None) is not None:
            char.hp = args.hp
            char.max_hp = max(char.max_hp, args.hp)
            plrs_modified = True
        if getattr(args, 'max_hp', None) is not None:
            char.max_hp = args.max_hp; plrs_modified = True
        if getattr(args, 'mp', None) is not None:
            char.mp = args.mp; plrs_modified = True
        if getattr(args, 'gold', None) is not None:
            char.gold = args.gold; plrs_modified = True
        if getattr(args, 'exp', None) is not None:
            char.exp = args.exp; plrs_modified = True
        if getattr(args, 'food', None) is not None:
            char.food = args.food; plrs_modified = True

        if plrs_modified:
            plrs_data[offset:offset + CHAR_RECORD_SIZE] = char.raw
            print(f"Modified PLRS slot {plrs_slot}:")
            char.display(plrs_slot)

            if not dry_run:
                plrs_output = args.output if args.output else plrs_path
                if do_backup and (not args.output or args.output == plrs_path):
                    backup_file(plrs_path)
                with open(plrs_output, 'wb') as f:
                    f.write(plrs_data)
                print(f"Saved PLRS to {plrs_output}")

    if not prty_modified and not plrs_modified:
        print("No modifications specified.")
        return

    if prty_modified:
        if dry_run:
            print("Dry run - no changes written.")
            party.display()
            return
        output = args.output if args.output else prty_path
        if do_backup and (not args.output or args.output == prty_path):
            backup_file(prty_path)
        with open(output, 'wb') as f:
            f.write(bytes(party.raw) + data[PRTY_FILE_SIZE:])
        print(f"Saved party state to {output}")
        party.display()
    elif dry_run:
        print("Dry run - no changes written.")


def cmd_import(args) -> None:
    """Import save state from JSON."""
    game_dir = args.game_dir
    do_backup = getattr(args, 'backup', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    party_data = jdata.get('party', {})
    if party_data:
        prty_path = resolve_single_file(game_dir, 'PRTY')
        if not prty_path:
            print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
            sys.exit(1)
        with open(prty_path, 'rb') as f:
            data = bytearray(f.read())
        party = PartyState(data)

        if 'transport' in party_data:
            party.transport = party_data['transport']
        if 'party_size' in party_data:
            party.party_size = party_data['party_size']
        if 'x' in party_data:
            party.x = party_data['x']
        if 'y' in party_data:
            party.y = party_data['y']
        if 'slot_ids' in party_data:
            party.slot_ids = party_data['slot_ids']

        output = args.output if args.output else prty_path
        if do_backup and (not args.output or args.output == prty_path):
            backup_file(prty_path)
        with open(output, 'wb') as f:
            f.write(bytes(party.raw) + data[PRTY_FILE_SIZE:])
        print(f"Imported party state to {output}")


def _add_plrs_edit_args(p) -> None:
    """Add PLRS character editing arguments."""
    p.add_argument('--plrs-slot', type=int, help='Active character slot (0-3)')
    p.add_argument('--name', help='Character name')
    p.add_argument('--str', type=int, help='Strength (0-99)')
    p.add_argument('--dex', type=int, help='Dexterity (0-99)')
    p.add_argument('--int', type=int, dest='int_', help='Intelligence (0-99)')
    p.add_argument('--wis', type=int, help='Wisdom (0-99)')
    p.add_argument('--hp', type=int, help='Hit points (0-9999)')
    p.add_argument('--max-hp', type=int, help='Max HP (0-9999)')
    p.add_argument('--mp', type=int, help='Magic points (0-99)')
    p.add_argument('--gold', type=int, help='Gold (0-9999)')
    p.add_argument('--exp', type=int, help='Experience (0-9999)')
    p.add_argument('--food', type=int, help='Food (0-9999)')


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('save', help='Save state viewer/editor')
    sub = p.add_subparsers(dest='save_command')

    p_view = sub.add_parser('view', help='View save state')
    p_view.add_argument('game_dir', help='GAME directory')
    p_view.add_argument('--brief', action='store_true', help='Skip overworld map')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit party state')
    p_edit.add_argument('game_dir', help='GAME directory')
    p_edit.add_argument('--transport', help='Transport: horse, ship, foot')
    p_edit.add_argument('--x', type=int, help='X coordinate (0-63)')
    p_edit.add_argument('--y', type=int, help='Y coordinate (0-63)')
    p_edit.add_argument('--party-size', type=int, help='Party size (0-4)')
    p_edit.add_argument('--slot-ids', type=int, nargs='+', help='Roster slot IDs (e.g., 0 1 2 3)')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    _add_plrs_edit_args(p_edit)

    p_import = sub.add_parser('import', help='Import save state from JSON')
    p_import.add_argument('game_dir', help='GAME directory')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')


def dispatch(args) -> None:
    cmd = args.save_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit save {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Save State Viewer/Editor')
    sub = parser.add_subparsers(dest='save_command')

    p_view = sub.add_parser('view', help='View save state')
    p_view.add_argument('game_dir', help='GAME directory')
    p_view.add_argument('--brief', action='store_true')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    p_edit = sub.add_parser('edit', help='Edit party state')
    p_edit.add_argument('game_dir', help='GAME directory')
    p_edit.add_argument('--transport')
    p_edit.add_argument('--x', type=int)
    p_edit.add_argument('--y', type=int)
    p_edit.add_argument('--party-size', type=int)
    p_edit.add_argument('--slot-ids', type=int, nargs='+')
    p_edit.add_argument('--output', '-o')
    p_edit.add_argument('--backup', action='store_true')
    p_edit.add_argument('--dry-run', action='store_true')
    _add_plrs_edit_args(p_edit)

    p_import = sub.add_parser('import', help='Import save state from JSON')
    p_import.add_argument('game_dir', help='GAME directory')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o')
    p_import.add_argument('--backup', action='store_true')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
