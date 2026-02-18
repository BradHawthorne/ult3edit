"""Color theme for u3edit TUI editors."""

from prompt_toolkit.styles import Style

U3_STYLE = Style.from_dict({
    # Cursor and selection
    'cursor':           'bg:ansiyellow ansiblack bold',
    'highlight':        'bg:#333333',

    # Grid labels
    'row-label':        'ansigray',
    'col-header':       'ansigray',

    # Tile colors (overworld/town)
    'tile-water':       'ansiblue',
    'tile-grass':       'ansigreen',
    'tile-forest':      'ansigreen bold',
    'tile-mountain':    'ansiwhite bold',
    'tile-wall':        'ansigray',
    'tile-floor':       'ansiyellow',
    'tile-town':        'ansired bold',
    'tile-dungeon':     'ansimagenta',
    'tile-monster':     'ansired',
    'tile-npc':         'ansicyan',
    'tile-special':     'ansimagenta bold',
    'tile-ship':        'ansiblue bold',
    'tile-default':     '',

    # Palette
    'palette-selected': 'bg:ansiblue ansiwhite bold',
    'palette-normal':   '',
    'palette-header':   'ansicyan bold',

    # Status bar
    'status':           'bg:ansiblue ansiwhite',
    'status-dirty':     'bg:ansired ansiwhite bold',
    'status-mode':      'bg:ansigreen ansiblack bold',
    'status-key':       'ansigreen bold',
    'status-text':      'ansigray',

    # Overlays (combat editor)
    'overlay-monster':  'bg:ansired ansiwhite bold',
    'overlay-pc':       'bg:ansigreen ansiblack bold',

    # Help
    'help-key':         'ansigreen bold',
    'help-text':        '',

    # Tab bar
    'tab-active':       'bg:ansiblue ansiwhite bold',
    'tab-inactive':     'bg:#333333 ansigray',
    'tab-dirty':        'ansired bold',
    'tab-bar':          'bg:#222222',
})

# Map canonical tile IDs to style classes
_TILE_STYLES = {
    0x00: 'tile-water',
    0x04: 'tile-grass',
    0x08: 'tile-grass',       # Brush
    0x0C: 'tile-forest',
    0x10: 'tile-mountain',
    0x14: 'tile-dungeon',
    0x18: 'tile-town',
    0x1C: 'tile-town',        # Castle
    0x20: 'tile-floor',
    0x24: 'tile-special',     # Chest
    0x28: 'tile-npc',         # Horse
    0x2C: 'tile-ship',
    0x30: 'tile-water',       # Whirlpool
    0x34: 'tile-monster',     # Serpent
    0x38: 'tile-monster',     # Man-o-War
    0x3C: 'tile-monster',     # Pirate
    0x40: 'tile-npc',         # Merchant
    0x44: 'tile-npc',         # Jester
    0x48: 'tile-npc',         # Guard
    0x4C: 'tile-npc',         # Lord British
    0x50: 'tile-npc',         # Fighter
    0x54: 'tile-npc',         # Cleric
    0x58: 'tile-npc',         # Wizard
    0x5C: 'tile-npc',         # Thief
    0x60: 'tile-monster',     # Orc
    0x64: 'tile-monster',     # Skeleton
    0x68: 'tile-monster',     # Giant
    0x6C: 'tile-monster',     # Daemon
    0x70: 'tile-monster',     # Pincher
    0x74: 'tile-monster',     # Dragon
    0x78: 'tile-monster',     # Balron
    0x7C: 'tile-monster',     # Exodus
    0x80: 'tile-special',     # Force Field
    0x84: 'tile-special',     # Lava
    0x88: 'tile-special',     # Moongate
    0x8C: 'tile-wall',
    0x90: 'tile-default',     # Void
    0xF0: 'tile-special',     # Magic
    0xF4: 'tile-special',     # Fire
    0xFC: 'tile-special',     # Hidden
}

# Dungeon tile styles (lower nibble only)
_DUNGEON_TILE_STYLES = {
    0x00: 'tile-floor',       # Open
    0x01: 'tile-wall',
    0x02: 'tile-special',     # Door
    0x03: 'tile-special',     # Secret door
    0x04: 'tile-special',     # Chest
    0x05: 'tile-special',     # Ladder down
    0x06: 'tile-special',     # Ladder up
    0x07: 'tile-special',     # Both ladders
    0x08: 'tile-special',     # Trap
    0x09: 'tile-special',     # Fountain
    0x0A: 'tile-monster',     # Mark
    0x0B: 'tile-wall',        # Wind
    0x0C: 'tile-monster',     # Gremlins
    0x0D: 'tile-npc',         # Orb
    0x0E: 'tile-npc',         # Pit
    0x0F: 'tile-default',     # Unknown
}


def tile_style(byte_val: int, is_dungeon: bool = False) -> str:
    """Map a tile byte value to a prompt_toolkit style string."""
    if is_dungeon:
        return 'class:' + _DUNGEON_TILE_STYLES.get(byte_val & 0x0F, 'tile-default')
    return 'class:' + _TILE_STYLES.get(byte_val & 0xFC, 'tile-default')
