# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Differential test: run the same scenarios through two builds of the v11 cave (Unicorn) and compare
every observable effect (fake-heap contents, call logs, preserved registers, return address).
usage: python3 difftest.py [DIR_A DIR_B]   (default: build4_compact and this folder)
Build both first (build_patch_v11.py in each folder leaves v11.elf and cave11.bin). Needs unicorn, keystone-engine."""
import struct, subprocess, sys, random, itertools
from unicorn import *
from unicorn.arm64_const import *
import keystone
ks = keystone.Ks(keystone.KS_ARCH_ARM64, keystone.KS_MODE_LITTLE_ENDIAN)
XR = [UC_ARM64_REG_X0 + i for i in range(29)] + [UC_ARM64_REG_X29, UC_ARM64_REG_X30]
F32 = lambda f: struct.unpack('<I', struct.pack('<f', f))[0]

class World:
    def __init__(s, d):
        nm = subprocess.run(['llvm-nm', d + '/v11.elf'], capture_output=True, text=True).stdout
        s.A = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
        cave = open(d + '/cave11.bin', 'rb').read(); s.size = len(cave)
        mu = s.mu = Uc(UC_ARCH_ARM64, UC_MODE_ARM); mu.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
        mu.mem_map(0x3c46000, 0x2000); mu.mem_write(0x3c46400, cave)
        mu.mem_map(0x4c7e000, 0x1000); mu.mem_map(0x10000000, 0x400000); mu.mem_map(0x20000000, 0x10000)
        mu.mem_map(0x3c83000, 0x1000); mu.mem_map(0x3db4000, 0x1000)
        s.heap = 0x10000000; s.n = 0
        mu.hook_add(UC_HOOK_CODE, s._code)
        # stop addresses: fake return + game continuations
        s.stops = {0x3c47ff0: 'RET', s.A['ORIG_CONT']: 'ORIG_CONT', s.A['CONT1']: 'CONT1', s.A['CONT2']: 'CONT2', s.A['CONT3']: 'CONT3'}
        for a in (0x2e1e000, 0x4fa000, 0x83000, 0x31c5000, 0x98a000, 0xdce000, 0x4ef000): mu.mem_map(a, 0x1000)
        s.log = s.alloc(0x4000); s.w64(s.log, 0)
        # game functions called by the cave: log (id, x0, x1, x2, x3, x4) and return
        s.alloc_ret = s.alloc(0x40)          # queue of UNIT_ALLOC return values
        s.stub(s.A['UNIT_FREE_CONT'], 1, None)
        s.stub(s.A['UNIT_ATTACH'], 2, None)
        s.stub(s.A['UNIT_ALLOC'], 3, s.alloc_ret)
    def _code(s, mu, addr, size, ud):
        if 0x3c46400 <= addr < 0x3c47000: s.n += 1
        if addr in s.stops: s.stopped = s.stops[addr]; mu.emu_stop()
    def alloc(s, n):
        a = s.heap; s.heap += (n + 15) & ~15; return a
    def w64(s, a, v): s.mu.mem_write(a, struct.pack('<Q', v & (2**64 - 1)))
    def w32(s, a, v): s.mu.mem_write(a, struct.pack('<I', v & 0xffffffff))
    def w16(s, a, v): s.mu.mem_write(a, struct.pack('<H', v & 0xffff))
    def r32(s, a): return struct.unpack('<I', s.mu.mem_read(a, 4))[0]
    def imm(s, reg, v): return 'movz %s, #%d, lsl #16; movk %s, #%d' % (reg, v >> 16, reg, v & 0xffff)
    def asm_at(s, addr, src):
        b, _ = ks.asm(src, addr); s.mu.mem_write(addr, bytes(b))
    def fn(s, src):
        a = s.alloc(0x100); s.asm_at(a, src); return a
    def logsrc(s, ident):   # append (ident, x0..x4) to the log; uses x9-x12 only
        return (s.imm('x9', s.log) + '; ldr x10, [x9]; add x11, x9, x10, lsl #3; mov x12, #%d; str x12, [x11, #8];'
                'str x0, [x11, #16]; str x1, [x11, #24]; str x2, [x11, #32]; str x3, [x11, #40]; str x4, [x11, #48];'
                'str s0, [x11, #56]; add x10, x10, #7; str x10, [x9];' % ident)
    def stub(s, addr, ident, retq):
        src = s.logsrc(ident)
        if retq: src += s.imm('x9', retq) + '; ldr x10, [x9]; add x10, x10, #1; str x10, [x9]; ldr x0, [x9, x10, lsl #3];'
        # scramble caller-saved registers like a real callee would
        src += ''.join('mov x%d, #0x%x;' % (r, 0xbad0 + r) for r in list(range(1, 18)) if True) + ('' if retq else 'mov x0, #0xbad;') + 'ret'
        s.asm_at(addr, src)
    def run(s, entry, regs, lr=0x3c47ff0):
        mu = s.mu
        for i, r in enumerate(XR): mu.reg_write(r, regs.get(i, 0x7700000000000000 + i * 0x101))
        mu.reg_write(UC_ARM64_REG_SP, 0x2000f000); mu.reg_write(UC_ARM64_REG_LR, regs.get(30, lr))
        mu.reg_write(UC_ARM64_REG_NZCV, 0); mu.reg_write(UC_ARM64_REG_D0, regs.get('d0', 0x3f000000))
        s.n = 0; s.stopped = None
        mu.emu_start(s.A[entry], 0, count=2000000)
        out = [mu.reg_read(r) for r in XR]
        return dict(stop=s.stopped, regs=out, sp=mu.reg_read(UC_ARM64_REG_SP), d0=mu.reg_read(UC_ARM64_REG_D0) & 0xffffffff, n=s.n)
    def snapshot(s): return bytes(s.mu.mem_read(0x10000000, s.heap - 0x10000000))

def build(w, rng):
    """Deterministic fake game state (identical layout in both worlds)."""
    o = type('O', (), {})()
    # ---- models
    def model(names, vt):
        d = w.alloc(0x20 + 16 * len(names)); w.w32(d + 4, len(names))
        for i, n in enumerate(names):
            if n is None: continue
            st = w.alloc(64); w.mu.mem_write(st, struct.pack('<H', len(n)) + n.encode() + b'\0' + bytes([0x4c, 0x31, 0x5f][:0]))
            w.w64(d + 0x20 + 16 * i, st)
        f = w.alloc(0x48); w.w64(f + 0x40, d); r = w.alloc(0x18); w.w64(r + 0x10, f); q = w.alloc(0x68); w.w64(q + 0x60, r)
        m = w.alloc(0x100); w.w64(m + 0xd8, q); w.w64(m, vt)
        S = w.alloc(0x30); ents = w.alloc(0x14 * len(names)); w.w64(S + 8, ents); w.w64(m + 0x38, S)
        return m, ents
    o.params = w.alloc(0x100); o.vis = w.alloc(0x100)
    # virtual functions: log + behave. material index in w1; per-model offset not needed (log has model ptr)
    f_find = w.fn(w.logsrc(10) + 'and w0, w1, #3; cmp w0, #3; mov w0, #7; csinv w0, w0, wzr, ne;' + ''.join('mov x%d, #0x%x;' % (r, 0xf00 + r) for r in range(1, 18)) + 'ret')   # material idx%4==3 -> param missing (-1)
    f_set = w.fn(w.logsrc(11) + w.imm('x8', o.params) + '; str s0, [x8, w1, uxtw #2];' + ''.join('mov x%d, #0x%x;' % (r, 0xf00 + r) for r in range(0, 18)) + 'ret')
    f_isv = w.fn(w.logsrc(12) + w.imm('x8', o.vis) + '; ldr w0, [x8, w1, uxtw #2];' + ''.join('mov x%d, #0x%x;' % (r, 0xf00 + r) for r in range(1, 18)) + 'ret')
    f_setv = w.fn(w.logsrc(13) + w.imm('x8', o.vis) + '; str w2, [x8, w1, uxtw #2];' + ''.join('mov x%d, #0x%x;' % (r, 0xf00 + r) for r in range(0, 18)) + 'ret')
    o.shape_tbl = w.alloc(8 * 64)
    f_shape = w.fn(w.imm('x8', o.shape_tbl) + '; ldr x0, [x8, w1, uxtw #3];' + ''.join('mov x%d, #0x%x;' % (r, 0xf00 + r) for r in range(1, 18)) + 'ret')
    vt = w.alloc(0x200)
    for off, f in ((0xe0, f_find), (0x128, f_set), (0x1d0, f_isv), (0x1c8, f_setv), (0x1f0, f_shape)): w.w64(vt + off, f)
    o.names = ['Mt_Face', 'L0_Leather', 'L1_Satin', 'L1_NoParam', 'L', 'L1', 'L0_', 'L1_', 'L2_a', 'M1_x', '', None,
               'l1_x', 'L1-x', 'L0x', 'L0_Second', 'Mt_L1_', 'K1_a', 'L:_a', 'L/_a', '\x4c\x31\x5f\xff']
    o.m1, o.ents1 = model(o.names, vt)
    o.m2, o.ents2 = model(['Mt_Face', 'Mt_Body', 'Mt_Hair'], vt)
    o.m3 = w.alloc(0x100); w.w64(o.m3, vt)                          # model with no material dict chain
    o.m4, _ = model([], vt)                                         # empty dict
    # ---- lens state
    o.ctrl = w.alloc(0x20); c1 = w.alloc(0xc00); c0 = w.alloc(0x200); g = w.alloc(8)
    w.w64(0x4c7e740, g); w.w64(g, c0); w.w64(c0 + 0x1e8, c1); w.w64(c1 + 0xb90, o.ctrl)
    # ---- renderer, pool, lists
    o.ren = w.alloc(0xd00); o.pool = w.alloc(0x20 * 8); w.w32(o.ren + 0xa88, 8); w.w64(o.ren + 0xa90, o.pool)
    o.units = []
    for i in range(8):
        u = w.alloc(0x870); o.units.append(u); w.w32(o.pool + 0x20 * i + 8, i); w.w64(o.pool + 0x20 * i + 0x10, u)
        w.w32(u + 0x824, i); w.w64(u + 0x868, o.ren)
    o.buf = w.alloc(0x18 * 64); bh = w.alloc(0x18); w.w32(bh + 8, 64); w.w64(bh + 0x10, o.buf); w.w64(o.ren + 0xb40, bh)
    w.w32(o.ren + 0xc60, 0); w.w32(o.ren + 0xb10, 2)
    grp = w.alloc(0x20); o.lists = [w.alloc(0x30) for _ in range(2)]
    for i, l in enumerate(o.lists): w.w64(grp + 16 * i + 8, l); w.w64(l + 0x20, w.alloc(8 * 64))
    w.w64(o.ren + 0xb18, grp); o.act = w.alloc(8 * 8); w.w32(o.ren + 0xc44, 8); w.w64(o.ren + 0xc48, o.act)
    w.w32(0x3c834e0, 3); w.w32(0x3c834e4, 250)
    # ---- shapes of m1 (one per material) + model draw data
    o.shapes = []
    for i in range(len(o.names)):
        sh = w.alloc(0x40); w.w16(sh + 0x1a, i); w.w16(sh + 0x1e, rng.randrange(65536)); w.w64(sh + 8, o.m1)
        o.shapes.append(sh); w.w64(o.shape_tbl + 8 * i, sh)
    o.shapes.append(0)                                                # getShape returning null
    idx = w.alloc(2 * 64); w.mu.mem_write(idx, struct.pack('<%dH' % (len(o.names) + 1), *range(len(o.names) + 1)))
    w.w64(o.m1 + 0x30, idx); w.w16(o.m1 + 0x24, len(o.names) + 1)
    p40 = w.alloc(0x70); w.w64(o.m1 + 0x40, p40); w.mu.mem_write(p40 + 0x64, b'\x0b')
    o.R = w.alloc(0x90)
    # ---- actor / holder for hook 1 and attach_hook
    def holder(models):
        h = w.alloc(0x30); sl = w.alloc(8 * (len(models) + 1))
        for i, m in enumerate(models):
            if m == 'nullslot': continue
            sp = w.alloc(8)
            if m != 'nullmodel': w.w64(sp, m)
            w.w64(sl + 8 * i, sp)
        w.w32(h + 0x20, len(models)); w.w64(h + 0x28, sl); return h
    o.holders = {'L': holder([o.m2, 'nullslot', o.m3, 'nullmodel', o.m1, o.m4]), 'noL': holder([o.m2, o.m3, o.m4, o.m2]), 'empty': holder([])}
    o.G = {}
    for k, h in o.holders.items():
        fh = w.fn(w.imm('x0', h) + ';' + ''.join('mov x%d, #0x%x;' % (r, 0xf00 + r) for r in range(1, 18)) + 'ret')
        mc = w.alloc(0x10); mcvt = w.alloc(0x100); w.w64(mcvt + 0xf8, fh); w.w64(mc, mcvt)
        comp = w.alloc(0x10); w.w64(comp + 8, mc); actor = w.alloc(0x280); w.w64(actor + 0x270, comp); G = w.alloc(0x20); w.w64(G + 0x18, actor); o.G[k] = G
    Gn = w.alloc(0x20); o.G['noactor'] = Gn
    fh0 = w.fn('mov x0, #0; ret'); mc = w.alloc(0x10); mcvt = w.alloc(0x100); w.w64(mcvt + 0xf8, fh0); w.w64(mc, mcvt)
    comp = w.alloc(0x10); w.w64(comp + 8, mc); actor = w.alloc(0x280); w.w64(actor + 0x270, comp); G = w.alloc(0x20); w.w64(G + 0x18, actor); o.G['noholder'] = G
    return o

def lens(w, o, on, v):
    w.w32(o.ctrl + 0x10, on); w.w32(o.ctrl + 0xc, v)
def links(w, o, la, lb, a=2, b=5):
    for i in range(8): w.w32(o.pool + 0x20 * i + 0x1c, 0)
    w.w32(o.pool + 0x20 * a + 0x1c, la); w.w32(o.pool + 0x20 * b + 0x1c, lb)

def scenarios(rng):
    """yield (name, entry, setup(w, o) -> regs dict, preserved register indices, output regs)"""
    ALLP = list(range(0, 31))
    lens_states = [(F32(1.0), F32(0.5)), (F32(1.0), 0), (F32(1.0), 0x80000000), (0, F32(0.5)), (0, 0), (F32(-1.0), F32(0.3)), (1, F32(-0.7))]
    # --- hook 1
    for gk in ('L', 'noL', 'empty', 'noactor', 'noholder'):
        for on, v in lens_states:
            for visinit in (0, 1, 0xffffffff, 2):
                def su(w, o, gk=gk, on=on, v=v, visinit=visinit):
                    lens(w, o, on, v)
                    w.mu.mem_write(o.params, struct.pack('<64f', *([9.0] * 64))); w.mu.mem_write(o.vis, struct.pack('<64I', *([visinit] * 64)))
                    return {0: o.G[gk]}
                yield ('hook %s on=%x v=%x vis=%x' % (gk, on, v, visinit), 'hook', su, [0, 1] + list(range(19, 30)), 'ORIG_CONT')
    # --- filter stubs
    partner_cfgs = [(0xb0000005, 0xa0000002), (0, 0), (0xb0000005, 0xa0000003), (0xb0000009, 0xa0000002), (0xa0000005, 0xa0000002), (0xb0010005, 0xa0000002)]
    for stub in (1, 2, 3):
        for mat in range(21):
            for flags in (0, 1, 2, 3, 4, 6, 0xfffd, 0xffff):
                for pc in partner_cfgs:
                    for slot in (2, 5, 0xffffffff, 8):
                        for mask in ((2,) if stub < 3 else (2, 4, 1)):
                            if rng.random() > 0.35: continue
                            def su(w, o, stub=stub, mat=mat, flags=flags, pc=pc, slot=slot, mask=mask):
                                links(w, o, *pc); w.w32(o.R + 0x28, slot)
                                e = o.ents1 + 0x14 * mat; w.w16(e + 0xe, flags)
                                if stub == 1: return {0: o.shapes[mat], 8: e, 1: o.m1, 19: o.ren, 24: o.R}
                                if stub == 2: return {0: o.shapes[mat], 8: e, 19: o.m1, 20: o.ren, 23: o.R}
                                return {0: o.shapes[mat], 9: e, 8: o.m1, 28: o.ren, 21: o.R, 25: mask}
                            out = 8 if stub < 3 else 9
                            yield ('fstub%d mat%d flags=%x pc=%x/%x slot=%x mask=%d' % (stub, mat, flags, pc[0], pc[1], slot, mask), 'fstub%d' % stub, su,
                                   [i for i in range(31) if i not in range(11, 18) and i != 30], 'RET')
    # --- direction stubs
    for stub in (1, 2, 3):
        for on, v in lens_states:
            for pc in partner_cfgs:
                for fl in (2, 0, 6):
                    for mask in ((2,) if stub < 3 else (2, 4)):
                        for bflags in (0, 4, 0x66):
                            def su(w, o, stub=stub, on=on, v=v, pc=pc, fl=fl, mask=mask, bflags=bflags):
                                lens(w, o, on, v); links(w, o, *pc); w.w32(o.R + 0x28, 2); w.mu.mem_write(o.R + 0x8a, b'\x5a')
                                for i in range(21): w.w16(o.ents1 + 0x14 * i + 0xe, fl if i % 5 else fl ^ 2); w.mu.mem_write(o.ents1 + 0x14 * i + 0x10, bytes([i * 7 & 255]))
                                uA, uB = o.units[2], o.units[5]
                                for off in range(0x5f8, 0x840, 4): w.w32(uA + off, 0x1000 + off); w.w32(uB + off, 0x2000 + off)
                                w.w32(uA + 0x5f8, 0x22); w.w32(uB + 0x5f8, bflags); w.w32(uA + 0x824, 2); w.w32(uB + 0x824, 5)
                                for l in o.lists: w.w32(l + 0x2c, 0)
                                w.w32(o.ren + 0xb48, 0); w.w32(o.ren + 0xc40, 0)
                                fp = w.alloc(0x20) ; w.w64(fp + 8, o.m1)     # [x29-8] = model (sites 1 and 3)
                                if stub == 1: return {29: fp + 0x10, 19: o.ren, 24: o.R, 22: uA, 23: o.pool + 0x40}
                                if stub == 2: return {19: o.m1, 20: o.ren, 23: o.R, 25: uA, 26: o.pool + 0x40}
                                return {29: fp + 0x10, 28: o.ren, 21: o.R, 19: uA, 20: o.pool + 0x40, 25: mask}
                            yield ('dstub%d on=%x v=%x pc=%x/%x fl=%x mask=%d b=%x' % (stub, on, v, pc[0], pc[1], fl, mask, bflags), 'dstub%d' % stub, su, 'dstub', None)
    # --- unit lifetime
    for a_ret, b_ret in ((2, 5), (0xffffffff, 5), (2, 0xffffffff), (2, 9), (9, 5), (0, 7)):
        def su(w, o, a_ret=a_ret, b_ret=b_ret):
            links(w, o, 0, 0); w.w64(w.alloc_ret, 0); w.w64(w.alloc_ret + 8, a_ret); w.w64(w.alloc_ret + 16, b_ret)
            return {0: o.ren, 1: 0x1234, 2: 1, 3: 0x77, 4: 0x8888}
        yield ('init_hook A=%x B=%x' % (a_ret, b_ret), 'init_hook', su, list(range(19, 30)), 'RET')
    for hk in ('L', 'noL', 'empty'):
        for pc in partner_cfgs:
            for idx, cnt in ((0, 1), (0, 6), (5, 6), (3, 4), (2, 6)):
                def su(w, o, hk=hk, pc=pc, idx=idx, cnt=cnt):
                    links(w, o, *pc); return {0: o.units[2], 1: o.m1, 22: o.holders[hk], 23: cnt if hk != 'empty' else 1, 24: idx if hk != 'empty' else 0}
                if hk == 'empty' and (idx, cnt) != (0, 1): continue
                if hk == 'noL' and cnt > 4: continue
                yield ('attach_hook %s pc=%x/%x %d/%d' % (hk, pc[0], pc[1], idx, cnt), 'attach_hook', su, list(range(19, 30)), 'RET')
    for pc in partner_cfgs:
        for slot in (2, 5, 0xffffffff):
            def su(w, o, pc=pc, slot=slot):
                links(w, o, *pc); return {0: o.ren, 1: slot}
            yield ('free_hook pc=%x/%x slot=%x' % (pc[0], pc[1], slot), 'free_hook', su, list(range(19, 30)), 'RET')

def main():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    da, db = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (os.path.join(here, 'build4_compact'), here)
    wa, wb = World(da), World(db); oa, ob = build(wa, random.Random(1)), build(wb, random.Random(1))
    assert wa.heap == wb.heap
    fails = 0; total = 0; cost = {}
    for (name, entry, su, pres, stop) in scenarios(random.Random(7)):
        res = []
        for w, o in ((wa, oa), (wb, ob)):
            h0 = w.heap; regs = su(w, o); w.w64(w.log, 0); w.mu.mem_write(w.log + 8, b'\0' * 0x3ff0)
            assert w.heap - h0 in (0, 0x20)
            r = w.run(entry, regs); r['heap'] = w.snapshot(); r['in'] = regs; res.append(r)
        a, b = res; total += 1; why = []
        if a['heap'] != b['heap']:
            i = next(i for i in range(len(a['heap'])) if a['heap'][i] != b['heap'][i]); why.append('heap differs at +%#x' % i)
        if a['stop'] != b['stop']: why.append('stop %s vs %s' % (a['stop'], b['stop']))
        if a['sp'] != b['sp'] or b['sp'] != 0x2000f000: why.append('sp')
        if pres == 'dstub':
            # not handled: everything preserved except x8 (= ldrb result) and return to the site; handled: jump to CONTn with everything preserved (x8 is dead there)
            keep = [i for i in range(31) if i != 8 and i != 30]
            if b['stop'] == 'RET' and (a['regs'][8] != b['regs'][8]): why.append('x8 out')
        else:
            keep = pres
        if entry == 'hook' and (a['d0'] != b['d0'] or b['d0'] != 0x3f000000): why.append('d0')
        for i in keep:
            want = b['in'].get(i, 0x7700000000000000 + i * 0x101)
            if entry.startswith('fstub') and i == (8 if entry != 'fstub3' else 9):
                if a['regs'][i] != b['regs'][i]: why.append('output reg x%d %#x vs %#x' % (i, a['regs'][i], b['regs'][i]))
                continue
            if entry in ('init_hook',) and i == 0: continue
            if b['regs'][i] != want: why.append('B clobbers x%d' % i)
            if a['regs'][i] != want and i not in (30,): why.append('A clobbers x%d' % i)
        if entry == 'init_hook' and a['regs'][0] & 0xffffffff != b['regs'][0] & 0xffffffff: why.append('return value')
        if entry == 'hook' and b['regs'][30] != 0x3c47ff0: why.append('lr')
        if why: fails += 1; print('FAIL', name, why[:4])
        c = cost.setdefault(entry, [0, 0, 0]); c[0] += a['n']; c[1] += b['n']; c[2] += 1
    print('%d scenarios, %d failures' % (total, fails))
    for k, (x, y, n) in sorted(cost.items()): print('  %-12s avg instructions: A %7.1f  B %7.1f  (%d runs)' % (k, x / n, y / n, n))
    print('cave bytes: A %d, B %d' % (wa.size, wb.size))
    return fails
if __name__ == '__main__': sys.exit(1 if main() else 0)
