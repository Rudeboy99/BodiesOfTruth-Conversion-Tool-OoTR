# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Grow a TotK-engine bfres v10 (Switch 2 OoT) and append shapes/materials/vertex buffers.
Bfres(data): opens a CPU gap at the start of the GPU memory pool (end of RLT section 0).
Bfres.append_gpu(blob): appends data at the end of the memory pool, returns its pool-relative offset.
New CPU-side structs go in the gap (section 0 is extended to cover them) and their pointers are
registered in the RLT."""
import struct
from bf import rlt_locs
def u64(d,o): return struct.unpack_from('<Q',d,o)[0]
def cstr(d,o): n=struct.unpack_from('<H',d,o)[0]; return d[o+2:o+2+n].decode()
class Bfres:
    def __init__(self,data,delta=0x2000,gpu=b''):
        self.d=bytearray(data); rlt,self.secs,self.ents,locs=rlt_locs(self.d)
        self.locs=locs; self.new_ptrs=[]
        self.pool=u64(self.d,0x170); self.pool_size=struct.unpack_from('<I',self.d,0x16c)[0]
        self.gpu_off=None
        if gpu:
            g=(len(gpu)+0xfff)&~0xfff; end=self.pool+self.pool_size
            self._insert(end,g,grow_before=True)
            self.d[end:end+len(gpu)]=gpu; self.gpu_off=self.pool_size
            self.pool_size+=g; struct.pack_into('<I',self.d,0x16c,self.pool_size)
        X=self.pool; self._insert(X,delta,grow_before=False)
        self.pool=u64(self.d,0x170); self.X=X; self.cur=X; self.end=X+delta
    def _insert(self,at,delta,grow_before):
        d=self.d; rlt=struct.unpack_from('<I',d,0x18)[0]; nsec=len(self.secs)
        for _,l in self.locs:
            t=u64(d,l)
            if t>=at: struct.pack_into('<Q',d,l,t+delta)
        stro=d.find(b'_STR'); struct.pack_into('<I',d,stro+8,struct.unpack_from('<I',d,stro+8)[0]+delta)
        for i in range(nsec):
            so=rlt+0x10+0x18*i; pos,size=struct.unpack_from('<II',d,so+8)
            # section that ends exactly at `at` grows (gpu append); sections starting at/after `at` move
            if grow_before and pos<at<=pos+size and pos+size==at: struct.pack_into('<I',d,so+0xc,size+delta)
            if pos>=at and not (grow_before and pos+size==at and size>0): struct.pack_into('<I',d,so+8,pos+delta); self.secs[i][1]=pos+delta
        d[at:at]=bytes(delta)
        rlt+=delta; struct.pack_into('<I',d,0x18,rlt); struct.pack_into('<I',d,rlt+4,rlt)
        struct.pack_into('<I',d,0x1c,len(d))
    def alloc(self,n,align=8):
        self.cur=(self.cur+align-1)&~(align-1); o=self.cur; self.cur+=n
        assert self.cur<=self.end,'gap too small'; return o
    def put(self,b,align=8):
        o=self.alloc(len(b),align); self.d[o:o+len(b)]=b; return o
    def string(self,s):
        b=s.encode(); return self.put(struct.pack('<H',len(b))+b+b'\0',2)
    def ptr(self,loc,target,section=0):
        struct.pack_into('<Q',self.d,loc,target); self.new_ptrs.append((section,loc))
    def finish(self):
        d=self.d; rlt=struct.unpack_from('<I',d,0x18)[0]; nsec=len(self.secs)
        struct.pack_into('<I',d,rlt+0x10+0xc,(self.cur+7)&~7)
        per=[[] for _ in range(nsec)]
        for si,off,sc,oc,pc in self.ents: per[si].append((off,sc,oc,pc))
        for si,loc in sorted(self.new_ptrs): per[si].append((loc,1,1,0))
        for si in range(nsec): per[si].sort()
        ent0=rlt+0x10+0x18*nsec; out=bytearray(d[:ent0]); idx=0
        for si in range(nsec):
            struct.pack_into('<II',out,rlt+0x10+0x18*si+0x10,idx,len(per[si]))
            for e in per[si]: out+=struct.pack('<IHBB',*e)
            idx+=len(per[si])
        struct.pack_into('<I',out,0x1c,len(out)); return bytes(out)
