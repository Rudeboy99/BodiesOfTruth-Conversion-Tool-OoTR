# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""BodiesOfTruth copy of NPC Outfit Import/lib/add_shapes.py, extended with:
  retex={material: {old_tex: new_tex}}  -> give an EXISTING material its own texture-name array
  spec["bounds"]=dict(skin_list=bytes, skin_count=n, bbox=bytes, radius=bytes, bone=i) -> FSHP culling data of the new shape

Add several shapes to a bfres v10 model in one pass, keeping vanilla's 1:1 rule:
shape i uses vertex buffer i (the engine sizes per-shape runtime data by the vertex-buffer count).
spec = dict(tmpl_shape, tmpl_mat, name, mat,
            lods=[(pool_ioff,count,first_vertex),...]   -> reuse the template's vertex data (alias FVTX)
         or vbytes=..., nvert=..., idx_lods=[[...],...]  -> new vertex/index data (must match the template layout))"""
import struct
from bfres_add import Bfres, u64, cstr
from sdict import build as build_dict
import bf
FMDL=0xf0
def add_shapes(data, specs, renames=None, retex=None):
    blob=bytearray(); plan=[]
    for s in specs:
        if 'vbytes' in s:
            io=[]
            for idx in s['idx_lods']:
                io.append(len(blob)); blob+=struct.pack('<%dH'%len(idx),*idx); blob+=bytes((-len(blob))%0x100)
            vo=len(blob); blob+=s['vbytes']; blob+=bytes((-len(blob))%0x100); plan.append((io,vo))
        else: plan.append(None)
    b=Bfres(data,delta=0x2000*(2+len(specs)),gpu=bytes(blob)); d=b.d; base=b.gpu_off or 0
    reloc={l:s for s,l in bf.rlt_locs(bytes(d))[3]}
    def cp(src,size,dst):
        d[dst:dst+size]=d[src:src+size]
        for l in range(src,src+size,8):
            if l in reloc: b.new_ptrs.append((reloc[l],dst+(l-src)))
    vtx,shp,sdic,mat,mdic=(u64(d,FMDL+f) for f in (0x20,0x28,0x30,0x38,0x40))
    nv,ns,nm=struct.unpack_from('<HHH',d,FMDL+0x68)
    assert nv==ns,'model must start with shape i <-> vertex buffer i (got %d buffers, %d shapes)'%(nv,ns)
    snames=[cstr(d,u64(d,shp+0x60*i+8)) for i in range(ns)]; mnames=[cstr(d,u64(d,mat+0xb0*i+8)) for i in range(nm)]
    k=len(specs); umats=list(dict.fromkeys(s['mat'] for s in specs)); km=len(umats); newmat={}   # specs with the same 'mat' share one new material
    nvtx=b.alloc(0x58*(nv+k)); nshp=b.alloc(0x60*(ns+k)); nmat=b.alloc(0xb0*(nm+km))
    for i in range(nv): cp(vtx+0x58*i,0x58,nvtx+0x58*i)
    for i in range(nm): cp(mat+0xb0*i,0xb0,nmat+0xb0*i)
    orig_mnames=list(mnames)
    for old,new in (renames or {}).items():
        i=mnames.index(old); struct.pack_into('<Q',d,nmat+0xb0*i+8,b.string(new)); mnames[i]=new
    for mn,tm in (retex or {}).items():
        fm=nmat+0xb0*orig_mnames.index(mn); ntex=d[fm+0xa3]; tp=u64(d,fm+0x20); arr=b.alloc(8*ntex)
        for t in range(ntex):
            old=cstr(d,u64(d,tp+8*t)); new=tm.get(old)
            b.ptr(arr+8*t, b.string(new) if new else u64(d,tp+8*t))
        struct.pack_into('<Q',d,fm+0x20,arr)
    targets=sorted(set(u64(d,l) for l in reloc))
    def region(p):   # size of the block starting at p = distance to the next pointer target
        import bisect; j=bisect.bisect_right(targets,p); return (targets[j] if j<len(targets) else p+0x40)-p
    for i in range(ns):
        o=nshp+0x60*i; cp(shp+0x60*i,0x60,o)
        struct.pack_into('<Q',d,o+0x10,nvtx+0x58*struct.unpack_from('<H',d,o+0x56)[0])
    for j,s in enumerate(specs):
        si=snames.index(s['tmpl_shape']); mi=orig_mnames.index(s['tmpl_mat']); tsh=shp+0x60*si
        tvb=u64(d,tsh+0x10); vi=nv+j; fv=nvtx+0x58*vi
        cp(tvb,0x58,fv)
        stride=struct.unpack_from('<I',d,u64(d,tvb+0x38))[0]
        struct.pack_into('<Q',d,fv+0x20,b.put(bytes(0x48))); struct.pack_into('<Q',d,fv+0x28,b.put(bytes(8)))
        if s.get('attr_fmt'):
            ap=u64(d,tvb+8); na=d[tvb+0x4c]; nap=b.alloc(0x10*na); cp(ap,0x10*na,nap)
            for a in range(na):
                nm_=cstr(d,u64(d,nap+0x10*a))
                if nm_ in s['attr_fmt']: f=s['attr_fmt'][nm_]; d[nap+0x10*a+8]=f>>8; d[nap+0x10*a+9]=f&0xff
            struct.pack_into('<Q',d,fv+8,nap)
        if plan[j]:
            io,vo=plan[j]; nvert=s['nvert']; assert len(s['vbytes'])==stride*nvert
            struct.pack_into('<I',d,fv+0x48,base+vo); struct.pack_into('<I',d,fv+0x50,nvert)
            size=len(s['vbytes']); lods=[(base+io[x],len(s['idx_lods'][x]),0) for x in range(len(io))]
        else:
            size=struct.unpack_from('<I',d,u64(d,tvb+0x30))[0]; lods=s['lods']
        struct.pack_into('<Q',d,fv+0x30,b.put(struct.pack('<IIII',size,0,0,0)))
        struct.pack_into('<Q',d,fv+0x38,b.put(struct.pack('<IIII',stride,0,0,0)))
        struct.pack_into('<H',d,fv+0x4e,vi)
        if s['mat'] in newmat: mj=newmat[s['mat']]
        else:
            mj=newmat[s['mat']]=len(newmat)
            fm=nmat+0xb0*(nm+mj); cp(mat+0xb0*mi,0xb0,fm)
            struct.pack_into('<Q',d,fm+8,b.string(s['mat'])); struct.pack_into('<H',d,fm+0xa0,nm+mj)
            if s.get('tex_map'):
                ntex=d[fm+0xa3]; tp=u64(d,fm+0x20); arr=b.alloc(8*ntex)
                for t in range(ntex):
                    old=cstr(d,u64(d,tp+8*t)); new=s['tex_map'].get(old)
                    b.ptr(arr+8*t, b.string(new) if new else u64(d,tp+8*t))
                struct.pack_into('<Q',d,fm+0x20,arr)
            for f in (0x18,0x28,0x58,0x80):           # per-material runtime areas (zero in the file): every copy gets its own
                p=u64(d,fm+f)
                if p:
                    n=region(p)
                    if not any(d[p:p+n]): struct.pack_into('<Q',d,fm+f,b.put(bytes(n)))
        tm=u64(d,tsh+0x18); marr=b.alloc(0x38*len(lods))
        for x,(lo,lc,lf) in enumerate(lods):
            e=marr+0x38*x; cp(tm+0x38*min(x,d[tsh+0x5b]-1),0x38,e)
            struct.pack_into('<Q',d,e,b.put(struct.pack('<II',0,lc)))
            struct.pack_into('<Q',d,e+0x10,b.put(bytes(0x48)))
            struct.pack_into('<Q',d,e+0x18,b.put(struct.pack('<IIII',2*lc,0,0,0)))
            struct.pack_into('<III',d,e+0x20,lo,struct.unpack_from('<I',d,e+0x24)[0],1); struct.pack_into('<II',d,e+0x2c,lc,lf)
        fs=nshp+0x60*(ns+j); cp(tsh,0x60,fs)
        struct.pack_into('<Q',d,fs+8,b.string(s['name'])); struct.pack_into('<Q',d,fs+0x10,fv); struct.pack_into('<Q',d,fs+0x18,marr)
        struct.pack_into('<HH',d,fs+0x50,ns+j,nm+newmat[s['mat']]); struct.pack_into('<H',d,fs+0x56,vi); d[fs+0x5b]=len(lods)
        bd=s.get('bounds')
        if bd:
            for f,blob in ((0x20,bd['skin_list']),(0x38,bd['bbox']),(0x40,bd['radius'])):
                if not blob: continue
                t=b.put(blob,8)
                if u64(d,tsh+f): struct.pack_into('<Q',d,fs+f,t)     # location already registered by cp()
                else: b.ptr(fs+f,t)
            struct.pack_into('<H',d,fs+0x54,bd['bone']); struct.pack_into('<H',d,fs+0x58,bd['skin_count'])
    root=u64(d,sdic+16)
    def wdict(names,ptrs):
        nodes=build_dict(names); o=b.alloc(8+16*len(nodes)); struct.pack_into('<II',d,o,0,len(names))
        for i,(ref,L,R,_) in enumerate(nodes):
            struct.pack_into('<IHH',d,o+8+16*i,ref,L,R); b.ptr(o+8+16*i+8,root if i==0 else ptrs[i-1])
        return o
    nsd=wdict(snames+[s['name'] for s in specs],[u64(d,nshp+0x60*i+8) for i in range(ns+k)])
    nmd=wdict(mnames+umats,[u64(d,nmat+0xb0*i+8) for i in range(nm+km)])
    for f,v in ((0x20,nvtx),(0x28,nshp),(0x30,nsd),(0x38,nmat),(0x40,nmd)): struct.pack_into('<Q',d,FMDL+f,v)
    struct.pack_into('<HHH',d,FMDL+0x68,nv+k,ns+k,nm+km)
    if specs or retex: print('    added %d shapes; gap 0x%x/0x%x, gpu 0x%x'%(k,b.cur-b.X,b.end-b.X,len(blob)))
    return b.finish()
