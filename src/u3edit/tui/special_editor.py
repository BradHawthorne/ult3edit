"""TUI editor for special locations (BRND/SHRN/FNTN/TIME, 128 bytes, 11x11 tiles)."""

from ..constants import SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_MAP_TILES
from .base import EditorState, BaseTileEditor


class SpecialEditor(BaseTileEditor):
    """11x11 special location tile editor. Preserves 7 metadata bytes."""

    def __init__(self, file_path: str, data: bytes):
        self.full_data = bytearray(data)
        tile_data = bytearray(data[:SPECIAL_MAP_TILES])
        state = EditorState(
            data=tile_data,
            width=SPECIAL_MAP_WIDTH,
            height=SPECIAL_MAP_HEIGHT,
        )
        super().__init__(state, file_path, title='Special Location Editor')

    def _save(self) -> None:
        out = bytearray(self.full_data)
        out[:SPECIAL_MAP_TILES] = self.state.data
        with open(self.file_path, 'wb') as f:
            f.write(bytes(out))
        self.state.dirty = False
