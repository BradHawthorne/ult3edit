"""Rebuild a vanilla ProDOS disk image through our builder to test correctness."""
import os
import sys
import math

VANILLA = sys.argv[1]
OUTPUT = sys.argv[2]

with open(VANILLA, 'rb') as f:
    orig = f.read()

# --- Extract ---
def read_block_orig(blk):
    return orig[blk*512:(blk+1)*512]

def read_file_data(key_block, storage_type, eof):
    if storage_type == 1:
        return read_block_orig(key_block)[:eof]
    elif storage_type == 2:
        idx = read_block_orig(key_block)
        data = bytearray()
        for i in range(256):
            blk = idx[i] | (idx[256+i] << 8)
            if blk == 0:
                break
            data.extend(read_block_orig(blk))
        return bytes(data[:eof])
    elif storage_type == 3:
        master = read_block_orig(key_block)
        data = bytearray()
        for j in range(256):
            idx_blk = master[j] | (master[256+j] << 8)
            if idx_blk == 0:
                break
            idx = read_block_orig(idx_blk)
            for i in range(256):
                blk = idx[i] | (idx[256+i] << 8)
                if blk == 0:
                    break
                data.extend(read_block_orig(blk))
        return bytes(data[:eof])
    return b''

def parse_dir_blocks(first_block):
    files = []
    blk_num = first_block
    first = True
    while blk_num > 0:
        blk = read_block_orig(blk_num)
        next_blk = blk[2] | (blk[3] << 8)
        for i in range(13):
            offset = 4 + i * 0x27
            if offset + 0x27 > 512:
                break
            stype = blk[offset] >> 4
            nlen = blk[offset] & 0x0F
            if i == 0 and first:
                first = False
                continue
            if stype == 0 or nlen == 0:
                continue
            name = blk[offset+1:offset+1+nlen].decode('ascii', errors='replace')
            ftype = blk[offset+0x10]
            key = blk[offset+0x11] | (blk[offset+0x12] << 8)
            eof = blk[offset+0x15] | (blk[offset+0x16] << 8) | (blk[offset+0x17] << 16)
            aux = blk[offset+0x1F] | (blk[offset+0x20] << 8)
            files.append((name, ftype, key, stype, eof, aux))
        blk_num = next_blk
    return files

root_files_data = []
game_files_data = []
root_entries = parse_dir_blocks(2)
for name, ftype, key, stype, eof, aux in root_entries:
    if stype == 0xD:
        sub_files = parse_dir_blocks(key)
        for sname, sftype, skey, sstype, seof, saux in sub_files:
            if sstype == 0xD:
                continue
            data = read_file_data(skey, sstype, seof)
            game_files_data.append((sname, sftype, saux, data))
    else:
        data = read_file_data(key, stype, eof)
        root_files_data.append((name, ftype, aux, data))

print(f"Extracted: {len(root_files_data)} root files, {len(game_files_data)} game files")

# === REBUILD ===
TOTAL_BLOCKS = 1600
BLOCK_SIZE = 512
ENTRY_LENGTH = 0x27
ENTRIES_PER_BLOCK = 0x0D
VOL_NAME = b'ULTIMA3'

boot_blocks = orig[:1024]
disk = bytearray(TOTAL_BLOCKS * BLOCK_SIZE)
disk[0:len(boot_blocks)] = boot_blocks

bitmap_block = 6
vol_dir_blocks = [2, 3, 4, 5]
next_free = 7

def alloc_block():
    global next_free
    if next_free >= TOTAL_BLOCKS:
        raise RuntimeError('Disk full')
    blk = next_free
    next_free += 1
    return blk

def write_block(blk_num, data):
    offset = blk_num * BLOCK_SIZE
    disk[offset:offset + len(data)] = data

def write_file(data):
    eof = len(data)
    if eof == 0:
        blk = alloc_block()
        return blk, 1, 1
    data_blocks_needed = math.ceil(eof / BLOCK_SIZE)
    if data_blocks_needed == 1:
        blk = alloc_block()
        padded = data + b'\x00' * (BLOCK_SIZE - len(data))
        write_block(blk, padded)
        return blk, 1, 1
    elif data_blocks_needed <= 256:
        idx_blk = alloc_block()
        data_blks = []
        for i in range(data_blocks_needed):
            dblk = alloc_block()
            chunk = data[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE]
            if len(chunk) < BLOCK_SIZE:
                chunk = chunk + b'\x00' * (BLOCK_SIZE - len(chunk))
            write_block(dblk, chunk)
            data_blks.append(dblk)
        idx = bytearray(BLOCK_SIZE)
        for i, dblk in enumerate(data_blks):
            idx[i] = dblk & 0xFF
            idx[256 + i] = (dblk >> 8) & 0xFF
        write_block(idx_blk, idx)
        return idx_blk, 2, 1 + data_blocks_needed
    else:
        master_blk = alloc_block()
        idx_blks = []
        total_written = 0
        remaining = data_blocks_needed
        while remaining > 0:
            chunk_count = min(256, remaining)
            idx_blk = alloc_block()
            data_blks = []
            for i in range(chunk_count):
                dblk = alloc_block()
                start = total_written * BLOCK_SIZE
                chunk = data[start:start+BLOCK_SIZE]
                if len(chunk) < BLOCK_SIZE:
                    chunk = chunk + b'\x00' * (BLOCK_SIZE - len(chunk))
                write_block(dblk, chunk)
                data_blks.append(dblk)
                total_written += 1
            idx = bytearray(BLOCK_SIZE)
            for i, dblk in enumerate(data_blks):
                idx[i] = dblk & 0xFF
                idx[256 + i] = (dblk >> 8) & 0xFF
            write_block(idx_blk, idx)
            idx_blks.append(idx_blk)
            remaining -= chunk_count
        master = bytearray(BLOCK_SIZE)
        for i, iblk in enumerate(idx_blks):
            master[i] = iblk & 0xFF
            master[256 + i] = (iblk >> 8) & 0xFF
        write_block(master_blk, master)
        return master_blk, 3, 1 + len(idx_blks) + data_blocks_needed

def make_entry(storage_type, name, file_type, key_block, blocks_used, eof, aux_type, header_pointer=0):
    entry = bytearray(ENTRY_LENGTH)
    name_bytes = name.encode('ascii')[:15]
    entry[0x00] = (storage_type << 4) | len(name_bytes)
    entry[0x01:0x01+len(name_bytes)] = name_bytes
    entry[0x10] = file_type
    entry[0x11] = key_block & 0xFF
    entry[0x12] = (key_block >> 8) & 0xFF
    entry[0x13] = blocks_used & 0xFF
    entry[0x14] = (blocks_used >> 8) & 0xFF
    entry[0x15] = eof & 0xFF
    entry[0x16] = (eof >> 8) & 0xFF
    entry[0x17] = (eof >> 16) & 0xFF
    entry[0x1E] = 0xE3
    entry[0x1F] = aux_type & 0xFF
    entry[0x20] = (aux_type >> 8) & 0xFF
    entry[0x25] = header_pointer & 0xFF
    entry[0x26] = (header_pointer >> 8) & 0xFF
    return entry

# Write root files first
prodos_order = {'PRODOS': 0, 'LOADER.SYSTEM': 1}
root_files_data.sort(key=lambda r: (prodos_order.get(r[0], 99), r[0]))
file_records = []
for prodos_name, file_type, aux_type, data in root_files_data:
    key_block, storage_type, blocks_used = write_file(data)
    file_records.append((prodos_name, file_type, aux_type, key_block, storage_type, blocks_used, len(data), True))

# Correct GAME dir block count
if len(game_files_data) <= 12:
    game_dir_block_count = 1
else:
    game_dir_block_count = 1 + math.ceil((len(game_files_data) - 12) / 13)
game_dir_blocks = [alloc_block() for _ in range(game_dir_block_count)]

for prodos_name, file_type, aux_type, data in game_files_data:
    key_block, storage_type, blocks_used = write_file(data)
    file_records.append((prodos_name, file_type, aux_type, key_block, storage_type, blocks_used, len(data), False))

# Build GAME subdirectory
for i, blk in enumerate(game_dir_blocks):
    prev_blk = game_dir_blocks[i-1] if i > 0 else 0
    next_blk = game_dir_blocks[i+1] if i < len(game_dir_blocks) - 1 else 0
    block_data = bytearray(BLOCK_SIZE)
    block_data[0] = prev_blk & 0xFF
    block_data[1] = (prev_blk >> 8) & 0xFF
    block_data[2] = next_blk & 0xFF
    block_data[3] = (next_blk >> 8) & 0xFF

    if i == 0:
        hdr = bytearray(ENTRY_LENGTH)
        name_bytes = b'GAME'
        hdr[0x00] = (0x0E << 4) | len(name_bytes)
        hdr[0x01:0x01+len(name_bytes)] = name_bytes
        hdr[0x1C] = 0x00
        hdr[0x1D] = 0x00
        hdr[0x1E] = 0xE3
        hdr[0x1F] = ENTRY_LENGTH
        hdr[0x20] = ENTRIES_PER_BLOCK
        game_file_count = len([r for r in file_records if not r[7]])
        hdr[0x21] = game_file_count & 0xFF
        hdr[0x22] = (game_file_count >> 8) & 0xFF
        hdr[0x23] = vol_dir_blocks[0] & 0xFF
        hdr[0x24] = (vol_dir_blocks[0] >> 8) & 0xFF
        hdr[0x25] = 0x01  # placeholder
        hdr[0x26] = ENTRY_LENGTH
        block_data[4:4+ENTRY_LENGTH] = hdr

    entry_slot = 1 if i == 0 else 0
    if i == 0:
        file_idx = 0
    else:
        file_idx = 12 + (i - 1) * 13
    game_entries = [r for r in file_records if not r[7]]
    for slot in range(entry_slot, 13):
        if file_idx >= len(game_entries):
            break
        rec = game_entries[file_idx]
        name, ftype, aux, key, stype, blks, eof, _ = rec
        entry = make_entry(stype, name, ftype, key, blks, eof, aux, header_pointer=game_dir_blocks[0])
        offset = 4 + slot * ENTRY_LENGTH
        block_data[offset:offset+ENTRY_LENGTH] = entry
        file_idx += 1
    write_block(blk, block_data)

# Build volume directory
root_dir_entries = []
root_recs = [r for r in file_records if r[7]]
root_recs.sort(key=lambda r: (prodos_order.get(r[0], 99), r[0]))
for rec in root_recs:
    name, ftype, aux, key, stype, blks, eof, _ = rec
    entry = make_entry(stype, name, ftype, key, blks, eof, aux, header_pointer=vol_dir_blocks[0])
    root_dir_entries.append(entry)

game_entry = bytearray(ENTRY_LENGTH)
name_bytes = b'GAME'
game_entry[0x00] = (0x0D << 4) | len(name_bytes)
game_entry[0x01:0x01+len(name_bytes)] = name_bytes
game_entry[0x10] = 0x0F
game_entry[0x11] = game_dir_blocks[0] & 0xFF
game_entry[0x12] = (game_dir_blocks[0] >> 8) & 0xFF
game_total_blocks = len(game_dir_blocks)
game_entry[0x13] = game_total_blocks & 0xFF
game_entry[0x14] = (game_total_blocks >> 8) & 0xFF
game_entry[0x15] = (len(game_dir_blocks) * BLOCK_SIZE) & 0xFF
game_entry[0x16] = ((len(game_dir_blocks) * BLOCK_SIZE) >> 8) & 0xFF
game_entry[0x17] = ((len(game_dir_blocks) * BLOCK_SIZE) >> 16) & 0xFF
game_entry[0x1E] = 0xE3
game_entry[0x25] = vol_dir_blocks[0] & 0xFF
game_entry[0x26] = (vol_dir_blocks[0] >> 8) & 0xFF
root_dir_entries.append(game_entry)

root_file_count = len(root_dir_entries)

for i, blk in enumerate(vol_dir_blocks):
    prev_blk = vol_dir_blocks[i-1] if i > 0 else 0
    next_blk = vol_dir_blocks[i+1] if i < len(vol_dir_blocks) - 1 else 0
    block_data = bytearray(BLOCK_SIZE)
    block_data[0] = prev_blk & 0xFF
    block_data[1] = (prev_blk >> 8) & 0xFF
    block_data[2] = next_blk & 0xFF
    block_data[3] = (next_blk >> 8) & 0xFF

    if i == 0:
        hdr = bytearray(ENTRY_LENGTH)
        hdr[0x00] = (0x0F << 4) | len(VOL_NAME)
        hdr[0x01:0x01+len(VOL_NAME)] = VOL_NAME
        hdr[0x1C] = 0x00
        hdr[0x1D] = 0x00
        hdr[0x1E] = 0xE3
        hdr[0x1F] = ENTRY_LENGTH
        hdr[0x20] = ENTRIES_PER_BLOCK
        hdr[0x21] = root_file_count & 0xFF
        hdr[0x22] = (root_file_count >> 8) & 0xFF
        hdr[0x23] = bitmap_block & 0xFF
        hdr[0x24] = (bitmap_block >> 8) & 0xFF
        hdr[0x25] = TOTAL_BLOCKS & 0xFF
        hdr[0x26] = (TOTAL_BLOCKS >> 8) & 0xFF
        block_data[4:4+ENTRY_LENGTH] = hdr

    entry_slot = 1 if i == 0 else 0
    if i == 0:
        file_idx = 0
    else:
        file_idx = 12 + (i - 1) * 13
    for slot in range(entry_slot, 13):
        if file_idx >= len(root_dir_entries):
            break
        offset = 4 + slot * ENTRY_LENGTH
        block_data[offset:offset+ENTRY_LENGTH] = root_dir_entries[file_idx]
        file_idx += 1
    write_block(blk, block_data)

# Fix GAME parent entry number
game_parent_entry = len(root_dir_entries) + 1
disk[game_dir_blocks[0] * BLOCK_SIZE + 4 + 0x25] = game_parent_entry

# Bitmap
bitmap_size = math.ceil(TOTAL_BLOCKS / 8)
bitmap_blocks_needed = math.ceil(bitmap_size / BLOCK_SIZE)
bitmap = bytearray(bitmap_blocks_needed * BLOCK_SIZE)
for i in range(len(bitmap)):
    bitmap[i] = 0xFF
def mark_used(blk_num):
    byte_idx = blk_num // 8
    bit_idx = 7 - (blk_num % 8)
    bitmap[byte_idx] &= ~(1 << bit_idx)
mark_used(0)
mark_used(1)
for blk in vol_dir_blocks:
    mark_used(blk)
for i in range(bitmap_blocks_needed):
    mark_used(bitmap_block + i)
for blk in game_dir_blocks:
    mark_used(blk)
for blk in range(7, next_free):
    mark_used(blk)
for blk in range(TOTAL_BLOCKS, bitmap_blocks_needed * BLOCK_SIZE * 8):
    if blk // 8 < len(bitmap):
        mark_used(blk)
for i in range(bitmap_blocks_needed):
    write_block(bitmap_block + i, bitmap[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE])

with open(OUTPUT, 'wb') as f:
    f.write(disk)

print(f"Rebuilt vanilla: {OUTPUT}")
print(f"  {len(root_files_data)} root files, {len(game_files_data)} game files")
print(f"  {game_dir_block_count} GAME dir blocks, {next_free} total blocks used")
print(f"  File size: {len(disk)} bytes")
