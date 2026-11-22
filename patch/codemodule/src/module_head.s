// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
// Lens Outfit Swap v11 as a separate code module (subsdk1) - OoT (Switch 2) v131072.
// Module header, MOD0 and a minimal dynamic section (no imports, no exports, no relocations),
// so the game's rtld accepts the module. The lens code itself is lensswap_v11.s, unchanged.
        .section .text.head, "ax"
        .global __module_start
__module_start:
        .word   0                               // not an entry point
        .word   __mod0 - __module_start
        .p2align 4
__mod0:
        .ascii  "MOD0"
        .word   _DYNAMIC        - __mod0
        .word   __bss_start     - __mod0
        .word   __bss_end       - __mod0
        .word   __eh_frame_hdr  - __mod0
        .word   __eh_frame_hdr  - __mod0        // empty: no unwind info
        .word   __module_object - __mod0
        .p2align 2
        .global __lens_init_stub
__lens_init_stub:                               // DT_INIT / DT_FINI target: nothing to do
        ret

        .section .rodata.dyn, "a"
        .p2align 3
        .global __dynsym, __dynstr, __hash, __gnu_hash
__dynsym:                                       // one null symbol
        .zero   24
__dynstr:
        .byte   0
        .p2align 3
__hash:                                         // SysV hash: 1 bucket, 1 chain, all empty
        .word   1, 1, 0, 0
        .p2align 3
__gnu_hash:                                     // GNU hash: 1 bucket, symoffset 1, 1 bloom word = 0
        .word   1, 1, 1, 0
        .quad   0
        .word   0
        .p2align 3
__eh_frame_hdr:
        .word   0

        .section .data.dyn, "aw"
        .p2align 3
        .global _DYNAMIC
_DYNAMIC:                                       // values: offsets from the module start (set in the linker script)
        .quad   4,  DYN_HASH        // DT_HASH
        .quad   0x6ffffef5, DYN_GNU_HASH // DT_GNU_HASH
        .quad   5,  DYN_STRTAB      // DT_STRTAB
        .quad   6,  DYN_SYMTAB      // DT_SYMTAB
        .quad   10, 1                                   // DT_STRSZ
        .quad   11, 24                                  // DT_SYMENT
        .quad   12, DYN_INIT    // DT_INIT
        .quad   13, DYN_INIT    // DT_FINI
        .quad   0x1e, 8                                 // DT_FLAGS = BIND_NOW
        .quad   0x6ffffffb, 1                           // DT_FLAGS_1 = NOW
        .quad   0,  0                                   // DT_NULL

        .section .bss.modobj, "aw", %nobits
        .p2align 4
__module_object:                                // rtld writes its module object here
        .zero   0x200
