"""TUI Shapes Viewer: browse character set / tile glyphs."""

from prompt_toolkit.layout import HSplit, Window, FormattedTextControl, VSplit
from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.key_binding import KeyBindings
from .editor_tab import EditorTab
from ..shapes import render_glyph_ascii, GLYPH_SIZE


class ShapesViewer(EditorTab):
    def __init__(self, data):
        self.data = data
        self.selected_glyph = 0

    @property
    def name(self):
        return "Shapes"

    @property
    def is_dirty(self):
        return False

    def build_ui(self): # pragma: no cover
        tab = self

        class GlyphListControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header', " Glyphs (0-255) ".ljust(width))])
                lines.append([('class:palette-header', " " + "─" * (width - 2) + " ")])

                # Show list of glyphs
                for i in range(256):
                    style = 'class:palette-selected' if i == tab.selected_glyph else ''
                    marker = ' <' if i == tab.selected_glyph else ''
                    label = f" Glyph ${i:02X} ({i})"
                    lines.append([(style, f"{label}{marker}".ljust(width))])

                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        class GlyphPreviewControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header', " Preview ".center(width))])
                lines.append([])

                # Render current glyph
                glyph_lines = render_glyph_ascii(tab.data, tab.selected_glyph * GLYPH_SIZE)
                for row in glyph_lines:
                    # Double-wide for better aspect ratio in terminal
                    pixels = "".join(ch * 2 for ch in row)
                    lines.append([('class:tile-grass', f"  {pixels}  ".center(width))])

                lines.append([])
                lines.append([('', f" Byte offsets: ${tab.selected_glyph*8:04X} - ${(tab.selected_glyph*8)+7:04X} ".center(width))])

                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            return [('class:status', f" Shapes Viewer | Glyph {tab.selected_glyph} ")]

        def get_help():
            return [
                ('class:help-key', ' Up/Down '), ('class:help-text', '=navigate '),
            ]

        root = HSplit([
            VSplit([
                Window(content=GlyphListControl(), width=25, wrap_lines=False),
                Window(content=GlyphPreviewControl(), wrap_lines=False),
            ]),
            Window(content=FormattedTextControl(get_status), height=1),
            Window(content=FormattedTextControl(get_help), height=1),
        ])

        kb = KeyBindings()

        @kb.add('up')
        def _up(event):
            tab.selected_glyph = max(0, tab.selected_glyph - 1)

        @kb.add('down')
        def _down(event):
            tab.selected_glyph = min(255, tab.selected_glyph + 1)

        return root, kb
