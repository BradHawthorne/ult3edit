"""Tests for EditorTab, DrillDownTab state management."""


import pytest

from ult3edit.tui.editor_tab import EditorTab, TileEditorTab, DrillDownTab
from ult3edit.tui.base import EditorState, BaseTileEditor


class TestEditorTabDefaults:
    def test_default_is_dirty_and_save(self):
        tab = EditorTab()
        assert not tab.is_dirty
        assert tab.save() is None

    def test_name_and_build_ui_raise(self):
        tab = EditorTab()
        with pytest.raises(NotImplementedError):
            _ = tab.name
        with pytest.raises(NotImplementedError):
            tab.build_ui()


class TestTileEditorTab:
    def test_name(self):
        state = EditorState(data=bytearray(256), width=16, height=16)
        editor = BaseTileEditor(state, '/tmp/test', title='Test Editor')
        tab = TileEditorTab(editor)
        assert tab.name == 'Test Editor'

    def test_dirty_tracking(self):
        state = EditorState(data=bytearray(256), width=16, height=16)
        editor = BaseTileEditor(state, '/tmp/test')
        tab = TileEditorTab(editor)
        assert not tab.is_dirty
        state.dirty = True
        assert tab.is_dirty

    def test_save_clears_dirty(self):
        state = EditorState(data=bytearray(256), width=16, height=16)
        saved = []
        editor = BaseTileEditor(state, '/tmp/test',
                                save_callback=lambda d: saved.append(d))
        tab = TileEditorTab(editor)
        state.dirty = True
        tab.save()
        assert not tab.is_dirty
        assert len(saved) == 1


class MockEditor:
    """Mock editor for DrillDownTab tests."""

    def __init__(self, fail_on_save=False):
        self._dirty = False
        self._saved = False
        self._fail_on_save = fail_on_save

    @property
    def is_dirty(self):
        return self._dirty

    def build_ui(self):
        from prompt_toolkit.layout import Window
        from prompt_toolkit.key_binding import KeyBindings
        return Window(), KeyBindings()

    def save(self):
        if self._fail_on_save:
            raise OSError('disk full')
        self._saved = True
        self._dirty = False


class TestDrillDownTab:
    def _make_tab(self, file_list=None):
        if file_list is None:
            file_list = [('MAPA', 'Sosaria'), ('MAPB', 'LB Castle')]

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                def cb(data):
                    pass
                return cb

        def factory(fname, data, save_cb):
            return MockEditor()

        return DrillDownTab('Maps', file_list, factory, MockSession())

    def test_initial_state(self):
        tab = self._make_tab()
        assert tab.name == 'Maps'
        assert tab.active_editor is None
        assert tab.selected_index == 0
        assert not tab.is_dirty

    def test_selector_navigation(self):
        tab = self._make_tab()
        tab.selected_index = 0
        tab.selected_index = min(len(tab.file_list) - 1, tab.selected_index + 1)
        assert tab.selected_index == 1

    def test_open_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        assert tab.active_editor is not None

    def test_close_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        assert tab.active_editor is not None
        tab.active_editor = None
        tab._editor_container = None
        assert tab.active_editor is None

    def test_dirty_from_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        assert not tab.is_dirty
        tab.active_editor._dirty = True
        assert tab.is_dirty

    def test_empty_file_list(self):
        tab = self._make_tab(file_list=[])
        assert not tab.is_dirty
        tab._open_editor()  # Should be a no-op
        assert tab.active_editor is None

    def test_save_propagates_to_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        tab.active_editor._dirty = True
        tab.save()
        assert tab.active_editor._saved
        assert not tab.active_editor._dirty

    def test_save_noop_without_editor(self):
        tab = self._make_tab()
        tab.save()  # Should not crash

    def test_is_dirty_false_in_selector(self):
        """is_dirty should be False when no editor is open."""
        tab = self._make_tab()
        assert not tab.is_dirty

    def test_switch_to_file_saves_dirty_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        first = tab.active_editor
        first._dirty = True
        assert tab.switch_to_file(1)
        assert first._saved
        assert tab.selected_index == 1
        assert tab.active_editor is not first

    def test_switch_to_file_invalid_index(self):
        tab = self._make_tab()
        assert not tab.switch_to_file(99)

    def test_close_active_editor_no_editor_returns_true(self):
        tab = self._make_tab()
        assert tab._close_active_editor()

    def test_close_active_editor_refuses_dirty_without_save_or_discard(self):
        tab = self._make_tab()
        tab._open_editor()
        tab.active_editor._dirty = True
        assert not tab._close_active_editor(save_if_dirty=False, discard_if_dirty=False)
        assert tab.active_editor is not None

    def test_switch_to_file_refuses_when_dirty_and_save_disabled(self):
        tab = self._make_tab()
        tab._open_editor()
        tab.active_editor._dirty = True
        assert not tab.switch_to_file(1, save_if_dirty=False)
        assert tab.selected_index == 0

    def test_open_editor_closes_existing_editor_first(self):
        tab = self._make_tab()
        tab._open_editor()
        first = tab.active_editor
        first._dirty = True
        tab.selected_index = 1
        tab._open_editor()
        assert first._saved
        assert tab.active_editor is not first

    def test_close_active_editor_save_failure_returns_false(self):
        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld')],
            lambda fname, data, save_cb: MockEditor(fail_on_save=True),
            MockSession(),
        )
        tab._open_editor()
        tab.active_editor._dirty = True
        assert not tab._close_active_editor(save_if_dirty=True)
        assert tab.active_editor is not None
        assert isinstance(tab.last_close_error, OSError)

    def test_open_editor_does_not_replace_when_save_fails(self):
        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        def factory(fname, data, save_cb):
            if fname == 'MAPA':
                return MockEditor(fail_on_save=True)
            return MockEditor()

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld'), ('MAPB', 'Town')],
            factory,
            MockSession(),
        )
        tab._open_editor()
        first = tab.active_editor
        first._dirty = True

        tab.selected_index = 1
        tab._open_editor()

        assert tab.active_editor is first

    def test_switch_to_file_returns_false_when_save_fails(self):
        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                return lambda data: None

        def factory(fname, data, save_cb):
            if fname == 'MAPA':
                return MockEditor(fail_on_save=True)
            return MockEditor()

        tab = DrillDownTab(
            'Maps',
            [('MAPA', 'Overworld'), ('MAPB', 'Town')],
            factory,
            MockSession(),
        )
        tab._open_editor()
        tab.active_editor._dirty = True

        assert not tab.switch_to_file(1, save_if_dirty=True)
        assert tab.selected_index == 0
