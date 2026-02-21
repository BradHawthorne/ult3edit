"""Verify engine build output matches original binaries byte-for-byte.

Usage:
    python engine/verify.py                    # Verify all 3 binaries
    python engine/verify.py --binary SUBS      # Verify one binary
    python engine/verify.py --omf-header-size  # Print OMF header size
"""

import argparse
import os
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ENGINE_DIR, 'build')
ORIGINALS_DIR = os.path.join(ENGINE_DIR, 'originals')

OMF_HEADER_SIZE = 60  # asmiigs OMF v2.1 segment header

BINARIES = {
    'SUBS': {'size': 3584, 'org': 0x4100},
    'ULT3': {'size': 17408, 'org': 0x5000},
    'EXOD': {'size': 26208, 'org': 0x2000},
}


def verify_binary(name: str) -> tuple[bool, str]:
    """Verify a single binary. Returns (success, message)."""
    info = BINARIES.get(name)
    if not info:
        return False, f"Unknown binary: {name}"

    omf_path = os.path.join(BUILD_DIR, f'{name}.omf')
    orig_path = os.path.join(ORIGINALS_DIR, f'{name}.bin')

    if not os.path.exists(omf_path):
        return False, f"Build output not found: {omf_path}"
    if not os.path.exists(orig_path):
        return False, f"Original binary not found: {orig_path}"

    with open(omf_path, 'rb') as f:
        omf_data = f.read()
    with open(orig_path, 'rb') as f:
        orig_data = f.read()

    if len(orig_data) != info['size']:
        return False, f"Original size mismatch: expected {info['size']}, got {len(orig_data)}"

    # Extract code from OMF (skip header)
    code = omf_data[OMF_HEADER_SIZE:OMF_HEADER_SIZE + len(orig_data)]
    if len(code) != len(orig_data):
        return False, (f"OMF code section size mismatch: "
                       f"expected {len(orig_data)}, got {len(code)}")

    if code == orig_data:
        return True, f"{name}: {len(orig_data):,} bytes BYTE-IDENTICAL (${info['org']:04X})"

    mismatches = sum(1 for a, b in zip(code, orig_data) if a != b)
    first_offset = next(i for i, (a, b) in enumerate(zip(code, orig_data)) if a != b)
    return False, (f"{name}: {mismatches} byte(s) differ — "
                   f"first at 0x{first_offset:04X}: "
                   f"built=0x{code[first_offset]:02X} "
                   f"orig=0x{orig_data[first_offset]:02X}")


def verify_all() -> bool:
    """Verify all engine binaries. Returns True if all pass."""
    all_pass = True
    for name in BINARIES:
        ok, msg = verify_binary(name)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {msg}")
        if not ok:
            all_pass = False
    return all_pass


def main():
    parser = argparse.ArgumentParser(description='Verify engine build output')
    parser.add_argument('--binary', '-b', help='Verify single binary (SUBS/ULT3/EXOD)')
    parser.add_argument('--omf-header-size', action='store_true',
                        help='Print OMF header size and exit')
    args = parser.parse_args()

    if args.omf_header_size:
        print(OMF_HEADER_SIZE)
        return

    if args.binary:
        ok, msg = verify_binary(args.binary.upper())
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        sys.exit(0 if ok else 1)

    print("=== Engine Build Verification ===")
    ok = verify_all()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
