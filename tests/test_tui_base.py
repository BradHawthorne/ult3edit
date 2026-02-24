"""Tests for EditorState logic (no terminal or prompt_toolkit needed)."""

from ult3edit.tui.base import EditorState


class TestTileAccess:
    def test_tile_at_valid(self):
        data = bytearray([0x04] * 16)
        state = EditorState(data=data, width=4, height=4)
        assert state.tile_at(0, 0) == 0x04

    def test_tile_at_out_of_bounds(self):
        data = bytearray([0x04] * 16)
        state = EditorState(data=data, width=4, height=4)
        assert state.tile_at(10, 10) == 0

    def test_set_tile(self):
        data = bytearray([0x04] * 16)
        state = EditorState(data=data, width=4, height=4)
        state.set_tile(1, 1, 0x00)
        assert state.tile_at(1, 1) == 0x00
        assert state.dirty is True

    def test_set_tile_out_of_bounds_ignored(self):
        data = bytearray([0x04] * 16)
        state = EditorState(data=data, width=4, height=4)
        state.set_tile(10, 10, 0x00)
        assert state.dirty is False

    def test_dirty_clears_when_undo_returns_to_saved_state(self):
        data = bytearray([0x04] * 16)
        state = EditorState(data=data, width=4, height=4)
        state.set_tile(0, 0, 0x00)
        assert state.dirty
        state.undo()
        assert not state.dirty

    def test_dirty_tracks_saved_revision_across_redo(self):
        data = bytearray([0x04] * 16)
        state = EditorState(data=data, width=4, height=4)
        state.set_tile(0, 0, 0x00)
        state.mark_saved()
        assert not state.dirty
        state.undo()
        assert state.dirty
        state.redo()
        assert not state.dirty


class TestCursorMovement:
    def test_move_right(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.move_cursor(1, 0)
        assert state.cursor_x == 1
        assert state.cursor_y == 0

    def test_move_clamps_negative(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.move_cursor(-1, -1)
        assert state.cursor_x == 0
        assert state.cursor_y == 0

    def test_move_clamps_positive(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.move_cursor(100, 100)
        assert state.cursor_x == 3
        assert state.cursor_y == 3

    def test_move_incremental(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        for _ in range(5):
            state.move_cursor(1, 1)
        assert state.cursor_x == 5
        assert state.cursor_y == 5


class TestViewportScrolling:
    def test_viewport_scrolls_right(self):
        state = EditorState(
            data=bytearray(64 * 64), width=64, height=64,
            viewport_w=20, viewport_h=10,
        )
        for _ in range(25):
            state.move_cursor(1, 0)
        assert state.viewport_x > 0
        assert state.cursor_x >= state.viewport_x
        assert state.cursor_x < state.viewport_x + state.viewport_w

    def test_viewport_scrolls_down(self):
        state = EditorState(
            data=bytearray(64 * 64), width=64, height=64,
            viewport_w=20, viewport_h=10,
        )
        for _ in range(15):
            state.move_cursor(0, 1)
        assert state.viewport_y > 0
        assert state.cursor_y >= state.viewport_y
        assert state.cursor_y < state.viewport_y + state.viewport_h

    def test_small_grid_no_scroll(self):
        state = EditorState(
            data=bytearray(11 * 11), width=11, height=11,
            viewport_w=20, viewport_h=20,
        )
        state.move_cursor(10, 10)
        assert state.viewport_x == 0
        assert state.viewport_y == 0


class TestPaint:
    def test_paint_applies_selected_tile(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.selected_tile = 0x18
        state.cursor_x = 2
        state.cursor_y = 2
        state.paint()
        assert state.tile_at(2, 2) == 0x18
        assert state.dirty is True

    def test_paint_at_origin(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.selected_tile = 0x0C
        state.paint()
        assert state.tile_at(0, 0) == 0x0C


class TestPalette:
    def test_default_palette_overworld(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        assert len(state.palette) > 0
        assert state.selected_tile == state.palette[0]

    def test_default_palette_dungeon(self):
        state = EditorState(data=bytearray(16), width=4, height=4, is_dungeon=True)
        assert len(state.palette) > 0

    def test_select_next_tile(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        first = state.selected_tile
        state.select_next_tile()
        assert state.palette_index == 1
        assert state.selected_tile == state.palette[1]
        assert state.selected_tile != first

    def test_select_prev_tile_wraps(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.select_prev_tile()
        assert state.palette_index == len(state.palette) - 1

    def test_select_next_wraps(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        for _ in range(len(state.palette)):
            state.select_next_tile()
        assert state.palette_index == 0

    def test_select_palette_index(self):
        state = EditorState(data=bytearray(16), width=4, height=4)
        state.palette_index = 5
        state.selected_tile = state.palette[5]
        assert state.palette_index == 5
        assert state.selected_tile == state.palette[5]
