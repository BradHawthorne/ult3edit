#!/bin/bash
# Ultima III SDK Engine Build System
# Assembles all engine binaries and verifies byte-identical output
#
# Usage: bash engine/build.sh [--verify-only]
#
# Requires:
#   - asmiigs (Project Rosetta v2.0.0+ assembler)
#   - Python 3.10+ (for verification)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASMIIGS="${ASMIIGS:-D:/Projects/rosetta_v2/build-release/asmiigs/Release/asmiigs.exe}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BUILD_DIR="${SCRIPT_DIR}/build"
mkdir -p "$BUILD_DIR"

ERRORS=0
WARNINGS=0

# Convert git-bash path to Windows path for Python
winpath() {
    echo "$1" | sed 's|^/\([a-zA-Z]\)/|\1:/|'
}

verify() {
    local name="$1"
    local omf_unix="${BUILD_DIR}/${name}.omf"
    local orig_unix="${SCRIPT_DIR}/originals/${name}.bin"
    local omf_win=$(winpath "$omf_unix")
    local orig_win=$(winpath "$orig_unix")

    echo -n "  Verifying ${name}... "
    RESULT=$(python -c "
omf = open(r'${omf_win}', 'rb').read()
orig = open(r'${orig_win}', 'rb').read()
code = omf[60:60+len(orig)]
if len(code) != len(orig):
    print(f'SIZE MISMATCH: OMF code={len(code)}, original={len(orig)}')
    exit(1)
if code == orig:
    print('BYTE-IDENTICAL')
    exit(0)
else:
    mismatches = sum(1 for a, b in zip(code, orig) if a != b)
    print(f'MISMATCH: {mismatches} bytes differ')
    for i, (a, b) in enumerate(zip(code, orig)):
        if a != b:
            print(f'  First: offset 0x{i:04x} OMF=0x{a:02x} orig=0x{b:02x}')
            break
    exit(1)
" 2>&1) || {
        echo -e "${RED}FAIL${NC} — $RESULT"
        ERRORS=$((ERRORS + 1))
        return 1
    }
    echo -e "${GREEN}${RESULT}${NC}"
}

assemble() {
    local name="$1"
    local source="$2"
    local omf="${BUILD_DIR}/${name}.omf"

    echo -n "  Assembling ${name}... "
    OUTPUT=$("$ASMIIGS" "$source" -o "$omf" --cpu 6502 2>&1) || {
        echo -e "${RED}FAILED${NC}"
        echo "$OUTPUT"
        ERRORS=$((ERRORS + 1))
        return 1
    }

    if echo "$OUTPUT" | grep -qi "warning"; then
        echo -e "${YELLOW}OK (with warnings)${NC}"
        echo "$OUTPUT" | grep -i "warning"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}OK${NC}"
    fi

    verify "$name"
}

echo "=== Ultima III SDK Engine Build ==="
echo ""

if [ "$1" = "--verify-only" ]; then
    echo "Verify-only mode"
    echo ""
    for name in SUBS ULT3 EXOD; do
        if [ -f "${BUILD_DIR}/${name}.omf" ] && [ -f "${SCRIPT_DIR}/originals/${name}.bin" ]; then
            verify "$name"
        else
            echo "  ${name}: missing files"
        fi
    done
else
    echo "Phase 1: Assemble + Verify"
    echo ""
    assemble "SUBS" "${SCRIPT_DIR}/subs/subs.s"
    assemble "ULT3" "${SCRIPT_DIR}/ult3/ult3.s"
    assemble "EXOD" "${SCRIPT_DIR}/exod/exod.s"
fi

echo ""
echo "=== Build Summary ==="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All 3 binaries: assembled + byte-identical.${NC}"
    echo "  SUBS  3,584 bytes  (\$4100)"
    echo "  ULT3 17,408 bytes  (\$5000)"
    echo "  EXOD 26,208 bytes  (\$2000)"
else
    echo -e "${RED}${ERRORS} error(s) detected.${NC}"
fi
[ $WARNINGS -gt 0 ] && echo -e "${YELLOW}${WARNINGS} warning(s).${NC}"
echo ""

exit $ERRORS
