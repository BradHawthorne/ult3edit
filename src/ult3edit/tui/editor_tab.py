"""Editor tab abstractions for the unified tabbed editor.

EditorTab: protocol interface for all tabs.
TileEditorTab: wraps a BaseTileEditor subclass.
TextEditorTab: wraps a TextEditor.
DrillDownTab: file selector → embedded editor → back.
"""

from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.containers import DynamicContainer
from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings, \
    ConditionalKeyBindings
from prompt_toolkit.filters import Condition


class EditorTab:
    """Interface for all top-level editor tabs."""

    @property
    def name(self) -> str:
        raise NotImplementedError # pragma: no cover

    @property
    def is_dirty(self) -> bool:
        return False

    def build_ui(self):
        raise NotImplementedError # pragma: no cover

    def save(self):
        pass


class TileEditorTab(EditorTab):
    """Wraps a BaseTileEditor subclass as a tab."""

    def __init__(self, editor):
        self._editor = editor

    @property
    def name(self):
        return self._editor.title

    @property
    def is_dirty(self):
        return self._editor.state.dirty

    def build_ui(self):  # pragma: no cover
        return self._editor._build_ui(embedded=True)

    def save(self):
        self._editor._save()


class TextEditorTab:
    """Wraps a TextEditor as a tab."""

    def __init__(self, editor):
        self._editor = editor

    @property
    def name(self):
        return 'Text'

    @property
    def is_dirty(self):
        return self._editor.dirty

    def build_ui(self):  # pragma: no cover
        return self._editor._build_ui(embedded=True)

    def save(self):
        self._editor._save()


class DialogEditorTab:
    """Wraps a DialogEditor as a tab."""

    def __init__(self, editor):
        self._editor = editor

    @property
    def name(self):
        return 'Dialog'

    @property
    def is_dirty(self):
        return self._editor.is_dirty

    def build_ui(self):  # pragma: no cover
        return self._editor.build_ui()

    def save(self):
        self._editor.save()


class DrillDownTab:
    """Multi-file tab: file selector list → editor → back with Escape.

    file_list: [(file_name, display_name), ...]
    editor_factory: (file_name, data, save_callback) -> tab-like object with
                    build_ui()/save()/is_dirty
    """

    def __init__(self, tab_name, file_list, editor_factory, session):
        self.tab_name = tab_name
        self.file_list = file_list
        self.editor_factory = editor_factory
        self.session = session
        self.selected_index = 0
        self.active_editor = None  # None = selector mode
        self._editor_version = 0
        self._last_close_error = None

    @property
    def name(self):
        return self.tab_name

    @property
    def is_dirty(self):
        if self.active_editor:
            return self.active_editor.is_dirty
        return False

    def save(self):
        if self.active_editor:
            self.active_editor.save()

    @property
    def last_close_error(self):
        return self._last_close_error

    def _close_active_editor(
        self,
        save_if_dirty: bool = True,
        discard_if_dirty: bool = False,
    ) -> bool:
        """Close current sub-editor; optionally save first if dirty.

        Returns True when the editor is closed, False if close was refused.
        """
        if not self.active_editor:
            self._last_close_error = None
            return True

        self._last_close_error = None
        if self.active_editor.is_dirty:
            if save_if_dirty:
                try:
                    self.active_editor.save()
                except Exception as exc:
                    self._last_close_error = exc
                    return False
            elif not discard_if_dirty:
                return False

        self.active_editor = None
        self._editor_container = None
        self._editor_kb = None
        self._editor_version += 1
        return True

    def switch_to_file(self, file_index: int, save_if_dirty: bool = True) -> bool:
        """Switch to a file index, closing/saving active sub-editor first."""
        if file_index < 0 or file_index >= len(self.file_list):
            return False
        if not self._close_active_editor(save_if_dirty=save_if_dirty):
            return False
        self.selected_index = file_index
        self._open_editor()
        return self.active_editor is not None

    def build_ui(self):  # pragma: no cover
        """Build a dynamic container that switches between selector and editor."""
        tab = self

        # --- Selector UI ---
        class SelectorControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header',
                               f' {tab.tab_name} — Select a file '.ljust(width))])
                lines.append([('class:palette-header', ' ' + '─' * (width - 2) + ' ')])
                for i, (fname, display) in enumerate(tab.file_list):
                    label = f' {fname:<8s} {display}'
                    if i == tab.selected_index:
                        style = 'class:palette-selected'
                        marker = ' <'
                    else:
                        style = 'class:palette-normal'
                        marker = ''
                    lines.append([(style, f'{label}{marker}'.ljust(width))])
                if not tab.file_list:
                    lines.append([('', ' (no files found)')])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_selector_status():
            if tab.file_list:
                fname, display = tab.file_list[tab.selected_index]
                return [('class:status', f' {tab.tab_name}: {fname} — {display}')]
            return [('class:status', f' {tab.tab_name}: (empty)')]

        def get_selector_help():
            return [
                ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                ('class:help-key', 'Enter'), ('class:help-text', '=open '),
            ]

        selector_layout = HSplit([
            Window(content=SelectorControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_selector_status), height=1),
            Window(content=FormattedTextControl(get_selector_help), height=1),
        ])

        # --- Dynamic content ---
        self._selector_layout = selector_layout
        self._editor_container = None
        self._editor_kb = None

        def get_container():
            if tab.active_editor and tab._editor_container:
                return tab._editor_container
            return tab._selector_layout

        dynamic = DynamicContainer(get_container)

        # --- Keybindings ---
        # Selector keybindings (only active when no sub-editor is open)
        selector_kb = KeyBindings()
        in_selector = Condition(lambda: tab.active_editor is None)

        @selector_kb.add('up')
        def _up(event):
            if tab.file_list:
                tab.selected_index = max(0, tab.selected_index - 1)

        @selector_kb.add('down')
        def _down(event):
            if tab.file_list:
                tab.selected_index = min(len(tab.file_list) - 1,
                                         tab.selected_index + 1)

        @selector_kb.add('enter')
        def _open(event):
            if tab.file_list:
                tab._open_editor()

        # Escape: return to selector (always active, saves dirty sub-editor)
        nav_kb = KeyBindings()

        @nav_kb.add('escape')
        def _back(event):
            if tab.active_editor:
                # If sub-editor has a palette picker open, close that first
                if (hasattr(tab.active_editor, 'state')
                        and hasattr(tab.active_editor.state, 'picker_mode')
                        and tab.active_editor.state.picker_mode):
                    tab.active_editor.state.picker_mode = False
                    return

                # If sub-editor has field-editing mode, exit that first
                if (hasattr(tab.active_editor, 'editing_fields')
                        and tab.active_editor.editing_fields):
                    tab.active_editor.editing_fields = False
                    tab.active_editor._current_fields = []
                    return
                if tab.active_editor.is_dirty:
                    from prompt_toolkit.shortcuts import button_dialog
                    choice = button_dialog(
                        title='Unsaved Changes',
                        text=f"Save changes before closing {tab.tab_name} editor?",
                        buttons=[
                            ('Save', 'save'),
                            ('Discard', 'discard'),
                            ('Cancel', 'cancel'),
                        ],
                    ).run()
                    if choice == 'cancel' or choice is None:
                        return
                    if choice == 'save':
                        closed = tab._close_active_editor(save_if_dirty=True)
                        if not closed:
                            from prompt_toolkit.shortcuts import message_dialog
                            err = tab.last_close_error
                            message_dialog(
                                title='Save Failed',
                                text=f"Failed to save {tab.tab_name}: {err}",
                            ).run()
                    else:
                        tab._close_active_editor(
                            save_if_dirty=False,
                            discard_if_dirty=True,
                        )
                    return
                tab._close_active_editor(save_if_dirty=False, discard_if_dirty=True)

        # Sub-editor keybindings: dynamically forwarded via _DynamicEditorBindings
        class _DynamicEditorBindings:
            """Proxy that delegates to the current sub-editor's keybindings."""

            def _update_cache(self):
                pass

            @property
            def _version(self):
                return tab._editor_version

            @property
            def bindings(self):
                kb = tab._editor_kb
                return kb.bindings if kb else []

        in_editor = Condition(lambda: tab.active_editor is not None)
        editor_proxy = _DynamicEditorBindings()
        editor_cond = ConditionalKeyBindings(editor_proxy, in_editor)

        merged = merge_key_bindings([
            nav_kb,
            ConditionalKeyBindings(selector_kb, in_selector),
            editor_cond,
        ])
        return dynamic, merged

    def _open_editor(self):
        """Open the editor for the currently selected file."""
        if not self.file_list:
            return
        # Prevent dirty sub-editor from being silently overwritten.
        if self.active_editor:
            if not self._close_active_editor(save_if_dirty=True):
                return
        fname, display = self.file_list[self.selected_index]
        data = self.session.read(fname)
        if data is None:
            return
        save_cb = self.session.make_save_callback(fname)
        self.active_editor = self.editor_factory(fname, data, save_cb)
        # Build the editor's UI
        container, kb = self.active_editor.build_ui()
        self._editor_container = container
        self._editor_kb = kb
        self._editor_version += 1
