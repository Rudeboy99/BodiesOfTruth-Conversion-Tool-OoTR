#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Build the NPC index used by BodiesOfTruth.py (index/npc_index.json + index/npc_index.md).
  python index/build_index.py [game files] (default: OOT_GAME_FILES, else the game files folder remembered by BodiesOfTruth.py)
Re-run only after a game update. Needs numpy + zstandard (same as the tool)."""
import sys, os, re, glob, json, struct, hashlib, time
sys.dont_write_bytecode=True
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,'..','lib'))
from zsx import Zs, sarc_files
import bfres_info
from retarget_core import skel
def _update(g):   # game files folder (base + updates) or an update romfs -> update romfs
    if not g: return None
    for c in sorted(glob.glob(os.path.join(g,'updates','*','romfs')))+[g,os.path.join(g,'romfs')]:
        if os.path.isfile(os.path.join(c,'Pack','ZsDic.pack.zs')) and glob.glob(os.path.join(c,'System','Resource','*.Product.111.*')): return c
    return None
def _remembered():
    try: return json.load(open(os.path.join(HERE,'..','settings.json'),encoding='utf-8')).get('game_files')
    except (OSError,ValueError,AttributeError): return None
ROMFS=_update(sys.argv[1] if len(sys.argv)>1 else (os.environ.get('OOT_GAME_FILES') or _remembered()))
if not ROMFS: sys.exit('usage: python index/build_index.py <game files folder holding base and updates>')
zs=Zs(ROMFS); t0=time.time()
STR=lambda b:[x.decode() for x in re.findall(rb'[\x20-\x7e]{4,}',b)]
# ---- actors -> model file key (Project.Fmdb); follow ModelInfo $parent, then the actor's $parent chain
mdir=os.path.join(ROMFS,'Model'); allm=sorted(os.listdir(mdir))
KEYS=[f[:-9] for f in allm if f.endswith('.bfres.zs') and '.anim.' not in f and '.Skeleton.' not in f]
PROJ={}
for k in KEYS: PROJ.setdefault(k.split('.')[0],[]).append(k)
def model_of(fs,mi):
    seen=set()
    while mi in fs and mi not in seen:
        seen.add(mi); ss=STR(fs[mi]); S=set(ss)
        for P in [x for x in ss if x in PROJ]:
            ks=PROJ[P]; hit=[k for k in ks if k.split('.',1)[1] in S and k.split('.',1)[1]!=P]
            return hit[0] if hit else ('%s.%s'%(P,P) if '%s.%s'%(P,P) in ks else ks[0])
        par=[x for x in ss if x.startswith('Work/Component/ModelInfo/')]
        mi='Component/ModelInfo/'+par[0].split('/')[-1].replace('.gyml','.bgyml') if par else None
    return ''
actors={}
for p in sorted(glob.glob(os.path.join(ROMFS,'Pack','Actor','Npc_*.pack.zs'))):
    name=os.path.basename(p)[:-8]; fs=sarc_files(zs.read(p)); cur='Actor/%s.engine__actor__ActorParam.bgyml'%name; model=''
    while cur in fs and not model:
        ss=STR(fs[cur]); mi=[x[1:] for x in ss if x.startswith('?Component/ModelInfo/')]
        if mi: model=model_of(fs,mi[0])
        par=[x for x in ss if x.startswith('Work/Actor/')]
        cur='Actor/'+par[0].split('/')[-1].replace('.gyml','.bgyml') if par else None
    actors[name]=model
users={}
for a,m in actors.items(): users.setdefault(m,[]).append(a)
print('actors',len(actors),'%.0fs'%(time.time()-t0),flush=True)
# ---- files
models=[f[:-9] for f in allm if f.endswith('.bfres.zs') and '.anim.' not in f and '.Skeleton.' not in f]
anims=[f for f in allm if f.endswith('.anim.bfres.zs')]
skels=[f for f in allm if f.endswith('.Skeleton.bfres.zs')]
want=[k for k in models if k.startswith('Npc_') or k in users or k.startswith('Player_')]
texdir=os.path.join(ROMFS,'Tex'); texfiles={f[:-8] for f in os.listdir(texdir) if f.endswith('.bntx.zs')}
clothdir=os.path.join(ROMFS,'Phive','Cloth'); cloth=set(os.listdir(clothdir)) if os.path.isdir(clothdir) else set()
def family(p):
    s=p.split('_'); return '_'.join(s[:3]) if len(s)>3 else p
B36='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
out={'_about':'BodiesOfTruth NPC index. Built from game update 131072 on %s. One entry per model file (Project.Fmdb).'%time.strftime('%Y-%m-%d'),
     'game':{'title_id':'0400486024DEC000','update':'131072','build_id':'E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348'},
     'models':{},'textures':{},'actors':actors}
tex_users={}
for n,key in enumerate(want):
    P,F=key.split('.',1); path=os.path.join(mdir,key+'.bfres.zs')
    try: d=zs.read(path); sh=bfres_info.shapes(d); mats=bfres_info.materials(d); k=skel(d)
    except Exception as e: out['models'][key]={'project':P,'fmdb':F,'error':str(e)}; continue
    nb=len(k['names']); ns=sum(1 for s in k['sm'] if s>=0); nr=len(k['m2b'])-ns
    fam=family(P); spec=[a for a in anims if P in a]
    others=[q for q in PROJ if q!=P and q.startswith(fam)]
    fama=[a for a in anims if fam in a and a not in spec and (a.startswith('CmnTex_') or not any(q in a for q in others))]   # skip anims named after a sibling model
    an=[]
    for a in spec+fama:
        try: ad=zs.read(os.path.join(mdir,a))
        except Exception: continue
        refs=[m['name'] for m in mats if struct.pack('<H',len(m['name']))+m['name'].encode()+b'\0' in ad]
        if refs or a in spec: an.append({'file':a,'model_specific':a in spec,'materials':refs})
    for m in mats:
        for t in m['textures']: tex_users.setdefault(t,set()).add(key)
    out['models'][key]={'project':P,'fmdb':F,'file':'Model/%s.bfres.zs'%key,'size':len(d),'tex_tag':'L%s%s_'%(B36[n//36],B36[n%36]),
        'actors':sorted(users.get(key,[])),'bones':{'total':nb,'smooth':ns,'rigid':nr,'names_md5':hashlib.md5('\n'.join(k['names']).encode()).hexdigest()},
        'cloth':('Phive/Cloth/%s.Nin_Ounce_NVN2.bphcl'%F) if '%s.Nin_Ounce_NVN2.bphcl'%F in cloth else None,
        'anim_skeletons':[s for s in skels if fam in s],
        'materials':{m['name']:m['textures'] for m in mats},
        'shapes':[{'name':s['name'],'material':s['material'],'skin':s['skin'],'lods':s['lods'],'verts':s['verts'],'layout':bfres_info.layout_key(s)} for s in sh],
        'anims':an}
    if n%20==0: print(n,len(want),key,'%.0fs'%(time.time()-t0),flush=True)
for t,u in sorted(tex_users.items()):
    out['textures'][t]={'in_tex_folder':t in texfiles,'used_by':sorted(u)}
json.dump(out,open(os.path.join(HERE,'npc_index.json'),'w'),indent=1)
# ---- human-readable summary
md=['# NPC index (BodiesOfTruth)','','Generated by `build_index.py`. Machine-readable data: `npc_index.json`. One section per model file.',
    'Lens swap = the mod\'s shapes become `L1_` (only inside the Lens of Truth iris), vanilla shapes are kept as `L0_` (hidden in the iris).',
    'Columns: shape | material | skin influences | LODs | verts. "Shared textures" = textures also used by other models, so a mod that overwrites them would change those NPCs too (the tool renames them with the model tag).','']
for key,m in out['models'].items():
    if 'error' in m: md+=['## %s'%key,'unreadable: '+m['error'],'']; continue
    shared=sorted({t for ts in m['materials'].values() for t in ts if len(out['textures'][t]['used_by'])>1 and out['textures'][t]['in_tex_folder']})
    md+=['## %s'%key,'- actors: %s'%(', '.join(m['actors']) or '(none in Npc_* packs)'),
         '- tag `%s`, %d bones (%d smooth, %d rigid), %d shapes, %d materials, cloth: %s'%(m['tex_tag'],m['bones']['total'],m['bones']['smooth'],m['bones']['rigid'],len(m['shapes']),len(m['materials']),m['cloth'] or '-'),
         '- anims: '+('; '.join('%s%s%s'%(a['file'][:-14],'' if a['model_specific'] else ' (shared)',' -> '+','.join(a['materials']) if a['materials'] else '') for a in m['anims']) or '-'),
         '- anim skeletons: '+(', '.join(m['anim_skeletons']) or '-'),
         '- shared textures: '+(', '.join(shared) or '-'),'```']
    for s in m['shapes']: md.append('%-44s %-20s skin %d lods %2d verts %6d'%(s['name'],s['material'],s['skin'],s['lods'],s['verts']))
    md+=['```','']
open(os.path.join(HERE,'npc_index.md'),'w',newline='\n').write('\n'.join(md))
print('models %d, textures %d, actors %d, %.0fs'%(len(out['models']),len(out['textures']),len(actors),time.time()-t0))
