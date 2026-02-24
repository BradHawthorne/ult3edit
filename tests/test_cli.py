"""Tests for unified CLI dispatcher."""

import argparse
import json
import subprocess
import sys


def _help_output(module: str, subcmd: str) -> str:
    """Get --help output from a standalone module entry point."""
    result = subprocess.run(
        [sys.executable, '-m', f'ult3edit.{module}', subcmd, '--help'],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout + result.stderr


class TestCLI:
    def test_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', '--help'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'roster' in result.stdout
        assert 'bestiary' in result.stdout
        assert 'spell' in result.stdout
        assert 'equip' in result.stdout
        assert 'disk' in result.stdout

    def test_version(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', '--version'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'ult3edit' in result.stdout

    def test_no_args_shows_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'usage' in result.stdout.lower() or 'positional' in result.stdout.lower()

    def test_spell_view(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'spell', 'view'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'Wizard Spells' in result.stdout
        assert 'Cleric Spells' in result.stdout

    def test_equip_view(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'equip', 'view'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'Weapons' in result.stdout
        assert 'Armor' in result.stdout

    def test_spell_json(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'spell', 'view', '--json'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'wizard' in data
        assert len(data['wizard']) == 16

    def test_equip_json(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'equip', 'view', '--json'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'weapons' in data
        assert 'armors' in data

    def test_all_subcommands_in_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', '--help'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        for cmd in ['roster', 'bestiary', 'map', 'tlk', 'combat',
                     'save', 'special', 'text', 'spell', 'equip', 'disk',
                     'shapes', 'sound', 'patch', 'ddrw', 'diff', 'edit']:
            assert cmd in result.stdout, f"Missing subcommand '{cmd}' in help"

    def test_edit_missing_image(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'edit', '/nonexistent/fake.po'],
            capture_output=True, text=True
        )
        assert result.returncode != 0
        assert 'not found' in result.stderr.lower() or 'error' in result.stderr.lower()


# ── Migrated from test_new_features.py ──

class TestCliParity:
    """Verify standalone main() parsers have full arg parity with register_parser()."""

    def test_roster_main_create_help(self):
        out = _help_output('roster', 'create')
        assert '--name' in out
        assert '--race' in out
        assert '--force' in out
        assert 'Overwrite existing' in out

    def test_bestiary_main_validate(self):
        out = _help_output('bestiary', 'view')
        assert '--validate' in out

    def test_map_main_set_exists(self):
        out = _help_output('map', 'set')
        assert '--tile' in out
        assert '--x' in out
        assert '--y' in out

    def test_map_main_import_exists(self):
        out = _help_output('map', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_map_main_fill_exists(self):
        out = _help_output('map', 'fill')
        assert '--x1' in out
        assert '--tile' in out

    def test_map_main_replace_exists(self):
        out = _help_output('map', 'replace')
        assert '--from' in out
        assert '--to' in out

    def test_map_main_find_exists(self):
        out = _help_output('map', 'find')
        assert '--tile' in out
        assert '--json' in out

    def test_combat_main_edit_exists(self):
        out = _help_output('combat', 'edit')
        assert '--tile' in out
        assert '--monster-pos' in out
        assert '--pc-pos' in out

    def test_combat_main_import_exists(self):
        out = _help_output('combat', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_combat_main_validate(self):
        out = _help_output('combat', 'view')
        assert '--validate' in out

    def test_special_main_edit_exists(self):
        out = _help_output('special', 'edit')
        assert '--tile' in out
        assert '--backup' in out

    def test_special_main_import_exists(self):
        out = _help_output('special', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_save_main_validate(self):
        out = _help_output('save', 'view')
        assert '--validate' in out

    def test_save_main_import_dryrun(self):
        out = _help_output('save', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_text_main_import_exists(self):
        out = _help_output('text', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_tlk_main_edit_help(self):
        out = _help_output('tlk', 'edit')
        assert '--find' in out
        assert '--replace' in out
        assert '--ignore-case' in out

    def test_spell_main_help(self):
        out = _help_output('spell', 'view')
        assert '--wizard-only' in out
        assert '--cleric-only' in out

    def test_equip_main_help(self):
        out = _help_output('equip', 'view')
        assert '--json' in out

    def test_shapes_main_export_help(self):
        out = _help_output('shapes', 'export')
        assert '--scale' in out
        assert '--sheet' in out
        assert 'Scale factor' in out

    def test_sound_main_import_dryrun(self):
        out = _help_output('sound', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_patch_main_dump_help(self):
        out = _help_output('patch', 'dump')
        assert '--offset' in out
        assert '--length' in out
        assert 'Start offset' in out

    def test_ddrw_main_import_dryrun(self):
        out = _help_output('ddrw', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_disk_main_info_help(self):
        out = _help_output('disk', 'info')
        assert '--json' in out
        assert 'image' in out.lower()

    def test_disk_main_list_help(self):
        out = _help_output('disk', 'list')
        assert '--json' in out
        assert '--path' in out

    def test_disk_main_extract_help(self):
        out = _help_output('disk', 'extract')
        assert 'image' in out.lower()

    def test_disk_main_audit_help(self):
        out = _help_output('disk', 'audit')
        assert '--json' in out
        assert '--detail' in out

    def test_diff_main_help(self):
        """diff module standalone main() has correct args."""
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit.diff', '--help'],
            capture_output=True, text=True, timeout=10)
        out = result.stdout + result.stderr
        assert 'path1' in out
        assert 'path2' in out
        assert '--json' in out
        assert '--summary' in out

    def test_map_main_compile_help(self):
        out = _help_output('map', 'compile')
        assert '--dungeon' in out
        assert 'source' in out

    def test_map_main_decompile_help(self):
        out = _help_output('map', 'decompile')
        assert '--output' in out

    def test_shapes_main_compile_help(self):
        out = _help_output('shapes', 'compile')
        assert '--format' in out
        assert 'source' in out

    def test_shapes_main_decompile_help(self):
        out = _help_output('shapes', 'decompile')
        assert '--output' in out

    def test_patch_main_compile_names_help(self):
        out = _help_output('patch', 'compile-names')
        assert 'source' in out
        assert '--output' in out

    def test_patch_main_decompile_names_help(self):
        out = _help_output('patch', 'decompile-names')
        assert '--output' in out

    def test_patch_main_validate_names_help(self):
        out = _help_output('patch', 'validate-names')
        assert 'source' in out

    def test_patch_main_strings_edit_help(self):
        out = _help_output('patch', 'strings-edit')
        assert '--text' in out
        assert '--index' in out
        assert '--vanilla' in out
        assert '--address' in out

    def test_patch_main_strings_import_help(self):
        out = _help_output('patch', 'strings-import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_exod_main_view_help(self):
        out = _help_output('exod', 'view')
        assert '--json' in out

    def test_exod_main_export_help(self):
        out = _help_output('exod', 'export')
        assert '--frame' in out
        assert '--scale' in out

    def test_exod_main_import_help(self):
        out = _help_output('exod', 'import')
        assert '--frame' in out
        assert '--backup' in out
        assert '--dry-run' in out

    def test_exod_main_glyph_help(self):
        out = _help_output('exod', 'glyph')
        assert 'view' in out
        assert 'export' in out
        assert 'import' in out

    def test_exod_main_crawl_help(self):
        out = _help_output('exod', 'crawl')
        assert 'view' in out
        assert 'compose' in out

    def test_disk_main_build_help(self):
        out = _help_output('disk', 'build')
        assert '--vol-name' in out
        assert '--boot-from' in out


class TestCliDispatch:
    """Test CLI dispatcher edge cases."""

    def test_unknown_subcommand(self, capsys):
        """CLI with no subcommand prints help or exits."""
        from ult3edit.cli import main
        sys_argv_backup = sys.argv
        sys.argv = ['ult3edit']
        try:
            main()
        except SystemExit:
            pass  # Expected
        finally:
            sys.argv = sys_argv_backup


# =============================================================================
# Batch 7: Final gaps — combat edit, dispatch fallbacks, directory errors
# =============================================================================


class TestDispatchFallbacks:
    """Test dispatch() fallback for unrecognized subcommands."""

    def test_combat_dispatch_unknown(self, capsys):
        """Combat dispatch with unknown command prints usage."""
        from ult3edit.combat import dispatch
        args = argparse.Namespace(combat_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_bestiary_dispatch_unknown(self, capsys):
        """Bestiary dispatch with unknown command prints usage."""
        from ult3edit.bestiary import dispatch
        args = argparse.Namespace(bestiary_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_map_dispatch_unknown(self, capsys):
        """Map dispatch with unknown command prints usage."""
        from ult3edit.map import dispatch
        args = argparse.Namespace(map_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_tlk_dispatch_unknown(self, capsys):
        """TLK dispatch with unknown command prints usage."""
        from ult3edit.tlk import dispatch
        args = argparse.Namespace(tlk_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_save_dispatch_unknown(self, capsys):
        """Save dispatch with unknown command prints usage."""
        from ult3edit.save import dispatch
        args = argparse.Namespace(save_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_special_dispatch_unknown(self, capsys):
        """Special dispatch with unknown command prints usage."""
        from ult3edit.special import dispatch
        args = argparse.Namespace(special_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_text_dispatch_unknown(self, capsys):
        """Text dispatch with unknown command prints usage."""
        from ult3edit.text import dispatch
        args = argparse.Namespace(text_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_ddrw_dispatch_unknown(self, capsys):
        """DDRW dispatch with unknown command prints usage."""
        from ult3edit.ddrw import dispatch
        args = argparse.Namespace(ddrw_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_patch_dispatch_unknown(self, capsys):
        """Patch dispatch with unknown command prints usage."""
        from ult3edit.patch import dispatch
        args = argparse.Namespace(patch_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_roster_dispatch_unknown(self, capsys):
        """Roster dispatch with unknown command prints usage."""
        from ult3edit.roster import dispatch
        args = argparse.Namespace(roster_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_sound_dispatch_unknown(self, capsys):
        """Sound dispatch with unknown command prints usage."""
        from ult3edit.sound import dispatch
        args = argparse.Namespace(sound_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_shapes_dispatch_unknown(self, capsys):
        """Shapes dispatch with unknown command prints usage."""
        from ult3edit.shapes import dispatch
        args = argparse.Namespace(shapes_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_equip_dispatch_unknown(self, capsys):
        """Equip dispatch with unknown command prints usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_spell_dispatch_unknown(self, capsys):
        """Spell dispatch with unknown command prints usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()


import pytest


class TestConsoleScriptEntryPoints:
    """Verify all ult3-* console scripts respond to --help."""

    ALL_MODULES = [
        "roster", "bestiary", "map", "tlk", "combat", "save",
        "special", "text", "spell", "equip", "disk", "shapes",
        "sound", "patch", "ddrw", "diff", "exod",
    ]

    @pytest.mark.parametrize("module", ALL_MODULES)
    def test_module_help(self, module):
        result = subprocess.run(
            [sys.executable, '-m', f'ult3edit.{module}', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert len(result.stdout) > 20  # Non-trivial help text

