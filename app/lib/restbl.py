# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""RESTBL (System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs, plain zstd).
A bfres entry = file size + runtime overhead (~14-16 KB per shape+material in vanilla models).
When shapes/materials are added, the overhead must grow too, or the extra shapes get garbage
(slivers/flicker) once the vanilla slack is used up."""
import struct, zlib
PER_ADDED_SHAPE=0x8000           # 32 KB per added shape+material (vanilla uses ~14-16 KB; 2x margin)
a32=lambda n:(n+31)&~31
def entries(r):
    cn=struct.unpack_from('<I',r,0xe)[0]
    return {struct.unpack_from('<I',r,0x16+8*i)[0]:0x16+8*i+4 for i in range(cn)}
def bump(r, path, new_size, old_size, added_shapes=0):
    """r: bytearray of the decompressed table; path like 'Model/X.X.bfres' (no .zs)."""
    loc=entries(r)[zlib.crc32(path.encode())]; old=struct.unpack_from('<I',r,loc)[0]
    new=old+a32(new_size)-a32(old_size)+PER_ADDED_SHAPE*added_shapes
    struct.pack_into('<I',r,loc,new); return old,new
def add_entry(r, path, value):
    """Insert a new CRC entry (sorted by hash). r: bytearray, modified in place; returns the new table."""
    cn=struct.unpack_from('<I',r,0xe)[0]; h=zlib.crc32(path.encode())
    ents=[struct.unpack_from('<II',r,0x16+8*i) for i in range(cn)]
    assert h not in {e[0] for e in ents},'hash already present: '+path
    ents.append((h,value)); ents.sort()
    out=bytearray(r[:0x16]); struct.pack_into('<I',out,0xe,cn+1)
    for e in ents: out+=struct.pack('<II',*e)
    out+=r[0x16+8*cn:]; return out
def value(r, path):
    return struct.unpack_from('<I',r,entries(r)[zlib.crc32(path.encode())])[0]
