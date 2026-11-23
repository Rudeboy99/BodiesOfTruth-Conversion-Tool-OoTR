# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
import struct, json, os
def sbit(name,idx):
    b=name.encode(); by=idx>>3
    return (b[len(b)-1-by]>>(idx&7))&1 if by<len(b) else 0
def read(d,od):
    n=struct.unpack_from('<I',d,od+4)[0]
    return [list(struct.unpack_from('<IHHQ',d,od+8+16*i)) for i in range(n+1)]
def lookup(nodes,names,name):
    p=0; c=nodes[0][1]
    while True:
        rp=-1 if nodes[p][0]==0xffffffff else nodes[p][0]; rc=-1 if nodes[c][0]==0xffffffff else nodes[c][0]
        if rc<=rp: return c
        p=c; c=nodes[c][2] if sbit(name,nodes[c][0]) else nodes[c][1]
def first_diff(a,b):
    for i in range(max(len(a),len(b))*8):
        if sbit(a,i)!=sbit(b,i): return i
    return None
def build(names):
    """Nintendo ResDic build (as in BfresLibrary/oead): insert keys in order."""
    nodes=[[0xffffffff,0,0,'']]
    nodes[0][1]=0; nodes[0][2]=0
    for name in names:
        # find best match
        c=lookup(nodes,[n[3] for n in nodes],name) if len(nodes)>1 else 0
        other=nodes[c][3]
        bitidx=first_diff(name,other)
        # walk down to insertion point
        p=0; cur=nodes[0][1]; side=1
        while True:
            rp=-1 if nodes[p][0]==0xffffffff else nodes[p][0]; rc=-1 if nodes[cur][0]==0xffffffff else nodes[cur][0]
            if rc<=rp or rc>bitidx: break
            p=cur
            if sbit(name,nodes[cur][0]): cur=nodes[cur][2]; side=2
            else: cur=nodes[cur][1]; side=1
        ni=len(nodes); new=[bitidx,0,0,name]
        if sbit(name,bitidx): new[1]=cur; new[2]=ni
        else: new[1]=ni; new[2]=cur
        nodes.append(new)
        if p==0: nodes[0][1]=ni
        else: nodes[p][side]=ni
    return nodes
