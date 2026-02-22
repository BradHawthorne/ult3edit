# Ultima III SDK — Scenario Author Guide

## Quick Start

```bash
# 1. Create your scenario directory
mkdir -p my_scenario/sources

# 2. Copy the template patch file
cp engine/templates/engine_strings.json my_scenario/sources/engine_strings_full.json

# 3. Edit the patch file with your string replacements
#    (edit my_scenario/sources/engine_strings_full.json)

# 4. Build the modified engine binary
bash engine/scenario_build.sh my_scenario/

# 5. Apply to a game directory (optional)
bash engine/scenario_build.sh my_scenario/ --apply-to /path/to/GAME/
```

## Architecture

The SDK provides a two-tier build pipeline:

### Source-Level (Recommended)
Modifies `.s` assembly source files, then reassembles with `asmiigs`.
- **No string length constraints** — replacements can be any length
- Requires `asmiigs` assembler from Project Rosetta v2.0.0+
- Produces a new engine binary from modified source

### Binary-Level (Fallback)
Patches the engine binary in-place using byte replacement.
- **Length constrained** — replacement must fit in original byte allocation
- No external tools needed beyond Python
- Faster, but limited

## What You Can Change

### Engine Inline Strings (245 strings in ULT3)
Every text string displayed by the JSR $46BA inline printer can be replaced.
Categories include:
- Quest items (CARD OF DEATH, MARK OF KINGS, etc.)
- Combat messages (KILLED!, MISSED!, VICTORY!, etc.)
- Movement prompts (NORTH, SOUTH, BOARD, KLIMB, etc.)
- Magic system (SPELL TYPE, HEAL WHOM?, CURE, etc.)
- Equipment (WHICH WEAPON:, WHICH ARMOUR:, etc.)
- Shop transactions (GOLD-, AMOUNT-, HOW MANY-, etc.)
- Status messages (INCAPACITATED, STARVING, etc.)
- Story/quest text (EVOCARE, Time Lord visions, etc.)
- UI prompts (ACTION-, WHO-, DIRECT-, etc.)

Full catalog: `engine/tools/ult3_strings.json`

### Name Table (921 bytes)
Terrain names, monster names, weapon/armor names, spell names.
Edit via: `ult3edit patch edit <ULT3> --region name-table --data <hex>`
Or compile from text: `conversions/tools/name_compiler.py`

### Moongates (8 X + 8 Y coordinates)
Edit via: `ult3edit patch edit <ULT3> --region moongate-x --data <hex>`

### Food Depletion Rate (1 byte)
Edit via: `ult3edit patch edit <ULT3> --region food-rate --data <hex>`

### All Data Files
Every game data file can be edited via ult3edit CLI:
- `roster` — Characters (stats, equipment, inventory)
- `bestiary` — Monster encounters (13 files)
- `combat` — Battlefield maps (9 files)
- `map` — World, castle, town, dungeon maps (20 files)
- `special` — Shrines, fountains, brands, time lord (4 files)
- `tlk` — NPC dialog (19 files)
- `text` — Title/prompt strings
- `shapes` — Tile graphics (256 tiles)
- `sound` — Sound effects and music (SOSA/SOSM/MBS)
- `ddrw` — Dungeon drawing data

## Patch File Format

```json
{
  "description": "My scenario engine string patches",
  "patches": [
    {"vanilla": "CARD OF DEATH",  "text": "MY CUSTOM ITEM"},
    {"vanilla": "MARK OF KINGS",  "text": "MY CUSTOM MARK"},
    {"index": 142, "text": "CUSTOM TEXT BY INDEX"}
  ]
}
```

### Matching Methods
- `"vanilla"`: Match by original string text (case-insensitive)
- `"index"`: Match by string catalog index (0-244)
- `"address"`: Match by engine address (binary patcher only)

## Directory Layout

```
my_scenario/
  sources/
    engine_strings_full.json    # Source-level string patches (preferred)
    engine_strings.json         # Binary-level patches (fallback)
    names.names                 # Name table text source
    bestiary_a.json             # Monster stats (per encounter file)
    combat_a.json               # Battlefield layouts
    mapa.map                    # Overworld map (text-art format)
    tlka.txt                    # NPC dialog text
    tiles.tiles                 # Tile graphics (text-art pixel art)
    ...
  apply.sh                      # Master conversion script
```

## Tools Reference

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `source_patcher.py` | Source-level string replacement | `.s` + `.json` | Modified `.s` |
| `string_patcher.py` | Binary-level string replacement | `.bin` + `.json` | Patched `.bin` |
| `string_catalog.py` | List all inline strings | `.bin` | JSON/text catalog |
| `scenario_build.sh` | End-to-end scenario build | scenario dir | Patched binary |
| `tile_compiler.py` | Text-art → tile binary | `.tiles` | `.json` |
| `map_compiler.py` | Text-art → map binary | `.map` | `.json` |
| `name_compiler.py` | Text names → hex data | `.names` | hex string |
