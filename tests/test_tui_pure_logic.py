"""Tests for TUI pure logic methods (no prompt_toolkit required)."""


from ult3edit.constants import (
    CON_FILE_SIZE, CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CHAR_RECORD_SIZE, CHAR_MAX_SLOTS, TLK_RECORD_END,
)
from ult3edit.tui.base import EditorState, BaseTileEditor
from ult3edit.tui.combat_editor import CombatEditor
from ult3edit.tui.map_editor import MapEditor
from ult3edit.tui.special_editor import SpecialEditor
from ult3edit.tui.dialog_editor import DialogEditor
from ult3edit.tui.text_editor import TextEditor, parse_text_records, rebuild_text_data
from ult3edit.tui.exod_editor import (
    ExodCrawlEditor, ExodGlyphViewer, ExodFrameViewer,
    make_exod_crawl_editor, make_exod_glyph_viewer, make_exod_frame_viewer,
)
from ult3edit.tui.form_editor import FormEditorTab
from ult3edit.tui.roster_editor import _character_label
from ult3edit.tui.bestiary_editor import _monster_label, _byte_clamp
from ult3edit.tui.editor_tab import TileEditorTab, TextEditorTab, DialogEditorTab, DrillDownTab


# ---- BaseTileEditor pure logic ----

class TestBaseTileEditorPureLogic:
    """Test BaseTileEditor methods that don't require prompt_toolkit."""

    def test_save_with_callback(self):
        data = bytearray(64)
        data[0] = 0x04
        state = EditorState(data=data, width=8, height=8)
        state.dirty = True
        saved = []
        editor = BaseTileEditor(state, 'test.map', save_callback=lambda d: saved.append(d))
        editor._save()
        assert len(saved) == 1
        assert saved[0][0] == 0x04
        assert not state.dirty

    def test_save_to_file(self, tmp_path):
        data = bytearray(64)
        data[5] = 0x10
        state = EditorState(data=data, width=8, height=8)
        state.dirty = True
        fpath = str(tmp_path / 'test.map')
        editor = BaseTileEditor(state, fpath)
        editor._save()
        assert not state.dirty
        assert (tmp_path / 'test.map').read_bytes()[5] == 0x10

    def test_extra_status_returns_empty(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        assert editor._extra_status() == ''

    def test_render_cell(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        style, ch = editor._render_cell(0, 0, 0x04)
        assert isinstance(style, str)
        assert isinstance(ch, str)

    def test_extra_keybindings_noop(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        editor._extra_keybindings(None)  # Should not raise


# ---- CombatEditor pure logic ----

class TestCombatEditorPureLogic:
    """Test CombatEditor methods that don't require prompt_toolkit."""

    def _make_editor(self):
        data = bytearray(CON_FILE_SIZE)
        # Set monster 0 at (3, 4)
        data[CON_MONSTER_X_OFFSET] = 3
        data[CON_MONSTER_Y_OFFSET] = 4
        # Set PC 0 at (5, 6)
        data[CON_PC_X_OFFSET] = 5
        data[CON_PC_Y_OFFSET] = 6
        saved = []
        editor = CombatEditor('test.con', bytes(data), save_callback=lambda d: saved.append(d))
        return editor, saved

    def test_render_cell_monster_overlay(self):
        editor, _ = self._make_editor()
        style, ch = editor._render_cell(3, 4, 0x00)
        assert style == 'class:overlay-monster'
        assert ch == '0'

    def test_render_cell_pc_overlay(self):
        editor, _ = self._make_editor()
        style, ch = editor._render_cell(5, 6, 0x00)
        assert style == 'class:overlay-pc'
        assert ch == '1'

    def test_render_cell_tile(self):
        editor, _ = self._make_editor()
        style, ch = editor._render_cell(1, 1, 0x04)
        assert 'class:' in style
        assert ch  # non-empty char

    def test_extra_status_paint_mode(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'paint'
        assert 'PAINT' in editor._extra_status()

    def test_extra_status_monster_mode(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'monster'
        status = editor._extra_status()
        assert 'MONSTER' in status
        assert 'slot' in status

    def test_extra_status_pc_mode(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'pc'
        assert 'PC' in editor._extra_status()

    def test_place_at_cursor_monster(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'monster'
        editor.placement_slot = 2
        editor.state.cursor_x = 7
        editor.state.cursor_y = 8
        editor._place_at_cursor()
        assert editor.monster_x[2] == 7
        assert editor.monster_y[2] == 8
        assert editor.state.dirty
        assert editor.state.revision == 1
        assert editor.placement_slot == 3  # auto-advance

    def test_place_at_cursor_pc(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'pc'
        editor.placement_slot = 1
        editor.state.cursor_x = 9
        editor.state.cursor_y = 10
        editor._place_at_cursor()
        assert editor.pc_x[1] == 9
        assert editor.pc_y[1] == 10
        assert editor.state.dirty
        assert editor.state.revision == 1

    def test_place_at_cursor_paint(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'paint'
        editor.state.selected_tile = 0x20
        editor.state.cursor_x = 0
        editor.state.cursor_y = 0
        editor._place_at_cursor()
        assert editor.state.tile_at(0, 0) == 0x20

    def test_save_callback(self):
        editor, saved = self._make_editor()
        editor.state.set_tile(0, 0, 0x20)
        editor._save()
        assert len(saved) == 1
        assert len(saved[0]) == CON_FILE_SIZE
        assert saved[0][0] == 0x20
        assert not editor.state.dirty

    def test_short_data_pads(self):
        """CombatEditor pads short data to CON_FILE_SIZE."""
        editor = CombatEditor('test.con', bytes(10))
        assert len(editor.full_data) == CON_FILE_SIZE


# ---- MapEditor pure logic ----

class TestMapEditorPureLogic:
    """Test MapEditor methods that don't require prompt_toolkit."""

    def test_overworld_extra_status(self):
        data = bytearray(4096)  # 64x64
        editor = MapEditor('test.map', bytes(data))
        status = editor._extra_status()
        assert '64x64' in status

    def test_dungeon_extra_status(self):
        data = bytearray(2048)  # 8 levels of 16x16
        editor = MapEditor('test.map', bytes(data), is_dungeon=True)
        status = editor._extra_status()
        assert 'Level 1/8' in status

    def test_switch_level(self):
        data = bytearray(2048)
        data[0] = 0xAA  # Level 0, first tile
        data[256] = 0xBB  # Level 1, first tile
        editor = MapEditor('test.map', bytes(data), is_dungeon=True)
        assert editor.state.data[0] == 0xAA
        # Edit level 0 to make it dirty
        editor.state.set_tile(0, 0, 0x04)
        assert editor.state.revision == 1
        assert editor.state.dirty
        # Switch to level 1
        editor.switch_level(1)
        assert editor.current_level == 1
        assert editor.state.data[0] == 0xBB
        assert editor.state.revision == 0
        assert editor.state.saved_revision == 0
        assert not editor.state.dirty

    def test_switch_level_out_of_range(self):
        data = bytearray(2048)
        editor = MapEditor('test.map', bytes(data), is_dungeon=True)
        editor.switch_level(99)  # Should be ignored
        assert editor.current_level == 0

    def test_save_overworld_callback(self):
        data = bytearray(4096)
        saved = []
        editor = MapEditor('test.map', bytes(data), save_callback=lambda d: saved.append(d))
        editor.state.set_tile(0, 0, 0x04)
        editor._save()
        assert len(saved) == 1
        assert saved[0][0] == 0x04

    def test_save_dungeon_merges_level(self):
        data = bytearray(2048)
        saved = []
        editor = MapEditor('test.map', bytes(data), is_dungeon=True,
                           save_callback=lambda d: saved.append(d))
        editor.state.set_tile(0, 0, 0x01)
        editor._save()
        assert len(saved) == 1
        assert saved[0][0] == 0x01
        assert len(saved[0]) == 2048

    def test_save_to_file(self, tmp_path):
        fpath = str(tmp_path / 'test.map')
        data = bytearray(4096)
        editor = MapEditor(fpath, bytes(data))
        editor.state.set_tile(0, 0, 0x10)
        editor._save()
        assert (tmp_path / 'test.map').read_bytes()[0] == 0x10


# ---- SpecialEditor pure logic ----

class TestSpecialEditorPureLogic:

    def test_save_to_file(self, tmp_path):
        fpath = str(tmp_path / 'BRND')
        data = bytearray(128)
        editor = SpecialEditor(fpath, bytes(data))
        editor.state.set_tile(0, 0, 0x20)
        editor._save()
        result = (tmp_path / 'BRND').read_bytes()
        assert result[0] == 0x20


# ---- DialogEditor pure logic ----

class TestDialogEditorPureLogic:

    def _make_tlk_data(self):
        """Build minimal TLK data with 2 text records."""
        from ult3edit.fileutil import encode_high_ascii
        rec1 = encode_high_ascii('HELLO', 5) + bytes([0xFF]) + encode_high_ascii('WORLD', 5)
        rec2 = encode_high_ascii('TEST', 4)
        return rec1 + bytes([TLK_RECORD_END]) + rec2 + bytes([TLK_RECORD_END])

    def test_init_parses_records(self):
        data = self._make_tlk_data()
        editor = DialogEditor('test.tlk', data)
        assert len(editor.records) >= 1

    def test_save_with_callback(self):
        data = self._make_tlk_data()
        saved = []
        editor = DialogEditor('test.tlk', data, save_callback=lambda d: saved.append(d))
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        assert len(saved) == 1
        assert not editor.dirty

    def test_save_to_file(self, tmp_path):
        data = self._make_tlk_data()
        fpath = str(tmp_path / 'TLKA')
        editor = DialogEditor(fpath, data)
        editor._save()
        assert (tmp_path / 'TLKA').exists()

    def test_sync_dirty_uses_revision_counters(self):
        data = self._make_tlk_data()
        editor = DialogEditor('test.tlk', data)
        editor._revision = 2
        editor._saved_revision = 1
        editor._sync_dirty()
        assert editor.dirty


# ---- TextEditor pure logic ----

class TestTextEditorPureLogic:

    def _make_text_data(self):
        """Build minimal TEXT data with high-ASCII strings."""
        from ult3edit.fileutil import encode_high_ascii
        s1 = encode_high_ascii('HELLO', 5) + b'\x00'
        s2 = encode_high_ascii('WORLD', 5) + b'\x00'
        return s1 + s2

    def test_parse_text_records(self):
        data = self._make_text_data()
        records = parse_text_records(data)
        assert len(records) == 2
        assert records[0].text == 'HELLO'
        assert records[1].text == 'WORLD'

    def test_rebuild_text_data(self):
        data = self._make_text_data()
        records = parse_text_records(data)
        rebuilt = rebuild_text_data(records, len(data))
        assert len(rebuilt) == len(data)
        # Re-parse should get same records
        re_parsed = parse_text_records(bytes(rebuilt))
        assert len(re_parsed) == 2

    def test_text_editor_init(self):
        data = self._make_text_data()
        editor = TextEditor('test.txt', data)
        assert len(editor.records) == 2
        assert not editor.dirty

    def test_text_editor_save_callback(self):
        data = self._make_text_data()
        saved = []
        editor = TextEditor('test.txt', data, save_callback=lambda d: saved.append(d))
        editor.records[0].text = 'THERE'
        editor.dirty = True
        editor._save()
        assert len(saved) == 1
        assert not editor.dirty

    def test_text_editor_save_to_file(self, tmp_path):
        data = self._make_text_data()
        fpath = str(tmp_path / 'TEXT')
        editor = TextEditor(fpath, data)
        editor._save()
        assert (tmp_path / 'TEXT').exists()

    def test_text_editor_sync_dirty_uses_revision_counters(self):
        data = self._make_text_data()
        editor = TextEditor('test.txt', data)
        editor._revision = 3
        editor._saved_revision = 2
        editor._sync_dirty()
        assert editor.dirty


# ---- ExodEditor pure logic ----

class TestExodEditorPureLogic:

    def _make_exod_data(self):
        """Build minimal EXOD data (26208 bytes)."""
        return bytearray(26208)

    def test_crawl_editor_init(self):
        data = self._make_exod_data()
        editor = ExodCrawlEditor(data)
        assert editor.name == 'Crawl'
        assert not editor.is_dirty

    def test_crawl_editor_save(self):
        data = self._make_exod_data()
        saved = []
        editor = ExodCrawlEditor(data, save_callback=lambda d: saved.append(d))
        editor.coords = [(140, 132), (100, 100)]
        editor.dirty = True
        editor.save()
        assert len(saved) == 1
        assert not editor.dirty

    def test_glyph_viewer_properties(self):
        data = self._make_exod_data()
        viewer = ExodGlyphViewer(data)
        assert viewer.name == 'Glyphs'
        assert not viewer.is_dirty
        viewer.save()  # no-op

    def test_frame_viewer_properties(self):
        data = self._make_exod_data()
        viewer = ExodFrameViewer(data)
        assert viewer.name == 'Frames'
        assert not viewer.is_dirty
        viewer.save()  # no-op

    def test_factory_crawl_editor(self):
        data = self._make_exod_data()
        editor = make_exod_crawl_editor(data, save_callback=lambda d: None)
        assert isinstance(editor, ExodCrawlEditor)

    def test_factory_glyph_viewer(self):
        data = self._make_exod_data()
        viewer = make_exod_glyph_viewer(data)
        assert isinstance(viewer, ExodGlyphViewer)

    def test_factory_frame_viewer(self):
        data = self._make_exod_data()
        viewer = make_exod_frame_viewer(data)
        assert isinstance(viewer, ExodFrameViewer)


# ---- FormEditorTab pure logic ----

class TestFormEditorTabPureLogic:

    def test_properties(self):
        tab = FormEditorTab(
            tab_name='Test',
            records=['a', 'b'],
            record_label_fn=lambda r, i: f'{i}: {r}',
            field_factory=lambda r: [],
            save_callback=lambda d: None,
            get_save_data=lambda: b'data',
        )
        assert tab.name == 'Test'
        assert not tab.is_dirty
        tab.dirty = True
        assert tab.is_dirty

    def test_save(self):
        saved = []
        tab = FormEditorTab(
            tab_name='Test',
            records=[],
            record_label_fn=lambda r, i: '',
            field_factory=lambda r: [],
            save_callback=lambda d: saved.append(d),
            get_save_data=lambda: b'testdata',
        )
        tab.dirty = True
        tab.save()
        assert saved == [b'testdata']
        assert not tab.dirty


# ---- Editor tab wrappers ----

class TestEditorTabWrappers:

    def test_tile_editor_tab(self):
        data = bytearray(64)
        state = EditorState(data=data, width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        tab = TileEditorTab(editor)
        assert tab.name == 'Tile Editor'
        assert not tab.is_dirty
        state.dirty = True
        assert tab.is_dirty

    def test_tile_editor_tab_save(self):
        data = bytearray(64)
        state = EditorState(data=data, width=8, height=8)
        saved = []
        editor = BaseTileEditor(state, 'test', save_callback=lambda d: saved.append(d))
        tab = TileEditorTab(editor)
        state.dirty = True
        tab.save()
        assert len(saved) == 1

    def test_text_editor_tab(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('TEST', 4) + b'\x00'
        text_editor = TextEditor('test', data)
        tab = TextEditorTab(text_editor)
        assert tab.name == 'Text'
        assert not tab.is_dirty

    def test_text_editor_tab_save(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('TEST', 4) + b'\x00'
        saved = []
        text_editor = TextEditor('test', data, save_callback=lambda d: saved.append(d))
        tab = TextEditorTab(text_editor)
        text_editor.dirty = True
        tab.save()
        assert len(saved) == 1

    def test_dialog_editor_tab(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])
        dialog_editor = DialogEditor('test', data)
        tab = DialogEditorTab(dialog_editor)
        assert tab.name == 'Dialog'
        assert not tab.is_dirty

    def test_dialog_editor_tab_save(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])
        saved = []
        dialog_editor = DialogEditor('test', data, save_callback=lambda d: saved.append(d))
        tab = DialogEditorTab(dialog_editor)
        dialog_editor.dirty = True
        tab.save()
        assert len(saved) == 1


# ---- DrillDownTab pure logic ----

class TestDrillDownTabPureLogic:

    def test_properties_no_editor(self):
        tab = DrillDownTab('Test', [('FILE', 'Display')], lambda f, d, s: None, None)
        assert tab.name == 'Test'
        assert not tab.is_dirty

    def test_save_no_editor(self):
        tab = DrillDownTab('Test', [], lambda f, d, s: None, None)
        tab.save()  # no-op, no active editor

    def test_open_editor_empty_list(self):
        tab = DrillDownTab('Test', [], lambda f, d, s: None, None)
        tab._open_editor()
        assert tab.active_editor is None


# ---- Roster editor label ----

class TestRosterEditorLabel:

    def test_character_label_non_empty(self):
        from ult3edit.roster import Character
        raw = bytearray(CHAR_RECORD_SIZE)
        # Write a name in high-ASCII
        from ult3edit.fileutil import encode_high_ascii
        name_bytes = encode_high_ascii('HERO', 10)
        raw[0:10] = name_bytes
        raw[0x16] = 0  # Human
        raw[0x17] = 0  # Fighter
        char = Character(raw)
        label = _character_label(char, 0)
        assert 'HERO' in label
        assert '[' in label

    def test_character_label_empty(self):
        from ult3edit.roster import Character
        raw = bytearray(CHAR_RECORD_SIZE)
        char = Character(raw)
        label = _character_label(char, 5)
        assert 'empty' in label


# ---- Bestiary editor label ----

class TestBestiaryEditorLabel:

    def test_monster_label_non_empty(self):
        from ult3edit.bestiary import Monster
        attrs = [0x60, 0x64, 0x00, 0x00, 10, 5, 3, 2, 0, 0]
        mon = Monster(attrs, 0, 'A')
        label = _monster_label(mon, 0)
        assert 'HP:' in label

    def test_monster_label_empty(self):
        from ult3edit.bestiary import Monster
        attrs = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        mon = Monster(attrs, 0, 'A')
        label = _monster_label(mon, 3)
        assert 'empty' in label

    def test_byte_clamp_hex(self):
        assert _byte_clamp('0xFF') == 255
        assert _byte_clamp('$FF') == 255
        assert _byte_clamp('256') == 255
        assert _byte_clamp('-1') == 0
        assert _byte_clamp('100') == 100

    def test_monster_field_validator(self):
        from ult3edit.bestiary import Monster
        from ult3edit.tui.bestiary_editor import _monster_fields
        mon = Monster([0x60, 0x60, 0, 0, 10, 5, 3, 2, 0, 0], 0, 'A')
        fields = _monster_fields(mon)
        assert fields[0].validator('0x10')


# ---- UnifiedApp factory methods ----

class TestUnifiedAppFactories:

    def test_make_map_editor_overworld(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(4096)
        saved = []
        tab = app._make_map_editor('MAPA', bytes(data), lambda d: saved.append(d))
        assert isinstance(tab, TileEditorTab)
        assert tab.name == 'Map Editor'

    def test_make_map_editor_dungeon(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.constants import MAP_DUNGEON_SIZE
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(MAP_DUNGEON_SIZE)
        tab = app._make_map_editor('MAPD', bytes(data), lambda d: None)
        assert isinstance(tab, TileEditorTab)

    def test_make_combat_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(CON_FILE_SIZE)
        tab = app._make_combat_editor('CONA', bytes(data), lambda d: None)
        assert isinstance(tab, TileEditorTab)

    def test_make_special_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(128)
        tab = app._make_special_editor('BRND', bytes(data), lambda d: None)
        assert isinstance(tab, TileEditorTab)

    def test_make_dialog_editor(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.fileutil import encode_high_ascii
        app = UnifiedApp.__new__(UnifiedApp)
        data = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])
        tab = app._make_dialog_editor('TLKA', data, lambda d: None)
        assert isinstance(tab, DialogEditorTab)

    def test_make_text_editor(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.fileutil import encode_high_ascii

        app = UnifiedApp.__new__(UnifiedApp)
        data = encode_high_ascii('TEST', 4) + b'\x00'
        tab = app._make_text_editor('TEXT', data, lambda d: None)
        assert isinstance(tab, TextEditorTab)

    def test_make_party_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        tab = app._make_party_editor('PRTY', bytearray(16), lambda d: None)
        assert isinstance(tab, FormEditorTab)

    def test_make_bestiary_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(256)
        tab = app._make_bestiary_editor('MONA', bytes(data), lambda d: None)
        assert tab is not None
        assert isinstance(tab, FormEditorTab)

    def test_make_exod_editor_crawl(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:crawl', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodCrawlEditor)

    def test_make_exod_editor_glyphs(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:glyphs', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodGlyphViewer)

    def test_make_exod_editor_frames(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:frames', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodFrameViewer)

    def test_make_exod_editor_none_data(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:crawl', bytearray(26208), lambda d: None)
        assert tab is None

    def test_make_exod_editor_unknown_sub(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:unknown', bytearray(26208), lambda d: None)
        assert tab is None

    def test_make_exod_editor_without_prefix(self):
        """fname without EXOD: prefix still routes by sub-editor name."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)

            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('crawl', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodCrawlEditor)

    def test_make_shapes_viewer(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.shapes_editor import ShapesViewer
        app = UnifiedApp.__new__(UnifiedApp)
        tab = app._make_shapes_viewer('SHPS', bytearray(2048), lambda d: None)
        assert isinstance(tab, ShapesViewer)

    def test_tab_matches_category_exod(self):
        from ult3edit.tui.app import UnifiedApp

        class Tab:
            name = 'EXOD'

        assert UnifiedApp._tab_matches_category(Tab(), 'exod')
        assert not UnifiedApp._tab_matches_category(Tab(), 'maps')

    def test_set_record_selection_helper(self):
        from ult3edit.tui.app import UnifiedApp

        class A:
            selected_record = 0

        class B:
            selected_index = 0

        a = A()
        b = B()
        assert UnifiedApp._set_record_selection(a, 3)
        assert a.selected_record == 3
        assert UnifiedApp._set_record_selection(b, 4)
        assert b.selected_index == 4
        assert not UnifiedApp._set_record_selection(None, 1)
        assert not UnifiedApp._set_record_selection(object(), 1)

    def test_save_tabs_collects_failures(self):
        from ult3edit.tui.app import UnifiedApp

        class GoodTab:
            name = 'Good'
            def save(self):
                return None

        class BadTab:
            name = 'Bad'
            def save(self):
                raise RuntimeError('boom')

        failed = UnifiedApp._save_tabs([GoodTab(), BadTab()])
        assert failed == ['Bad']

    def test_build_tabs(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def has_category(self, cat):
                return cat == 'party'
            def files_in(self, cat):
                return []
            def read(self, name):
                return bytearray(16)  # PRTY size
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert len(app.tabs) >= 1  # At least the Party tab


# =============================================================================
# Coverage: app.py _build_tabs with multiple categories (lines 29, 36, 43,
# 50, 57-62, 66-70, 74, 89), editor_tab.py _open_editor None data (line 241)
# =============================================================================


class TestUnifiedAppBuildTabsMulti:
    """Cover app.py _build_tabs with maps, combat, special, dialog, text,
    roster, bestiary, exod categories."""

    def _make_mock_session(self, categories):
        """Create a mock session with specified categories."""
        from ult3edit.fileutil import encode_high_ascii
        from ult3edit.constants import CON_FILE_SIZE, CHAR_RECORD_SIZE

        file_data = {}
        catalog = {}

        if 'maps' in categories:
            catalog['maps'] = [('MAPA', 'Sosaria')]
            file_data['MAPA'] = bytearray(4096)

        if 'combat' in categories:
            catalog['combat'] = [('CONA', 'Combat A')]
            file_data['CONA'] = bytearray(CON_FILE_SIZE)

        if 'special' in categories:
            catalog['special'] = [('BRND', 'Brand')]
            file_data['BRND'] = bytearray(128)

        if 'dialog' in categories:
            catalog['dialog'] = [('TLKA', 'Dialog A')]
            file_data['TLKA'] = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])

        if 'text' in categories:
            catalog['text'] = [('TEXT', 'Game Text')]
            file_data['TEXT'] = encode_high_ascii('TEST', 4) + b'\x00'

        if 'roster' in categories:
            catalog['roster'] = [('ROST', 'Roster')]
            file_data['ROST'] = bytearray(CHAR_RECORD_SIZE * CHAR_MAX_SLOTS)

        if 'bestiary' in categories:
            catalog['bestiary'] = [('MONA', 'Monsters A')]
            file_data['MONA'] = bytearray(256)

        if 'exod' in categories:
            catalog['exod'] = [
                ('EXOD:crawl', 'Text Crawl'),
                ('EXOD:glyphs', 'Glyph Table'),
                ('EXOD:frames', 'HGR Frames'),
            ]
            file_data['EXOD'] = bytearray(26208)

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat in catalog
            def files_in(self, cat):
                return catalog.get(cat, [])
            def read(self, name):
                base = name.split(':')[0] if ':' in name else name
                return file_data.get(base)
            def make_save_callback(self, name):
                return lambda d: None

        return MockSession()

    def test_build_tabs_maps(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['maps'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Maps' for t in app.tabs)

    def test_build_tabs_combat(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['combat'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Combat' for t in app.tabs)

    def test_build_tabs_special(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['special'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Special' for t in app.tabs)

    def test_build_tabs_dialog(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['dialog'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Dialog' for t in app.tabs)

    def test_build_tabs_text(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['text'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Text' for t in app.tabs)

    def test_build_tabs_roster(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['roster'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert len(app.tabs) >= 1

    def test_build_tabs_bestiary(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['bestiary'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Bestiary' for t in app.tabs)

    def test_build_tabs_exod(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['exod'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'EXOD' for t in app.tabs)

    def test_build_tabs_text_none_data(self):
        """Text category where read returns None should not add tab."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat == 'text'
            def files_in(self, cat):
                return [('TEXT', 'Game Text')] if cat == 'text' else []
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert not any(t.name == 'Text' for t in app.tabs)

    def test_build_tabs_roster_none_data(self):
        """Roster category where read returns None should not add tab."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat == 'roster'
            def files_in(self, cat):
                return [('ROST', 'Roster')] if cat == 'roster' else []
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert len(app.tabs) == 1 # Just SearchTab

    def test_build_tabs_party_none_data(self):
        """Party category where read returns None should not add tab."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat == 'party'
            def files_in(self, cat):
                return [('PRTY', 'Party State')] if cat == 'party' else []
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert len(app.tabs) == 1 # Just SearchTab


class TestDrillDownTabOpenEditorNoneData:
    """Cover editor_tab.py line 241: _open_editor returns early when
    session.read returns None."""

    def test_open_editor_none_data(self):
        class MockSession:
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        tab = DrillDownTab('Test', [('MISSING', 'Missing File')],
                           lambda f, d, s: None, MockSession())
        tab._open_editor()
        assert tab.active_editor is None


class TestEditorStateUndoRedo:
    def test_undo_redo(self):
        from ult3edit.tui.base import EditorState
        state = EditorState(data=bytearray(64), width=8, height=8)
        state.set_tile(0, 0, 0x10)
        assert state.tile_at(0, 0) == 0x10
        assert len(state.undo_stack) == 1
        assert state.dirty

        state.undo()
        assert state.tile_at(0, 0) == 0x00
        assert len(state.undo_stack) == 0
        assert len(state.redo_stack) == 1
        assert not state.dirty

        state.redo()
        assert state.tile_at(0, 0) == 0x10
        assert len(state.redo_stack) == 0
        assert state.dirty

        # Test no-op undo/redo
        state.redo()
        state.undo()
        state.undo()

    def test_set_tile_no_track(self):
        from ult3edit.tui.base import EditorState
        state = EditorState(data=bytearray(64), width=8, height=8)
        state.set_tile(0, 0, 0x10, track_undo=False)
        assert len(state.undo_stack) == 0
        assert state.tile_at(0, 0) == 0x10

    def test_tile_at_out_of_bounds(self):
        from ult3edit.tui.base import EditorState
        state = EditorState(data=bytearray(64), width=8, height=8)
        assert state.tile_at(99, 99) == 0

    def test_move_cursor_and_scroll(self):
        from ult3edit.tui.base import EditorState
        state = EditorState(data=bytearray(4096), width=64, height=64, viewport_w=10, viewport_h=10)
        state.move_cursor(20, 20)
        assert state.cursor_x == 20
        assert state.cursor_y == 20
        assert state.viewport_x > 0
        assert state.viewport_y > 0

        state.move_cursor(-20, -20)
        assert state.cursor_x == 0
        assert state.cursor_y == 0
        assert state.viewport_x == 0
        assert state.viewport_y == 0

        # Clamp to max
        state.move_cursor(100, 100)
        assert state.cursor_x == 63
        assert state.cursor_y == 63


class TestFormField:
    def test_form_field(self):
        from ult3edit.tui.form_editor import FormField
        f = FormField('Label', lambda: 'val', lambda x: None, fmt='int')
        assert f.label == 'Label'
        assert f.getter() == 'val'
        assert f.fmt == 'int'


class TestActivePartyTabBuilding:
    def test_build_tabs_active_party(self):
        from ult3edit.tui.app import UnifiedApp
        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat): return cat == 'active_party'
            def files_in(self, cat): return [('PLRS', 'Active Characters')] if cat == 'active_party' else []
            def read(self, name): return bytearray(256)
            def make_save_callback(self, name): return lambda d: None
        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert any(t.name == 'Active Party' for t in app.tabs)

    def test_build_tabs_active_party_none(self):
        from ult3edit.tui.app import UnifiedApp
        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat): return cat == 'active_party'
            def files_in(self, cat): return [('PLRS', 'Active Characters')] if cat == 'active_party' else []
            def read(self, name): return None
            def make_save_callback(self, name): return lambda d: None
        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert not any(t.name == 'Active Party' for t in app.tabs)


class TestSearchJumpFlow:
    def test_prepare_drilldown_jump_clean_editor_returns_true(self):
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import DrillDownTab

        class MockEditor:
            def __init__(self):
                self._dirty = False

            @property
            def is_dirty(self):
                return self._dirty

            def build_ui(self):
                return Window(), KeyBindings()

            def save(self):
                self._dirty = False

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld')],
            lambda fname, data, save_cb: MockEditor(),
            MockSession(),
        )
        tab._open_editor()

        app = UnifiedApp.__new__(UnifiedApp)
        assert app._prepare_drilldown_jump(tab)

    def test_jump_to_file_saves_dirty_drilldown_editor(self):
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import DrillDownTab

        class MockEditor:
            def __init__(self):
                self._dirty = False
                self.saved = False
                self.selected_record = 0

            @property
            def is_dirty(self):
                return self._dirty

            def build_ui(self):
                return Window(), KeyBindings()

            def save(self):
                self.saved = True
                self._dirty = False

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        editors = []

        def factory(fname, data, save_cb):
            ed = MockEditor()
            editors.append(ed)
            return ed

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld'), ('MAPB', 'Town')],
            factory,
            MockSession(),
        )
        tab._open_editor()
        first_editor = tab.active_editor
        first_editor._dirty = True

        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [tab]
        app.active_tab_index = 0
        app._prompt_unsaved_jump = lambda _tab_name: 'save'
        app._show_error_dialog = lambda **kwargs: None

        app._jump_to_file(('maps', 'MAPB', 7))

        assert first_editor.saved
        assert tab.selected_index == 1
        assert tab.active_editor is not None
        assert tab.active_editor is not first_editor
        assert tab.active_editor.selected_record == 7

    def test_jump_to_file_discard_switches_without_save(self):
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import DrillDownTab

        class MockEditor:
            def __init__(self):
                self._dirty = False
                self.saved = False
                self.selected_record = 0

            @property
            def is_dirty(self):
                return self._dirty

            def build_ui(self):
                return Window(), KeyBindings()

            def save(self):
                self.saved = True
                self._dirty = False

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld'), ('MAPB', 'Town')],
            lambda fname, data, save_cb: MockEditor(),
            MockSession(),
        )
        tab._open_editor()
        first_editor = tab.active_editor
        first_editor._dirty = True

        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [tab]
        app.active_tab_index = 0
        app._prompt_unsaved_jump = lambda _tab_name: 'discard'
        app._show_error_dialog = lambda **kwargs: None

        app._jump_to_file(('maps', 'MAPB', 4))

        assert not first_editor.saved
        assert tab.selected_index == 1
        assert tab.active_editor is not first_editor
        assert tab.active_editor.selected_record == 4

    def test_jump_to_file_cancel_keeps_editor_open(self):
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import DrillDownTab

        class MockEditor:
            def __init__(self):
                self._dirty = False
                self.saved = False

            @property
            def is_dirty(self):
                return self._dirty

            def build_ui(self):
                return Window(), KeyBindings()

            def save(self):
                self.saved = True
                self._dirty = False

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld'), ('MAPB', 'Town')],
            lambda fname, data, save_cb: MockEditor(),
            MockSession(),
        )
        tab._open_editor()
        first_editor = tab.active_editor
        first_editor._dirty = True

        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [tab]
        app.active_tab_index = 0
        app._prompt_unsaved_jump = lambda _tab_name: 'cancel'
        app._show_error_dialog = lambda **kwargs: None

        app._jump_to_file(('maps', 'MAPB', 1))

        assert tab.selected_index == 0
        assert tab.active_editor is first_editor
        assert not first_editor.saved

    def test_jump_to_file_save_failure_shows_error_and_stays(self):
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import DrillDownTab

        class MockEditor:
            def __init__(self):
                self._dirty = False

            @property
            def is_dirty(self):
                return self._dirty

            def build_ui(self):
                return Window(), KeyBindings()

            def save(self):
                raise OSError('read-only')

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld'), ('MAPB', 'Town')],
            lambda fname, data, save_cb: MockEditor(),
            MockSession(),
        )
        tab._open_editor()
        first_editor = tab.active_editor
        first_editor._dirty = True

        errors = []
        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [tab]
        app.active_tab_index = 0
        app._prompt_unsaved_jump = lambda _tab_name: 'save'
        app._show_error_dialog = lambda **kwargs: errors.append(kwargs)

        app._jump_to_file(('maps', 'MAPB', 1))

        assert tab.selected_index == 0
        assert tab.active_editor is first_editor
        assert errors

    def test_jump_to_file_sets_selected_index_for_text_editor(self):
        from ult3edit.fileutil import encode_high_ascii
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import TextEditorTab
        from ult3edit.tui.text_editor import TextEditor

        data = encode_high_ascii('A', 1) + b'\x00' + encode_high_ascii('B', 1) + b'\x00'
        text_tab = TextEditorTab(TextEditor('TEXT', data))

        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [text_tab]
        app.active_tab_index = 0

        app._jump_to_file(('text', 'TEXT', 1))
        assert text_tab._editor.selected_index == 1

    def test_jump_to_file_sets_selected_index_for_dialog_editor(self):
        from ult3edit.fileutil import encode_high_ascii
        from ult3edit.constants import TLK_RECORD_END
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.editor_tab import DialogEditorTab
        from ult3edit.tui.dialog_editor import DialogEditor

        tlk_data = (
            encode_high_ascii('A', 1) + bytes([TLK_RECORD_END]) +
            encode_high_ascii('B', 1) + bytes([TLK_RECORD_END])
        )
        dialog_tab = DialogEditorTab(DialogEditor('TLKA', tlk_data))

        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [dialog_tab]
        app.active_tab_index = 0

        app._jump_to_file(('dialog', 'TLKA', 1))
        assert dialog_tab._editor.selected_index == 1

    def test_jump_to_file_sets_selected_record_for_form_tab(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.tui.form_editor import FormEditorTab

        form_tab = FormEditorTab(
            tab_name='Roster',
            records=['A', 'B', 'C'],
            record_label_fn=lambda r, i: str(i),
            field_factory=lambda r: [],
            save_callback=lambda d: None,
            get_save_data=lambda: b'',
        )

        app = UnifiedApp.__new__(UnifiedApp)
        app.tabs = [form_tab]
        app.active_tab_index = 0

        app._jump_to_file(('roster', 'ROST', 2))
        assert form_tab.selected_record == 2


class TestSearchTabLogic:
    def test_search_empty(self):
        from ult3edit.tui.search_tab import SearchTab
        tab = SearchTab(None)
        tab.query = ""
        tab._perform_search()
        assert tab.results == []

    def test_search_roster(self, tmp_dir):
        from ult3edit.tui.search_tab import SearchTab
        from ult3edit.constants import CHAR_RECORD_SIZE

        # Setup mock session with roster data
        roster_data = bytearray(CHAR_RECORD_SIZE * 20)
        # Set name 'HERO' in slot 0
        from ult3edit.fileutil import encode_high_ascii
        roster_data[0:4] = encode_high_ascii('HERO', 4)

        class MockSession:
            def has_category(self, cat): return cat == 'roster'
            def files_in(self, cat): return [('ROST', 'Roster')] if cat == 'roster' else []
            def read(self, name): return roster_data if name == 'ROST' else None

        session = MockSession()
        tab = SearchTab(session)
        tab.query = 'HERO'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Roster'
        assert 'HERO' in tab.results[0]['label']

    def test_search_active_party(self):
        from ult3edit.constants import CHAR_RECORD_SIZE
        from ult3edit.fileutil import encode_high_ascii
        from ult3edit.tui.search_tab import SearchTab

        plrs_data = bytearray(CHAR_RECORD_SIZE * 4)
        plrs_data[0:4] = encode_high_ascii('HERO', 4)

        class MockSession:
            def has_category(self, cat): return cat == 'active_party'
            def files_in(self, cat): return [('PLRS', 'Active Characters')]
            def read(self, name): return plrs_data

        tab = SearchTab(MockSession())
        tab.query = 'hero'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Party'
        assert tab.results[0]['jump'][0] == 'active_party'

    def test_search_bestiary(self, monkeypatch):
        from ult3edit.tui.search_tab import SearchTab

        class MockMonster:
            def __init__(self, name):
                self.name = name
                self.is_empty = False

        monkeypatch.setattr('ult3edit.bestiary.load_monsters',
                            lambda data, letter: [MockMonster('DRAGON')])

        class MockSession:
            def has_category(self, cat): return cat == 'bestiary'
            def files_in(self, cat): return [('MONA', 'Monsters A')]
            def read(self, name): return bytes(256)

        tab = SearchTab(MockSession())
        tab.query = 'drag'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Monster'

    def test_search_dialog(self):
        from ult3edit.tui.search_tab import SearchTab
        from ult3edit.fileutil import encode_high_ascii
        tlk_data = encode_high_ascii('SECRET MESSAGE', 20)

        class MockSession:
            def has_category(self, cat): return cat == 'dialog'
            def files_in(self, cat): return [('TLKA', 'Dialog A')]
            def read(self, name): return tlk_data

        session = MockSession()
        tab = SearchTab(session)
        tab.query = 'SECRET'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Dialog'

    def test_selection_normalizes_and_never_goes_negative(self):
        from ult3edit.tui.search_tab import SearchTab

        tab = SearchTab(None)
        tab.results = [{'jump': ('maps', 'MAPA', 0)}]
        tab.selected_index = 99
        tab._normalize_selection()
        assert tab.selected_index == 0

        tab.results = []
        tab.selected_index = 5
        tab.move_selection(1)
        assert tab.selected_index == 0
        assert tab.selected_result() is None

        tab.results = [
            {'jump': ('maps', 'MAPA', 0)},
            {'jump': ('maps', 'MAPB', 0)},
        ]
        tab.move_selection(1)
        assert tab.selected_index == 1
        assert tab.selected_result()['jump'][1] == 'MAPB'

    def test_search_maps(self):
        from ult3edit.tui.search_tab import SearchTab
        class MockSession:
            def has_category(self, cat): return cat == 'maps'
            def files_in(self, cat): return [('MAPA', 'Sosaria')]
            def read(self, name): return None

        session = MockSession()
        tab = SearchTab(session)
        tab.query = 'Sosaria'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Map'
        assert not tab.is_dirty
        tab.save() # no-op

    def test_search_special(self):
        from ult3edit.tui.search_tab import SearchTab

        class MockSession:
            def has_category(self, cat): return cat == 'special'
            def files_in(self, cat): return [('BRND', 'Branding Area')]
            def read(self, name): return None

        tab = SearchTab(MockSession())
        tab.query = 'brand'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Special'
        assert tab.results[0]['jump'][0] == 'special'

class TestFormFieldValidation:
    def test_is_valid_none(self):
        from ult3edit.tui.form_editor import FormField
        f = FormField('HP', lambda: 100, lambda x: None)
        assert f.is_valid()

    def test_is_valid(self):
        from ult3edit.tui.form_editor import FormField
        f = FormField('HP', lambda: 100, lambda x: None, validator=lambda x: int(x) < 200)
        assert f.is_valid()
        f = FormField('HP', lambda: 300, lambda x: None, validator=lambda x: int(x) < 200)
        assert not f.is_valid()

    def test_is_valid_exception(self):
        from ult3edit.tui.form_editor import FormField
        f = FormField('Err', lambda: 'val', lambda x: None, validator=lambda x: 1/0)
        assert not f.is_valid()

    def test_validate_input_uses_user_value(self):
        from ult3edit.tui.form_editor import FormField, FormEditorTab
        tab = FormEditorTab(
            tab_name='Test',
            records=[],
            record_label_fn=lambda r, i: '',
            field_factory=lambda r: [],
            save_callback=lambda d: None,
            get_save_data=lambda: b'',
        )
        f = FormField('Race', lambda: 'H', lambda x: None,
                      validator=lambda v: v.upper() in ('H', 'E', 'D', 'B', 'F'))
        assert tab._validate_input(f, 'E')
        assert not tab._validate_input(f, 'INVALID')

    def test_validate_input_no_validator_and_exception_path(self):
        from ult3edit.tui.form_editor import FormField, FormEditorTab
        tab = FormEditorTab(
            tab_name='Test',
            records=[],
            record_label_fn=lambda r, i: '',
            field_factory=lambda r: [],
            save_callback=lambda d: None,
            get_save_data=lambda: b'',
        )
        no_validator = FormField('Any', lambda: 'x', lambda x: None)
        assert tab._validate_input(no_validator, 'whatever')
        bad_validator = FormField('Bad', lambda: 'x', lambda x: None,
                                  validator=lambda v: 1 / 0)
        assert not tab._validate_input(bad_validator, 'x')

    def test_sync_dirty_uses_revision_counters(self):
        from ult3edit.tui.form_editor import FormEditorTab
        tab = FormEditorTab(
            tab_name='Test',
            records=[],
            record_label_fn=lambda r, i: '',
            field_factory=lambda r: [],
            save_callback=lambda d: None,
            get_save_data=lambda: b'',
        )
        tab._revision = 2
        tab._saved_revision = 1
        tab._sync_dirty()
        assert tab.dirty


class TestSearchTextAndShapes:
    def test_search_text(self):
        from ult3edit.tui.search_tab import SearchTab
        from ult3edit.fileutil import encode_high_ascii
        text_data = encode_high_ascii('TITLE STRING', 20) + b'\\x00'

        class MockSession:
            def has_category(self, cat): return cat == 'text'
            def files_in(self, cat): return [('TEXT', 'Game Text')]
            def read(self, name): return text_data

        session = MockSession()
        tab = SearchTab(session)
        tab.query = 'TITLE'
        tab._perform_search()
        assert len(tab.results) == 1
        assert tab.results[0]['type'] == 'Text'

    def test_shapes_viewer_logic(self):
        from ult3edit.tui.shapes_editor import ShapesViewer
        data = bytearray(2048)
        viewer = ShapesViewer(data)
        assert viewer.name == 'Shapes'
        assert viewer.selected_glyph == 0
        assert not viewer.is_dirty
