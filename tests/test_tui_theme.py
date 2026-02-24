"""Tests for TUI theme tile_style() function."""

import pytest

from ult3edit.tui.theme import tile_style


class TestOverworldTileStyles:
    """Verify overworld tile byte -> style class mapping."""

    @pytest.mark.parametrize("byte_val,expected_style", [
        (0x00, 'class:tile-water'),
        (0x04, 'class:tile-grass'),
        (0x08, 'class:tile-grass'),       # Brush
        (0x0C, 'class:tile-forest'),
        (0x10, 'class:tile-mountain'),
        (0x14, 'class:tile-dungeon'),
        (0x18, 'class:tile-town'),
        (0x1C, 'class:tile-town'),         # Castle
        (0x20, 'class:tile-floor'),
        (0x24, 'class:tile-special'),      # Chest
        (0x28, 'class:tile-npc'),          # Horse
        (0x2C, 'class:tile-ship'),
        (0x30, 'class:tile-water'),        # Whirlpool
        (0x34, 'class:tile-monster'),      # Serpent
        (0x38, 'class:tile-monster'),      # Man-o-War
        (0x3C, 'class:tile-monster'),      # Pirate
        (0x40, 'class:tile-npc'),          # Merchant
        (0x48, 'class:tile-npc'),          # Guard
        (0x60, 'class:tile-monster'),      # Orc
        (0x74, 'class:tile-monster'),      # Dragon
        (0x7C, 'class:tile-monster'),      # Exodus
        (0x80, 'class:tile-special'),      # Force Field
        (0x8C, 'class:tile-wall'),
        (0x90, 'class:tile-default'),      # Void
        (0xF0, 'class:tile-special'),      # Magic
        (0xFC, 'class:tile-special'),      # Hidden
    ])
    def test_overworld_tile_mapping(self, byte_val, expected_style):
        assert tile_style(byte_val) == expected_style

    def test_unknown_overworld_tile_returns_default(self):
        """Tiles not in the lookup table should return tile-default."""
        assert tile_style(0x94) == 'class:tile-default'

    def test_overworld_masks_lower_bits(self):
        """Overworld lookup uses byte & 0xFC, so lower bits are ignored."""
        # 0x05 & 0xFC = 0x04 (grass)
        assert tile_style(0x05) == 'class:tile-grass'
        assert tile_style(0x07) == 'class:tile-grass'

    def test_return_type_is_string(self):
        assert isinstance(tile_style(0x00), str)
        assert tile_style(0x00).startswith('class:')


class TestDungeonTileStyles:
    """Verify dungeon tile byte -> style class mapping."""

    @pytest.mark.parametrize("byte_val,expected_style", [
        (0x00, 'class:tile-floor'),        # Open
        (0x01, 'class:tile-wall'),
        (0x02, 'class:tile-special'),      # Door
        (0x03, 'class:tile-special'),      # Secret door
        (0x04, 'class:tile-special'),      # Chest
        (0x05, 'class:tile-special'),      # Ladder down
        (0x06, 'class:tile-special'),      # Ladder up
        (0x07, 'class:tile-special'),      # Both ladders
        (0x08, 'class:tile-special'),      # Trap
        (0x09, 'class:tile-special'),      # Fountain
        (0x0A, 'class:tile-monster'),      # Mark
        (0x0B, 'class:tile-wall'),         # Wind
        (0x0C, 'class:tile-monster'),      # Gremlins
        (0x0D, 'class:tile-npc'),          # Orb
        (0x0E, 'class:tile-npc'),          # Pit
        (0x0F, 'class:tile-default'),      # Unknown
    ])
    def test_dungeon_tile_mapping(self, byte_val, expected_style):
        assert tile_style(byte_val, is_dungeon=True) == expected_style

    def test_dungeon_masks_upper_nibble(self):
        """Dungeon lookup uses byte & 0x0F, so upper nibble is ignored."""
        # 0xF1 & 0x0F = 0x01 (wall)
        assert tile_style(0xF1, is_dungeon=True) == 'class:tile-wall'
        assert tile_style(0xA0, is_dungeon=True) == 'class:tile-floor'

    def test_dungeon_return_type(self):
        assert isinstance(tile_style(0x00, is_dungeon=True), str)
        assert tile_style(0x00, is_dungeon=True).startswith('class:')
