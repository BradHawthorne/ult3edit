"""Integration tests for conversion tools, cross-module dispatch, and multi-module workflows."""

import json
import os
import sys

import pytest

from ult3edit.constants import (
    MON_MONSTERS_PER_FILE,
    CON_FILE_SIZE, SPECIAL_FILE_SIZE,
    TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
)
from ult3edit.shapes import encode_overlay_string, extract_overlay_strings


# =============================================================================
# Verify tool tests
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
# Round-trip integration tests (Voidborn sources)
# =============================================================================


class TestRoundTripIntegration:
    """End-to-end: load Voidborn source -> import into binary -> verify."""

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
        assert grid[0][0] == 0  # Unknown char -> tile 0

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
# Cross-module view commands
# =============================================================================


class TestViewOnlyCommands:
    """Tests for view-only commands (equip, spell, shapes export)."""

    def test_equip_view(self, capsys):
        """equip view produces equipment stats table."""
        from ult3edit.equip import cmd_view
        import argparse
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Dagger' in out or 'Leather' in out

    def test_equip_view_json(self, tmp_path):
        """equip view --json produces valid JSON."""
        from ult3edit.equip import cmd_view
        import argparse
        outfile = tmp_path / 'equip.json'
        args = argparse.Namespace(json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'weapons' in result or 'armors' in result

    def test_spell_view(self, capsys):
        """spell view produces spell reference table."""
        from ult3edit.spell import cmd_view
        import argparse
        args = argparse.Namespace(
            json=False, output=None,
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 50

    def test_spell_view_json(self, tmp_path):
        """spell view --json produces valid JSON."""
        from ult3edit.spell import cmd_view
        import argparse
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
        import argparse
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
        import argparse
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
        import argparse
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
        import argparse
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
        import argparse
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
        import argparse
        monfile = tmp_path / 'MONA'
        monfile.write_bytes(bytes(256))
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
        import argparse
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
        import argparse
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        args = argparse.Namespace(
            path=str(con), json=False, output=None,
            validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0


# =============================================================================
# Cross-module dispatch routing
# =============================================================================


class TestDispatchIntegration:
    """Tests for dispatch() functions and CLI filter flags."""

    def test_equip_view_text(self, capsys):
        """equip view text mode shows weapon and armor tables."""
        from ult3edit.equip import cmd_view
        import argparse
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
        import argparse
        args = argparse.Namespace(equip_command='view', json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Weapons' in out

    def test_equip_dispatch_none(self, capsys):
        """equip dispatch with no subcommand shows usage."""
        from ult3edit.equip import dispatch
        import argparse
        args = argparse.Namespace(equip_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_spell_wizard_only(self, capsys):
        """spell view --wizard-only shows only wizard spells."""
        from ult3edit.spell import cmd_view
        import argparse
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
        import argparse
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
        import argparse
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_combat_dispatch_view(self, tmp_path, capsys):
        """combat dispatch routes 'view' correctly."""
        from ult3edit.combat import dispatch
        import argparse
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
        import argparse
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
        from ult3edit.constants import PRTY_FILE_SIZE
        import argparse
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
        import argparse
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
        import argparse
        sosa = tmp_path / 'SOSA'
        sosa.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            sound_command='view', path=str(sosa),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0


# =============================================================================
# Cross-module import validation
# =============================================================================


class TestImportTypeValidation:
    """Tests for graceful handling of invalid JSON values in import paths."""

    def test_sound_import_non_int_in_raw_exits(self, tmp_path):
        """sound cmd_import with non-integer in raw array exits gracefully."""
        from ult3edit.sound import cmd_import as sound_import
        import argparse
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
        import argparse
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
        import argparse
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
        import argparse
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
        import argparse
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
# Verify tool size warnings
# =============================================================================


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
