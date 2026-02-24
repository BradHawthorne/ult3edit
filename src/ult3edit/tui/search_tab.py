"""TUI Search Tab: unified search across dialog, maps, and roster."""

from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import input_dialog
from .editor_tab import EditorTab


class SearchTab(EditorTab):
    def __init__(self, session, jump_callback=None):
        self.session = session
        self.jump_callback = jump_callback
        self.query = ""
        self.results = []
        self.selected_index = 0
        self.dirty = False

    @property
    def name(self):
        return "Search"

    @property
    def is_dirty(self):
        return False

    def save(self):
        pass

    def _normalize_selection(self):
        """Keep selected_index in bounds for current results."""
        if not self.results:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(self.results) - 1))

    def move_selection(self, delta: int):
        """Move selection by delta while keeping bounds valid."""
        if not self.results:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(len(self.results) - 1, self.selected_index + delta))

    def selected_result(self):
        """Return the currently selected result, or None if there are none."""
        self._normalize_selection()
        if not self.results:
            return None
        return self.results[self.selected_index]

    def build_ui(self): # pragma: no cover
        tab = self

        class SearchControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header', f" SEARCH: '{tab.query}' ".ljust(width))])
                lines.append([('class:palette-header', " " + "─" * (width - 2) + " ")])

                if not tab.results:
                    lines.append([('', " No results found. Press 'S' to search. ")])
                else:
                    for i, res in enumerate(tab.results):
                        style = 'class:palette-selected' if i == tab.selected_index else ''
                        marker = ' <' if i == tab.selected_index else ''
                        label = f" [{res['type']}] {res['label']}"
                        lines.append([(style, f"{label}{marker}".ljust(width))])

                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            return [('class:status', f" Search | {len(tab.results)} results ")]

        def get_help():
            return [
                ('class:help-key', ' S '), ('class:help-text', '=new search '),
                ('class:help-key', ' Up/Down '), ('class:help-text', '=navigate '),
                ('class:help-key', ' Enter '), ('class:help-text', '=jump '),
            ]

        root = HSplit([
            Window(content=SearchControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_status), height=1),
            Window(content=FormattedTextControl(get_help), height=1),
        ])

        kb = KeyBindings()

        @kb.add('s')
        def _search(event):
            res = input_dialog(title="Global Search", text="Enter search query:").run()
            if res:
                tab.query = res
                tab._perform_search()

        @kb.add('up')
        def _up(event):
            tab.move_selection(-1)

        @kb.add('down')
        def _down(event):
            tab.move_selection(1)

        @kb.add('enter')
        def _jump(event):
            res = tab.selected_result()
            if res and tab.jump_callback:
                tab.jump_callback(res['jump'])

        return root, kb

    def _perform_search(self):
        if not self.query:
            self.results = []
            self._normalize_selection()
            return

        self.results = []
        q = self.query.lower()

        # 1. Search Roster / Active Party
        for cat in ['roster', 'active_party']:
            if self.session.has_category(cat):
                files = self.session.files_in(cat)
                if files:
                    fname, _ = files[0]
                    data = self.session.read(fname)
                    if data:
                        from ..roster import Character
                        from ..constants import CHAR_RECORD_SIZE
                        for i in range(len(data) // CHAR_RECORD_SIZE):
                            char = Character(data[i*CHAR_RECORD_SIZE : (i+1)*CHAR_RECORD_SIZE])
                            if not char.is_empty and q in char.name.lower():
                                self.results.append({
                                    'type': 'Roster' if cat == 'roster' else 'Party',
                                    'file': fname,
                                    'label': f"{char.name} (Slot {i})",
                                    'jump': (cat, fname, i)
                                })

        # 2. Search Dialog (TLK)
        if self.session.has_category('dialog'):
            for fname, display in self.session.files_in('dialog'):
                data = self.session.read(fname)
                if data:
                    from ..tlk import parse_tlk_data
                    # Scan records individually to find matching index
                    records = parse_tlk_data(data, skip_binary=True)
                    for i, lines in enumerate(records):
                        combined = " ".join(lines).lower()
                        if q in combined:
                            self.results.append({
                                'type': 'Dialog',
                                'file': fname,
                                'label': f"{display} (Match in record {i})",
                                'jump': ('dialog', fname, i)
                            })

        # 3. Search Bestiary
        if self.session.has_category('bestiary'):
            for fname, display in self.session.files_in('bestiary'):
                data = self.session.read(fname)
                if data:
                    from ..bestiary import load_monsters
                    monsters = load_monsters(data, fname[-1])
                    for i, mon in enumerate(monsters):
                        if not mon.is_empty and q in mon.name.lower():
                            self.results.append({
                                'type': 'Monster',
                                'file': fname,
                                'label': f"{mon.name} ({display}, slot {i})",
                                'jump': ('bestiary', fname, i)
                            })

        # 4. Search Maps / Special
        for cat in ['maps', 'special']:
            if self.session.has_category(cat):
                for fname, display in self.session.files_in(cat):
                    if q in display.lower() or q in fname.lower():
                        self.results.append({
                            'type': 'Map' if cat == 'maps' else 'Special',
                            'file': fname,
                            'label': display,
                            'jump': (cat, fname, 0)
                        })

        # 5. Search Text
        if self.session.has_category('text'):
            data = self.session.read('TEXT')
            if data:
                from .text_editor import parse_text_records
                records = parse_text_records(data)
                for i, rec in enumerate(records):
                    if q in rec.text.lower():
                        self.results.append({
                            'type': 'Text',
                            'file': 'TEXT',
                            'label': f"Game String {i}: {rec.text[:30]}...",
                            'jump': ('text', 'TEXT', i)
                        })

        self._normalize_selection()
