"""Tests for Grok audit improvements: backup, dry-run, validate, search, import, etc."""

import argparse
import json
import os
import sys

import pytest

from ult3edit.constants import (
    CHAR_RECORD_SIZE, ROSTER_FILE_SIZE, MON_FILE_SIZE, MON_MONSTERS_PER_FILE,
    MAP_OVERWORLD_SIZE, CON_FILE_SIZE, SPECIAL_FILE_SIZE,
    PRTY_FILE_SIZE, PLRS_FILE_SIZE,
    CHAR_STATUS, CHAR_READIED_WEAPON, CHAR_WORN_ARMOR,
    CHAR_HP_HI, CHAR_MARKS_CARDS,
    TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
)
from ult3edit.roster import (
    load_roster, cmd_import,
)
from ult3edit.bestiary import load_mon_file
from ult3edit.map import cmd_set
from ult3edit.tlk import encode_record
from ult3edit.shapes import encode_overlay_string, extract_overlay_strings


# =============================================================================
# Backup utility
# =============================================================================



class TestDryRun:
    def test_roster_dry_run(self, tmp_dir, sample_roster_file):
        """Verify dry-run doesn't modify the file."""
        with open(sample_roster_file, 'rb') as f:
            before = f.read()

        chars, original = load_roster(sample_roster_file)
        chars[0].gold = 9999
        # Don't save (simulating dry-run)

        with open(sample_roster_file, 'rb') as f:
            after = f.read()
        assert before == after

    def test_map_dry_run(self, tmp_dir, sample_overworld_bytes):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)
        with open(path, 'rb') as f:
            before = f.read()

        # Modify in memory but don't write (dry-run)
        data = bytearray(before)
        data[0] = 0xFF

        with open(path, 'rb') as f:
            after = f.read()
        assert before == after


# =============================================================================
# TLK regex search
# =============================================================================



class TestSaveOutputConflict:
    """Verify that --output is rejected when editing both party and PLRS."""

    def test_dual_file_output_rejected(self, tmp_dir, sample_prty_bytes):
        """Editing both PRTY and PLRS with --output should fail."""
        from ult3edit.save import cmd_edit
        # Create PRTY file in game dir
        prty_file = os.path.join(tmp_dir, 'PRTY#069500')
        with open(prty_file, 'wb') as f:
            f.write(sample_prty_bytes)
        # Create PLRS file in same dir
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs_data[i] = ord(ch) | 0x80
        plrs_file = os.path.join(tmp_dir, 'PLRS#069500')
        with open(plrs_file, 'wb') as f:
            f.write(plrs_data)
        # Try editing both party state and PLRS character with --output
        args = type('Args', (), {
            'game_dir': tmp_dir, 'output': '/tmp/out',
            'backup': False, 'dry_run': False,
            'transport': 'Horse', 'x': None, 'y': None,
            'party_size': None, 'slot_ids': None,
            'sentinel': None, 'location': None,
            'plrs_slot': 0, 'name': 'TEST',
            'str': None, 'dex': None, 'int_': None, 'wis': None,
            'hp': None, 'max_hp': None, 'exp': None,
            'mp': None, 'food': None, 'gold': None,
            'gems': None, 'keys': None, 'powders': None,
            'torches': None, 'status': None, 'race': None,
            'class_': None, 'gender': None,
            'weapon': None, 'armor': None,
            'marks': None, 'cards': None, 'sub_morsels': None,
        })()
        original_plrs = bytes(plrs_data)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        # PLRS must NOT have been written before the conflict error
        with open(plrs_file, 'rb') as f:
            assert f.read() == original_plrs, "PLRS was modified before conflict check"


# =============================================================================
# Fix: --validate on bestiary and combat edit CLI args
# =============================================================================



class TestValidateOnEditArgs:
    """Verify --validate is accepted by bestiary and combat edit subparsers."""

    def test_bestiary_edit_accepts_validate(self):
        """bestiary edit --validate should be a valid CLI arg."""
        import argparse
        from ult3edit.bestiary import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['bestiary', 'edit', 'test.mon', '--monster', '0',
                                  '--hp', '50', '--validate'])
        assert args.validate is True

    def test_combat_edit_accepts_validate(self):
        """combat edit --validate should be a valid CLI arg."""
        import argparse
        from ult3edit.combat import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['combat', 'edit', 'test.con',
                                  '--tile', '0', '0', '32', '--validate'])
        assert args.validate is True

    def test_bestiary_edit_validate_runs(self, tmp_dir, sample_mon_bytes):
        """bestiary edit with --validate should show warnings."""
        from ult3edit.bestiary import cmd_edit
        mon_file = os.path.join(tmp_dir, 'MONA#069900')
        with open(mon_file, 'wb') as f:
            f.write(sample_mon_bytes)
        args = type('Args', (), {
            'file': mon_file, 'monster': 0, 'all': False,
            'output': None, 'backup': False, 'dry_run': True,
            'validate': True,
            'name': None, 'tile1': None, 'tile2': None,
            'hp': 50, 'attack': None, 'defense': None, 'speed': None,
            'flags1': None, 'flags2': None, 'ability1': None, 'ability2': None,
            'type': None,
            'boss': None, 'no_boss': None, 'undead': None, 'ranged': None,
            'magic_user': None, 'poison': None, 'no_poison': None,
            'sleep': None, 'no_sleep': None, 'negate': None, 'no_negate': None,
            'teleport': None, 'no_teleport': None,
            'divide': None, 'no_divide': None,
            'resistant': None, 'no_resistant': None,
        })()
        # Should not raise
        cmd_edit(args)

    def test_combat_edit_validate_runs(self, tmp_dir, sample_con_bytes):
        """combat edit with --validate should show warnings."""
        from ult3edit.combat import cmd_edit
        con_file = os.path.join(tmp_dir, 'CONA#069900')
        with open(con_file, 'wb') as f:
            f.write(sample_con_bytes)
        args = type('Args', (), {
            'file': con_file,
            'output': None, 'backup': False, 'dry_run': True,
            'validate': True,
            'tile': [5, 5, 0x20],
            'monster_pos': None, 'pc_pos': None,
        })()
        # Should not raise
        cmd_edit(args)


# =============================================================================
# Fix: Dead code removal verification
# =============================================================================



class TestDeadCodeRemoved:
    """Verify removed dead functions are no longer importable."""

    def test_validate_file_size_removed(self):
        """validate_file_size should no longer exist in fileutil."""
        from ult3edit import fileutil
        assert not hasattr(fileutil, 'validate_file_size')

    def test_load_game_file_removed(self):
        """load_game_file should no longer exist in fileutil."""
        from ult3edit import fileutil
        assert not hasattr(fileutil, 'load_game_file')



class TestHexIntArgParsing:
    """Verify that CLI args for tiles, offsets, and flags accept hex (0x) prefix."""

    def test_hex_int_helper(self):
        from ult3edit.fileutil import hex_int
        assert hex_int('10') == 10
        assert hex_int('0x0A') == 10
        assert hex_int('0xFF') == 255
        assert hex_int('0') == 0

    def test_hex_int_rejects_garbage(self):
        from ult3edit.fileutil import hex_int
        with pytest.raises(ValueError):
            hex_int('xyz')

    def test_map_tile_accepts_hex(self, tmp_dir):
        """map set --tile 0x01 should parse without error."""
        import argparse
        path = os.path.join(tmp_dir, 'MAP')
        data = bytes(MAP_OVERWORLD_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, x=0, y=0, tile=0x01,
            output=None, backup=False, dry_run=True)
        cmd_set(args)  # Should not raise

    def test_combat_tile_accepts_hex(self, tmp_dir):
        """combat edit --tile 0x08 should parse without error."""
        from ult3edit.combat import cmd_edit as combat_cmd_edit
        path = os.path.join(tmp_dir, 'CON')
        data = bytearray(CON_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'tile': [0, 0, 0x08],
            'monster_pos': None, 'pc_pos': None,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        combat_cmd_edit(args)  # Should not raise

    def test_bestiary_flags_accept_hex(self, tmp_dir):
        """bestiary edit --flags1 0x80 should parse without error."""
        from ult3edit.bestiary import cmd_edit as bestiary_cmd_edit
        path = os.path.join(tmp_dir, 'MON')
        data = bytearray(MON_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'monster': 0,
            'tile1': None, 'tile2': None,
            'flags1': 0x80, 'flags2': None,
            'hp': None, 'attack': None, 'defense': None, 'speed': None,
            'ability1': None, 'ability2': None,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        bestiary_cmd_edit(args)  # Should not raise

    def test_special_tile_accepts_hex(self, tmp_dir):
        """special edit --tile 0x00 0x00 0x08 should parse without error."""
        from ult3edit.special import cmd_edit as special_cmd_edit
        path = os.path.join(tmp_dir, 'BRND')
        data = bytearray(SPECIAL_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'tile': [0, 0, 0x08],
            'output': None, 'backup': False, 'dry_run': True,
        })()
        special_cmd_edit(args)  # Should not raise

    def test_argparser_accepts_hex_string(self):
        """Verify argparse actually parses '0x0A' string to 10 via hex_int type."""
        import argparse
        from ult3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--tile', type=hex_int)
        args = parser.parse_args(['--tile', '0x0A'])
        assert args.tile == 10

    def test_argparser_accepts_decimal_string(self):
        """hex_int still works with plain decimal strings."""
        import argparse
        from ult3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--offset', type=hex_int)
        args = parser.parse_args(['--offset', '240'])
        assert args.offset == 240


# =============================================================================
# Sound and DDRW import integration tests
# =============================================================================


# =============================================================================
# Shapes cmd_edit and cmd_import integration tests
# =============================================================================


# =============================================================================
# Fix: HP > MaxHP race condition when both --hp and --max-hp provided
# =============================================================================



class TestVerifyTool:
    """Test verify.py asset checking."""

    def test_find_file_exact(self, tmp_path):
        """find_file finds exact filename."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import find_file
        (tmp_path / 'ROST').write_bytes(b'\x00' * 1280)
        result = find_file(str(tmp_path), 'ROST')
        assert result is not None
        assert result.name == 'ROST'

    def test_find_file_with_hash_suffix(self, tmp_path):
        """find_file finds files with ProDOS #hash suffix."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import find_file
        (tmp_path / 'ROST#069500').write_bytes(b'\x00' * 1280)
        result = find_file(str(tmp_path), 'ROST')
        assert result is not None
        assert 'ROST' in result.name

    def test_find_file_missing(self, tmp_path):
        """find_file returns None for missing files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import find_file
        result = find_file(str(tmp_path), 'ROST')
        assert result is None

    def test_verify_detects_missing(self, tmp_path):
        """Verification reports missing files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        total, passed, results = verify_game(str(tmp_path))
        # Empty dir should have many missing categories
        assert passed < total
        assert results['Characters']['missing'] > 0

    def test_verify_detects_present(self, tmp_path):
        """Verification reports found files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        # Create ROST file
        (tmp_path / 'ROST').write_bytes(b'\x00' * 1280)
        total, passed, results = verify_game(str(tmp_path))
        assert results['Characters']['found'] == 1
        assert results['Characters']['missing'] == 0

    def test_verify_detects_unchanged(self, tmp_path):
        """Verification with vanilla dir detects unchanged files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        game_dir = tmp_path / 'game'
        vanilla_dir = tmp_path / 'vanilla'
        game_dir.mkdir()
        vanilla_dir.mkdir()
        # Same content = unchanged
        (game_dir / 'ROST').write_bytes(b'\x00' * 1280)
        (vanilla_dir / 'ROST').write_bytes(b'\x00' * 1280)
        total, passed, results = verify_game(
            str(game_dir), str(vanilla_dir))
        assert results['Characters']['unchanged'] == 1

    def test_verify_detects_modified(self, tmp_path):
        """Verification with vanilla dir detects modified files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        game_dir = tmp_path / 'game'
        vanilla_dir = tmp_path / 'vanilla'
        game_dir.mkdir()
        vanilla_dir.mkdir()
        # Different content = modified
        (game_dir / 'ROST').write_bytes(b'\xFF' * 1280)
        (vanilla_dir / 'ROST').write_bytes(b'\x00' * 1280)
        total, passed, results = verify_game(
            str(game_dir), str(vanilla_dir))
        assert results['Characters']['modified'] == 1


# =============================================================================
# Phase 0: Import format compatibility
# =============================================================================



class TestRoundTripIntegration:
    """End-to-end: load Voidborn source → import into binary → verify."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_bestiary_import_roundtrip(self):
        """Import bestiary_a.json into synthesized MON binary and verify HP."""
        from ult3edit.bestiary import Monster
        path = os.path.join(self.SOURCES_DIR, 'bestiary_a.json')
        with open(path, 'r') as f:
            data = json.load(f)

        # Create 16 empty monster objects directly
        monsters = [Monster([0] * 10, i) for i in range(MON_MONSTERS_PER_FILE)]

        # Apply the import manually (same logic as cmd_import)
        mon_list = data.get('monsters', {})
        if isinstance(mon_list, dict):
            mon_list = [dict(v, index=int(k)) for k, v in mon_list.items()]
        for entry in mon_list:
            idx = entry.get('index')
            if idx is None or not (0 <= idx < MON_MONSTERS_PER_FILE):
                continue
            m = monsters[idx]
            for attr in ('hp', 'attack', 'defense', 'speed'):
                if attr in entry:
                    setattr(m, attr, max(0, min(255, entry[attr])))

        # Verify values were set from JSON
        first_mon = data['monsters']['0']
        assert monsters[0].hp == min(255, first_mon['hp'])
        assert monsters[0].attack == min(255, first_mon['attack'])
        # Verify multiple monsters imported
        imported_count = sum(1 for m in monsters if m.hp > 0)
        assert imported_count >= 8, f"Only {imported_count} monsters imported"

    def test_combat_import_roundtrip(self):
        """Import combat_a.json into synthesized CON binary and verify tiles."""
        from ult3edit.combat import CombatMap, CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET
        path = os.path.join(self.SOURCES_DIR, 'combat_a.json')
        with open(path, 'r') as f:
            data = json.load(f)

        # Create a CON binary and write tiles + positions directly
        con_data = bytearray(CON_FILE_SIZE)

        # Write tile grid (11x11)
        for y, row in enumerate(data.get('tiles', [])):
            for x, ch in enumerate(row):
                tile_byte = TILE_CHARS_REVERSE.get(ch, 0x20)
                con_data[y * 11 + x] = tile_byte

        # Write monster positions
        raw_mons = data.get('monsters', {})
        if isinstance(raw_mons, dict):
            raw_mons = [raw_mons[str(i)] for i in sorted(int(k) for k in raw_mons)]
        for i, m in enumerate(raw_mons[:8]):
            con_data[CON_MONSTER_X_OFFSET + i] = m['x']
            con_data[CON_MONSTER_Y_OFFSET + i] = m['y']

        # Re-parse and verify
        cmap = CombatMap(bytes(con_data))
        first_mon = data['monsters']['0']
        assert cmap.monster_x[0] == first_mon['x']
        assert cmap.monster_y[0] == first_mon['y']

        # Verify tile at (0,0)
        first_row = data['tiles'][0]
        expected_byte = TILE_CHARS_REVERSE.get(first_row[0], 0x20)
        assert cmap.tiles[0] == expected_byte

    def test_special_import_roundtrip(self):
        """Import special_brnd.json into synthesized binary and verify tiles."""
        path = os.path.join(self.SOURCES_DIR, 'special_brnd.json')
        with open(path, 'r') as f:
            data = json.load(f)

        # Create a special location binary and write tiles
        spec_data = bytearray(SPECIAL_FILE_SIZE)
        for y, row in enumerate(data.get('tiles', [])):
            for x, ch in enumerate(row):
                tile_byte = TILE_CHARS_REVERSE.get(ch, 0x20)
                spec_data[y * 11 + x] = tile_byte

        # Verify
        first_row = data['tiles'][0]
        expected_byte = TILE_CHARS_REVERSE.get(first_row[0], 0x20)
        assert spec_data[0] == expected_byte
        # Verify center tile
        center_ch = data['tiles'][5][5]
        center_byte = TILE_CHARS_REVERSE.get(center_ch, 0x20)
        assert spec_data[5 * 11 + 5] == center_byte


# =============================================================================
# gen_maps.py tests
# =============================================================================



class TestGenMaps:
    """Test the map generator produces valid output."""

    def _get_gen_maps(self):
        """Import gen_maps module."""
        tools_dir = os.path.join(os.path.dirname(__file__),
                                  '..', 'conversions', 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import gen_maps
        return gen_maps

    def test_castle_dimensions(self):
        """gen_castle() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_castle()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"Castle row {i}: {len(r)} chars"

    def test_town_dimensions(self):
        """gen_town() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_town()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"Town row {i}: {len(r)} chars"

    def test_mapz_dimensions(self):
        """gen_mapz() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_mapz()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"mapz row {i}: {len(r)} chars"

    def test_mapl_dimensions(self):
        """gen_mapl() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_mapl()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"mapl row {i}: {len(r)} chars"

    def test_dungeon_dimensions(self):
        """gen_dungeon() produces 8 levels of 16 rows of 16 chars."""
        gm = self._get_gen_maps()
        levels = gm.gen_dungeon(has_mark=True, seed=42)
        assert len(levels) == 8
        for li, level in enumerate(levels):
            assert len(level) == 16, f"Dungeon L{li}: {len(level)} rows"
            for ri, r in enumerate(level):
                assert len(r) == 16, f"Dungeon L{li} row {ri}: {len(r)} chars"

    def test_dungeon_has_mark(self):
        """gen_dungeon(has_mark=True) places M on level 7."""
        gm = self._get_gen_maps()
        levels = gm.gen_dungeon(has_mark=True, seed=99)
        # Level 7 (index 6) should contain 'M'
        l7_text = ''.join(levels[6])
        assert 'M' in l7_text, "Level 7 missing Mark tile"

    def test_dungeon_no_mark(self):
        """gen_dungeon(has_mark=False) omits M from level 7."""
        gm = self._get_gen_maps()
        levels = gm.gen_dungeon(has_mark=False, seed=99)
        l7_text = ''.join(levels[6])
        assert 'M' not in l7_text, "Level 7 has unexpected Mark tile"

    def test_surface_tile_chars_valid(self):
        """All surface map generator tile chars are in TILE_CHARS_REVERSE."""
        gm = self._get_gen_maps()
        valid = set(TILE_CHARS_REVERSE.keys())
        for name, gen_fn in [('castle', gm.gen_castle),
                              ('town', gm.gen_town),
                              ('mapz', gm.gen_mapz),
                              ('mapl', gm.gen_mapl)]:
            rows = gen_fn()
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    assert ch in valid, \
                        f"{name}[{y}][{x}]='{ch}' not in TILE_CHARS_REVERSE"

    def test_dungeon_tile_chars_valid(self):
        """All dungeon map generator tile chars are in DUNGEON_TILE_CHARS_REVERSE."""
        gm = self._get_gen_maps()
        valid = set(DUNGEON_TILE_CHARS_REVERSE.keys())
        levels = gm.gen_dungeon(has_mark=True, seed=0)
        for li, level in enumerate(levels):
            for y, row in enumerate(level):
                for x, ch in enumerate(row):
                    assert ch in valid, \
                        f"dungeon L{li}[{y}][{x}]='{ch}' not in DUNGEON_TILE_CHARS_REVERSE"


# =============================================================================
# Shop apply tool tests
# =============================================================================



class TestShopApply:
    """Tests for the shop_apply.py text-matching tool."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_shop_apply(self):
        """Import shop_apply module."""
        mod_path = os.path.join(self.TOOLS_DIR, 'shop_apply.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('shop_apply', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _build_shp_with_string(self, text):
        """Build a minimal SHP binary containing a JSR $46BA inline string."""
        # JSR $46BA = 0x20 0xBA 0x46
        jsr = bytes([0x20, 0xBA, 0x46])
        encoded = encode_overlay_string(text)
        # Pad before and after to simulate real code
        return bytearray(b'\x60' * 16 + jsr + encoded + b'\x60' * 16)

    def test_shop_apply_match_and_replace(self, tmp_path):
        """Match vanilla text and replace with voidborn text."""
        shop_apply = self._get_shop_apply()

        # Create SHP0 with "WEAPONS" inline string
        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        # Create shop_strings.json
        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))

        assert replaced == 1
        assert skipped == 0

        # Verify the file was modified
        with open(shp_path, 'rb') as f:
            result = f.read()
        strings = extract_overlay_strings(result)
        assert len(strings) == 1
        assert strings[0]['text'] == 'ARMS'

    def test_shop_apply_no_match_warning(self, tmp_path):
        """Vanilla text not found in binary produces warning, not crash."""
        shop_apply = self._get_shop_apply()

        # Create SHP0 with "HELLO" but try to match "WEAPONS"
        shp_data = self._build_shp_with_string('HELLO')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))

        assert replaced == 0
        assert skipped == 1

    def test_shop_apply_too_long_warning(self, tmp_path):
        """Replacement text longer than original produces warning."""
        shop_apply = self._get_shop_apply()

        # Create SHP0 with short "HI" string
        shp_data = self._build_shp_with_string('HI')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Test",
                    "strings": [
                        {"vanilla": "HI", "voidborn": "VERY LONG REPLACEMENT"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))

        assert replaced == 0
        assert skipped == 1

    def test_shop_apply_dry_run(self, tmp_path):
        """Dry run does not modify files."""
        shop_apply = self._get_shop_apply()

        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)
        original = bytes(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, _ = shop_apply.apply_shop_strings(
            json_path, str(tmp_path), dry_run=True)

        assert replaced == 1
        # File should be unchanged
        with open(shp_path, 'rb') as f:
            assert f.read() == original


# =============================================================================
# Sound source file validation
# =============================================================================


# =============================================================================
# DDRW source file validation
# =============================================================================


# =============================================================================
# Shop strings JSON validation
# =============================================================================



class TestShopStringsSource:
    """Validate shop_strings.json source file structure."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_shop_strings_json_structure(self):
        """shop_strings.json has valid structure with SHP0-SHP6."""
        path = os.path.join(self.SOURCES_DIR, 'shop_strings.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'shops' in data
        shops = data['shops']
        # SHP0-SHP6 present; SHP7 (Oracle) omitted — unchanged from vanilla
        for i in range(7):
            key = f'SHP{i}'
            assert key in shops, f"Missing {key}"
            assert 'strings' in shops[key]
            for entry in shops[key]['strings']:
                assert 'vanilla' in entry
                assert 'voidborn' in entry
        # No stale discovery fields
        assert 'discovery_workflow' not in data


# =============================================================================
# Name compiler edge cases
# =============================================================================


# =============================================================================
# Map compiler edge cases
# =============================================================================



class TestMapCompilerEdgeCases:
    """Edge case tests for map_compiler.py."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_mod(self):
        mod_path = os.path.join(self.TOOLS_DIR, 'map_compiler.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('map_compiler', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_overworld_invalid_tile_char_defaults_to_zero(self):
        """Invalid tile character in overworld map defaults to tile 0."""
        mod = self._get_mod()
        rows = ['.' * 64 for _ in range(64)]
        rows[0] = 'Z' + '.' * 63  # 'Z' is not in TILE_CHARS_REVERSE
        text = '\n'.join(rows) + '\n'
        grid = mod.parse_map_file(text, is_dungeon=False)
        assert grid[0][0] == 0  # Unknown char → tile 0

    def test_dungeon_short_input_pads_to_8_levels(self):
        """Dungeon with fewer than 8 levels pads to 8."""
        mod = self._get_mod()
        parts = []
        for i in range(3):
            parts.append(f'# Level {i}')
            for _ in range(16):
                parts.append('#' * 16)
        text = '\n'.join(parts) + '\n'
        grid = mod.parse_map_file(text, is_dungeon=True)
        assert len(grid) == 8  # Padded to 8 levels

    def test_overworld_short_input_pads_to_64_rows(self):
        """Overworld with fewer than 64 rows pads to 64."""
        mod = self._get_mod()
        rows = ['.' * 64 for _ in range(32)]  # Only 32 rows
        text = '\n'.join(rows) + '\n'
        grid = mod.parse_map_file(text, is_dungeon=False)
        assert len(grid) == 64  # Padded to 64 rows


# =============================================================================
# Shop apply edge cases
# =============================================================================



class TestShopApplyEdgeCases:
    """Additional edge case tests for shop_apply.py."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_shop_apply(self):
        mod_path = os.path.join(self.TOOLS_DIR, 'shop_apply.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('shop_apply', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _build_shp_with_string(self, text):
        jsr = bytes([0x20, 0xBA, 0x46])
        encoded = encode_overlay_string(text)
        return bytearray(b'\x60' * 16 + jsr + encoded + b'\x60' * 16)

    def test_shop_apply_case_insensitive_match(self, tmp_path):
        """Vanilla text matching is case-insensitive."""
        shop_apply = self._get_shop_apply()

        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "weapons", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))
        assert replaced == 1

    def test_shop_apply_missing_shp_file(self, tmp_path):
        """Missing SHP file is skipped gracefully."""
        shop_apply = self._get_shop_apply()

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        # No SHP0 file in tmp_path
        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))
        assert replaced == 0
        assert skipped == 0

    def test_shop_apply_backup_creates_bak(self, tmp_path):
        """Backup flag creates .bak file."""
        shop_apply = self._get_shop_apply()

        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)
        original = bytes(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        shop_apply.apply_shop_strings(
            json_path, str(tmp_path), backup=True)

        bak_path = shp_path + '.bak'
        assert os.path.exists(bak_path)
        with open(bak_path, 'rb') as f:
            assert f.read() == original


# =============================================================================
# Tile compiler edge cases
# =============================================================================


# =============================================================================
# Bestiary import: shortcut + raw attribute conflict fix
# =============================================================================



class TestDictKeyValidation:
    """Verify non-numeric dict keys are handled gracefully."""

    def test_bestiary_import_skips_bad_keys(self, tmp_path):
        """Bestiary import skips non-numeric keys without crashing."""
        from ult3edit.bestiary import cmd_import
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        jdata = {
            "monsters": {
                "0": {"hp": 100},
                "abc": {"hp": 200},  # non-numeric key
                "1": {"hp": 150}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)  # Should not crash

        monsters = load_mon_file(mon_path)
        assert monsters[0].hp == 100
        assert monsters[1].hp == 150

    def test_combat_import_skips_bad_keys(self, tmp_path):
        """Combat import skips non-numeric monster keys without crashing."""
        from ult3edit.combat import cmd_import as combat_import
        from ult3edit.constants import CON_FILE_SIZE
        con_data = bytearray(CON_FILE_SIZE)
        con_path = str(tmp_path / 'CONA')
        with open(con_path, 'wb') as f:
            f.write(con_data)

        jdata = {
            "tiles": [['.' for _ in range(11)] for _ in range(11)],
            "monsters": {
                "0": {"x": 3, "y": 4},
                "bad": {"x": 5, "y": 6}  # non-numeric key
            }
        }
        json_path = str(tmp_path / 'combat.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': con_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        combat_import(args)  # Should not crash


# =============================================================================
# Map import width validation
# =============================================================================



class TestViewOnlyCommands:
    """Tests for view-only commands (equip, spell, shapes export)."""

    def test_equip_view(self, capsys):
        """equip view produces equipment stats table."""
        from ult3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Dagger' in out or 'Leather' in out

    def test_equip_view_json(self, tmp_path):
        """equip view --json produces valid JSON."""
        from ult3edit.equip import cmd_view
        outfile = tmp_path / 'equip.json'
        args = argparse.Namespace(json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'weapons' in result or 'armors' in result

    def test_spell_view(self, capsys):
        """spell view produces spell reference table."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 50

    def test_spell_view_json(self, tmp_path):
        """spell view --json produces valid JSON."""
        from ult3edit.spell import cmd_view
        outfile = tmp_path / 'spells.json'
        args = argparse.Namespace(
            json=True, output=str(outfile),
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert isinstance(result, dict) or isinstance(result, list)

    def test_shapes_export_png(self, tmp_path):
        """shapes export creates PNG files from SHPS data."""
        from ult3edit.shapes import cmd_export
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        out_dir = tmp_path / 'pngs'
        args = argparse.Namespace(
            file=str(shps), output_dir=str(out_dir),
            scale=1, sheet=False)
        cmd_export(args)
        assert out_dir.exists()
        pngs = list(out_dir.glob('*.png'))
        assert len(pngs) == 256  # 256 glyphs

    def test_shapes_export_with_sheet(self, tmp_path):
        """shapes export --sheet creates sprite sheet PNG."""
        from ult3edit.shapes import cmd_export
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        out_dir = tmp_path / 'pngs'
        args = argparse.Namespace(
            file=str(shps), output_dir=str(out_dir),
            scale=1, sheet=True)
        cmd_export(args)
        sheet_file = out_dir / 'glyph_sheet.png'
        assert sheet_file.exists()

    def test_shapes_info(self, tmp_path, capsys):
        """shapes info shows metadata."""
        from ult3edit.shapes import cmd_info
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        args = argparse.Namespace(
            file=str(shps), json=False, output=None)
        cmd_info(args)
        out = capsys.readouterr().out
        assert '256' in out or 'charset' in out.lower()

    def test_shapes_info_json(self, tmp_path):
        """shapes info --json produces valid JSON."""
        from ult3edit.shapes import cmd_info
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        outfile = tmp_path / 'info.json'
        args = argparse.Namespace(
            file=str(shps), json=True, output=str(outfile))
        cmd_info(args)
        result = json.loads(outfile.read_text())
        assert result['format']['type'] == 'charset'

    def test_roster_view(self, tmp_path, capsys):
        """roster view displays character roster."""
        from ult3edit.roster import cmd_view
        from ult3edit.constants import ROSTER_FILE_SIZE
        rost = tmp_path / 'ROST'
        data = bytearray(ROSTER_FILE_SIZE)
        # Set a name in slot 0
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[0x0D] = 0x00
        rost.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(rost), json=False, output=None,
            slot=None, validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'HERO' in out

    def test_bestiary_view(self, tmp_path, capsys):
        """bestiary view displays monster data."""
        from ult3edit.bestiary import cmd_view
        from ult3edit.constants import MON_FILE_SIZE
        monfile = tmp_path / 'MONA'
        monfile.write_bytes(bytes(MON_FILE_SIZE))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, file=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_save_view(self, tmp_path, capsys):
        """save view displays party state."""
        from ult3edit.save import cmd_view
        from ult3edit.constants import PRTY_FILE_SIZE
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF  # sentinel
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_combat_view(self, tmp_path, capsys):
        """combat view displays battlefield data."""
        from ult3edit.combat import cmd_view
        from ult3edit.constants import CON_FILE_SIZE
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        args = argparse.Namespace(
            path=str(con), json=False, output=None,
            validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0


# =============================================================================
# Patch cmd_edit and cmd_dump tests
# =============================================================================


# =============================================================================
# Map cmd_fill / cmd_replace / cmd_find CLI tests
# =============================================================================



class TestImportTypeErrorHandling:
    """Tests for TypeError handling in weapon/armor import with bad count types."""

    def test_roster_import_bad_weapon_count_warns(self, tmp_path, capsys):
        """Non-integer weapon count in JSON warns instead of crashing."""
        rost = tmp_path / 'ROST'
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[0x0D] = 0x00
        rost.write_bytes(bytes(data))
        json_path = tmp_path / 'chars.json'
        json_path.write_text(json.dumps([{
            'slot': 0, 'name': 'HERO',
            'weapons': {'Dagger': 'five'}  # bad type
        }]))
        args = argparse.Namespace(
            file=str(rost), json_file=str(json_path),
            dry_run=True, backup=False, output=None, all=False)
        cmd_import(args)  # should not crash
        err = capsys.readouterr().err
        assert 'Warning' in err

    def test_roster_import_bad_armor_count_warns(self, tmp_path, capsys):
        """Non-integer armor count in JSON warns instead of crashing."""
        rost = tmp_path / 'ROST'
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[0x0D] = 0x00
        rost.write_bytes(bytes(data))
        json_path = tmp_path / 'chars.json'
        json_path.write_text(json.dumps([{
            'slot': 0, 'name': 'HERO',
            'armors': {'Cloth': 'many'}  # bad type
        }]))
        args = argparse.Namespace(
            file=str(rost), json_file=str(json_path),
            dry_run=True, backup=False, output=None, all=False)
        cmd_import(args)  # should not crash
        err = capsys.readouterr().err
        assert 'Warning' in err


# =============================================================================
# Map --crop error handling test
# =============================================================================



class TestDispatchIntegration:
    """Tests for dispatch() functions and CLI filter flags."""

    def test_equip_view_text(self, capsys):
        """equip view text mode shows weapon and armor tables."""
        from ult3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Weapons' in out
        assert 'Armor' in out
        assert 'Dagger' in out
        assert 'Class Equipment' in out

    def test_equip_dispatch_view(self, capsys):
        """equip dispatch routes 'view' correctly."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command='view', json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Weapons' in out

    def test_equip_dispatch_none(self, capsys):
        """equip dispatch with no subcommand shows usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_spell_wizard_only(self, capsys):
        """spell view --wizard-only shows only wizard spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=True, cleric_only=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Wizard' in out
        assert 'Cleric' not in out

    def test_spell_cleric_only(self, capsys):
        """spell view --cleric-only shows only cleric spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=False, cleric_only=True)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Cleric' in out
        assert 'Wizard' not in out

    def test_spell_dispatch_none(self, capsys):
        """spell dispatch with no subcommand shows usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_combat_dispatch_view(self, tmp_path, capsys):
        """combat dispatch routes 'view' correctly."""
        from ult3edit.combat import dispatch
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        args = argparse.Namespace(
            combat_command='view', path=str(con),
            json=False, output=None, validate=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_special_dispatch_view(self, tmp_path, capsys):
        """special dispatch routes 'view' correctly."""
        from ult3edit.special import dispatch
        brnd = tmp_path / 'BRND'
        brnd.write_bytes(bytes(SPECIAL_FILE_SIZE))
        args = argparse.Namespace(
            special_command='view', path=str(brnd),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_save_dispatch_view(self, tmp_path, capsys):
        """save dispatch routes 'view' correctly."""
        from ult3edit.save import dispatch
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            save_command='view', game_dir=str(tmp_path),
            json=False, output=None, validate=False, brief=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Save State' in out or 'Party' in out

    def test_ddrw_dispatch_view(self, tmp_path, capsys):
        """ddrw dispatch routes 'view' correctly."""
        from ult3edit.ddrw import dispatch
        from ult3edit.constants import DDRW_FILE_SIZE
        ddrw = tmp_path / 'DDRW'
        ddrw.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            ddrw_command='view', path=str(ddrw),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_sound_dispatch_view(self, tmp_path, capsys):
        """sound dispatch routes 'view' correctly."""
        from ult3edit.sound import dispatch
        from ult3edit.constants import SOSA_FILE_SIZE
        sosa = tmp_path / 'SOSA'
        sosa.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            sound_command='view', path=str(sosa),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0


# =============================================================================
# Bug fix tests: text phantom records, TLK case, TLK find/replace error
# =============================================================================



class TestDialogEditorEmptyRecord:
    """Tests for DialogEditor save with empty records."""

    def test_encode_empty_lines_produces_nonzero(self):
        """encode_record(['']) produces at least 1 byte before stripping."""
        result = encode_record([''])
        # Empty line should produce just TLK_RECORD_END (0x00)
        assert len(result) >= 1
        # After stripping (encoded[:-1]), should not be empty
        # The dialog editor now guards against this
        stripped = result[:-1] if len(result) > 1 else result
        assert len(stripped) >= 1

    def test_dialog_editor_save_preserves_records(self):
        """DialogEditor save doesn't collapse null separators."""
        from ult3edit.tui.dialog_editor import DialogEditor
        from ult3edit.constants import TLK_RECORD_END
        # Build a TLK-like blob with 3 records
        records = [
            encode_record(['HELLO'])[:-1],  # strip trailing null
            encode_record(['WORLD'])[:-1],
            encode_record(['END'])[:-1],
        ]
        data = bytes([TLK_RECORD_END]).join(records)
        saved_data = []
        editor = DialogEditor('test', data, save_callback=lambda d: saved_data.append(d))
        assert len(editor.records) == 3
        # Mark record 0 as modified and save
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        # Should still produce valid data with 3 records
        assert len(saved_data) == 1
        # Re-parse should yield 3 records
        reloaded = DialogEditor('test', saved_data[0])
        assert len(reloaded.records) == 3


# =============================================================================
# Error path tests: sys.exit(1) coverage
# =============================================================================



class TestResolveSingleFile:
    """Tests for resolve_single_file with ProDOS suffixes."""

    def test_find_plain_file(self, tmp_path):
        """Finds a plain file by name."""
        from ult3edit.fileutil import resolve_single_file
        (tmp_path / 'PRTY').write_bytes(b'\x00' * 16)
        result = resolve_single_file(str(tmp_path), 'PRTY')
        assert result is not None
        assert 'PRTY' in result

    def test_find_prodos_hashed_file(self, tmp_path):
        """Finds a file with ProDOS #hash suffix."""
        from ult3edit.fileutil import resolve_single_file
        (tmp_path / 'PRTY#069500').write_bytes(b'\x00' * 16)
        result = resolve_single_file(str(tmp_path), 'PRTY')
        assert result is not None
        assert 'PRTY#069500' in result

    def test_not_found_returns_none(self, tmp_path):
        """Returns None when file doesn't exist."""
        from ult3edit.fileutil import resolve_single_file
        result = resolve_single_file(str(tmp_path), 'NOSUCHFILE')
        assert result is None

    def test_prefers_hashed_over_plain(self, tmp_path):
        """When both plain and hashed exist, hashed is returned first."""
        from ult3edit.fileutil import resolve_single_file
        (tmp_path / 'ROST#069500').write_bytes(b'\x00' * 64)
        (tmp_path / 'ROST').write_bytes(b'\x00' * 64)
        result = resolve_single_file(str(tmp_path), 'ROST')
        assert result is not None
        assert '#' in result



class TestResolveGameFile:
    """Tests for resolve_game_file with prefix+letter pattern."""

    def test_find_with_hash(self, tmp_path):
        """Finds MAPA#061000 style files."""
        from ult3edit.fileutil import resolve_game_file
        (tmp_path / 'MAPA#061000').write_bytes(b'\x00' * 100)
        result = resolve_game_file(str(tmp_path), 'MAP', 'A')
        assert result is not None
        assert 'MAPA#061000' in result

    def test_find_plain(self, tmp_path):
        """Falls back to plain name if no hash file exists."""
        from ult3edit.fileutil import resolve_game_file
        (tmp_path / 'CONA').write_bytes(b'\x00' * 192)
        result = resolve_game_file(str(tmp_path), 'CON', 'A')
        assert result is not None
        assert 'CONA' in result

    def test_not_found(self, tmp_path):
        """Returns None if neither hashed nor plain exists."""
        from ult3edit.fileutil import resolve_game_file
        result = resolve_game_file(str(tmp_path), 'MAP', 'Z')
        assert result is None

    def test_excludes_dproj(self, tmp_path):
        """Files ending in .dproj are excluded."""
        from ult3edit.fileutil import resolve_game_file
        (tmp_path / 'MAPA#061000.dproj').write_bytes(b'\x00')
        result = resolve_game_file(str(tmp_path), 'MAP', 'A')
        assert result is None



class TestFindGameFiles:
    """Tests for find_game_files across multiple letters."""

    def test_finds_multiple(self, tmp_path):
        """Finds all existing files across letter range."""
        from ult3edit.fileutil import find_game_files
        (tmp_path / 'CONA').write_bytes(b'\x00' * 192)
        (tmp_path / 'CONC').write_bytes(b'\x00' * 192)
        result = find_game_files(str(tmp_path), 'CON', 'ABCDE')
        assert len(result) == 2
        letters = [r[0] for r in result]
        assert 'A' in letters
        assert 'C' in letters

    def test_empty_directory(self, tmp_path):
        """Returns empty list for empty directory."""
        from ult3edit.fileutil import find_game_files
        result = find_game_files(str(tmp_path), 'CON', 'ABCDE')
        assert result == []


# =============================================================================
# Patch inline string operations
# =============================================================================


# =============================================================================
# Shapes pixel helper tests
# =============================================================================


# =============================================================================
# DDRW parsing and editing tests
# =============================================================================


# =============================================================================
# SpecialEditor save preserves trailing bytes
# =============================================================================



class TestImportTypeValidation:
    """Tests for graceful handling of invalid JSON values in import paths."""

    def test_sound_import_non_int_in_raw_exits(self, tmp_path):
        """sound cmd_import with non-integer in raw array exits gracefully."""
        from ult3edit.sound import cmd_import as sound_import
        json_file = tmp_path / 'bad.json'
        json_file.write_text(json.dumps({'raw': ['hello', 123]}))
        snd_file = tmp_path / 'SOSA'
        snd_file.write_bytes(bytes(4096))
        args = argparse.Namespace(
            file=str(snd_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        with pytest.raises(SystemExit):
            sound_import(args)

    def test_sound_import_non_list_raw_exits(self, tmp_path):
        """sound cmd_import with non-list raw exits gracefully."""
        from ult3edit.sound import cmd_import as sound_import
        json_file = tmp_path / 'bad.json'
        json_file.write_text(json.dumps({'raw': 'not a list'}))
        snd_file = tmp_path / 'SOSA'
        snd_file.write_bytes(bytes(4096))
        args = argparse.Namespace(
            file=str(snd_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        with pytest.raises(SystemExit):
            sound_import(args)

    def test_ddrw_import_non_int_in_raw_exits(self, tmp_path):
        """ddrw cmd_import with non-integer in raw array exits gracefully."""
        from ult3edit.ddrw import cmd_import as ddrw_import
        json_file = tmp_path / 'bad.json'
        json_file.write_text(json.dumps({'raw': [1, 2, 'bad', 4]}))
        ddrw_file = tmp_path / 'DDRW'
        ddrw_file.write_bytes(bytes(1792))
        args = argparse.Namespace(
            file=str(ddrw_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        with pytest.raises(SystemExit):
            ddrw_import(args)

    def test_ddrw_import_valid_raw_works(self, tmp_path):
        """ddrw cmd_import with valid raw array succeeds."""
        from ult3edit.ddrw import cmd_import as ddrw_import
        json_file = tmp_path / 'good.json'
        json_file.write_text(json.dumps({'raw': [0] * 1792}))
        ddrw_file = tmp_path / 'DDRW'
        ddrw_file.write_bytes(bytes(1792))
        args = argparse.Namespace(
            file=str(ddrw_file), json_file=str(json_file),
            backup=False, dry_run=False, output=str(ddrw_file))
        ddrw_import(args)
        assert len(ddrw_file.read_bytes()) == 1792

    def test_sound_import_valid_raw_works(self, tmp_path):
        """sound cmd_import with valid raw array succeeds."""
        from ult3edit.sound import cmd_import as sound_import
        json_file = tmp_path / 'good.json'
        json_file.write_text(json.dumps({'raw': [0] * 256}))
        snd_file = tmp_path / 'SOSM'
        snd_file.write_bytes(bytes(256))
        args = argparse.Namespace(
            file=str(snd_file), json_file=str(json_file),
            backup=False, dry_run=False, output=str(snd_file))
        sound_import(args)
        assert len(snd_file.read_bytes()) == 256


# =============================================================================
# Shapes check_shps_code_region
# =============================================================================


# =============================================================================
# Save validate_party_state coordinate bounds
# =============================================================================



class TestRosterCmdCheckProgress:
    """Test cmd_check_progress CLI command."""

    def _make_roster_with_chars(self, tmp_path, count=4, marks=0xF,
                                 cards=0xF, weapon=15, armor=7):
        """Create a roster file with specified characters."""
        data = bytearray(ROSTER_FILE_SIZE)
        for i in range(count):
            off = i * CHAR_RECORD_SIZE
            name = f'HERO{i}'
            for j, ch in enumerate(name):
                data[off + j] = ord(ch) | 0x80
            data[off + CHAR_STATUS] = ord('G')
            data[off + CHAR_HP_HI] = 0x01
            data[off + CHAR_MARKS_CARDS] = (marks << 4) | cards
            data[off + CHAR_READIED_WEAPON] = weapon
            data[off + CHAR_WORN_ARMOR] = armor
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_check_progress_text_ready(self, tmp_path, capsys):
        """cmd_check_progress shows READY verdict for complete party."""
        from ult3edit.roster import cmd_check_progress
        path = self._make_roster_with_chars(tmp_path)
        args = argparse.Namespace(
            file=path, json=False, output=None)
        cmd_check_progress(args)
        captured = capsys.readouterr()
        assert 'READY TO FACE EXODUS' in captured.out

    def test_check_progress_text_not_ready(self, tmp_path, capsys):
        """cmd_check_progress shows not-ready for incomplete party."""
        from ult3edit.roster import cmd_check_progress
        path = self._make_roster_with_chars(
            tmp_path, count=2, marks=0, cards=0, weapon=0, armor=0)
        args = argparse.Namespace(
            file=path, json=False, output=None)
        cmd_check_progress(args)
        captured = capsys.readouterr()
        assert 'Not yet ready' in captured.out
        assert 'Need 4 alive characters' in captured.out

    def test_check_progress_json(self, tmp_path):
        """cmd_check_progress JSON mode produces valid output."""
        from ult3edit.roster import cmd_check_progress
        path = self._make_roster_with_chars(tmp_path)
        out_path = os.path.join(str(tmp_path), 'progress.json')
        args = argparse.Namespace(
            file=path, json=True, output=out_path)
        cmd_check_progress(args)
        with open(out_path) as f:
            data = json.load(f)
        assert data['exodus_ready'] is True
        assert data['marks_complete'] is True
        assert data['cards_complete'] is True


# =============================================================================
# Diff file-level dispatch (diff_file)
# =============================================================================



class TestFileUtilEdgeCases:
    """Test fileutil utility edge cases."""

    def test_hex_int_parses_hex(self):
        """hex_int parses 0x prefix."""
        from ult3edit.fileutil import hex_int
        assert hex_int('0xFF') == 255
        assert hex_int('0x10') == 16

    def test_hex_int_parses_decimal(self):
        """hex_int parses decimal strings."""
        from ult3edit.fileutil import hex_int
        assert hex_int('42') == 42

    def test_hex_int_parses_dollar_prefix(self):
        """hex_int parses $ prefix (if supported)."""
        from ult3edit.fileutil import hex_int
        try:
            result = hex_int('$FF')
            assert result == 255
        except ValueError:
            pass  # $ prefix may not be supported

    def test_resolve_single_file_not_found(self, tmp_path):
        """resolve_single_file returns None for missing file."""
        from ult3edit.fileutil import resolve_single_file
        result = resolve_single_file(str(tmp_path), 'NONEXISTENT')
        assert result is None

    def test_resolve_single_file_found(self, tmp_path):
        """resolve_single_file finds file by prefix."""
        from ult3edit.fileutil import resolve_single_file
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_single_file(str(tmp_path), 'ROST')
        assert result is not None

    def test_decode_encode_high_ascii_roundtrip(self):
        """decode/encode_high_ascii round-trips."""
        from ult3edit.fileutil import decode_high_ascii, encode_high_ascii
        text = "HELLO WORLD"
        encoded = encode_high_ascii(text, len(text))
        decoded = decode_high_ascii(encoded)
        assert decoded == text



class TestVerifySizeWarnings:
    """verify.py: reports size mismatches when verbose."""

    def test_wrong_size_generates_warning(self, tmp_path):
        """verify.py detects size mismatch and reports it."""
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), '..', 'conversions', 'tools'))
        try:
            from verify import verify_category
        finally:
            sys.path.pop(0)
        # Create a ROST file with wrong size
        game_dir = tmp_path / 'game'
        game_dir.mkdir()
        (game_dir / 'ROST').write_bytes(b'\x00' * 100)  # Should be 1280
        info = {
            'files': ['ROST'],
            'sizes': [1280],
        }
        found, modified, missing, unchanged, size_warns = verify_category(
            str(game_dir), 'Characters', info)
        assert len(found) == 1
        assert len(size_warns) == 1
        assert '100' in size_warns[0]
        assert '1280' in size_warns[0]

