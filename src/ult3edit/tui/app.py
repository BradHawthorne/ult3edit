"""Unified tabbed TUI editor for Ultima III game data.

Opens a disk image and provides tabbed access to all game data editors:
Maps, Combat, Special, Dialog, Text, Roster, Bestiary, Party.
"""

import os

from ..constants import MAP_DUNGEON_SIZE
from .game_session import GameSession
from .editor_tab import TileEditorTab, TextEditorTab, DialogEditorTab, DrillDownTab
from .theme import U3_STYLE


class UnifiedApp:
    """Single prompt_toolkit Application hosting all editor tabs."""

    def __init__(self, session: GameSession):
        self.session = session
        self.tabs = []
        self.active_tab_index = 0
        self._registry = {}
        self._init_registry()
        self.show_help = False
        self.theme_name = 'Modern'

    def _init_registry(self):
        """Register editor factories for each category."""
        self._registry['maps'] = self._make_map_editor
        self._registry['combat'] = self._make_combat_editor
        self._registry['special'] = self._make_special_editor
        self._registry['dialog'] = self._make_dialog_editor
        self._registry['text'] = self._make_text_editor
        self._registry['roster'] = self._make_roster_editor
        self._registry['bestiary'] = self._make_bestiary_editor
        self._registry['party'] = self._make_party_editor
        self._registry['active_party'] = self._make_active_party_editor
        self._registry['exod'] = self._make_exod_editor
        self._registry['shapes'] = self._make_shapes_viewer

    def _build_tabs(self):
        """Create all tabs from the game session catalog."""
        session = self.session

        # Define categories that use DrillDownTab (multi-file)
        drill_down_categories = ['maps', 'combat', 'special', 'dialog', 'bestiary', 'exod']

        for category, factory in self._registry.items():
            if not session.has_category(category):
                continue

            if category in drill_down_categories:
                self.tabs.append(DrillDownTab(
                    category.capitalize() if category != 'exod' else 'EXOD',
                    session.files_in(category),
                    factory, session,
                ))
            else:
                # Single-file categories
                files = session.files_in(category)
                if files:
                    fname, _ = files[0]
                    data = session.read(fname)
                    if data:
                        tab = factory(fname, data, session.make_save_callback(fname))
                        if tab:
                            self.tabs.append(tab)

        # Search tab
        from .search_tab import SearchTab
        self.tabs.append(SearchTab(session, jump_callback=self._jump_to_file))

    @staticmethod
    def _tab_matches_category(tab, category: str) -> bool:
        """Match a top-level tab to a search category key."""
        cat = category.lower()
        tab_name = tab.name.lower()
        if tab_name == cat.replace('_', ' '):
            return True
        return False

    @staticmethod
    def _set_record_selection(target, record_idx: int) -> bool:
        """Set selection index on a target editor/tab if supported."""
        if target is None:
            return False
        if hasattr(target, 'selected_record'):
            target.selected_record = record_idx
            return True
        if hasattr(target, 'selected_index'):
            target.selected_index = record_idx
            return True
        return False

    @staticmethod
    def _save_tabs(tabs) -> list[str]:
        """Save each tab and return names that failed to save."""
        import sys
        failed = []
        for tab in tabs:
            try:
                tab.save()
            except Exception as e:
                failed.append(tab.name)
                print(f'Warning: failed to save {tab.name}: {e}',
                      file=sys.stderr) # pragma: no cover
        return failed

    def _prompt_unsaved_jump(self, tab_name: str):  # pragma: no cover
        """Ask how to handle unsaved editor changes before a Search jump."""
        from prompt_toolkit.shortcuts import button_dialog
        return button_dialog(
            title='Unsaved Changes',
            text=f"Save changes before leaving {tab_name}?",
            buttons=[
                ('Save', 'save'),
                ('Discard', 'discard'),
                ('Cancel', 'cancel'),
            ],
        ).run()

    @staticmethod
    def _show_error_dialog(title: str, text: str):  # pragma: no cover
        from prompt_toolkit.shortcuts import message_dialog
        message_dialog(title=title, text=text).run()

    def _prepare_drilldown_jump(self, tab: DrillDownTab) -> bool:
        """Handle dirty editor state before Search-triggered tab/file switch."""
        if not tab.active_editor or not tab.active_editor.is_dirty:
            return True

        choice = self._prompt_unsaved_jump(tab.name)
        if choice in (None, 'cancel'):
            return False
        if choice == 'save':
            if tab._close_active_editor(save_if_dirty=True):
                return True
            self._show_error_dialog(
                title='Save Failed',
                text=f"Failed to save {tab.name}: {tab.last_close_error}",
            )
            return False
        return tab._close_active_editor(
            save_if_dirty=False,
            discard_if_dirty=True,
        )

    def _jump_to_file(self, jump_target): # pragma: no cover
        """Callback for SearchTab to jump to a specific file/record."""
        category, fname, record_idx = jump_target
        # 1. Find the tab for this category
        for i, tab in enumerate(self.tabs):
            if self._tab_matches_category(tab, category):
                self.active_tab_index = i
                # 2. If it's a DrillDownTab, open the file
                if isinstance(tab, DrillDownTab):
                    if not self._prepare_drilldown_jump(tab):
                        return
                    # Find index in file_list
                    for f_idx, (f, _) in enumerate(tab.file_list):
                        if f == fname:
                            try:
                                switched = tab.switch_to_file(f_idx, save_if_dirty=False)
                            except Exception:
                                import sys
                                print(f'Warning: failed to switch {tab.name} to {fname}',
                                      file=sys.stderr) # pragma: no cover
                                return
                            if not switched:
                                if tab.last_close_error:
                                    self._show_error_dialog(
                                        title='Save Failed',
                                        text=f"Failed to save {tab.name}: {tab.last_close_error}",
                                    )
                                return
                            # 3. Set selected record if supported
                            self._set_record_selection(tab.active_editor, record_idx)
                            break
                elif hasattr(tab, '_editor'):
                    self._set_record_selection(tab._editor, record_idx)
                else:
                    self._set_record_selection(tab, record_idx)
                break

    def _make_map_editor(self, fname, data, save_cb):
        """Factory for MapEditor wrapped as a tab."""
        from .map_editor import MapEditor
        is_dungeon = len(data) <= MAP_DUNGEON_SIZE
        editor = MapEditor(fname, data, is_dungeon, save_callback=save_cb)
        return TileEditorTab(editor)

    def _make_combat_editor(self, fname, data, save_cb):
        """Factory for CombatEditor wrapped as a tab."""
        from .combat_editor import CombatEditor
        editor = CombatEditor(fname, data, save_callback=save_cb)
        return TileEditorTab(editor)

    def _make_special_editor(self, fname, data, save_cb):
        """Factory for SpecialEditor wrapped as a tab."""
        from .special_editor import SpecialEditor
        editor = SpecialEditor(fname, data, save_callback=save_cb)
        return TileEditorTab(editor)

    def _make_dialog_editor(self, fname, data, save_cb):
        """Factory for DialogEditor wrapped as a tab."""
        from .dialog_editor import DialogEditor
        editor = DialogEditor(fname, data, save_callback=save_cb)
        return DialogEditorTab(editor)

    def _make_text_editor(self, fname, data, save_cb):
        """Factory for TextEditor wrapped as a tab."""
        from .text_editor import TextEditor
        editor = TextEditor(fname, data, save_callback=save_cb)
        return TextEditorTab(editor)

    def _make_roster_editor(self, fname, data, save_cb):
        """Factory for RosterEditor wrapped as a tab."""
        from .roster_editor import make_roster_tab
        return make_roster_tab(data, save_cb)

    def _make_bestiary_editor(self, fname, data, save_cb):
        """Factory for BestiaryEditor wrapped as a tab."""
        letter = fname[-1] if fname.startswith('MON') else '?'
        from .bestiary_editor import make_bestiary_tab
        return make_bestiary_tab(data, letter, save_cb)

    def _make_party_editor(self, fname, data, save_cb):
        """Factory for PartyEditor wrapped as a tab."""
        from .party_editor import make_party_tab
        return make_party_tab(data, save_cb)

    def _make_active_party_editor(self, fname, data, save_cb):
        """Factory for Active Party (PLRS) wrapped as a tab."""
        from .roster_editor import make_roster_tab
        return make_roster_tab(data, save_cb, tab_name='Active Party')

    def _make_exod_editor(self, fname, data, save_cb):
        """Factory for EXOD sub-editors (crawl, glyphs, frames).

        fname is 'EXOD:crawl', 'EXOD:glyphs', or 'EXOD:frames'.
        All read from the same EXOD binary via session.
        """
        exod_data = self.session.read('EXOD')
        if exod_data is None:
            return None
        sub = fname.split(':')[1] if ':' in fname else fname
        if sub == 'crawl':
            from .exod_editor import ExodCrawlEditor
            return ExodCrawlEditor(exod_data,
                                   save_callback=self.session.make_save_callback('EXOD'))
        elif sub == 'glyphs':
            from .exod_editor import ExodGlyphViewer
            return ExodGlyphViewer(exod_data)
        elif sub == 'frames':
            from .exod_editor import ExodFrameViewer
            return ExodFrameViewer(exod_data)
        return None

    def _make_shapes_viewer(self, fname, data, save_cb):
        """Factory for SHPS character set viewer."""
        from .shapes_editor import ShapesViewer
        return ShapesViewer(data)

    def run(self):  # pragma: no cover
        """Run the unified tabbed editor."""
        from prompt_toolkit import Application
        from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl, FloatContainer, Float
        from prompt_toolkit.layout.containers import DynamicContainer, ConditionalContainer
        from prompt_toolkit.widgets import Frame
        from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings, \
            ConditionalKeyBindings
        from prompt_toolkit.filters import Condition

        self._build_tabs()
        if not self.tabs:
            print("No game data files found on disk image.")
            return False

        # Build UI for each tab (skip tabs that fail to build)
        tab_containers = []
        tab_keybindings = []
        valid_tabs = []
        for tab in self.tabs:
            try:
                container, kb = tab.build_ui()
                tab_containers.append(container)
                tab_keybindings.append(kb)
                valid_tabs.append(tab)
            except Exception as e:
                import sys
                print(f"Warning: tab '{tab.name}' failed to build: {e}",
                      file=sys.stderr) # pragma: no cover # pragma: no cover
        self.tabs = valid_tabs
        if not self.tabs:
            print("No game data files found on disk image.")
            return False

        app_ref = self

        # Tab bar
        def get_tab_bar():
            fragments = [('class:tab-bar', ' ')]
            for i, tab in enumerate(app_ref.tabs):
                dirty = '*' if tab.is_dirty else ''
                if i == app_ref.active_tab_index:
                    style = 'class:tab-active'
                else:
                    style = 'class:tab-inactive'
                fragments.append((style, f' {i + 1}:{tab.name}{dirty} '))
                fragments.append(('class:tab-bar', ' '))
            return fragments

        tab_bar = Window(content=FormattedTextControl(get_tab_bar), height=1)

        # Dynamic content
        def get_content():
            return tab_containers[app_ref.active_tab_index]
        content = DynamicContainer(get_content)

        # Global status
        def get_global_status():
            img = os.path.basename(app_ref.session.image_path)
            dirty_count = sum(1 for t in app_ref.tabs if t.is_dirty)
            dirty_text = f' ({dirty_count} modified)' if dirty_count else ''
            return [
                ('class:status', f' ult3edit: {img}'),
                ('class:status-dirty' if dirty_count else 'class:status', dirty_text),
                ('class:status', f' | Tab {app_ref.active_tab_index + 1}/{len(app_ref.tabs)}'),
            ]

        # Global help bar
        def get_global_help_bar():
            return [
                ('class:help-key', ' F5/F6 '), ('class:help-text', '=tabs '),
                ('class:help-key', 'Ctrl+S'), ('class:help-text', '=save '),
                ('class:help-key', 'Ctrl+Q'), ('class:help-text', '=quit '),
                ('class:help-key', 'F2'), ('class:help-text', '=THEME '),
                ('class:help-key', 'F1/?'), ('class:help-text', '=HELP '),
            ]

        status_bar = Window(content=FormattedTextControl(get_global_status),
                            height=1)
        help_bar = Window(content=FormattedTextControl(get_global_help_bar), height=1)

        # Help Overlay
        def get_help_text():
            tab = app_ref.tabs[app_ref.active_tab_index]
            text = f" HELP: {tab.name} \n"
            text += "═" * 40 + "\n\n"
            text += " GLOBAL KEYS:\n"
            text += "  F5 / Ctrl+Left  : Previous Tab\n"
            text += "  F6 / Ctrl+Right : Next Tab\n"
            text += "  Ctrl+S          : Save current data\n"
            text += "  Ctrl+Q          : Save all and Quit\n"
            text += "  F1 / ?          : Toggle this help\n\n"

            text += f" {tab.name.upper()} KEYS:\n"
            if tab.name in {'Maps', 'Combat', 'Special',
                            'Map Editor', 'Combat Map Editor', 'Special Location Editor'}:
                text += "  Arrows          : Move cursor\n"
                text += "  Space / Enter   : Paint selected tile\n"
                text += "  [ / ]           : Cycle tiles\n"
                text += "  P               : Open visual tile picker\n"
                text += "  Ctrl+Z / Ctrl+Y : Undo / Redo\n"
            elif tab.name in {'Roster', 'Active Party', 'Bestiary', 'Party'} or tab.name.startswith('MON'):
                text += "  Up / Down       : Navigate list\n"
                text += "  Enter           : Edit selected record/field\n"
                text += "  Escape          : Back to list\n"
                text += "  Ctrl+Z / Ctrl+Y : Undo / Redo\n"
            elif tab.name == 'Dialog':
                text += "  Up / Down       : Navigate records\n"
                text += "  Enter           : Edit record text\n"
                text += "  Ctrl+Z / Ctrl+Y : Undo / Redo\n"
            elif tab.name == 'Text':
                text += "  Up / Down       : Navigate records\n"
                text += "  Enter           : Edit record text\n"
                text += "  Ctrl+Z / Ctrl+Y : Undo / Redo\n"
            elif tab.name == 'Search':
                text += "  S               : New search\n"
                text += "  Up / Down       : Navigate results\n"
                text += "  Enter           : Jump to result\n"

            text += "\n\n Press any key to close "
            return text

        help_overlay = ConditionalContainer(
            content=FloatContainer(
                content=Window(),
                floats=[
                    Float(Frame(Window(content=FormattedTextControl(get_help_text),
                                       style='class:status',
                                       align='center',
                                       width=60, height=20)))
                ]
            ),
            filter=Condition(lambda: app_ref.show_help)
        )

        root = FloatContainer(
            content=HSplit([tab_bar, content, status_bar, help_bar]),
            floats=[
                Float(help_overlay)
            ]
        )

        # Global keybindings
        global_kb = KeyBindings()

        @global_kb.add('f1')
        @global_kb.add('?')
        def _toggle_help(event):
            app_ref.show_help = not app_ref.show_help

        @global_kb.add('f2')
        def _toggle_theme(event):
            from .theme import THEMES
            theme_names = list(THEMES.keys())
            idx = (theme_names.index(app_ref.theme_name) + 1) % len(theme_names)
            app_ref.theme_name = theme_names[idx]
            from .theme import get_style
            event.app.style = get_style(app_ref.theme_name)

        @global_kb.add('any', filter=Condition(lambda: app_ref.show_help),
                       eager=True)
        def _close_help(event):
            app_ref.show_help = False
            event.app.invalidate()

        @global_kb.add('c-right')
        @global_kb.add('s-tab', eager=True)
        @global_kb.add('f6')
        def _next_tab(event):
            app_ref.active_tab_index = (
                (app_ref.active_tab_index + 1) % len(app_ref.tabs))

        @global_kb.add('c-left')
        @global_kb.add('f5')
        def _prev_tab(event):
            app_ref.active_tab_index = (
                (app_ref.active_tab_index - 1) % len(app_ref.tabs))

        @global_kb.add('c-s')
        def _save_current(event):
            tab = app_ref.tabs[app_ref.active_tab_index]
            if tab.is_dirty:
                from prompt_toolkit.shortcuts import confirm
                if confirm(title="Save Changes", text=f"Save changes to {tab.name}?").run():
                    failures = app_ref._save_tabs([tab])
                    if failures:
                        from prompt_toolkit.shortcuts import message_dialog
                        message_dialog(
                            title='Save Failed',
                            text=f"Failed to save: {', '.join(failures)}",
                        ).run()

        @global_kb.add('c-f')
        def _goto_search(event):
            for i, t in enumerate(app_ref.tabs):
                if t.name == "Search":
                    app_ref.active_tab_index = i
                    break

        @global_kb.add('c-q')
        def _quit(event):
            dirty_tabs = [t for t in app_ref.tabs if t.is_dirty]
            if dirty_tabs:
                from prompt_toolkit.shortcuts import button_dialog, message_dialog
                summary = ", ".join(t.name for t in dirty_tabs)
                choice = button_dialog(
                    title="Unsaved Changes",
                    text=f"Unsaved tabs: {summary}",
                    buttons=[
                        ('Save All', 'save'),
                        ('Discard', 'discard'),
                        ('Cancel', 'cancel'),
                    ],
                ).run()
                if choice in (None, 'cancel'):
                    return
                if choice == 'save':
                    failures = app_ref._save_tabs(dirty_tabs)
                    if failures:
                        message_dialog(
                            title='Save Failed',
                            text=f"Failed to save: {', '.join(failures)}\nQuit cancelled.",
                        ).run()
                        return
            event.app.exit(result=True)

        # Per-tab keybindings (conditional)
        conditional_kbs = []
        for i, kb in enumerate(tab_keybindings):
            if kb:
                cond = Condition(lambda idx=i: app_ref.active_tab_index == idx)
                conditional_kbs.append(ConditionalKeyBindings(kb, cond))

        all_kb = merge_key_bindings([global_kb] + conditional_kbs)

        app = Application(
            layout=Layout(root),
            key_bindings=all_kb,
            style=U3_STYLE,
            full_screen=True,
            mouse_support=False,
        )
        return app.run()
