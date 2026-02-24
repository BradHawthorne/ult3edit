"""TUI editor for special locations (BRND/SHRN/FNTN/TIME, 128 bytes, 11x11 tiles)."""

from ..constants import SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_MAP_TILES
from .base import EditorState, BaseTileEditor


class SpecialEditor(BaseTileEditor):
    """11x11 special location tile editor. Preserves 7 metadata bytes."""

    def __init__(self, file_path: str, data: bytes, save_callback=None):
        self.full_data = bytearray(data)
        # Pad tile data to exactly SPECIAL_MAP_TILES if short
        raw_tiles = data[:SPECIAL_MAP_TILES]
        if len(raw_tiles) < SPECIAL_MAP_TILES:
            raw_tiles = raw_tiles + bytes(SPECIAL_MAP_TILES - len(raw_tiles))
        tile_data = bytearray(raw_tiles)
        state = EditorState(
            data=tile_data,
            width=SPECIAL_MAP_WIDTH,
            height=SPECIAL_MAP_HEIGHT,
        )
        super().__init__(state, file_path, title='Special Location Editor',
                         save_callback=save_callback)

    def _save(self) -> None:
        out = bytearray(self.full_data)
        out[:SPECIAL_MAP_TILES] = self.state.data
        if self.save_callback:
            self.save_callback(bytes(out))
        else:
            with open(self.file_path, 'wb') as f:
                f.write(bytes(out))
        self.state.mark_saved()
