# Ultima III: Exodus - Complete File Format Reference

All byte offsets and field purposes verified by tracing engine code in the
symbolicated engine sources (`engine/ult3/ult3.s`, `engine/exod/exod.s`,
`engine/subs/subs.s`). Label names reference the fully symbolicated source.

---

## ROST / PLRS - Character Records

**ROST**: 1280 bytes = 20 slots x 64 bytes. Loaded at $9500.
**PLRS**: 256 bytes = 4 active slots x 64 bytes. Loaded at $4000.

### Character Record (64 bytes)

| Offset | Size | Field | Encoding | Notes |
|--------|------|-------|----------|-------|
| 0x00 | 14 | Name | High-ASCII, null-terminated | Max 13 chars (BOOT.s CPY #$0D), byte 0x0D = guaranteed null |
| 0x0E | 1 | Marks/Cards | Bitmask | High nibble=Marks (7:Kings 6:Snake 5:Fire 4:Force), Low=Cards (3:Death 2:Moons 1:Sol 0:Love) |
| 0x0F | 1 | Torches | Binary | Count of torch items |
| 0x10 | 1 | In-Party | Binary | $FF = in active party, $00 = not |
| 0x11 | 1 | Status | ASCII | G=Good, P=Poisoned, D=Dead, A=Ashes |
| 0x12 | 1 | STR | BCD | Strength (0-99) |
| 0x13 | 1 | DEX | BCD | Dexterity (0-99) |
| 0x14 | 1 | INT | BCD | Intelligence (0-99) |
| 0x15 | 1 | WIS | BCD | Wisdom (0-99) |
| 0x16 | 1 | Race | ASCII | H/E/D/B/F |
| 0x17 | 1 | Class | ASCII | F/C/W/T/L/I/D/A/R/P/B |
| 0x18 | 1 | Gender | ASCII | M/F/O |
| 0x19 | 1 | MP | BCD | Magic points (0-99) |
| 0x1A | 2 | HP | BCD16 | Hit points, hi:lo (0-9999) |
| 0x1C | 2 | Max HP | BCD16 | Maximum HP, hi:lo (0-9999) |
| 0x1E | 2 | EXP | BCD16 | Experience, hi:lo (0-9999) |
| 0x20 | 1 | Sub-morsels | Binary | Food fraction (R-4 fix: not level) |
| 0x21 | 2 | Food | BCD16 | Food supply, hi:lo (0-9999) |
| 0x23 | 2 | Gold | BCD16 | Gold, hi:lo (0-9999) |
| 0x25 | 1 | Gems | BCD | Gem count (0-99) |
| 0x26 | 1 | Keys | BCD | Key count (0-99) |
| 0x27 | 1 | Powders | BCD | Powder count (0-99) |
| 0x28 | 1 | Worn Armor | Index | Currently equipped armor (0-7) |
| 0x29 | 7 | Armor Inv | Binary[7] | Count of each armor type (Skin..Exotic) |
| 0x30 | 1 | Readied Weapon | Index | Currently equipped weapon (0-15) |
| 0x31 | 15 | Weapon Inv | Binary[15] | Count of each weapon type (Dagger..Exotic) |

**Total**: 64 bytes, all accounted for.

---

## PRTY - Party State

**16 bytes**, loaded to zero-page $E0-$EF.

| Offset | ZP | Size | Field | Notes |
|--------|-----|------|-------|-------|
| 0 | $E0 | 1 | Transport | Movement mode: $00=None, $01=Foot, $0A=Horse, $0B=Ship |
| 1 | $E1 | 1 | Party Size | Active member count (0-4) |
| 2 | $E2 | 1 | Location Type | $00=Sosaria, $01=Dungeon, $02=Town, $03=Castle, $80=Combat, $FF=Ambrosia |
| 3 | $E3 | 1 | Saved X | Overworld X coordinate (0-63) |
| 4 | $E4 | 1 | Saved Y | Overworld Y coordinate (0-63) |
| 5 | $E5 | 1 | Sentinel | $FF when party is active |
| 6-9 | $E6-$E9 | 4 | Slot IDs | Roster indices for 4 party members (0-19) |
| 10-15 | $EA-$EF | 6 | Unused | Always zero |

**Engine ZP aliases**: $E0=SPEEDZ, $E4=ERRFLG (Applesoft names, misleading).

---

## MON{A-Z} - Monster Encounter Files

**256 bytes** = 16 rows x 16 columns, columnar layout.
`file[row * 16 + monster_index]`

### Attribute Rows (0-9)

| Row | Attribute | Notes |
|-----|-----------|-------|
| 0 | Tile 1 | Primary sprite tile ID |
| 1 | Tile 2 | Secondary/animation tile ID |
| 2 | Flags 1 | Behavior flags (bit 7=Boss, bit 2=Undead, etc.) |
| 3 | Flags 2 | Additional flags |
| 4 | HP | Hit points |
| 5 | Attack | Attack strength |
| 6 | Defense | Defense value |
| 7 | Speed | Movement speed |
| 8 | Ability 1 | Special ability code |
| 9 | Ability 2 | Special ability code |

### Rows 10-15 (padding/runtime)

Not read from disk as monster attributes. At runtime ($4F00), the engine
repurposes this memory as five 32-entry parallel arrays for overworld
creature tracking:

| Runtime Addr | Purpose |
|-------------|---------|
| $4F00,X | Creature sprite tile |
| $4F20,X | Animation frame |
| $4F40,X | Creature X coordinate |
| $4F60,X | Creature Y coordinate |
| $4F80,X | Status flags ($C0=active) |

Last 4 bytes ($4FFC-$4FFF) are ship navigation workspace.

---

## MAP{A-Z} - Map Files

**MAPA** (Overworld): 4096 bytes = 64x64 tiles. `offset = y * 64 + x`
**MAPB-MAPK** (Towns/Castles): 4096 bytes = 64x64 tiles.
**MAPL** (Ambrosia): 4096 bytes = 64x64 tiles.
**MAPM-MAPS** (Dungeons): 2048 bytes = 8 levels x 16x16. `offset = level * 256 + y * 16 + x`

### Tile Encoding

- **Overworld/Town**: `tile_id = byte & 0xFC`, low 2 bits = animation frame
- **Dungeon**: `tile_id = byte & 0x0F`, uses separate DUNGEON_TILES table

---

## CON{A-S} - Combat Battlefield Maps

**192 bytes**, loaded at $9900.

| Offset | Size | Purpose | Editable? |
|--------|------|---------|-----------|
| 0x00-0x78 | 121 | 11x11 tile grid | YES |
| 0x79-0x7F | 7 | Unused padding | No (never read) |
| 0x80-0x87 | 8 | Monster start X [0-7] | YES |
| 0x88-0x8F | 8 | Monster start Y [0-7] | YES |
| 0x90-0x97 | 8 | Runtime: saved tile under monster | No (overwritten at init) |
| 0x98-0x9F | 8 | Runtime: monster type/status | No (overwritten at init) |
| 0xA0-0xA3 | 4 | PC start X [0-3] | YES |
| 0xA4-0xA7 | 4 | PC start Y [0-3] | YES |
| 0xA8-0xAB | 4 | Runtime: saved tile under PC | No (overwritten at init) |
| 0xAC-0xAF | 4 | Runtime: PC appearance tile | No (overwritten by JSR $7F5D) |
| 0xB0-0xBF | 16 | Unused tail padding | No (never read) |

Tile grid addressing: `offset = y * 11 + x` (`combat_tile_at_xy` at $7E18).

---

## BRND / SHRN / FNTN / TIME - Special Locations

**128 bytes**, loaded at $9900.

| Offset | Size | Purpose |
|--------|------|---------|
| 0x00-0x78 | 121 | 11x11 tile grid (same encoding as CON) |
| 0x79-0x7F | 7 | Unused padding (disk residue, text fragments) |

Engine only reads the 11x11 grid. Trailing 7 bytes contain residual data
from memory at file creation time (e.g. "DECFOOD", "CLRBD", "! THAT'").

---

## TLK{A-S} - Dialog Files

Variable-length records. Each record is a sequence of high-ASCII text
lines separated by $FF (line break) and terminated by $00 (record end).

---

## SOSA - Overworld Map State

**4096 bytes** = 64x64 tiles. Copy of MAPA with dynamic changes (opened
chests, destroyed terrain, etc.). Loaded at $1000.

Note: SOSA is a save-state file (dynamic overworld snapshot), not a sound
data file despite the name. Managed via the `sound` CLI subcommand.

---

## SOSM - Overworld Monster Positions

**256 bytes**. Tracks positions and states of overworld creatures. At
runtime, loaded to $4F00 where the engine manages creature arrays.

Note: SOSM is a save-state file (overworld creature tracking), not a sound
data file despite the name. Managed via the `sound` CLI subcommand.

---

## SHPS - Character Set / Tile Graphics

**2048 bytes** = 256 glyphs x 8 bytes. Loaded at $0800. Each glyph is
8 bytes = 7 pixels wide x 8 rows. Bit 7 of each byte is unused (always 0
in standard Apple II text mode charset).

**WARNING**: File offset $01F9 (address $09F9) contains a 7-byte embedded
code routine. Editing glyphs near index 63 may corrupt this code.

Tile sprites are 4 consecutive glyphs (4 animation frames per tile).
`tile_id / 4 = first glyph index`

---

## SHP{0-7} - Shop Overlay Code+Text

**~960 bytes each**, loaded at $9400. These are NOT tile shapes — they
are executable code overlays that draw shop interfaces and handle
transactions. Contains inline text strings using the `JSR $46BA` pattern
(3-byte JSR followed by high-ASCII text terminated by $00).

| File | Shop Type |
|------|-----------|
| SHP0 | Weapons |
| SHP1 | Armor |
| SHP2 | Grocery |
| SHP3 | Pub/Tavern |
| SHP4 | Healer |
| SHP5 | Oracle |
| SHP6 | Guild |
| SHP7 | Horse |

---

## TEXT - Title Screen Bitmap

**1024 bytes**. Despite the name, this is NOT text — it is an HGR
(Apple II high-resolution graphics) bitmap used for the title screen.
Loaded at $1000.

---

## MBS - Music/Sound Data

**5456 bytes**, loaded at $9A00. Contains AY-3-8910 sound chip register
data and music stream opcodes.

### Music Stream Opcodes

| Byte | Mnemonic | Operand | Meaning |
|------|----------|---------|---------|
| $00-$3F | NOTE | - | Note/rest value ($00=rest) |
| $80 | LOOP | - | Loop start/repeat |
| $81 | JUMP | addr_lo, addr_hi | Jump to address |
| $82 | END | - | End of stream |
| $83 | WRITE | register, value | Write AY register |
| $84 | TEMPO | value | Set playback tempo |
| $85 | MIXER | value | Set mixer control |

---

## DDRW - Dungeon Drawing Data

**1792 bytes**. Contains dungeon perspective rendering data: line vectors
for wall drawing and tile display records.

| Offset | Size | Purpose |
|--------|------|---------|
| 0x00F0 | 32 | Perspective line vectors |
| 0x0400+ | 7 each | Tile display records (col_start, col_end, step, flags, bright_lo, bright_hi, reserved) |

---

## ULT3 - Main Engine Binary

**17408 bytes**, ORG $5000.

### Key Patchable Regions

| Name | File Offset | Address | Size | Type |
|------|-------------|---------|------|------|
| Name Table | $397A | $897A | 921 | Null-terminated high-ASCII strings |
| Moongate X | $29A7 | $79A7 | 8 | X coordinates for 8 phases |
| Moongate Y | $29AF | $79AF | 8 | Y coordinates for 8 phases |
| Food Rate | $272C | $772C | 1 | Steps per food decrement (default $04) |

### Key Routines (symbolicated label names)

ULT3-defined routines ($5000+):

| Address | Label | Purpose |
|---------|-------|---------|
| $58E9 | `char_decrypt_records` | Character record decryption |
| $65B0 | `game_main_loop` | Central state machine / game loop |
| $7107 | `combat_add_hp` | Combat HP management |
| $7181 | `combat_apply_damage` | Apply damage and status effects |
| $75AE | `magic_cast_spell` | Spell casting handler |
| $7E18 | `combat_tile_at_xy` | Combat tile lookup (`offset = Y*11 + X`) |
| $93DE | `calc_hgr_scanline` | HGR scanline address computation |

SUBS routines called by ULT3 (defined in SUBS at $4100+):

| Address | Label | Purpose |
|---------|-------|---------|
| $4732 | `print_inline_str` | Inline string printer (JSR $46BA + text + $00) |
| $4935 | `calc_roster_ptr` | Roster slot address ($9500 + N*64) |
| $4955 | `copy_roster_to_plrs` | Copy roster records to active PLRS |
| $4BCA | `setup_char_ptr` | Character pointer ($FE/$FF = $4000 + slot*64) |
| $4CE8 | `play_sfx` | Sound effect dispatcher |
| $4E40 | `get_random` | Pseudo-random number generator |

---

## EXOD - Boot/Loader Engine Binary

**26208 bytes**, ORG $2000. 87% data (HGR animation frames), 13% code.
Fully symbolicated — all labels renamed to `intro_*` / `anim_data_*`.

### Key Functions

| Address | Label | Purpose |
|---------|-------|---------|
| $823D | `intro_print_string` | Print high-ASCII string from $FE/$FF |
| $825E | `intro_sequence` | Main intro sequence orchestrator |
| $82E6 | `intro_wipe_title` | Title screen wipe animation |
| $83E3 | `intro_hgr_blit` | HGR block blit with transparency |
| $84E6 | `intro_check_key` | Poll keyboard with timeout |
| $850C | `intro_sound_effect` | Speaker tone generation |
| $856A | `intro_reveal_anim` | Progressive column reveal |

### Patchable Data Regions

| Name | File Offset | Address | Size | Type |
|------|-------------|---------|------|------|
| Text Crawl | $6000 | $8000 | ~533 | (X,Y) byte pairs, $00 terminated |
| Glyph Table | $0400 | $2400 | ~6,912 | 5-entry pointer table → 7 sub-pointers → 208-byte pixel blocks |
| HGR Frames | $2000-$3FFF | $4000-$5FFF | 8,192 | 6 animation frames on HGR page 2 |

**Text crawl** at $6000: Stream of (X, Y) coordinate pairs for the
"BY LORD BRITISH" pixel-plotted text. Y bytes stored as $BF - screen_y
(inverted). Terminated by $00 X byte. Each point plotted as double-wide
white pixel. Use `ult3edit exod crawl` subcommands to view/export/import/
render/compose.

**Glyph table** at $0400: Two-level pointer chain. 5-entry main table
(indices 0-3 drawn, 4 is sentinel) → 7 sub-pointer entries per glyph
(column variants for the reveal animation) → 208-byte pixel data blocks
(16 HGR rows x 13 bytes per row). Use `ult3edit exod glyph` subcommands.

**HGR frames**: 6 animation frames (title, serpent, castle, exodus,
frame3, frame4) stored on HGR page 2. Standard Apple II interleaved
scanline layout. Use `ult3edit exod export/import` for PNG conversion.

Previously documented addresses ($35E1, $35F9, $384D) were incorrectly
identified as coordinate tables — they are animation frame data
(`anim_data_*` labels).

---

## SUBS - Subroutine Library

**3584 bytes**, loaded at $4100. Fully symbolicated shared subroutine library.

### Key Functions

| Address | Label | Purpose |
|---------|-------|---------|
| $4732 | `print_inline_str` | Print text embedded after JSR $46BA |
| $4767 | `scroll_text_up` | Scroll text window, redraw border |
| $4855 | `draw_hgr_stripe` | Draw colored vertical stripe on HGR |
| $487B | `clear_hgr_page` | Zero-fill HGR page 1 ($2000-$3FFF) |
| $4893 | `plot_char_glyph` | Plot 7x8 character glyph to HGR |
| $48D9 | `swap_tile_frames` | Swap tile animation frames in memory |
| $48FF | `advance_ptr_128` | Add $80 to pointer $FE/$FF |
| $490D | `print_digit` | Print single ASCII digit |
| $4935 | `calc_roster_ptr` | Compute roster slot address ($9500+N*64) |
| $4955 | `copy_roster_to_plrs` | Copy roster records to active PLRS |
| $496B | `copy_plrs_to_roster` | Copy active PLRS back to roster |
| $49FF | `modulo` | A mod $F3 (modular arithmetic) |
| $4A13 | `update_viewport` | Full viewport display refresh |
| $4BCA | `setup_char_ptr` | Set $FE/$FF = $4000 + slot*64 |
| $4BE4 | `print_char_name` | Print character name centered |
| $4CE8 | `play_sfx` | Sound effect dispatcher ($F6-$FF) |
| $4E40 | `get_random` | Pseudo-random number generator |

---

## Encoding Conventions

- **BCD**: Most numeric fields (stats, HP, gold, etc.) use Binary Coded
  Decimal. Each nibble is a digit 0-9. Two-byte BCD16 is hi:lo for
  values 0-9999.
- **High-ASCII**: All text has bit 7 set ($80-$FE). Padding is $A0
  (space). Strings are null-terminated ($00).
- **Columnar layout**: MON files store data column-major:
  `file[attribute * 16 + monster_index]`.
- **Tile animation**: Overworld tile bytes encode the tile type in the
  upper 6 bits and the animation frame in the lower 2 bits. Mask with
  $FC to get the canonical tile ID.
