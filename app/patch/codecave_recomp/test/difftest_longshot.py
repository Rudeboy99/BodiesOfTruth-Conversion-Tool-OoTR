# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Differential test for the recompiler-safe lens cave (build 6) against shipped build 5.

A = build 5 as a console or an emulator runs it (sites reached by BL, stubs RET).
B = build 6 run under a model of Longshot's lift (third_party/a64-kit/lift/a64_lift.py, guest locals on):
    - BL/BLR is a C call and RET a C return: a RET must come back to the instruction after its BL
      (or to the entry's LR), whatever x30 holds; anything else is a failure;
    - at a callee's entry and right after a call returns, x9-x15 and NZCV hold garbage (the caller's locals are not
      written back before a call, and nothing in x9-x15 or the flags comes back from one);
    - routines entered from a game function's entry (hook, free_hook) or by BL (init_hook, attach_hook) start with
      garbage in x9-x15; the B-reached site stubs run inside the game function, so they see its real registers.
Every scenario of difftest_base.py (scenario by scenario, same fake game state, same call logs, heap compared
byte for byte) is run in both, plus stricter checks for B: the site stubs keep every register but their output,
x30 included. `difftest_longshot.py old old` runs build 5 under the model: it must fail (that is the crash).
usage: python3 difftest_longshot.py DIR_A DIR_B [--emu]   (--emu: run B as a console does, without the Longshot model)"""
import struct, sys, random
from unicorn import *
from unicorn.arm64_const import *
import difftest_base as base

BACK = {0x4fae20: 'RET', 0x82ff8: 'RET', 0x31c57c8: 'RET', 0x4faedc: 'RET', 0x830bc: 'RET', 0x31c5890: 'RET'}
SCR = [UC_ARM64_REG_X0 + i for i in range(9, 16)]
TRAMP = ('fstub', 'dstub')

class World(base.World):
    def __init__(s, d, longshot):
        base.World.__init__(s, d)
        s.mu.mem_map(0x82000, 0x1000)
        s.ls = longshot
        s.stops.update(BACK)
        s.pend = None
        if longshot:
            s.mu.hook_add(UC_HOOK_CODE, s._abi)
    def _abi(s, mu, addr, size, ud):
        if s.pend:
            kind, want = s.pend; s.pend = None; s.k += 1
            for j, r in enumerate(SCR): mu.reg_write(r, 0xdead000000000000 + (s.k << 8) + j)
            mu.reg_write(UC_ARM64_REG_NZCV, (s.k * 0x30000000) & 0xf0000000)
            if kind == 'ret' and addr != want and s.viol is None:
                s.viol = 'RET went to %#x, not %#x (return address rewritten)' % (addr, want)
        try: w = struct.unpack('<I', mu.mem_read(addr, 4))[0]
        except UcError: return
        if (w & 0xFC000000) == 0x94000000 or (w & 0xFFFFFC1F) == 0xD63F0000:      # BL, BLR
            s.cs.append(addr + 4); s.pend = ('call', None)
        elif (w & 0xFFFFFC1F) == 0xD65F0000 or w in (0xD65F0BFF, 0xD65F0FFF):      # RET, RETAA, RETAB
            s.pend = ('ret', s.cs.pop() if s.cs else s.entry_lr)
    def run(s, entry, regs, lr=0x3c47ff0):
        s.pend = None; s.cs = []; s.viol = None; s.k = 0; s.entry_lr = regs.get(30, lr)
        if s.ls and not entry.startswith(TRAMP):
            regs = dict(regs)
            for j in range(9, 16):
                if j not in regs: regs[j] = 0xbeef000000000000 + j
        try:
            r = base.World.run(s, entry, regs, lr)
        except UcError as e:
            pc = s.mu.reg_read(UC_ARM64_REG_PC)
            r = dict(stop='CRASH', regs=[s.mu.reg_read(x) for x in base.XR], sp=0, d0=0, n=s.n)
            s.viol = s.viol or 'crash: %s at pc %#x (cave+%#x)' % (e, pc, pc - 0x3c46400)
        r['viol'] = s.viol
        return r

def main():
    da, db = sys.argv[1], sys.argv[2]
    wa, wb = World(da, False), World(db, '--emu' not in sys.argv)
    oa, ob = base.build(wa, random.Random(1)), base.build(wb, random.Random(1))
    assert wa.heap == wb.heap
    fails = total = 0; cost = {}; kinds = {}
    for (name, entry, su, pres, stop) in base.scenarios(random.Random(7)):
        res = []
        for w, o in ((wa, oa), (wb, ob)):
            h0 = w.heap; regs = su(w, o); w.w64(w.log, 0); w.mu.mem_write(w.log + 8, b'\0' * 0x3ff0)
            assert w.heap - h0 in (0, 0x20)
            r = w.run(entry, regs); r['heap'] = w.snapshot(); r['in'] = regs; res.append(r)
        a, b = res; total += 1; why = []
        if b['viol']: why.append(b['viol'])
        if a['heap'] != b['heap']:
            i = next(i for i in range(len(a['heap'])) if a['heap'][i] != b['heap'][i]); why.append('heap differs at +%#x' % i)
        if a['stop'] != b['stop']: why.append('stop %s vs %s' % (a['stop'], b['stop']))
        if a['sp'] != b['sp'] or b['sp'] != 0x2000f000: why.append('sp')
        want = lambda i: b['in'].get(i, 0x3c47ff0 if i == 30 else 0x7700000000000000 + i * 0x101)   # (x30: the entry LR)
        if entry.startswith('fstub'):
            out = 8 if entry != 'fstub3' else 9
            if a['regs'][out] != b['regs'][out]: why.append('output x%d %#x vs %#x' % (out, a['regs'][out], b['regs'][out]))
            for i in range(31):     # B: everything but the output kept, x30 too (A only kept these, minus x11-x17)
                if i == out: continue
                if b['regs'][i] != want(i): why.append('B clobbers x%d' % i)
                if i in pres and a['regs'][i] != want(i): why.append('A clobbers x%d' % i)
        elif pres == 'dstub':
            if b['stop'] == 'RET' and a['regs'][8] != b['regs'][8]: why.append('x8 out')
            for i in range(31):
                if i == 8 and b['stop'] == 'RET': continue
                if b['regs'][i] != want(i): why.append('B clobbers x%d' % i)
                if i not in (8, 30) and a['regs'][i] != want(i): why.append('A clobbers x%d' % i)
        else:
            for i in pres:
                if entry == 'init_hook' and i == 0: continue
                if b['regs'][i] != want(i): why.append('B clobbers x%d' % i)
                if a['regs'][i] != want(i) and i != 30: why.append('A clobbers x%d' % i)
        if entry == 'hook' and (a['d0'] != b['d0'] or b['d0'] != 0x3f000000): why.append('d0')
        if entry == 'init_hook' and a['regs'][0] & 0xffffffff != b['regs'][0] & 0xffffffff: why.append('return value')
        if entry == 'hook' and b['regs'][30] != 0x3c47ff0: why.append('lr')
        if why:
            fails += 1; kinds[entry] = kinds.get(entry, 0) + 1
            if kinds[entry] <= 3: print('FAIL', name, why[:4])
        c = cost.setdefault(entry, [0, 0, 0]); c[0] += a['n']; c[1] += b['n']; c[2] += 1
    print('%d scenarios, %d failures %s' % (total, fails, kinds or ''))
    for k, (x, y, n) in sorted(cost.items()): print('  %-12s avg instructions: A %7.1f  B %7.1f  (%d runs)' % (k, x / n, y / n, n))
    print('cave bytes: A %d, B %d' % (wa.size, wb.size))
    return fails
if __name__ == '__main__': sys.exit(1 if main() else 0)
