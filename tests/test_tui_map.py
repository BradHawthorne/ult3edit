"""Tests for MapEditor data handling (no terminal needed)."""

import os

from ult3edit.tui.map_editor import MapEditor
from ult3edit.tui.base import EditorState


class TestDungeonLevelSwitching:
    def test_switch_level(self):
        data = bytearray(2048)
        data[0] = 0x01  # Wall at level 0, (0,0)
        data[256] = 0x02  # Door at level 1, (0,0)

        editor = MapEditor.__new__(MapEditor)
        editor.full_data = bytearray(data)
        editor.is_dungeon = True
        editor.current_level = 0
        editor.num_levels = 8
        editor.state = EditorState(
            data=bytearray(data[0:256]), width=16, height=16, is_dungeon=True,
        )

        assert editor.state.tile_at(0, 0) == 0x01
        editor.switch_level(1)
        assert editor.current_level == 1
        assert editor.state.tile_at(0, 0) == 0x02

    def test_switch_saves_current(self):
        data = bytearray(2048)
        editor = MapEditor.__new__(MapEditor)
        editor.full_data = bytearray(data)
        editor.is_dungeon = True
        editor.current_level = 0
        editor.num_levels = 8
        editor.state = EditorState(
            data=bytearray(data[0:256]), width=16, height=16, is_dungeon=True,
        )
        # Paint on level 0
        editor.state.set_tile(5, 5, 0x01)
        # Switch to level 1
        editor.switch_level(1)
        # Check that level 0 was saved back
        assert editor.full_data[5 * 16 + 5] == 0x01

    def test_switch_invalid_level_ignored(self):
        data = bytearray(2048)
        editor = MapEditor.__new__(MapEditor)
        editor.full_data = bytearray(data)
        editor.is_dungeon = True
        editor.current_level = 0
        editor.num_levels = 8
        editor.state = EditorState(
            data=bytearray(data[0:256]), width=16, height=16, is_dungeon=True,
        )
        editor.switch_level(99)  # Should be ignored
        assert editor.current_level == 0


class TestSaveRoundtrip:
    def test_overworld_save(self, tmp_dir, sample_overworld_bytes):
        path = os.path.join(tmp_dir, 'test_map')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)

        editor = MapEditor(path, sample_overworld_bytes, is_dungeon=False)
        editor.state.set_tile(32, 32, 0x18)  # Place a town
        editor._save()

        with open(path, 'rb') as f:
            saved = f.read()
        assert len(saved) == 4096
        assert saved[32 * 64 + 32] == 0x18

    def test_dungeon_save_all_levels(self, tmp_dir, sample_dungeon_bytes):
        path = os.path.join(tmp_dir, 'test_dun')
        with open(path, 'wb') as f:
            f.write(sample_dungeon_bytes)

        editor = MapEditor(path, sample_dungeon_bytes, is_dungeon=True)
        # Modify level 0
        editor.state.set_tile(5, 5, 0x03)
        # Switch to level 2 and modify
        editor.switch_level(2)
        editor.state.set_tile(8, 8, 0x04)
        editor._save()

        with open(path, 'rb') as f:
            saved = f.read()
        assert len(saved) == 2048
        assert saved[0 * 256 + 5 * 16 + 5] == 0x03  # Level 0
        assert saved[2 * 256 + 8 * 16 + 8] == 0x04  # Level 2
