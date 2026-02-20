"""Tests for special location tool."""

import json
import os
import types

import pytest

from u3edit.special import render_special_map, cmd_edit, cmd_import, _has_cli_edit_args
from u3edit.constants import SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_FILE_SIZE


class TestRenderSpecialMap:
    def test_dimensions(self, sample_special_bytes):
        rendered = render_special_map(sample_special_bytes)
        lines = rendered.strip().split('\n')
        # Header + 11 rows
        assert len(lines) == SPECIAL_MAP_HEIGHT + 1

    def test_content(self, sample_special_bytes):
        rendered = render_special_map(sample_special_bytes)
        assert '_' in rendered  # Floor tiles


class TestSizeHandling:
    def test_exact_size(self, sample_special_bytes):
        assert len(sample_special_bytes) == SPECIAL_FILE_SIZE

    def test_small_data(self):
        """Should handle data smaller than expected."""
        rendered = render_special_map(bytes(50))
        assert len(rendered) > 0


# --- Helper to build args namespace ---

def _edit_args(file, **kwargs):
    """Build an argparse-like namespace for cmd_edit."""
    defaults = dict(
        file=file, tile=None,
        output=None, backup=False, dry_run=False,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _import_args(file, json_file, **kwargs):
    """Build an argparse-like namespace for cmd_import."""
    defaults = dict(
        file=file, json_file=json_file,
        output=None, backup=False, dry_run=False,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


@pytest.fixture
def special_file(tmp_dir, sample_special_bytes):
    """Write a special file and return its path."""
    path = os.path.join(tmp_dir, 'BRND#069900')
    with open(path, 'wb') as f:
        f.write(sample_special_bytes)
    return path


class TestHasCliEditArgs:
    def test_no_args(self):
        args = _edit_args('x')
        assert not _has_cli_edit_args(args)

    def test_tile_arg(self):
        args = _edit_args('x', tile=[5, 5, 0x04])
        assert _has_cli_edit_args(args)


class TestSpecialCliEditTile:
    def test_set_tile(self, special_file):
        """Set a tile and verify it was written."""
        args = _edit_args(special_file, tile=[5, 5, 0x04])
        cmd_edit(args)
        with open(special_file, 'rb') as f:
            data = f.read()
        offset = 5 * SPECIAL_MAP_WIDTH + 5
        assert data[offset] == 0x04

    def test_set_tile_boundary(self, special_file):
        """Set tile at max valid position (10, 10)."""
        args = _edit_args(special_file, tile=[10, 10, 0x08])
        cmd_edit(args)
        with open(special_file, 'rb') as f:
            data = f.read()
        offset = 10 * SPECIAL_MAP_WIDTH + 10
        assert data[offset] == 0x08

    def test_set_tile_out_of_bounds(self, special_file):
        """Tile position outside grid should fail."""
        args = _edit_args(special_file, tile=[11, 5, 0x04])
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_set_tile_dry_run(self, special_file):
        """Dry run should not write changes."""
        with open(special_file, 'rb') as f:
            original = f.read()
        args = _edit_args(special_file, tile=[5, 5, 0x04], dry_run=True)
        cmd_edit(args)
        with open(special_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_set_tile_backup(self, special_file):
        """Backup should create .bak file."""
        args = _edit_args(special_file, tile=[5, 5, 0x04], backup=True)
        cmd_edit(args)
        assert os.path.exists(special_file + '.bak')

    def test_set_tile_output(self, special_file, tmp_dir):
        """Output to a different file."""
        out_path = os.path.join(tmp_dir, 'output.bin')
        args = _edit_args(special_file, tile=[5, 5, 0x04], output=out_path)
        cmd_edit(args)
        with open(out_path, 'rb') as f:
            data = f.read()
        offset = 5 * SPECIAL_MAP_WIDTH + 5
        assert data[offset] == 0x04


class TestSpecialImportDryRun:
    def test_import_dry_run(self, special_file, tmp_dir):
        """Import with --dry-run should not write."""
        with open(special_file, 'rb') as f:
            original = f.read()
        # Build JSON with different tiles
        tiles = [['T' for _ in range(SPECIAL_MAP_WIDTH)] for _ in range(SPECIAL_MAP_HEIGHT)]
        jdata = {'tiles': tiles, 'trailing_bytes': [0] * 7}
        json_path = os.path.join(tmp_dir, 'import.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = _import_args(special_file, json_path, dry_run=True)
        cmd_import(args)
        with open(special_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_import_writes_without_dry_run(self, special_file, tmp_dir):
        """Import without --dry-run should write changes."""
        tiles = [['T' for _ in range(SPECIAL_MAP_WIDTH)] for _ in range(SPECIAL_MAP_HEIGHT)]
        jdata = {'tiles': tiles, 'trailing_bytes': [0] * 7}
        json_path = os.path.join(tmp_dir, 'import.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = _import_args(special_file, json_path)
        cmd_import(args)
        with open(special_file, 'rb') as f:
            data = f.read()
        # 'T' should map to some tile byte — verify it changed from 0x20 (floor)
        assert data[0] != 0x20 or data[60] != 0x20  # At least some changed
