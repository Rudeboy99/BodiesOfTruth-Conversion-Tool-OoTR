# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
import struct
def rlt_locs(d):
    rlt=struct.unpack_from('<I',d,0x18)[0]; nsec=struct.unpack_from('<I',d,rlt+8)[0]
    secs=[list(struct.unpack_from('<QIIII',d,rlt+0x10+0x18*i)) for i in range(nsec)]
    ent0=rlt+0x10+0x18*nsec; locs=[]; ents=[]
    for si,(p,pos,size,ei,ec) in enumerate(secs):
        for e in range(ei,ei+ec):
            off,sc,oc,pc=struct.unpack_from('<IHBB',d,ent0+8*e); ents.append((si,off,sc,oc,pc))
            for s in range(sc):
                for o in range(oc): locs.append((si,off+(s*(oc+pc)+o)*8))
    return rlt,secs,ents,locs
