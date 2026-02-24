# Quick Start: Building a Total Conversion

This guide walks through modifying a few game assets to demonstrate the conversion workflow. For a complete asset checklist, see `CHECKLIST.md`.

## Prerequisites

```bash
pip install -e ".[dev]"
```

You need a vanilla Ultima III ProDOS disk image (`game.po`).

## Step 1: Extract Game Files

```bash
ult3edit disk extract game.po -o GAME/
```

This creates a directory with all game files (e.g., `ROST#069500`, `MONA#069900`, `MAPA#061000`, etc.).

## Step 2: Edit Monsters

```bash
# Make monster #0 in MONA a dragon with 200 HP
ult3edit bestiary edit GAME/MONA#069900 --monster 0 --hp 200 --attack 80 --name "DRAGON"

# Or use JSON for bulk edits
ult3edit bestiary view GAME/MONA#069900 --json -o monsters.json
# Edit monsters.json, then import back
ult3edit bestiary import GAME/MONA#069900 monsters.json
```

## Step 3: Edit a Map Tile

```bash
# Place a town tile at coordinates (10, 20) on the overworld
ult3edit map set GAME/MAPA#061000 --x 10 --y 20 --tile 0x18

# Or use the text-art compiler for full map replacement
ult3edit map decompile GAME/MAPA#061000 --output mapa.map
# Edit mapa.map with any text editor (single-char tiles: ~=water .=grass ^=mountain)
ult3edit map compile mapa.map --output GAME/MAPA#061000
```

## Step 4: Edit NPC Dialog

```bash
# Replace a word across all dialog records
ult3edit tlk edit GAME/TLKA#060000 --find "EXODUS" --replace "VOIDBORN"

# Or use extract/build for full text editing
ult3edit tlk extract GAME/TLKA#060000 tlka.txt
# Edit tlka.txt with any editor
ult3edit tlk build tlka.txt GAME/TLKA#060000
```

## Step 5: Build the Disk Image

```bash
# Build a new ProDOS disk image from modified files
ult3edit disk build modified.po GAME/

# Copy boot blocks from vanilla for compatibility
ult3edit disk build modified.po GAME/ --boot-from game.po
```

The resulting `modified.po` can be loaded in any Apple IIgs emulator.

## Next Steps

- See `CHECKLIST.md` for every replaceable asset with the exact ult3edit command
- See `STORY_TEMPLATE.md` for narrative structure guidance
- See `apply_template.sh` for a full 11-phase automation script
- See `../voidborn/` for a complete reference conversion
