"""Tests for CombatEditor data handling (no terminal needed)."""

from ult3edit.constants import (
    CON_FILE_SIZE, CON_MAP_WIDTH,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_MONSTER_COUNT,
    CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CON_PC_COUNT,
)
from ult3edit.tui.combat_editor import CombatEditor


class TestPositionExtraction:
    def test_monster_positions(self, sample_con_bytes):
        editor = CombatEditor.__new__(CombatEditor)
        data = bytearray(sample_con_bytes)
        editor.full_data = data
        editor.monster_x = [data[CON_MONSTER_X_OFFSET + i] for i in range(CON_MONSTER_COUNT)]
        editor.monster_y = [data[CON_MONSTER_Y_OFFSET + i] for i in range(CON_MONSTER_COUNT)]
        assert editor.monster_x[0] == 5
        assert editor.monster_y[0] == 3

    def test_pc_positions(self, sample_con_bytes):
        editor = CombatEditor.__new__(CombatEditor)
        data = bytearray(sample_con_bytes)
        editor.full_data = data
        editor.pc_x = [data[CON_PC_X_OFFSET + i] for i in range(CON_PC_COUNT)]
        editor.pc_y = [data[CON_PC_Y_OFFSET + i] for i in range(CON_PC_COUNT)]
        assert editor.pc_x[0] == 2
        assert editor.pc_y[0] == 8


class TestSerialization:
    def test_save_roundtrip(self, sample_con_bytes, tmp_dir):
        import os
        path = os.path.join(tmp_dir, 'test_con')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        editor = CombatEditor(path, sample_con_bytes)
        # Modify a tile
        editor.state.set_tile(5, 5, 0x04)
        # Modify monster position
        editor.monster_x[2] = 7
        editor.monster_y[2] = 9
        editor._save()

        with open(path, 'rb') as f:
            saved = f.read()
        assert len(saved) == CON_FILE_SIZE
        assert saved[5 * CON_MAP_WIDTH + 5] == 0x04
        assert saved[CON_MONSTER_X_OFFSET + 2] == 7
        assert saved[CON_MONSTER_Y_OFFSET + 2] == 9

    def test_preserves_padding(self, sample_con_bytes, tmp_dir):
        import os
        # Set some padding bytes to non-zero
        data = bytearray(sample_con_bytes)
        data[0x79] = 0xAB  # Padding between tiles and monster pos
        path = os.path.join(tmp_dir, 'test_con2')
        with open(path, 'wb') as f:
            f.write(data)

        editor = CombatEditor(path, bytes(data))
        editor._save()

        with open(path, 'rb') as f:
            saved = f.read()
        assert saved[0x79] == 0xAB  # Padding preserved


class TestPlacement:
    """Tests for monster/PC placement and mode switching."""

    def test_place_monster(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'monster'
        editor.placement_slot = 3
        editor.state.cursor_x = 7
        editor.state.cursor_y = 4
        editor._place_at_cursor()
        assert editor.monster_x[3] == 7
        assert editor.monster_y[3] == 4
        assert editor.state.dirty

    def test_place_monster_auto_advance(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'monster'
        editor.placement_slot = 0
        editor._place_at_cursor()
        assert editor.placement_slot == 1

    def test_place_monster_wraps(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'monster'
        editor.placement_slot = CON_MONSTER_COUNT - 1
        editor._place_at_cursor()
        assert editor.placement_slot == 0

    def test_place_pc(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'pc'
        editor.placement_slot = 1
        editor.state.cursor_x = 9
        editor.state.cursor_y = 2
        editor._place_at_cursor()
        assert editor.pc_x[1] == 9
        assert editor.pc_y[1] == 2
        assert editor.state.dirty

    def test_place_pc_auto_advance(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'pc'
        editor.placement_slot = 0
        editor._place_at_cursor()
        assert editor.placement_slot == 1

    def test_place_pc_wraps(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'pc'
        editor.placement_slot = CON_PC_COUNT - 1
        editor._place_at_cursor()
        assert editor.placement_slot == 0

    def test_paint_mode_paints_tile(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'paint'
        editor.state.cursor_x = 5
        editor.state.cursor_y = 5
        editor.state.selected_tile = 0x04
        editor._place_at_cursor()
        assert editor.state.tile_at(5, 5) == 0x04


class TestExtraStatus:
    def test_paint_mode(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'paint'
        assert 'PAINT' in editor._extra_status()

    def test_monster_mode(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'monster'
        editor.placement_slot = 3
        status = editor._extra_status()
        assert 'MONSTER' in status
        assert '3' in status

    def test_pc_mode(self, sample_con_bytes):
        editor = CombatEditor('test', sample_con_bytes)
        editor.state.mode = 'pc'
        editor.placement_slot = 2
        status = editor._extra_status()
        assert 'PC' in status
        assert '3' in status  # Displayed as slot+1


class TestSaveWithPositions:
    def test_save_callback_includes_positions(self, sample_con_bytes):
        saved = []
        editor = CombatEditor('test', sample_con_bytes, save_callback=lambda d: saved.append(d))
        editor.monster_x[5] = 10
        editor.monster_y[5] = 9
        editor.pc_x[2] = 8
        editor.pc_y[2] = 7
        editor.state.dirty = True
        editor._save()
        result = saved[0]
        assert result[CON_MONSTER_X_OFFSET + 5] == 10
        assert result[CON_MONSTER_Y_OFFSET + 5] == 9
        assert result[CON_PC_X_OFFSET + 2] == 8
        assert result[CON_PC_Y_OFFSET + 2] == 7
