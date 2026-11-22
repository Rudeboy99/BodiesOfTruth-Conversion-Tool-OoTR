# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Skeleton + source-shape readers (skel, read_shape) and the 10_10_10_2 codec, shared by retarget_any.py.
retarget() below is the original Malon-only version (stride 36, 5 influences), kept for reference."""
import struct, numpy as np
from bfres_add import u64
def cs(d,o): n=struct.unpack_from('<H',d,o)[0]; return d[o+2:o+2+n].decode('latin1')
def euler(x,y,z):
    cx,sx,cy,sy,cz,sz=np.cos(x),np.sin(x),np.cos(y),np.sin(y),np.cos(z),np.sin(z)
    return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])@np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]])@np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
def quat(x,y,z,w):
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def skel(d):
    f=u64(d,0xf0+0x18); ba=u64(d,f+0x10); mtb=u64(d,f+0x18); nb,ns,nr=struct.unpack_from('<HHH',d,f+0x38)
    W=[];names=[];par=[];sm=[]
    for i in range(nb):
        o=ba+0x58*i; idx,p,s,r,bb,uc,fl=struct.unpack_from('<HhhhHHI',d,o+0x20)
        S=np.array(struct.unpack_from('<3f',d,o+0x30)); q=struct.unpack_from('<4f',d,o+0x3c); T=np.array(struct.unpack_from('<3f',d,o+0x4c))
        M=np.eye(4); M[:3,:3]=(euler(*q[:3]) if fl&0x1000 else quat(*q))@np.diag(S); M[:3,3]=T
        W.append(M if p<0 else W[p]@M); names.append(cs(d,u64(d,o))); par.append(p); sm.append(s)
    m2b=struct.unpack_from('<%dH'%(ns+nr),d,mtb)
    return dict(W=W,names=names,par=par,sm=sm,m2b=m2b)
def dec1010(v):
    q=np.stack([(v>>s)&0x3ff for s in (0,10,20)],-1).astype(np.int64); q=np.where(q>511,q-1024,q); return q/511.0,(v>>30)&3
def enc1010(n,w):
    q=np.round(np.clip(n,-1,1)*511).astype(np.int64)&0x3ff
    return (q[:,0]|(q[:,1]<<10)|(q[:,2]<<20)|(w.astype(np.int64)<<30)).astype('<u4')
def read_shape(d,si):
    POOL=u64(d,0x170); shp=u64(d,0xf0+0x28); o=shp+0x60*si; fv=u64(d,o+0x10)
    ap=u64(d,fv+8); na=d[fv+0x4c]; at={}
    for k in range(na):
        b=d[ap+16*k+8:ap+16*k+10]; at[cs(d,u64(d,ap+16*k))]=((b[0]<<8)|b[1],struct.unpack_from('<H',d,ap+16*k+12)[0])
    st=struct.unpack_from('<I',d,u64(d,fv+0x38))[0]; nv=struct.unpack_from('<I',d,fv+0x50)[0]; boff=struct.unpack_from('<I',d,fv+0x48)[0]
    raw=np.frombuffer(d,dtype=np.uint8,count=nv*st,offset=POOL+boff).reshape(nv,st)
    P=raw[:,0:12].copy().view('<f4').astype(float)
    N,nw=dec1010(raw[:,at['_n0'][1]:at['_n0'][1]+4].copy().view('<u4')[:,0])
    T,tw=dec1010(raw[:,at['_t0'][1]:at['_t0'][1]+4].copy().view('<u4')[:,0])
    f,off=at['_u0']; u=raw[:,off:off+4].copy()
    UV=u.view('<f2').astype(float) if f==0x0512 else (u.view('<u2')/65535.0 if f==0x0112 else u.view('<i2')/32767.0)
    idx=[];wt=[]
    for a in ('0','1'):
        if '_i'+a in at:
            fi,oi=at['_i'+a]; fw,ow=at['_w'+a]; c=4 if (fi&0xff)==0x0b else (2 if (fi&0xff)==0x09 else 1)
            idx.append(raw[:,oi:oi+c].astype(int)); wt.append(raw[:,ow:ow+c].astype(float))
    sk=d[o+0x5a]; I=np.concatenate(idx,1)[:,:sk]; Wt=np.concatenate(wt,1)[:,:sk]   # slots beyond the skin count are filler
    m=u64(d,o+0x18); lods=[]
    for k in range(d[o+0x5b]):
        sub,mp,buf,bs,ioff,prim,fmt,cnt,f0,nsub=struct.unpack_from('<4QIIIIIH',d,m+0x38*k)
        lods.append((np.frombuffer(d,dtype='<u2' if fmt==1 else '<u4',count=cnt,offset=POOL+ioff).astype(int)+f0))
    return dict(name=cs(d,u64(d,o+8)),P=P,N=N,T=T,tw=tw,UV=UV,I=I,Wt=Wt,lods=lods,skin=d[o+0x5a])
def retarget(src,dst,sh,max_inf=5):
    S,D=src,dst; dn={n:i for i,n in enumerate(D['names'])}
    def map_bone(b):
        x=b
        while x>=0:
            n=S['names'][x]
            if n in dn and D['sm'][dn[n]]>=0: return x,dn[n]
            x=S['par'][x]
        raise ValueError('no mapped ancestor for '+S['names'][b])
    cache={}
    def mat_for(sb):
        if sb not in cache:
            sx,db=map_bone(sb); cache[sb]=(D['W'][db]@np.linalg.inv(S['W'][sx]),D['sm'][db])
        return cache[sb]
    nv=len(sh['P']); outP=np.zeros((nv,3)); outN=np.zeros((nv,3)); outT=np.zeros((nv,3))
    oi=np.zeros((nv,max_inf),int); ow=np.zeros((nv,max_inf),int)
    for v in range(nv):
        acc=np.zeros((4,4)); infl={}
        tot=sh['Wt'][v].sum() or 1
        for mi,w in zip(sh['I'][v],sh['Wt'][v]):
            if w<=0: continue
            M,dm=mat_for(S['m2b'][mi]); acc+=M*(w/tot); infl[dm]=infl.get(dm,0)+w
        outP[v]=(acc@np.append(sh['P'][v],1))[:3]; L=acc[:3,:3]
        n=L@sh['N'][v]; t=L@sh['T'][v]; outN[v]=n/(np.linalg.norm(n)+1e-9); outT[v]=t/(np.linalg.norm(t)+1e-9)
        top=sorted(infl.items(),key=lambda x:-x[1])[:max_inf]; s=sum(w for _,w in top)
        ws=[int(round(255*w/s)) for _,w in top]; ws[0]+=255-sum(ws)
        for k,((m,_),w) in enumerate(zip(top,ws)): oi[v,k]=m; ow[v,k]=w
    vb=bytearray()
    nn=enc1010(outN,np.ones(nv,int)); tt=enc1010(outT,sh['tw'])
    uv=sh['UV'].astype('<f2')
    for v in range(nv):
        vb+=struct.pack('<3fII',*outP[v],nn[v],tt[v])+uv[v].tobytes()+bytes(oi[v,:4].astype(np.uint8))+bytes(ow[v,:4].astype(np.uint8))+bytes([oi[v,4],ow[v,4],0,0])
    return bytes(vb),outP
