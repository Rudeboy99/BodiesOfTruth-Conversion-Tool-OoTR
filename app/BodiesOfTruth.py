#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""BodiesOfTruth V1.3.3: turn ordinary NPC outfit mods into Lens of Truth outfit swaps.

  python BodiesOfTruth.py <input> [-o OUTPUT_MOD | --name NAME] [--game-files GAME_FILES] [--platform P] [--no-patch] [--dry-run]
  python BodiesOfTruth.py --list   [-o OUTPUT_MOD]          show what the output mod already contains
  python BodiesOfTruth.py --remove MODEL [-o OUTPUT_MOD]    take one model back out (e.g. Npc_Gerudo_GEN_001)

<input> = a mod folder (contains romfs/), a pack of mod folders (each with romfs/), or a romfs folder.
Every model in the input that replaces a vanilla NPC model (romfs/Model/<Project>.<Fmdb>.bfres.zs) becomes that
NPC's 2nd outfit: outside the lens the NPC looks vanilla, inside the Lens of Truth iris it shows the modded outfit.
Output: two mod folders next to each other (default: in <tool folder>/Converted):
  BodiesOfTruth - Custom   every converted model, texture and pack, with one shared RESTBL (romfs only)
  LensPatch                the Lens of Truth code patch for the chosen platform (exefs only)
All swaps go into the ONE model folder: running the tool again adds to it. The lens patch doesn't depend on the
models, so LensPatch only changes when the platform changes. Copy BOTH folders into your game mod directory to play;
disable the original input mods and any other lens/IPS mod.
--platform: emulation (Fritchii: lens code as a separate code module, exefs/subsdk1),
recomp (Hookshot/Longshot) or native (official hardware): lens code in main's code cave. Asked if omitted.
See README.md."""
import sys, os, json, struct, shutil, hashlib, zlib, argparse, time, re, glob, textwrap, atexit
sys.dont_write_bytecode=True            # no __pycache__ (it would embed this PC's folder paths)
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,'lib'))
ROOT=os.path.dirname(HERE)   # the tool's top folder (V1.3.1: program files live in app/, user files at the top)
try:
    import numpy as np
    from zsx import Zs, sarc_files
except ImportError as e:
    sys.exit('Missing Python package (%s). Run the one-time setup first:\n'
             '  Windows: start the tool with BodiesOfTruth_GUI.bat (or command-line\\BodiesOfTruth.bat); it sets them up\n'
             '  Linux:   start the tool with bash BodiesOfTruth_GUI_linux.sh (or bash command-line/BodiesOfTruth_linux.sh)'%e)
import bfres_info, restbl, nup, gamefiles
from retarget_core import u64, skel
from lens_add_shapes import add_shapes
VERSION='BodiesOfTruth V1.3.3'
SETTINGS=os.path.join(ROOT,'settings.json')   # kept in the tool folder (delete it before sharing the tool)
CONVERTED=os.path.join(ROOT,'Converted')
NUP_CACHE=os.path.join(ROOT,'nup_cache')   # game files copied out of a .nup on demand; deleted when the tool exits
def clear_nup_cache():
    nup.close_all()
    if os.path.isdir(NUP_CACHE): shutil.rmtree(NUP_CACHE,ignore_errors=True)
DEFAULT_NAME='BodiesOfTruth - Custom'
LENS_NAME='LensPatch'   # the lens code's own mod folder, next to the model folder (V1.2)
LENS_INFO='LensPatch_info.txt'
RESTBL='System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs'
IPS='E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348.ips'; PCH='lens_outfit_swap_v11.pchtxt'; MODULE='subsdk1'
# lens code patch per platform: patch/codecave = code in main's end-of-code padding (IPS + pchtxt);
# patch/codecave_recomp = build 6 of the same code, written for recompilers that translate the code ahead of time
# (Longshot: BL = C call, RET = C return, x9-x15 not passed); IPS only, since Longshot applies every patch file and a
# second file writing the same bytes only adds a line. patch/codemodule = code in its own module exefs/subsdk1, main
# only gets the 10 hooks (IPS)
PLATFORMS={'emulation':('Emulation (Fritchii)','codemodule',(IPS,MODULE)),
           'recomp':('Recomp (Hookshot/Longshot)','codecave_recomp',(IPS,)),
           'native':('Native (Official Hardware)','codecave',(IPS,PCH))}
LONGSHOT_NOTE=('Longshot (README 2b): Place mod(s) at <build version>\\mods\\<mod name>\\ and rebuild once to install lens swap. '
               'Rebuilds for swapping converted mods is not necessary. Manage converted mods via your preferred mod manager.')
PLATFORM_WARN={'native':'Not yet tested on native hardware'}
if os.name=='nt': os.system('')                 # lets the Windows console show colours (Linux terminals already do)
def clean_path(t):
    """a typed, pasted or dragged-in path -> plain path. Handles "quotes" (Windows), 'quotes' and back\\ slashed
    spaces (Linux terminals), file:// links (some Linux file managers) and ~ (home folder)."""
    t=t.strip()
    if t.startswith('file://'):
        from urllib.parse import unquote; t=unquote(t[7:])
    elif os.name!='nt' and (t[:1] in '"\'' or '\\' in t):   # shell quoting, as a Linux terminal pastes it
        import shlex
        try: t=' '.join(shlex.split(t))
        except ValueError: t=t.strip('"\'')
    else: t=t.strip('"')                       # Windows "Copy as path" quotes
    return os.path.expanduser(t)
def red(t): print('\033[91m%s\033[0m'%t,flush=True)
def ask_platform():
    print('\nWhich platform will you use the mod on?')
    print('  1) Emulation (Fritchii)')
    print('  2) Recomp (Hookshot/Longshot)')
    print('  3) Native (Official Hardware)')
    while True:
        c=input('choose 1, 2 or 3: ').strip()
        if c in ('1','2','3'): return ('emulation','recomp','native')[int(c)-1]
        print('  type 1, 2 or 3, then press Enter')
def warn_platform(platform):
    if platform in PLATFORM_WARN: red(PLATFORM_WARN[platform])
MANIFEST='bodiesoftruth_manifest.json'; REPORT='BodiesOfTruth_report.txt'
a32=lambda n:(n+31)&~31
OUT_LINES=[]
def show(p):
    """path as printed/saved: relative to the tool folder, or just the folder name (no personal paths)"""
    a=os.path.abspath(p); h=os.path.join(ROOT,'')
    return os.path.relpath(a,ROOT) if a.startswith(h) else os.path.basename(a.rstrip('\\/')) or a
def mod_name(rd):
    rd=os.path.abspath(rd); return os.path.basename(os.path.dirname(rd)) if os.path.basename(rd).lower()=='romfs' else os.path.basename(rd)
def find_update(g):
    """game files folder -> the update 131072 romfs, or None (the reason is kept in FIND_MSG).
    Any folder around the game files works (lib/gamefiles.py): the folder holding base\\ and updates\\,
    updates\\, updates\\131072\\, its romfs\\ or exefs\\, a folder inside the romfs, a parent a few levels up,
    or an emulator RomFS dump; the version is checked with exefs/main's build ID.
    Or a .nup game archive (or a folder holding exactly one .nup): its files are copied out on demand into nup_cache."""
    global FIND_MSG
    if not g: return None
    g=os.path.abspath(g)
    p,FIND_MSG=gamefiles.find_game_romfs(g)
    if p:
        print('  game files: %s (%s)'%(gamefiles.describe(p),FIND_MSG),flush=True)
        return os.path.normpath(p)
    n=nup.find_nup(g)
    if n:
        try:
            print('  reading %s ...'%os.path.basename(n),flush=True)
            atexit.register(clear_nup_cache)   # runs after the conversion, on errors and on Ctrl+C too
            return nup.open_romfs(n,NUP_CACHE,want_version=131072,need=('Pack/ZsDic.pack.zs',RESTBL))
        except (nup.NupError,OSError) as e: red('  '+str(e))
    return None
FIND_MSG=''
def resolve_romfs(arg):
    """--game-files, then OOT_GAME_FILES, then settings.json in the tool folder, then ask once and remember"""
    for g in (arg,os.environ.get('OOT_GAME_FILES')):
        if g:
            p=find_update(g)
            if not p: sys.exit('Game files for update 131072 not found in: %s (%s)'%(g,FIND_MSG))
            return p
    try: p=find_update(json.load(open(SETTINGS,encoding='utf-8')).get('game_files'))
    except (OSError,ValueError,AttributeError): p=None
    if p: return p
    print('Where are the game files? Paste the path of the folder that holds your extracted game files(romfs and exefs) or .NUP file(conversion may be slower)')
    print('(the game must be on update 131072)')
    while True:
        g=clean_path(input('game files folder: '))
        p=find_update(g)
        if p: break
        print('  %s (pick the folder holding your extracted game files, any folder around them, or a .NUP file), try again'%FIND_MSG)
    try: s=json.load(open(SETTINGS,encoding='utf-8'))   # keep the GUI's own keys
    except (OSError,ValueError): s={}
    s=s if isinstance(s,dict) else {}; s['game_files']=os.path.abspath(g)
    json.dump(s,open(SETTINGS,'w',encoding='utf-8'),indent=1)
    print('  remembered for next time (delete settings.json in the tool folder to change it)'); return p
def log(*a,color=None):
    s=' '.join(str(x) for x in a); OUT_LINES.append(re.sub(r'\033\[\d+m','',s))   # the report gets plain text
    print('\033[%sm%s\033[0m'%(color,s) if color else s,flush=True)

# ---------------------------------------------------------------- bfres helpers
def raw_shape(d,si):
    """vertex bytes, vertex count, per-LOD index lists (absolute), key-shape count"""
    POOL=u64(d,0x170); o=u64(d,0xf0+0x28)+0x60*si; fv=u64(d,o+0x10)
    if d[fv+0x4d]!=1: raise ValueError('multi-buffer vertex data')
    st=struct.unpack_from('<I',d,u64(d,fv+0x38))[0]; nv=struct.unpack_from('<I',d,fv+0x50)[0]; boff=struct.unpack_from('<I',d,fv+0x48)[0]
    vb=bytes(d[POOL+boff:POOL+boff+nv*st]); m=u64(d,o+0x18); lods=[]
    for k in range(d[o+0x5b]):
        sub,mp,buf,bs,ioff,prim,fmt,cnt,f0,ns_=struct.unpack_from('<4QIIIIIH',d,m+0x38*k)
        a=struct.unpack_from('<%d%s'%(cnt,'H' if fmt==1 else 'I'),d,POOL+ioff); lods.append([x+f0 for x in a])
    return vb,nv,lods,d[o+0x5c]
def mesh_alias(d,si):
    o=u64(d,0xf0+0x28)+0x60*si; m=u64(d,o+0x18); out=[]
    for k in range(d[o+0x5b]):
        e=m+0x38*k; out.append((struct.unpack_from('<I',d,e+0x20)[0],struct.unpack_from('<I',d,e+0x2c)[0],struct.unpack_from('<I',d,e+0x30)[0]))
    return out
IDX_FMT={0x0b:(4,'u1'),0x09:(2,'u1'),0x02:(1,'u1'),0x15:(4,'<u2'),0x12:(2,'<u2'),0x0a:(1,'<u2')}
def remap_indices(vb,shape,mmap):
    """rewrite the bone-matrix index attributes (_i0/_i1) of a vanilla vertex buffer: vanilla matrix -> mod matrix"""
    st=shape['stride']; arr=np.frombuffer(vb,np.uint8).reshape(-1,st).copy()
    for nm,(fmt,off) in shape['attrs'].items():
        if not nm.startswith('_i'): continue
        if (fmt&0xff) not in IDX_FMT: raise ValueError('unknown bone-index format 0x%x'%fmt)
        n,dt=IDX_FMT[fmt&0xff]; sz=n*(2 if dt=='<u2' else 1)
        v=arr[:,off:off+sz].copy().view(dt).astype(np.int64)
        ok=v<len(mmap); w=v.copy(); w[ok]=mmap[v[ok]]
        if (ok&(w<0)).any(): raise ValueError('uses bones missing from the modded skeleton')
        if w.size and w.max()>=(256 if dt=='u1' else 65536): raise ValueError('bone index does not fit the attribute format')
        arr[:,off:off+sz]=w.astype(dt).view(np.uint8).reshape(-1,sz)
    return arr.tobytes()
def skin_slots(d,s):
    """(raw vertex array view, index matrix N x skin, weight matrix N x skin, column info) of a shape; weights unorm8 only"""
    o=u64(d,0xf0+0x28)+0x60*s['index']; fv=u64(d,o+0x10)
    raw=np.frombuffer(d,np.uint8,s['verts']*s['stride'],u64(d,0x170)+struct.unpack_from('<I',d,fv+0x48)[0]).reshape(-1,s['stride'])
    I=[];W=[];cols=[]
    for a in ('0','1'):
        if '_i'+a not in s['attrs']: continue
        f,off=s['attrs']['_i'+a]; n,dt=IDX_FMT[f&0xff]; sz=n*(2 if dt=='<u2' else 1)
        I.append(raw[:,off:off+sz].copy().view(dt).astype(np.int64))
        if '_w'+a in s['attrs']:
            wf,wo=s['attrs']['_w'+a]
            if (wf>>8)!=0x01 or (wf&0xff) not in (0x0b,0x09,0x02): return None
            W.append(raw[:,wo:wo+n].astype(np.int64))
        else:
            wo=None; w=np.zeros((len(raw),n),np.int64); w[:,0]=255; W.append(w)
        cols.append((off,n,dt,wo))
    if not I: return None
    sk=max(s['skin'],1); return raw,np.hstack(I)[:,:sk],np.hstack(W)[:,:sk],cols
def bones_used(d,k,s):
    r=skin_slots(d,s) if s['verts']>1 else None
    if r is None: return set()
    _,I,W,_=r; m=I[W>0]; m=m[m<len(k['m2b'])]
    return {k['names'][k['m2b'][x]] for x in np.unique(m)}
def detach_weights(d,s,mmap):
    """move skin weight from matrix i to mmap[i] (in place in bytearray d), merging slots that end on the same matrix"""
    r=skin_slots(d,s)
    if r is None: return 0
    raw,I,W,cols=r; ok=I<len(mmap); J=I.copy(); J[ok]=mmap[I[ok]]
    hit=((J!=I)&(W>0)).any(1); n=int(hit.sum())
    if not n: return 0
    S=J.shape[1]
    for k_ in range(1,S):
        for j in range(k_):
            same=(J[:,j]==J[:,k_])&(W[:,k_]>0)&(W[:,j]>0)
            W[same,j]+=W[same,k_]; W[same,k_]=0
    o=u64(d,0xf0+0x28)+0x60*s['index']; fv=u64(d,o+0x10); base=u64(d,0x170)+struct.unpack_from('<I',d,fv+0x48)[0]
    full=raw.copy(); c0=0
    for off,n_,dt,wo in cols:
        take=min(n_,max(0,S-c0))
        if take:
            iv=full[:,off:off+n_*(2 if dt=='<u2' else 1)].copy().view(dt); iv[:,:take]=J[:,c0:c0+take].astype(dt)
            full[:,off:off+n_*(2 if dt=='<u2' else 1)]=iv.view(np.uint8)
            if wo is not None: full[:,wo:wo+take]=W[:,c0:c0+take].astype(np.uint8)
        c0+=n_
    d[base:base+full.size]=full.tobytes(); return n
def shape_bounds(d,si,bmap,nlods):
    """FSHP culling data (bbox, per-bone spheres, skin-bone list) of vanilla shape si, bone indices remapped to the mod"""
    o=u64(d,0xf0+0x28)+0x60*si; sc=struct.unpack_from('<H',d,o+0x58)[0]; bone=struct.unpack_from('<H',d,o+0x54)[0]
    sl=u64(d,o+0x20); skin=[int(bmap[x]) for x in (struct.unpack_from('<%dH'%sc,d,sl) if sl and sc else [])]
    if any(x<0 for x in skin) or bmap[bone]<0: raise ValueError('bounds reference bones missing from the mod')
    m=u64(d,o+0x18); nsub=[struct.unpack_from('<H',d,m+0x38*k+0x34)[0] for k in range(d[o+0x5b])]
    bb=u64(d,o+0x38); rr=u64(d,o+0x40)
    bbox=bytes(d[bb:bb+48*nlods]) if all(x==1 for x in nsub) and len(nsub)==nlods else bytes(d[bb:bb+24])*(2*nlods)
    radius=bytes(d[rr:rr+16*max(sc,1)]) if rr else b''
    return dict(skin_list=struct.pack('<%dH'%len(skin),*skin) if skin else b'',skin_count=sc,bbox=bbox,radius=radius,bone=int(bmap[bone]))
def l_name(prefix,mat): return prefix+(mat[3:] if mat.startswith('Mt_') else mat)

# ---------------------------------------------------------------- context
class Ctx:
    def __init__(self,romfs):
        self.romfs=romfs; self.base=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(romfs))),'base','romfs')
        self.zs=Zs(romfs)
        ip=os.path.join(HERE,'index','npc_index.json')
        if not os.path.isfile(ip): sys.exit('app/index/npc_index.json missing: run  python app/index/build_index.py  first')
        self.index=json.load(open(ip,encoding='utf-8')); self.models=self.index['models']
        self.vanilla_rt=bytes(self.zs.read(self.game(RESTBL)))
    def game(self,rel):
        src=nup.source(self.romfs)
        if src: return src.path(rel)   # .nup: update over base, extracted on first use
        for r in (self.romfs,self.base):
            p=os.path.join(r,*rel.split('/'))
            if os.path.isfile(p): return p
        return None
    def read(self,path): return self.zs.read(path) if path.endswith('.zs') else open(path,'rb').read()

# ---------------------------------------------------------------- input discovery
def find_romfs(inp):
    inp=os.path.abspath(inp)
    if os.path.isdir(os.path.join(inp,'Model')) or os.path.basename(inp).lower()=='romfs': return [inp]
    out=[]
    for root,dirs,files in os.walk(inp):
        if os.path.basename(root).lower()=='romfs': out.append(root); dirs[:]=[]
        elif root[len(inp):].count(os.sep)>=4: dirs[:]=[]
    return sorted(out)
def scan_inputs(ctx,inp):
    jobs={}; passthru={}; textures={}   # textures: name -> [(romfs_dir, path)]
    for rd in find_romfs(inp):
        for root,_,files in os.walk(rd):
            for f in sorted(files):
                p=os.path.join(root,f); rel=os.path.relpath(p,rd).replace(os.sep,'/')
                if rel.startswith('System/Resource/') and 'rsizetable' in rel:
                    log('  note: ignoring the input RESTBL %s (the tool writes its own)'%rel); continue
                if rel.startswith('Model/') and rel.endswith('.bfres.zs') and '.anim.' not in rel and '.Skeleton.' not in rel:
                    key=f[:-9]
                    if ctx.game(rel):
                        if key in jobs: log('  ! %s appears in two input mods; using the one from %s'%(key,mod_name(rd)))
                        jobs[key]=dict(key=key,path=p,romfs=rd); continue
                    log('  note: %s is a new model (no vanilla file); copied as-is'%rel)
                if rel.startswith('Tex/') and f.endswith('.bntx.zs'):
                    textures.setdefault(f[:-8],[]).append((rd,p)); continue
                if rel in passthru and open(passthru[rel],'rb').read()!=open(p,'rb').read():
                    log('  ! two different versions of %s in the input; using the one from %s'%(rel,mod_name(rd)))
                passthru[rel]=p
    texonly={r for lst in textures.values() for r,_ in lst}-{j['romfs'] for j in jobs.values()}
    for j in jobs.values(): j['texonly']=texonly
    return jobs,passthru,textures
def pick_texture(lst,romfs):
    for r,p in lst:
        if r==romfs: return p
    return lst[0][1]
def md5f(p): return hashlib.md5(open(p,'rb').read()).hexdigest()

# ---------------------------------------------------------------- one model
def build_model(ctx,job,textures,tex_names):
    key=job['key']; ent=ctx.models.get(key)
    log('\n== %s%s'%(key,'' if ent else '  (not in the NPC index: building from the game file directly)'))
    if ent and ent.get('actors'): log('   actors: '+', '.join(ent['actors']))
    db=ctx.zs.read(ctx.game('Model/%s.bfres.zs'%key)); da=bytearray(ctx.zs.read(job['path']))
    kb,ka=skel(db),skel(da)
    an={n:i for i,n in enumerate(ka['names'])}; bmap=np.array([an.get(n,-1) for n in kb['names']])
    nsB=sum(1 for s in kb['sm'] if s>=0); nsA=sum(1 for s in ka['sm'] if s>=0)
    am={(b,m<nsA):m for m,b in enumerate(ka['m2b'])}
    mmap=np.array([am.get((int(bmap[b]),m<nsB),-1) if bmap[b]>=0 else -1 for m,b in enumerate(kb['m2b'])])
    vset=set(kb['names']); miss=[n for n in kb['names'] if n not in an]; added=[n for n in ka['names'] if n not in vset]
    moved=[kb['names'][i] for i in range(len(kb['names'])) if bmap[i]>=0 and np.abs(kb['W'][i]-ka['W'][bmap[i]]).max()>1e-3]
    log('   skeleton: vanilla %d bones, mod %d%s%s%s'%(len(kb['names']),len(ka['names']),'; added '+', '.join(added) if added else '',
        '; MISSING '+', '.join(miss[:8]) if miss else '','; bind pose moved: '+', '.join(moved[:8]) if moved else ''))
    if moved: log('   ! the mod moved bones: vanilla pieces (outside the lens) may look distorted')
    sb={s['name']:s for s in bfres_info.shapes(db)}; sa={s['name']:s for s in bfres_info.shapes(da)}
    mB={m['name']:m['textures'] for m in bfres_info.materials(db)}; mA={m['name']:m['textures'] for m in bfres_info.materials(da)}
    # re-authored textures that apply: those shipped next to this model, plus texture-only mod folders in the input
    alt_tex={t for t,lst in textures.items() if any(r==job['romfs'] or r in job['texonly'] for r,_ in lst)}
    # ---- compare every mod shape with its vanilla twin (vanilla bone indices remapped to the mod skeleton first)
    status={}; vb_cache={}
    for n,a in sorted(sa.items(),key=lambda x:x[1]['index']):
        b=sb.get(n)
        if b is None: status[n]='new'; continue
        if a['verts']<=1 and b['verts']<=1: status[n]='same'; continue
        try:
            va,_,la,_=raw_shape(da,a['index']); vbb,_,lb,_=raw_shape(db,b['index'])
            vr=remap_indices(vbb,b,mmap); vb_cache[n]=vr
            same=bfres_info.layout_key(a)==bfres_info.layout_key(b) and va==vr and la==lb and a['material']==b['material']
            status[n]='same' if same else ('removed' if a['verts']<=1 else 'changed')
        except ValueError as e: status[n]='changed'; log('   ! %s: %s'%(n,e))
    gone=[n for n in sb if n not in sa]
    affected={sa[n]['material'] for n,s in status.items() if s!='same'}
    affected|={m for m,t in mA.items() if set(t)&alt_tex}
    affected|={m for m in mA if m in mB and mA[m]!=mB[m]}
    affected|={sb[n]['material'] for n in gone if sb[n]['material'] in mA}
    if not affected: log('   nothing differs from vanilla: skipped'); return None
    if not ctx.keep_cloth: detach_lens_outfit(ctx,job,da,db,ka,kb,sa,sb,affected)
    tag=(ent or {}).get('tex_tag') or 'LZZ_'
    def tagged(t):
        new=t.replace('Npc_',tag,1) if 'Npc_' in t else tag+t[4:]
        assert len(new)==len(t); return new
    used=set(mA)|set(sa)
    def uniq(name):
        n,i=name,2
        while n in used: n='%s_%d'%(name,i); i+=1
        used.add(n); return n
    # ---- L1 = the mod's own materials, renamed in place; re-authored textures get tagged copies
    ren={}; retex={}; tex_out={}
    for X in sorted(affected):
        ren[X]=uniq(l_name('L1_',X)); tm={}
        for t in mA[X]:
            if t in alt_tex:
                src=pick_texture(textures[t],job['romfs']); h=md5f(src)
                new=tex_names.get((t,h)) or tagged(t); tex_names[(t,h)]=new; tm[t]=new; tex_out[new]=(t,src)
        if tm: retex[X]=tm
    # ---- L0 = vanilla pieces added back (vanilla mesh copied, or an alias when the mod kept the mesh)
    specs=[]; l0mat={}; lines=[]
    for n,b in sorted(sb.items(),key=lambda x:x[1]['index']):
        X=b['material']
        if X not in affected or b['verts']<=1: continue
        if X not in mA: log('   ! %s: its material %s is not in the mod; vanilla piece dropped'%(n,X)); continue
        if X not in l0mat: l0mat[X]=uniq(l_name('L0_',X))
        sp=dict(tmpl_mat=X,mat=l0mat[X],name=uniq(n.split('__')[0]+'__'+l0mat[X]))
        if X in mB and mA[X]!=mB[X]:
            if len(mA[X])==len(mB[X]): sp['tex_map']={x:y for x,y in zip(mA[X],mB[X]) if x!=y}
            else: log('   ! %s: the mod changed the texture list of %s; vanilla copy keeps the mod list'%(n,X))
        if n in sa and status[n]=='same':
            sp.update(tmpl_shape=n,lods=mesh_alias(da,sa[n]['index'])); kind='alias'
        else:
            lk=bfres_info.layout_key(b)
            tm=n if n in sa and bfres_info.layout_key(sa[n])==lk else next((s for s in sa if bfres_info.layout_key(sa[s])==lk),None)
            if tm is None: log('   ! %s: no shape with the same vertex layout in the mod; vanilla piece dropped'%n); continue
            try:
                _,nv,lods,ks=raw_shape(db,b['index'])
                if ks: raise ValueError('has key shapes')
                if any(l and max(l)-min(l)>=65536 for l in lods): raise ValueError('a LOD spans more than 65535 vertices')
                vr=vb_cache.get(n) or remap_indices(raw_shape(db,b['index'])[0],b,mmap)
                bd=shape_bounds(db,b['index'],bmap,len(lods))
            except ValueError as e: log('   ! %s: %s; vanilla piece dropped'%(n,e)); continue
            sp.update(tmpl_shape=tm,vbytes=vr,nvert=nv,idx_lods=lods,bounds=bd); kind='copy'
        specs.append(sp); lines.append('   L0 %-5s %-46s -> %s'%(kind,n,sp['mat']))
    why={'same':'same mesh','changed':'changed mesh','removed':'emptied by the mod','new':'new in the mod'}
    for n,a in sorted(sa.items(),key=lambda x:x[1]['index']):
        if a['material'] in affected:
            lines.append('   L1 %-52s -> %s (%s%s)'%(n,ren[a['material']],why[status[n]],', retextured' if a['material'] in retex else ''))
    for l in lines: log(l)
    model=add_shapes(da,specs,renames=ren,retex=retex)
    verify(model,da,specs,ren,retex)
    nsh=struct.unpack_from('<H',model,0xf0+0x6a)[0]
    log('   model %d -> %d bytes, %d shapes (%d vanilla pieces added), %d textures renamed'%(len(db),len(model),nsh,len(specs),len(tex_out)))
    return dict(key=key,model=model,db_size=len(db),added=len(specs),tex_out=tex_out,l0=l0mat,l1=ren)
def detach_lens_outfit(ctx,job,da,db,ka,kb,sa,sb,affected):
    """Give the lens outfit its own bone setup: its meshes stop following cloth-sim bones that only exist for vanilla
    pieces the mod removed (e.g. bare thighs weighted to the pants sim). Weight moves to the nearest unsimulated parent.
    A sim bone stays on the lens outfit if the mod added it, or if some piece uses it in both vanilla and the mod."""
    F=job['key'].split('.',1)[1]; rel='Phive/Cloth/%s.Nin_Ounce_NVN2.bphcl'%F
    cp=os.path.join(job['romfs'],*rel.split('/')); cp=cp if os.path.isfile(cp) else ctx.game(rel)
    if not cp: return
    cloth=open(cp,'rb').read()
    sim={n for n in ka['names'] if n.startswith('Ph_') and 'Assist' not in n and n.encode()+b'\0' in cloth}
    vset=set(kb['names']); keep=set()
    for n,b in sb.items():
        a=sa.get(n)
        if a is None or a['verts']<=1 or b['verts']<=1: continue
        keep|=bones_used(db,kb,b)&bones_used(da,ka,a)
    l1=[s for s in sa.values() if s['material'] in affected and s['verts']>1]
    used=set().union(*[bones_used(da,ka,s) for s in l1]) if l1 else set()
    det=sorted(b for b in used&sim if b in vset and b not in keep)
    if not det: return
    mmap=np.arange(len(ka['m2b'])); moves=[]
    for b in det:
        i=ka['names'].index(b); p=ka['par'][i]
        while p>=0 and (ka['names'][p] in det or ka['sm'][p]<0): p=ka['par'][p]
        if p<0 or ka['sm'][i]<0: continue
        mmap[ka['sm'][i]]=ka['sm'][p]; moves.append('%s->%s'%(b,ka['names'][p]))
    tot=sum(detach_weights(da,s,mmap) for s in l1)
    log('   lens outfit detached from %d vanilla cloth bones (%d verts): %s'%(len(moves),tot,', '.join(moves)))
def verify(model,da,specs,ren,retex):
    """re-read the written model: every mod shape keeps its mesh (L1 names), every vanilla piece is present byte-exact"""
    so={s['name']:s for s in bfres_info.shapes(model)}; mo={m['name']:m['textures'] for m in bfres_info.materials(model)}
    for s in bfres_info.shapes(da):
        o=so[s['name']]; assert o['material']==ren.get(s['material'],s['material']) and o['verts']==s['verts'],'mod shape changed: '+s['name']
    for X,tm in retex.items():
        assert mo[ren[X]]==[tm.get(t,t) for t in bfres_info.materials(da)[[m['name'] for m in bfres_info.materials(da)].index(X)]['textures']],'retexture failed: '+X
    for sp in specs:
        o=so[sp['name']]; assert o['material']==sp['mat'],'material of '+sp['name']
        if 'vbytes' in sp:
            vb,nv,lods,_=raw_shape(model,o['index'])
            assert vb==sp['vbytes'] and nv==sp['nvert'] and lods==sp['idx_lods'],'vanilla copy differs: '+sp['name']
        else: assert mesh_alias(model,o['index'])==sp['lods'],'alias differs: '+sp['name']
    assert len(so)==len(bfres_info.shapes(da))+len(specs)
def rename_in_bntx(d,src,new):
    out=d.replace(src.encode()+b'\0',new.encode()+b'\0')
    if out==d:
        s2=re.sub(r'\.\d+$','',src); n2=re.sub(r'\.\d+$','',new); out=d.replace(s2.encode()+b'\0',n2.encode()+b'\0')
    assert len(out)==len(d); return out

# ---------------------------------------------------------------- finalize: anims, RESTBL, IPS, manifest
def anim_plan(ctx,man):
    """anim file -> {Mt_X: L0_X} where every model that animates Mt_X through that file is swapped with an L0_X copy"""
    sw={k:v['l0'] for k,v in man['models'].items()}; users={}; plan={}; skipped=set()
    for mk,m in ctx.models.items():
        for a in m.get('anims',[]):
            for X in a['materials']: users.setdefault((a['file'],X),[]).append(mk)
    for mk,l0 in sw.items():
        for a in ctx.models.get(mk,{}).get('anims',[]):
            for X in a['materials']:
                if X not in l0: continue
                bad=[u for u in users[(a['file'],X)] if sw.get(u,{}).get(X)!=l_name('L0_',X)]
                if not bad and X.startswith('Mt_'): plan.setdefault(a['file'],{})[X]=l_name('L0_',X)
                else: skipped.add('%s: %s%s'%(a['file'][:-14],X,' (also animates unswapped '+', '.join(u.split('.')[1] for u in bad)+')' if bad else ''))
    return plan,sorted(skipped)
def lens_dir(out):
    """the LensPatch mod folder: next to the model folder (out)"""
    return os.path.join(os.path.dirname(os.path.abspath(out)),LENS_NAME)
def write_lens(out,platform):
    """the lens code patch for platform into the LensPatch folder (exefs only); returns that folder"""
    ld=lens_dir(out); _,folder,files=PLATFORMS[platform]
    os.makedirs(os.path.join(ld,'exefs'),exist_ok=True)
    for f in (IPS,PCH,MODULE):                    # drop the other platforms' files (they share the IPS name)
        if f not in files: rmfile(os.path.join(ld,'exefs',f))
    for f in files: shutil.copy(os.path.join(HERE,'patch',folder,f),os.path.join(ld,'exefs',f))
    open(os.path.join(ld,LENS_INFO),'w',encoding='utf-8').write(
        '%s lens code patch (%s)\nplatform: %s\nfiles: %s\n\nThe Lens of Truth code for every converted model mod. Enable it together with the\n'
        'model folder (%s). Only one lens / code-patch mod can be active at a time.\n'
        % (VERSION,time.strftime('%Y-%m-%d %H:%M'),PLATFORMS[platform][0],', '.join('exefs/'+f for f in files),os.path.basename(os.path.abspath(out))))
    return ld
def finalize(ctx,out,man,no_patch,platform=None):
    plan,skipped=anim_plan(ctx,man); old=set(man.get('anims',{})); man['anims']={}
    for f,ren in sorted(plan.items()):
        rel='Model/'+f; dst=os.path.join(out,'romfs',*rel.split('/'))
        x=ctx.zs.read(dst if rel in man['passthrough'] and os.path.isfile(dst) else ctx.game(rel)); y=x
        for a,b in ren.items(): y=y.replace(struct.pack('<H',len(a))+a.encode()+b'\0',struct.pack('<H',len(b))+b.encode()+b'\0')
        if y!=x: ctx.zs.write(os.path.join(out,'romfs',*rel.split('/')),y); man['anims'][rel]=sorted(ren)
    for rel in old-set(man['anims']):
        if rel not in man['passthrough']: rmfile(os.path.join(out,'romfs',*rel.split('/')))
    if man['anims']: log('\nMaterial animations moved to the vanilla (L0) copy: '+'; '.join('%s [%s]'%(r[6:-14],', '.join(v)) for r,v in sorted(man['anims'].items())))
    if skipped: log('Material animations left alone (the lens outfit / these NPCs keep or lose them as noted): '+'; '.join(skipped))
    rt=bytearray(ctx.vanilla_rt)
    for m in man['models'].values():
        for rel,v in m['restbl'].items(): rt=set_rt(rt,rel,v)
    for rel,m in man['passthrough'].items():
        if m.get('restbl') is not None: rt=set_rt(rt,rel,m['restbl'])
    inner={}
    for m in man['passthrough'].values():
        for k,v in m.get('restbl_inner',{}).items(): inner[k]=max(inner.get(k,0),v)
    for k,v in sorted(inner.items()): rt=set_rt(rt,k,v)
    ctx.zs.write(os.path.join(out,'romfs',*RESTBL.split('/')),bytes(rt))
    for f in (IPS,PCH,MODULE): rmfile(os.path.join(out,'exefs',f))   # V1.2: no code in the model folder (V1.1 put it there)
    try: os.rmdir(os.path.join(out,'exefs'))
    except OSError: pass
    if not no_patch:
        platform=platform or man.get('platform') or 'emulation'
        man['lens_folder']=os.path.basename(write_lens(out,platform))
        man['platform']=platform
    json.dump(man,open(os.path.join(out,MANIFEST),'w',encoding='utf-8'),indent=1)
def set_rt(rt,rel,v):
    key=rel[:-3] if rel.endswith('.zs') else rel; h=zlib.crc32(key.encode()); e=restbl.entries(rt)
    if h in e: struct.pack_into('<I',rt,e[h],v); return rt
    return restbl.add_entry(rt,key,v)
def pack_inner_restbl(ctx,modp,vanp):
    """RESTBL entries for files INSIDE a copied actor pack that differ from the game's pack. Without them the game can
    hang while loading a save (no error): new in-pack files need their own entry, and a ControllerSet that changed
    (e.g. gained a PathBoneModifier) needs a bigger one, or the actor's new BoneModifier has no memory budget.
    Sizes: new file 16 KB + 4x size; changed ControllerSet = game value + growth + 4 KB; another changed file that grew
    gets at least what a new file would (16 KB + 4x size); one that did not grow keeps the game value.
    (The Gerudo fighters' BoneModifier grew 732 -> 1912 B and kept the game's 7104: on Longshot the thief that loads
    first crashed the save load (null write at 0x60 on GeneralFormatAsync_); 24032 loads, physics work, 2026-11-20.
    The older rule came from one Fritchii test where 8288 hung.)"""
    fm=sarc_files(ctx.read(modp)); fv=sarc_files(ctx.read(vanp)); out={}; notes=[]
    for n,b in sorted(fm.items()):
        old=fv.get(n)
        if old==b: continue
        cur=rt_value(ctx,n); cs='ControllerSetParam' in n
        if old is None: v=max(cur or 0,16384+4*len(b)); why='new file'
        elif cur is None: v=16384+4*len(b); why='changed, no game entry'
        elif cs: v=cur+max(0,a32(len(b))-a32(len(old)))+4096; why='changed, physics settings +4 KB'
        elif len(b)>len(old): v=max(cur,16384+4*len(b)); why='changed, grown'
        else: v=cur; why='changed, game entry kept'
        out[n]=v; notes.append('inside pack: %s (%s): RESTBL %d'%(n.split('/')[-1],why,v))
    return out,notes
def rt_value(ctx,rel):
    key=rel[:-3] if rel.endswith('.zs') else rel; e=restbl.entries(ctx.vanilla_rt); h=zlib.crc32(key.encode())
    return struct.unpack_from('<I',ctx.vanilla_rt,e[h])[0] if h in e else None
def rmfile(p):
    try: os.remove(p)
    except OSError: pass
def load_manifest(out):
    p=os.path.join(out,MANIFEST)
    if os.path.isfile(p): return json.load(open(p,encoding='utf-8'))
    return {'tool':VERSION,'models':{},'passthrough':{},'anims':{}}

# ---------------------------------------------------------------- main
def run(args):
    ctx=Ctx(args.romfs); ctx.keep_cloth=args.keep_cloth_weights; out=os.path.abspath(args.output); man=load_manifest(out)
    if args.list:
        print('Output: %s'%show(out)); ld=lens_dir(out)
        print('Lens patch: %s%s'%(show(ld),' (%s)'%PLATFORMS[man['platform']][0] if man.get('platform') in PLATFORMS and os.path.isdir(ld) else ' (not written yet)'))
        for k,m in sorted(man['models'].items()): print('  %-58s from %s (%s)'%(k,m['mod'],m['built']))
        for r in sorted(man['passthrough']): print('  file  %s'%r)
        return
    if args.remove:
        hit=[k for k in man['models'] if args.remove in (k,)+tuple(k.split('.'))]
        if not hit: sys.exit('not in the output mod: '+args.remove)
        for k in hit:
            gone=man['models'].pop(k); rd=gone.get('romfs')
            still={rel for m in man['models'].values() for rel in m['files']}
            for rel in gone['files']:
                if rel not in still: rmfile(os.path.join(out,'romfs',*rel.split('/')))
            if rd and not any(m.get('romfs')==rd for m in man['models'].values()):   # extra files that came with that mod
                for rel in [r for r,m in man['passthrough'].items() if m.get('romfs')==rd]:
                    rmfile(os.path.join(out,'romfs',*rel.split('/'))); del man['passthrough'][rel]; log('removed '+rel)
            log('removed '+k)
        finalize(ctx,out,man,args.no_patch,args.platform); return
    if not args.input: sys.exit(__doc__)
    log('%s  %s\ninput:  %s\noutput: %s\nlens:   %s'%(VERSION,time.strftime('%Y-%m-%d %H:%M'),show(args.input),show(out),show(lens_dir(out)) if not args.no_patch else '(not written: --no-patch)'))
    if not args.no_patch: log('platform: %s (lens code %s)'%(PLATFORMS[args.platform][0],'in its own code module, %s/exefs/%s'%(LENS_NAME,MODULE) if args.platform=='emulation' else 'in the code cave, %s/exefs'%LENS_NAME))
    jobs,passthru,textures=scan_inputs(ctx,args.input)
    if not jobs: sys.exit('No vanilla model replacements (romfs/Model/<Project>.<Fmdb>.bfres.zs) found in '+args.input)
    log('models: '+', '.join(sorted(jobs)))
    tex_names={}
    for m in man['models'].values():          # reuse renamed copies of identical textures already in the output
        for new,(t,h) in m.get('tex_src',{}).items(): tex_names[(t,h)]=new
    results=[]
    for key in sorted(jobs):
        try: r=build_model(ctx,jobs[key],textures,tex_names)
        except Exception as e: log('   !! FAILED: %s: %s'%(type(e).__name__,e)); continue
        if r: results.append((jobs[key],r))
    used_tex={t for _,r in results for (t,_) in r['tex_out'].values()}
    for t in sorted(set(textures)-used_tex): log('  note: input texture %s is not used by any swapped material: not shipped (it would change every NPC using it)'%t)
    if args.dry_run: log('\ndry run: nothing written'); return
    if not results: sys.exit('nothing to write')
    keep_tex={rel for k,m in man['models'].items() if k not in {r['key'] for _,r in results} for rel in m['files']}
    for job,r in results:
        k=r['key']
        if k in man['models']:
            for rel in man['models'][k]['files']:
                if rel not in keep_tex: rmfile(os.path.join(out,'romfs',*rel.split('/')))
        files=[]; rv={}; tsrc={}
        rel='Model/%s.bfres.zs'%k; ctx.zs.write(os.path.join(out,'romfs','Model',k+'.bfres.zs'),r['model']); files.append(rel)
        rv[rel]=rt_value(ctx,rel)+a32(len(r['model']))-a32(r['db_size'])+restbl.PER_ADDED_SHAPE*r['added']
        for new,(t,src) in sorted(r['tex_out'].items()):
            rel='Tex/%s.bntx.zs'%new; dst=os.path.join(out,'romfs','Tex',new+'.bntx.zs')
            nd=rename_in_bntx(ctx.zs.read(src),t,new); ctx.zs.write(dst,nd)
            files.append(rel); rv[rel]=len(nd)+280; tsrc[new]=(t,md5f(src))
        man['models'][k]=dict(mod=mod_name(job['romfs']),romfs=mod_name(job['romfs']),built=time.strftime('%Y-%m-%d %H:%M'),files=files,restbl=rv,l0=r['l0'],l1=r['l1'],tex_src=tsrc)
    pt_romfs={rel:next((mod_name(r) for r in find_romfs(args.input) if os.path.abspath(p).startswith(os.path.join(r,''))),'') for rel,p in passthru.items()}
    for rel,p in sorted(passthru.items()):
        dst=os.path.join(out,'romfs',*rel.split('/')); os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.copy(p,dst)
        v=rt_value(ctx,rel); val=None
        if v is not None:
            g=ctx.game(rel); val=v+max(0,a32(len(ctx.read(p)))-a32(len(ctx.read(g)) if g else 0))
        elif rel.startswith('Tex/'): val=len(ctx.read(p))+280
        man['passthrough'][rel]=dict(mod=pt_romfs[rel],romfs=pt_romfs[rel],restbl=val)
        log('  copied as-is: %s%s'%(rel,'' if val is None else ' (RESTBL %d)'%val))
        g=ctx.game(rel)
        if rel.startswith('Pack/') and rel.endswith('.pack.zs') and g:
            inner,notes=pack_inner_restbl(ctx,p,g)
            if inner: man['passthrough'][rel]['restbl_inner']=inner
            for n_ in notes: log('      '+n_)
    finalize(ctx,out,man,args.no_patch,args.platform)
    log('\nDone: %d model(s) written to %s'%(len(results),show(out)),color=92)
    if not args.no_patch: log('Lens code patch: %s'%show(lens_dir(out)),color=92)
    R,X='\033[91m','\033[0m'                  # red highlight inside a line
    if args.platform=='recomp' and not args.no_patch: log(LONGSHOT_NOTE,color=91)   # (replaces the To play line on Longshot)
    else: log('To play (README 2a): Copy BOTH folders (%s and %s) into your game mod directory. '%(os.path.basename(out),LENS_NAME)+R+'Enable only those two (disable the original outfit mods and every other lens or code-patch mod)'+X+', then look through the Lens of Truth.')
    if args.platform=='emulation' and not args.no_patch:
        log('Emulation build: '+R+'The lens code is in %s/exefs/%s. Keep that file next to the IPS, and don\'t combine it with another mod that adds its own %s'%(LENS_NAME,MODULE,MODULE)+X+'.')
    open(os.path.join(out,REPORT),'w',encoding='utf-8').write('\n'.join(OUT_LINES)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=VERSION,usage=__doc__)
    ap.add_argument('input',nargs='?'); ap.add_argument('-o','--output',default=None)
    ap.add_argument('--name',default=None,help='model mod folder name inside the Converted folder (the lens patch goes next to it, in %s)'%LENS_NAME)
    ap.add_argument('--game-files','--romfs',dest='romfs',default=None,help='game files folder holding base and updates, or a .nup game file (asked once and remembered if omitted)')
    ap.add_argument('--no-patch',action='store_true'); ap.add_argument('--dry-run',action='store_true')
    ap.add_argument('--platform',choices=sorted(PLATFORMS),default=None,help='emulation, recomp or native (asked if omitted)')
    ap.add_argument('--keep-cloth-weights',action='store_true',help="don't detach the lens outfit from vanilla cloth-sim bones")
    ap.add_argument('--list',action='store_true'); ap.add_argument('--remove',default=None)
    a=ap.parse_args()
    if not a.output: a.output=os.path.join(CONVERTED,a.name or DEFAULT_NAME)
    a.romfs=resolve_romfs(a.romfs)   # first run (no settings.json): asks for the game files before anything else
    if not a.platform and not a.list: a.platform=ask_platform()
    if a.platform: warn_platform(a.platform)
    if not (a.input or a.list or a.remove):
        print()
        for line in textwrap.wrap('Be sure to convert all intended conversion mods together. This tool generates a unified RESTBL and code patch to avoid conflicts. You may merge this mod with others after your unified folder is generated (Untested).',74):
            red(line)
        print('-'*74)
        print('Which mod do you want to convert? Drag its folder into this window (or paste the path), then press Enter.')
        print('Press Enter on its own to just show what the converted mod already contains.')
        while True:
            p=clean_path(input('mod folder: '))
            if not p: a.list=True; break
            if os.path.isdir(p): a.input=p; break
            print('  folder not found, try again')
    run(a)
