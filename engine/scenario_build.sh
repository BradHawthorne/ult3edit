#!/bin/bash
# Ultima III SDK Scenario Build System
# Builds a modified engine binary from source patches + reassembly.
#
# This is the source-level build pipeline for scenario/conversion authors.
# Unlike binary patching (string_patcher.py), source-level patches have NO
# LENGTH CONSTRAINTS on string replacements.
#
# Usage:
#   bash engine/scenario_build.sh <scenario_dir> [--apply-to <game_dir>]
#
# Scenario directory structure:
#   my_scenario/
#     sources/
#       engine_strings_full.json    # Source-level string patches
#       engine_strings.json         # Binary-level patches (fallback)
#       names.names                 # Name table patches
#       ...
#
# Pipeline:
#   1. Copy vanilla .s source files to build directory
#   2. Apply source_patcher.py patches (from engine_strings_full.json)
#   3. Reassemble with asmiigs to produce modified binary
#   4. Optionally apply binary to game directory
#
# Requires:
#   - asmiigs (Project Rosetta v2.0.0+ assembler)
#   - Python 3.10+

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find asmiigs
ASMIIGS="${ASMIIGS:-}"
if [ -z "$ASMIIGS" ]; then
    for candidate in \
        "D:/Projects/rosetta_v2/release/rosetta-v2.2.0-preview-win64/asmiigs.exe" \
        "D:/Projects/rosetta_v2/build-release/asmiigs/Release/asmiigs.exe" \
        "D:/Projects/rosetta_v2/build/asmiigs/Release/asmiigs.exe" \
        "$(which asmiigs 2>/dev/null)"; do
        if [ -x "$candidate" ] 2>/dev/null || [ -f "$candidate" ]; then
            ASMIIGS="$candidate"
            break
        fi
    done
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Convert git-bash path to Windows path for Python
winpath() {
    echo "$1" | sed 's|^/\([a-zA-Z]\)/|\1:/|'
}

usage() {
    echo "Usage: $0 <scenario_dir> [--apply-to <game_dir>]"
    echo ""
    echo "Arguments:"
    echo "  scenario_dir    Directory containing sources/ with patch JSON files"
    echo "  --apply-to      Copy built binary to game directory"
    echo ""
    echo "Environment:"
    echo "  ASMIIGS          Path to asmiigs assembler (auto-detected if not set)"
    exit 1
}

# Parse arguments
SCENARIO_DIR=""
GAME_DIR=""

while [ $# -gt 0 ]; do
    case "$1" in
        --apply-to)
            GAME_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            SCENARIO_DIR="$1"
            shift
            ;;
    esac
done

if [ -z "$SCENARIO_DIR" ]; then
    usage
fi

if [ ! -d "$SCENARIO_DIR" ]; then
    echo -e "${RED}Error: scenario directory not found: $SCENARIO_DIR${NC}"
    exit 1
fi

SOURCES_DIR="${SCENARIO_DIR}/sources"
BUILD_DIR="${SCRIPT_DIR}/build"
TOOLS_DIR="${SCRIPT_DIR}/tools"

mkdir -p "$BUILD_DIR"

ERRORS=0

echo "=== Ultima III SDK Scenario Build ==="
echo "  Scenario: $(basename "$SCENARIO_DIR")"
echo "  Sources:  $SOURCES_DIR"
echo ""

# -------------------------------------------------------------------
# Phase 1: Source-level string patches (ULT3)
# -------------------------------------------------------------------
FULL_PATCHES="${SOURCES_DIR}/engine_strings_full.json"
BINARY_PATCHES="${SOURCES_DIR}/engine_strings.json"

if [ -f "$FULL_PATCHES" ] && [ -n "$ASMIIGS" ]; then
    echo "Phase 1: Source-level build (no length constraints)"
    echo ""

    # Copy vanilla source
    ULT3_SRC="${BUILD_DIR}/ult3_scenario.s"
    cp "${SCRIPT_DIR}/ult3/ult3.s" "$ULT3_SRC"

    # Apply source patches
    echo -n "  Patching source... "
    PATCH_OUT=$(python "${TOOLS_DIR}/source_patcher.py" "$ULT3_SRC" "$FULL_PATCHES" 2>&1) || {
        echo -e "${RED}FAILED${NC}"
        echo "$PATCH_OUT"
        ERRORS=$((ERRORS + 1))
    }
    if [ $ERRORS -eq 0 ]; then
        echo -e "${GREEN}OK${NC}"
        echo "$PATCH_OUT" | grep "^ *\[" | head -20

        # Assemble
        echo -n "  Assembling... "
        ULT3_OMF="${BUILD_DIR}/ULT3_scenario.omf"
        ASM_OUT=$("$ASMIIGS" "$ULT3_SRC" -o "$ULT3_OMF" --cpu 6502 2>&1) || {
            echo -e "${RED}FAILED${NC}"
            echo "$ASM_OUT"
            ERRORS=$((ERRORS + 1))
        }
        if [ $ERRORS -eq 0 ]; then
            echo -e "${GREEN}OK${NC}"

            # Extract binary from OMF
            ULT3_BIN="${BUILD_DIR}/ULT3_scenario.bin"
            ULT3_OMF_WIN=$(winpath "$ULT3_OMF")
            ULT3_BIN_WIN=$(winpath "$ULT3_BIN")
            ORIG_WIN=$(winpath "${SCRIPT_DIR}/originals/ULT3.bin")
            python -c "
omf = open(r'${ULT3_OMF_WIN}', 'rb').read()
code = omf[60:-1]
open(r'${ULT3_BIN_WIN}', 'wb').write(code)
orig = open(r'${ORIG_WIN}', 'rb').read()
diff = len(code) - len(orig)
if diff == 0:
    print('  Size: identical to vanilla')
else:
    print(f'  Size: {len(code)} bytes ({diff:+d} from vanilla)')
" 2>&1
            echo -e "  ${GREEN}Built: ${ULT3_BIN}${NC}"
        fi
    fi

elif [ -f "$BINARY_PATCHES" ]; then
    echo "Phase 1: Binary-level patches (in-place, length constrained)"
    echo "  Note: Install asmiigs for source-level builds (no length limits)"
    echo ""

    ULT3_BIN="${BUILD_DIR}/ULT3_scenario.bin"
    cp "${SCRIPT_DIR}/originals/ULT3.bin" "$ULT3_BIN"

    echo -n "  Patching binary... "
    PATCH_OUT=$(python "${TOOLS_DIR}/string_patcher.py" "$ULT3_BIN" "$BINARY_PATCHES" 2>&1) || {
        echo -e "${RED}FAILED${NC}"
        echo "$PATCH_OUT"
        ERRORS=$((ERRORS + 1))
    }
    if [ $ERRORS -eq 0 ]; then
        echo -e "${GREEN}OK${NC}"
        echo "$PATCH_OUT" | head -20
    fi

else
    echo "Phase 1: No engine string patches found (skipping)"
fi

echo ""

# -------------------------------------------------------------------
# Phase 2: Apply to game directory
# -------------------------------------------------------------------
if [ -n "$GAME_DIR" ] && [ -f "${BUILD_DIR}/ULT3_scenario.bin" ]; then
    echo "Phase 2: Apply to game directory"

    # Find ULT3 file in game dir
    ULT3_GAME=$(find "$GAME_DIR" -maxdepth 2 -name "ULT3*" -type f 2>/dev/null | head -1)
    if [ -n "$ULT3_GAME" ]; then
        echo "  Target: $ULT3_GAME"
        echo -n "  Copying... "
        cp "${BUILD_DIR}/ULT3_scenario.bin" "$ULT3_GAME"
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "  ${YELLOW}Warning: ULT3 file not found in $GAME_DIR${NC}"
    fi
fi

echo ""
echo "=== Scenario Build Summary ==="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}Build succeeded.${NC}"
else
    echo -e "${RED}${ERRORS} error(s).${NC}"
fi
echo ""

exit $ERRORS
