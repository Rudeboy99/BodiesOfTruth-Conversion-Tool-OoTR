# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Read-only bfres v10 model inspection (no numpy): shapes, materials, vertex layouts, textures."""
import struct
FMDL=0xf0
ATTR_FMT={0x518:'f32x3',0x515:'f16x4',0x512:'f16x2',0x20e:'snorm10_10_10_2',0x112:'unorm16x2',0x212:'snorm16x2',
          0x30b:'u8x4',0x309:'u8x2',0x302:'u8',0x10b:'unorm8x4',0x109:'unorm8x2',0x102:'unorm8',0x20b:'snorm8x4',0x00b:'unorm8x4c',0x30a:'u16',0x312:'u16x2',0x315:'u16x4',0x10a:'unorm16',0x112:'unorm16x2'}
def u64(d,o): return struct.unpack_from('<Q',d,o)[0]
def cstr(d,o): n=struct.unpack_from('<H',d,o)[0]; return d[o+2:o+2+n].decode('latin1')
def materials(d):
    mat=u64(d,FMDL+0x38); nm=struct.unpack_from('<H',d,FMDL+0x6c)[0]; out=[]
    for i in range(nm):
        fm=mat+0xb0*i; tp=u64(d,fm+0x20)
        out.append(dict(index=i,name=cstr(d,u64(d,fm+8)),textures=[cstr(d,u64(d,tp+8*t)) for t in range(d[fm+0xa3])]))
    return out
def shapes(d):
    shp=u64(d,FMDL+0x28); ns=struct.unpack_from('<H',d,FMDL+0x6a)[0]; mats=materials(d); out=[]
    for i in range(ns):
        o=shp+0x60*i; fv=u64(d,o+0x10); ap=u64(d,fv+8)
        attrs={cstr(d,u64(d,ap+16*k)):((d[ap+16*k+8]<<8)|d[ap+16*k+9],struct.unpack_from('<H',d,ap+16*k+12)[0]) for k in range(d[fv+0x4c])}
        out.append(dict(index=i,name=cstr(d,u64(d,o+8)),material=mats[struct.unpack_from('<H',d,o+0x52)[0]]['name'],
            skin=d[o+0x5a],lods=d[o+0x5b],stride=struct.unpack_from('<I',d,u64(d,fv+0x38))[0],
            verts=struct.unpack_from('<I',d,fv+0x50)[0],attrs=attrs))
    return out
def smooth_count(d):
    f=u64(d,FMDL+0x18); return struct.unpack_from('<H',d,f+0x3a)[0]
def wide_index(s): return '_i0' in s['attrs'] and (s['attrs']['_i0'][0]&0xff) in (0x0a,0x12,0x15)
def layout_key(s):
    return '%d/%d:'%(s['stride'],s['skin'])+','.join('%s@%d=%s'%(n,o,ATTR_FMT.get(f,hex(f))) for n,(f,o) in sorted(s['attrs'].items(),key=lambda x:x[1][1]))
