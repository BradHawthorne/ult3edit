#!/usr/bin/env bash
# =============================================================================
# Voidborn Disk Image Builder
# =============================================================================
#
# Builds a complete Voidborn total conversion disk image from a vanilla
# Ultima III: Exodus ProDOS disk image.
#
# Usage: bash build_disk.sh <vanilla.po> [output.po]
#
# Requires:
#   - ult3edit installed (pip install -e .)
#   - diskiigs on PATH (or DISKIIGS_PATH set)
#   - asmiigs on PATH (optional, for source-level engine string patching)
#
# =============================================================================

set -euo pipefail

VANILLA="${1:?Usage: bash build_disk.sh <vanilla.po> [output.po]}"
OUTPUT="${2:-voidborn.po}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Locate diskiigs ---

find_diskiigs() {
    if [ -n "${DISKIIGS_PATH:-}" ] && [ -f "$DISKIIGS_PATH" ]; then
        echo "$DISKIIGS_PATH"; return
    fi
    local found
    found=$(command -v diskiigs 2>/dev/null || true)
    if [ -n "$found" ]; then echo "$found"; return; fi
    for base in "$HOME/Projects/rosetta_v2" "D:/Projects/rosetta_v2" "/opt/rosetta"; do
        for sub in "build/diskiigs/Release/diskiigs.exe" "build/diskiigs/diskiigs" \
                   "release/rosetta-v2.2.0-preview-win64/diskiigs.exe"; do
            if [ -f "$base/$sub" ]; then echo "$base/$sub"; return; fi
        done
    done
}

DISKIIGS=$(find_diskiigs)

# --- Validate prerequisites ---

if [ ! -f "$VANILLA" ]; then
    echo "ERROR: Vanilla disk image not found: $VANILLA"
    exit 1
fi

if [ -z "$DISKIIGS" ]; then
    echo "ERROR: diskiigs not found. Set DISKIIGS_PATH or add to PATH."
    exit 1
fi

if ! command -v ult3edit &>/dev/null; then
    echo "ERROR: ult3edit not found. Run: pip install -e ."
    exit 1
fi

if [ -z "${PYTHON:-}" ]; then
    if python3 --version &>/dev/null 2>&1; then PYTHON=python3
    elif python --version &>/dev/null 2>&1; then PYTHON=python
    else echo "ERROR: Python not found."; exit 1; fi
fi

echo "=== Voidborn Disk Image Builder ==="
echo "Vanilla: $VANILLA"
echo "Output:  $OUTPUT"
echo ""

# --- Step 1: Extract vanilla files ---

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
GAME_DIR="$TMPDIR/game"
mkdir -p "$GAME_DIR"

echo "--- Extracting vanilla game files ---"

# Use Python ProDOS parser to extract (handles non-standard image sizes)
$PYTHON -c "
import os, sys

IMAGE = sys.argv[1]
OUTDIR = sys.argv[2]

with open(IMAGE, 'rb') as f:
    disk = f.read()

def read_block(blk):
    return disk[blk*512:(blk+1)*512]

def read_file_data(key_block, storage_type, eof):
    if storage_type == 1:
        return read_block(key_block)[:eof]
    elif storage_type == 2:
        idx = read_block(key_block)
        data = bytearray()
        for i in range(256):
            blk = idx[i] | (idx[256+i] << 8)
            if blk == 0: break
            data.extend(read_block(blk))
        return bytes(data[:eof])
    elif storage_type == 3:
        master = read_block(key_block)
        data = bytearray()
        for j in range(256):
            idx_blk = master[j] | (master[256+j] << 8)
            if idx_blk == 0: break
            idx = read_block(idx_blk)
            for i in range(256):
                blk = idx[i] | (idx[256+i] << 8)
                if blk == 0: break
                data.extend(read_block(blk))
        return bytes(data[:eof])
    return b''

def parse_dir_blocks(first_block):
    files = []
    blk_num = first_block
    first = True
    while blk_num > 0:
        blk = read_block(blk_num)
        next_blk = blk[2] | (blk[3] << 8)
        for i in range(13):
            offset = 4 + i * 0x27
            if offset + 0x27 > 512: break
            stype = blk[offset] >> 4
            nlen = blk[offset] & 0x0F
            if i == 0 and first: first = False; continue
            if stype == 0 or nlen == 0: continue
            name = blk[offset+1:offset+1+nlen].decode('ascii', errors='replace')
            ftype = blk[offset+0x10]
            key = blk[offset+0x11] | (blk[offset+0x12] << 8)
            eof = blk[offset+0x15] | (blk[offset+0x16] << 8) | (blk[offset+0x17] << 16)
            aux = blk[offset+0x1F] | (blk[offset+0x20] << 8)
            files.append((name, ftype, key, stype, eof, aux))
        blk_num = next_blk
    return files

count = 0
root_files = parse_dir_blocks(2)
for name, ftype, key, stype, eof, aux in root_files:
    if stype == 0xD:
        sub_files = parse_dir_blocks(key)
        for sname, sftype, skey, sstype, seof, saux in sub_files:
            if sstype == 0xD: continue
            fname = f'{sname}#{sftype:02X}{saux:04X}'
            data = read_file_data(skey, sstype, seof)
            with open(os.path.join(OUTDIR, fname), 'wb') as out:
                out.write(data)
            count += 1
    else:
        fname = f'{name}#{ftype:02X}{aux:04X}'
        data = read_file_data(key, stype, eof)
        with open(os.path.join(OUTDIR, fname), 'wb') as out:
            out.write(data)
        count += 1

print(f'    Extracted {count} files')
" "$VANILLA" "$GAME_DIR"

# --- Step 2: Apply Voidborn conversion ---

echo "--- Applying Voidborn conversion ---"
echo ""
bash "$SCRIPT_DIR/apply.sh" "$GAME_DIR"
echo ""

# --- Step 3: Build output disk image ---

echo "--- Building disk image ---"

# Convert VANILLA to absolute Windows path for diskiigs
ABS_OUTPUT=$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")

# Determine image size from vanilla
VANILLA_SIZE=$(stat -c%s "$VANILLA" 2>/dev/null || stat -f%z "$VANILLA" 2>/dev/null)
BLOCKS=$((VANILLA_SIZE / 512))

"$DISKIIGS" create "$ABS_OUTPUT" "$BLOCKS" ULTIMA3
"$DISKIIGS" mkdir "$ABS_OUTPUT" GAME

# Copy boot blocks from vanilla (essential for ProDOS boot)
$PYTHON -c "
import sys
with open(sys.argv[1], 'rb') as src:
    boot = src.read(1024)
with open(sys.argv[2], 'r+b') as dst:
    dst.write(boot)
print('    Boot blocks copied from vanilla')
" "$VANILLA" "$ABS_OUTPUT"

# Add root-level files (PRODOS, LOADER.SYSTEM, U3)
ADDED=0
for f in "$GAME_DIR"/PRODOS#* "$GAME_DIR"/LOADER.SYSTEM#* "$GAME_DIR"/U3#*; do
    [ -f "$f" ] || continue
    [[ "$f" == *.bak ]] && continue
    fname=$(basename "$f")
    pname="${fname%%#*}"
    suffix="${fname##*#}"
    ftype="${suffix:0:2}"
    aux="${suffix:2:4}"
    "$DISKIIGS" add "$ABS_OUTPUT" "$f" "$pname" "$ftype" "$aux"
    ADDED=$((ADDED + 1))
done

# Add game files to GAME/
for f in "$GAME_DIR"/*; do
    fname=$(basename "$f")
    case "$fname" in
        PRODOS#*|LOADER.SYSTEM#*|U3#*|*.bak) continue ;;
    esac
    pname="${fname%%#*}"
    suffix="${fname##*#}"
    ftype="${suffix:0:2}"
    aux="${suffix:2:4}"
    "$DISKIIGS" add "$ABS_OUTPUT" "$f" "GAME/$pname" "$ftype" "$aux"
    ADDED=$((ADDED + 1))
done

echo "    Added $ADDED files to $OUTPUT"

# --- Step 4: Summary ---

OUTPUT_SIZE=$(stat -c%s "$ABS_OUTPUT" 2>/dev/null || stat -f%z "$ABS_OUTPUT" 2>/dev/null || echo "unknown")

echo ""
echo "=== Build complete ==="
echo "Output: $OUTPUT ($OUTPUT_SIZE bytes)"
echo ""
echo "Test in an Apple II emulator to verify playability."
