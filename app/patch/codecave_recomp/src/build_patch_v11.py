#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Build the Lens Outfit Swap v11 exefs patch, build 6 (recompiler-safe: Longshot/Hookshot; also fine on hardware) (v8 iris swap + exact per-material lens shadows).
Needs clang, ld.lld, llvm-objcopy, llvm-nm. Targets OoT (Switch 2) update v131072, main E0F3CCFA...
Offsets are into the decompressed main image; IPS offsets add the 0x100 NSO header.
v11 drops v8's hook 2 (tagged-actor lens_alpha): use UNTAGGED actors only."""
import os, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
# Code cave origin/limit. Override to relocate the code when merging with other mods, e.g.
#   LENS_CAVE=0x3C46A00 LENS_CAVE_END=0x3C47000 python3 build_patch_v11.py
CAVE = int(os.environ.get('LENS_CAVE', '0x3C46400'), 16)
CAVE_END = int(os.environ.get('LENS_CAVE_END', '0x3C47000'), 16)
BUILD_ID = 'E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348'
# (site, expected original word, branch kind, target symbol)
SITES = [
    (0x2E1EB10, 0xD503237F, 'b',  'hook'),        # gfx controller update entry (pacibsp)
    (0x2E5359C, None,       'bl', 'init_hook'),   # bl 0xdce3a0 (shadow component allocates its unit)
    (0x4EE6AC,  None,       'bl', 'attach_hook'), # bl 0x4efb60 (attach model to shadow unit)
    (0x98A4A8,  0xD503237F, 'b',  'free_hook'),   # shadow unit free (pacibsp)
    (0x4FAE1C,  None,       'b',  'fstub1'),      # ldrh w8,[x8,#0xe]  (0x4fa9a0)
    (0x82FF4,   None,       'b',  'fstub2'),      # ldrh w8,[x8,#0xe]  (inline copy in 0x7bb80)
    (0x31C57C4, None,       'b',  'fstub3'),      # ldrh w9,[x9,#0xe]  (0x31c5540)
    (0x4FAED8,  None,       'b',  'dstub1'),      # ldrb w8,[x24,#0x8a]
    (0x830B8,   None,       'b',  'dstub2'),      # ldrb w8,[x23,#0x8a]
    (0x31C588C, None,       'b',  'dstub3'),      # ldrb w8,[x21,#0x8a]
]
def run(*c): subprocess.run(c, check=True, cwd=HERE)
def main():
    ld = os.path.join(HERE, 'link_v11.ld'); lines = open(ld).read().splitlines()
    lines[0] = 'SECTIONS { . = %#x; .text : { *(.text) } }' % CAVE
    open(ld, 'w').write('\n'.join(lines) + '\n')
    run('clang', '-target', 'aarch64-none-elf', '-march=armv8.3-a', '-c', 'lensswap_v11.s', '-o', 'v11.o')
    run('ld.lld', '-T', 'link_v11.ld', 'v11.o', '-o', 'v11.elf')
    run('llvm-objcopy', '-O', 'binary', '-j', '.text', 'v11.elf', 'cave11.bin')
    nm = subprocess.run(['llvm-nm', 'v11.elf'], capture_output=True, text=True, cwd=HERE).stdout
    addr = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
    cave = open(os.path.join(HERE, 'cave11.bin'), 'rb').read()
    if addr['hook'] != CAVE or CAVE + len(cave) > CAVE_END: sys.exit('cave overflow')
    main_img = os.path.join(HERE, 'main.img')
    img = open(main_img, 'rb').read() if os.path.exists(main_img) else None
    patches = []
    for site, orig, kind, sym in SITES:
        if img and orig is not None and struct.unpack_from('<I', img, site)[0] != orig: sys.exit('unexpected original at %#x' % site)
        op = 0x14000000 if kind == 'b' else 0x94000000
        patches.append((site, struct.pack('<I', op | (((addr[sym] - site) >> 2) & 0x3FFFFFF))))
    patches.append((CAVE, cave))
    ips = b'IPS32' + b''.join(struct.pack('>IH', o + 0x100, len(d)) + d for o, d in patches) + b'EEOF'
    open(os.path.join(HERE, BUILD_ID + '.ips'), 'wb').write(ips)
    lines = ['@nsobid-' + BUILD_ID + '0' * 24, '', '# Lens of Truth outfit swap v11 build 6, recompiler-safe (iris swap + per-material lens shadows), OoT Switch 2 v131072',
             '# L0_* materials: vanish in the iris, shadow only outside it. L1_*: appear in the iris, shadow only inside. Untagged actors only.',
             '@flag offset_shift 0x100', '', '@enabled'] + ['%08X %s' % (o, d.hex().upper()) for o, d in patches] + ['@stop', '']
    open(os.path.join(HERE, 'lens_outfit_swap_v11.pchtxt'), 'w').write('\n'.join(lines))
    print('cave %#x-%#x (%d bytes, %d free)' % (CAVE, CAVE + len(cave), len(cave), CAVE_END - CAVE - len(cave)))
if __name__ == '__main__': main()
