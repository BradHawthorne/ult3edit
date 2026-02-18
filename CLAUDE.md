# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

u3edit is a data toolkit for Ultima III: Exodus (Apple II, 1983). It provides CLI viewers, editors, and a unified TUI for all game data formats. Python 3.10+, no runtime dependencies. MIT license.

## Commands

```bash
pip install -e ".[dev]"              # Install with pytest
pip install -e ".[tui]"              # Install with prompt_toolkit for TUI editors
pytest -v                            # Run all 335 tests
pytest tests/test_roster.py          # Run one test module
pytest -v tests/test_bcd.py::TestBcdToInt::test_zero  # Run single test
u3edit roster view path/to/ROST      # CLI usage pattern
u3edit edit game.po                  # Unified TUI editor (requires prompt_toolkit)
```

## Architecture

### Module-per-data-type pattern

Each game data type lives in `src/u3edit/{module}.py` (roster, bestiary, map, tlk, combat, save, special, text, spell, equip). Every module follows the same contract:

- **Data class** (e.g., `Character`, `Monster`): wraps `bytearray` with `@property` accessors
- **`load_*(path)` / `save_*(path, obj)`**: File I/O
- **`cmd_view(args)`**: Text or `--json --output` rendering
- **`cmd_edit(args)`**: CLI editing with `--backup`, `--dry-run` flags
- **`cmd_import(args)`**: Import from JSON (`u3edit <module> import <binary> <json>`)
- **`register_parser(subparsers)`**: Adds CLI subcommands
- **`dispatch(args)`**: Routes to command handlers
- **`main()`**: Standalone entry point (also registered as `u3-{module}` console script)

### CLI dispatcher (`cli.py`)

`cli.py:main()` creates an argparse parser, calls each module's `register_parser()`, then dispatches to the matching module's `dispatch()`. The `edit` subcommand launches the unified TUI via `GameSession` + `UnifiedApp`.

### Binary encoding conventions

- **BCD (Binary Coded Decimal)**: Most numeric fields. See `bcd.py` for `bcd_to_int()`, `int_to_bcd()`, `int_to_bcd16()`.
- **High-bit ASCII**: Text has bit 7 set (0x80–0xFE). See `fileutil.py` for `decode_high_ascii()` / `encode_high_ascii()`. Padding char is 0xA0 (high-ASCII space).
- **Columnar layout**: MON files store 16 monsters × 10 attributes column-major: `file[attr * 16 + monster_index]`.
- **Bitmask fields**: Marks/cards packed in nibbles, monster flags as bitwise combinations.

### Constants as single source of truth

`constants.py` holds all tile tables, character attributes, weapon/armor stats, spell lists, file format layouts, and map names. All modules import from here.

### Disk image integration (`disk.py`)

`DiskContext` is a context manager that extracts ProDOS disk image files to a temp directory (via external `diskiigs` tool), caches reads, stages writes, and writes back on exit. Preserves ProDOS type/aux suffixes (`ROST#069500`). Writes even if an exception occurred (prevents data loss).

### TUI architecture (`tui/`)

- **`GameSession`** wraps `DiskContext`, catalogs available files by category, provides factory methods for editors
- **`UnifiedApp`** (`app.py`): Master tabbed editor using prompt_toolkit
- **`EditorState`** (`base.py`): Pure dataclass with zero I/O — all editor logic (cursor, viewport, painting) is testable without prompt_toolkit
- **`BaseTileEditor`**: UI layer that wraps `EditorState` for rendering and key handling

### File resolution (`fileutil.py`)

`resolve_game_file()` handles ProDOS type/aux suffixes and plain filenames with fallback glob. `find_game_files()` resolves multiple files by prefix pattern.

## Testing conventions

- Tests use **synthesized binary data** — no real game files needed
- Fixtures in `tests/conftest.py` build exact binary blobs matching Ultima III formats
- Each fixture produces known values so tests can assert decoded fields directly
- Setter tests verify validation (clamping, length limits, BCD encoding)

## CLI features across modules

- **`--backup`**: Creates `.bak` copy before overwriting (edit/import commands). Uses `fileutil.backup_file()`.
- **`--dry-run`**: Shows changes without writing (edit commands on roster, bestiary, tlk, save, map).
- **`--validate`**: Roster validation — checks BCD integrity, race stat caps, class equipment limits.
- **`--all`**: Bulk roster editing — applies edits to all non-empty slots (mutually exclusive with `--slot`).
- **`import`**: Every editable module supports `import <binary_file> <json_file>` to apply JSON data.
- **`map set/fill/replace/find`**: Map CLI editing — set tiles, fill regions, replace tile types, search.
- **`tlk search`**: Case-insensitive text search across TLK dialog files.
- **`save edit --plrs-slot`**: Edit active characters in PLRS file via save subcommand.
- **`TILE_CHARS_REVERSE` / `DUNGEON_TILE_CHARS_REVERSE`**: Reverse lookups in `constants.py` for char→tile-byte conversion (used by import commands).

## Data integrity rules

- Setter properties validate and clamp to valid ranges (e.g., coordinates 0–63, BCD max 99/9999)
- File size validation via `fileutil.validate_file_size()`
- TLK records use `is_text_record()` to filter binary data from dialog
- `DiskContext` preserves ProDOS file type/aux info through read-modify-write cycles
