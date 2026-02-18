"""Unified CLI for u3edit: Ultima III data toolkit.

Dispatches to all tool modules via a single entry point:
    u3edit edit <disk_image>
    u3edit roster view <file>
    u3edit bestiary view <dir>
    u3edit map view <file>
    u3edit tlk view <dir>
    u3edit combat view <dir>
    u3edit save view <dir>
    u3edit special view <dir>
    u3edit text view <file>
    u3edit spell view
    u3edit equip view
"""

import argparse
import sys

from . import __version__
from . import roster
from . import bestiary
from . import map
from . import tlk
from . import combat
from . import save
from . import special
from . import text
from . import spell
from . import equip
from . import disk


def _cmd_unified_edit(args) -> None:
    """Launch the unified tabbed TUI editor for a disk image."""
    import os
    if not os.path.isfile(args.image):
        print(f"Error: Disk image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    from .tui import require_prompt_toolkit
    require_prompt_toolkit()
    from .tui.game_session import GameSession
    from .tui.app import UnifiedApp

    try:
        with GameSession(args.image) as session:
            app = UnifiedApp(session)
            app.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='u3edit',
        description='Ultima III: Exodus - Game Data Toolkit',
        epilog='See https://github.com/BradHawthorne/u3edit for documentation.',
    )
    parser.add_argument('--version', action='version', version=f'u3edit {__version__}')

    subparsers = parser.add_subparsers(dest='tool', help='Tool to run')

    # Top-level unified editor
    edit_parser = subparsers.add_parser(
        'edit', help='Open unified tabbed TUI editor for a disk image')
    edit_parser.add_argument('image', help='Path to ProDOS disk image (.po, .2mg)')

    # Register all tool modules
    roster.register_parser(subparsers)
    bestiary.register_parser(subparsers)
    map.register_parser(subparsers)
    tlk.register_parser(subparsers)
    combat.register_parser(subparsers)
    save.register_parser(subparsers)
    special.register_parser(subparsers)
    text.register_parser(subparsers)
    spell.register_parser(subparsers)
    equip.register_parser(subparsers)
    disk.register_parser(subparsers)

    args = parser.parse_args()

    if not args.tool:
        parser.print_help()
        sys.exit(0)

    # Dispatch to the appropriate module
    dispatchers = {
        'roster': roster.dispatch,
        'bestiary': bestiary.dispatch,
        'map': map.dispatch,
        'tlk': tlk.dispatch,
        'combat': combat.dispatch,
        'save': save.dispatch,
        'special': special.dispatch,
        'text': text.dispatch,
        'spell': spell.dispatch,
        'equip': equip.dispatch,
        'disk': disk.dispatch,
    }

    if args.tool == 'edit':
        _cmd_unified_edit(args)
        return

    handler = dispatchers.get(args.tool)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
