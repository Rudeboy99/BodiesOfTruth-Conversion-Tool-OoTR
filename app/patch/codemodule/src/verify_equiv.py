#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Check the module build runs the same instructions as shipped v11: disassemble both at their real
addresses, turn branch/adrp targets into either 'code+off' (inside the lens code) or the absolute main
address, and compare instruction by instruction."""
import re, subprocess, sys
D = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x4F80000
def dis(elf, adj, lo_sym):
    nm = subprocess.run(['llvm-nm', elf], capture_output=True, text=True).stdout
    a = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
    out = subprocess.run(['llvm-objdump', '-d', '--no-show-raw-insn', '--adjust-vma=%#x' % adj, '-j', '.text', elf],
                         capture_output=True, text=True).stdout
    ins = []
    for l in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
        if m: ins.append((int(m.group(1), 16), m.group(2), re.sub(r'\s*<.*>', '', m.group(3)).split('//')[0].strip()))
    start = a[lo_sym] + adj
    ins = [i for i in ins if i[0] >= start]
    end = ins[-1][0] + 4
    def norm(addr, op, args):
        def fix(m):
            v = int(m.group(1), 16)
            if op == 'adrp' or start <= v < end:
                if start <= v < end: return 'code+%#x' % (v - start)
                if op == 'adrp' and (start & ~0xfff) <= v <= (end | 0xfff): return 'codepage+%#x' % (v - (start & ~0xfff))
            return 'main:%#x' % v
        if op in ('b', 'bl', 'adrp', 'adr', 'cbz', 'cbnz', 'tbz', 'tbnz') or op.startswith('b.'):
            args = re.sub(r'0x([0-9a-f]+)$', fix, args)
        return (op, args)
    return [(i[0] - start,) + norm(*i) for i in ins], start
o, os_ = dis('orig/v11.elf', 0, 'hook')
n, ns = dis('module_v11.elf', 0, 'hook')
print('original: %d instructions at main+%#x; module: %d at main+%#x' % (len(o), os_, len(n), ns))
bad = [(x, y) for x, y in zip(o, n) if x != y]
for x, y in bad[:20]: print('DIFF', x, '|', y)
print('identical' if not bad and len(o) == len(n) else '%d differences' % (len(bad) + abs(len(o) - len(n))))
