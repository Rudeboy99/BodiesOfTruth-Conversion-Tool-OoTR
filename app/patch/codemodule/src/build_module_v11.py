#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Build Lens Outfit Swap v11 as a separate code module (TEST BUILD).

The lens code (lensswap_v11.s, unchanged) goes into its own module `subsdk1` instead of the padding
after main's code, so it can't collide with Fritchii's built-in patches in that padding.
main only gets the 10 four-byte hooks, which branch straight into the module.

Layout: modules load back to back in the order rtld, main, subsdk0, subsdk1, ..., sdk, each page
aligned (Fritchii/Lichii loader and the console loader both do this). So subsdk1 starts at
    main + image(main) + image(subsdk0)
where image = page-aligned end of the furthest segment plus .bss. For v131072 that is
0x4EA0000 + 0xE0000 = 0x4F80000. Pass the game's exefs folder to recompute it from the NSO headers:
    python3 build_module_v11.py [path/to/exefs]
Every reference from the module into main is PC-relative (b/bl/adrp), linked against that offset.
If anything changes the layout (a game update, a mod replacing subsdk0, another mod's subsdk1),
the offset is wrong and the hooks land in the wrong place: rebuild.

Needs clang, ld.lld, llvm-objcopy, llvm-nm. Outputs (in ./out):
    exefs/subsdk1                                   the module (uncompressed NSO)
    exefs/E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348.ips   the 10 hooks for main
    lens_module_v11_hooks.pchtxt                    the same hooks as text (reference)
"""
import hashlib, os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD_ID = 'E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348'
MODULE_NAME = 'subsdk1'
DEFAULT_DELTA = 0x4F80000
GAME_SYMS = {  # main image offsets used by lensswap_v11.s (same as link_v11.ld)
    'GOT_GFX': 0x4c7e740, 'ORIG_CONT': 0x2e1eb14, 'PGTA_STR': 0x3db413c, 'PER_GROUP_TBL': 0x3c834e0,
    'UNIT_ATTACH': 0x4efb60, 'UNIT_ALLOC': 0xdce3a0, 'UNIT_FREE_CONT': 0x98a4ac,
    'CONT1': 0x4faef4, 'CONT2': 0x830d4, 'CONT3': 0x31c58f0}
SITES = [  # (site in main, branch kind, target symbol) - same as build_patch_v11.py
    (0x2E1EB10, 'b', 'hook'), (0x2E5359C, 'bl', 'init_hook'), (0x4EE6AC, 'bl', 'attach_hook'),
    (0x98A4A8, 'b', 'free_hook'), (0x4FAE1C, 'bl', 'fstub1'), (0x82FF4, 'bl', 'fstub2'),
    (0x31C57C4, 'bl', 'fstub3'), (0x4FAED8, 'bl', 'dstub1'), (0x830B8, 'bl', 'dstub2'),
    (0x31C588C, 'bl', 'dstub3')]
PAGE = 0x1000
align = lambda x: (x + PAGE - 1) & ~(PAGE - 1)


def nso_image_size(path):
    h = open(path, 'rb').read(0x100)
    assert h[:4] == b'NSO0', path
    end = max(struct.unpack_from('<I', h, o + 4)[0] + struct.unpack_from('<I', h, o + 8)[0] for o in (0x10, 0x20, 0x30))
    return align(end + struct.unpack_from('<I', h, 0x3C)[0])


def module_delta(exefs):
    if not exefs:
        return DEFAULT_DELTA
    for n in ('subsdk1', 'subsdk2', 'subsdk3', 'subsdk4', 'subsdk5', 'subsdk6', 'subsdk7', 'subsdk8', 'subsdk9'):
        if os.path.exists(os.path.join(exefs, n)) and n == MODULE_NAME:
            sys.exit('the game already has a %s; pick another module name' % n)
    h = open(os.path.join(exefs, 'main'), 'rb').read(0x60)
    if h[0x40:0x54].hex().upper() != BUILD_ID:
        sys.exit('main build id is not %s' % BUILD_ID)
    return nso_image_size(os.path.join(exefs, 'main')) + nso_image_size(os.path.join(exefs, 'subsdk0'))


def run(*c):
    subprocess.run(c, check=True, cwd=HERE)


def main():
    delta = module_delta(sys.argv[1] if len(sys.argv) > 1 else None)
    out = os.path.join(HERE, 'out'); os.makedirs(os.path.join(out, 'exefs'), exist_ok=True)
    # Linked at its real place (main + delta), so game symbols are plain main offsets as in link_v11.ld.
    ld = ['%s = %#x;' % kv for kv in GAME_SYMS.items()] + [
        'SECTIONS {', '  . = %#x;' % delta, '  .text : { *(.text.head) *(.text) }', '  . = ALIGN(%#x);' % PAGE,
        '  .rodata : { *(.rodata.dyn) *(.rodata*) }', '  . = ALIGN(%#x);' % PAGE,
        '  .data : { *(.data.dyn) *(.data*) }', '  __bss_start = .;', '  .bss : { *(.bss*) }',
        '  __bss_end = .;', '  /DISCARD/ : { *(.comment) *(.note*) }', '}'] + [
        'DYN_%s = %s - __module_start;' % (k, v) for k, v in (('HASH', '__hash'), ('GNU_HASH', '__gnu_hash'),
        ('STRTAB', '__dynstr'), ('SYMTAB', '__dynsym'), ('INIT', '__lens_init_stub'))]
    open(os.path.join(HERE, 'module_v11.ld'), 'w').write('\n'.join(ld) + '\n')
    for s in ('module_head', 'lensswap_v11'):
        run('clang', '-target', 'aarch64-none-elf', '-march=armv8.3-a', '-c', s + '.s', '-o', s + '.o')
    run('ld.lld', '-T', 'module_v11.ld', '-e', '0', 'module_head.o', 'lensswap_v11.o', '-o', 'module_v11.elf')
    seg = {}
    for sec in ('.text', '.rodata', '.data'):
        run('llvm-objcopy', '-O', 'binary', '-j', sec, 'module_v11.elf', 'seg' + sec)
        seg[sec] = open(os.path.join(HERE, 'seg' + sec), 'rb').read()
    nm = subprocess.run(['llvm-nm', 'module_v11.elf'], capture_output=True, text=True, cwd=HERE).stdout
    addr = {l.split()[2]: int(l.split()[0], 16) - delta for l in nm.splitlines() if len(l.split()) == 3}
    if any(k.startswith('__AArch64') for k in addr): sys.exit('linker added branch thunks')
    ro_off, data_off = addr['__dynsym'] & ~(PAGE - 1), addr['_DYNAMIC'] & ~(PAGE - 1)
    bss_size = addr['__bss_end'] - (data_off + len(seg['.data']))
    if ro_off < len(seg['.text']) or data_off < ro_off + len(seg['.rodata']):
        sys.exit('segment layout overlap')

    # NSO (uncompressed, no segment hashes)
    body = seg['.text'] + seg['.rodata'] + seg['.data']
    build_id = hashlib.sha256(body).digest()[:20] + bytes(12)
    hdr = bytearray(0x100)
    struct.pack_into('<4sIII', hdr, 0, b'NSO0', 0, 0, 0)
    f = 0x100
    for i, (sec, mem) in enumerate((('.text', 0), ('.rodata', ro_off), ('.data', data_off))):
        struct.pack_into('<III', hdr, 0x10 + 0x10 * i, f, mem, len(seg[sec]))
        struct.pack_into('<I', hdr, 0x60 + 4 * i, len(seg[sec]))
        f += len(seg[sec])
    struct.pack_into('<I', hdr, 0x3C, bss_size)
    hdr[0x40:0x60] = build_id
    struct.pack_into('<IIIIII', hdr, 0x88, 0, 0, addr['__dynstr'] - ro_off, 1, addr['__dynsym'] - ro_off, 24)
    nso = bytes(hdr) + body
    open(os.path.join(out, 'exefs', MODULE_NAME), 'wb').write(nso)
    image = align(data_off + len(seg['.data']) + bss_size)

    # hooks for main
    patches = []
    for site, kind, sym in SITES:
        rel = delta + addr[sym] - site
        if not -(1 << 27) <= rel < (1 << 27):
            sys.exit('hook at %#x cannot reach the module' % site)
        patches.append((site, struct.pack('<I', (0x14000000 if kind == 'b' else 0x94000000) | ((rel >> 2) & 0x3FFFFFF))))
    ips = b'IPS32' + b''.join(struct.pack('>IH', o + 0x100, len(d)) + d for o, d in patches) + b'EEOF'
    open(os.path.join(out, 'exefs', BUILD_ID + '.ips'), 'wb').write(ips)
    lines = ['@nsobid-' + BUILD_ID + '0' * 24, '',
             '# Lens of Truth outfit swap v11, CODE MODULE TEST BUILD: hooks only, code lives in exefs/%s' % MODULE_NAME,
             '# Module expected at main+%#x (rtld, main, subsdk0, %s). Reference copy; the mod uses the .ips.' % (delta, MODULE_NAME),
             '@flag offset_shift 0x100', '', '@enabled'] + ['%08X %s' % (o, d.hex().upper()) for o, d in patches] + ['@stop', '']
    open(os.path.join(out, 'lens_module_v11_hooks.pchtxt'), 'w').write('\n'.join(lines))
    code = addr['hook']
    print('module %s: text %#x, ro %#x+%#x, data %#x+%#x, bss %#x, image %#x, %d bytes on disk' % (
        MODULE_NAME, len(seg['.text']), ro_off, len(seg['.rodata']), data_off, len(seg['.data']), bss_size, image, len(nso)))
    print('lens code at module+%#x = main+%#x (%d bytes); module at main+%#x' % (
        code, delta + code, len(seg['.text']) - code, delta))
    print('build id', build_id[:20].hex().upper())


if __name__ == '__main__':
    main()
