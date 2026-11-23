// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
// Lens of Truth outfit swap v11 build 5 (compact + fast paths) - OoT (Switch 2) update v131072, main E0F3CCFA...
//   Material prefix "L0_" = normal outfit: vanishes inside the lens iris, shadow only outside it.
//                   "L1_" = lens outfit:   appears only inside the iris, shadow only inside it.
//   Other materials = shared (unaffected).  UNTAGGED actors only (no AppearWith/DisappearWithGlassTruth).
// Iris swap: hook 1 writes p_glass_truth_alpha (-v for L0, +v for L1) and L1 visibility per frame.
// Shadows: each actor whose models use L materials gets a second LocalDepthShadow unit (B, Appear)
//   next to the engine's unit (A, forced Disappear while the lens is on). L1 never casts through A.
// Build 5: same behaviour as build 4 (checked scenario by scenario with difftest.py); the two per-frame
//   hot paths (hook 1's material scan and the shape-filter stubs) are shorter.
        .text

// =================================================================== hook 1 (iris swap)
// gfx-controller per-frame update entry (0x2e1eb10, original "pacibsp"). x0 = G, s0 = dt.
// Runs for every actor every frame: the material scan is a tight pointer walk, and the lens state is
// only read once an L material has been found.
        .global hook
hook:
        stp     x29, x30, [sp, #-0x80]!
        mov     x29, sp
        stp     x19, x20, [sp, #0x10]
        stp     x21, x22, [sp, #0x20]
        stp     x23, x24, [sp, #0x30]
        stp     x25, x26, [sp, #0x40]
        stp     x27, x28, [sp, #0x50]
        stp     x0,  x1,  [sp, #0x60]
        str     d0,       [sp, #0x70]
        ldr     x8, [x0, #0x18]             // actor
        cbz     x8, h_out
        ldr     x8, [x8, #0x270]
        cbz     x8, h_out
        ldr     x0, [x8, #0x8]              // model controller
        cbz     x0, h_out
        ldr     x9, [x0]
        ldr     x9, [x9, #0xf8]
        blr     x9                          // model holder
        cbz     x0, h_out
        mov     x20, x0
        mov     x21, #0
        mov     w25, #-1                    // lens state not read yet (bit31)
h_model:
        ldr     w8, [x20, #0x20]
        cmp     x21, x8
        b.ge    h_out
        ldr     x8, [x20, #0x28]
        ldr     x8, [x8, x21, lsl #3]
        add     x21, x21, #1
        cbz     x8, h_model
        ldr     x22, [x8]                   // M
        cbz     x22, h_model
        mov     x11, x22
        bl      dict_of
        cbz     x11, h_model
        ldr     w28, [x11, #4]              // material count
        add     x23, x11, #0x20             // name pointers, 16 bytes apart
        mov     w24, #-1
h_mat:
        add     w24, w24, #1                // material index
        cmp     w24, w28
        b.hs    h_model
        ldr     x8, [x23], #16              // name (u16 length + chars)
        cbz     x8, h_mat
        ldur    w27, [x8, #2]
        and     w27, w27, #0xffffff
        sub     w27, w27, #0x5f3, lsl #12
        sub     w27, w27, #0x4c             // - "L0_"
        ror     w27, w27, #8                // 0 = L0_, 1 = L1_, anything else = other
        cmp     w27, #1
        b.hi    h_mat
        tbz     w25, #31, 1f
        bl      lens_state
        orr     w25, w0, w1, lsl #1         // bit0 ready (on && v != 0), bit1 on
        mov     w26, w2                     // v (float bits)
1:      adrp    x8, PGTA_STR
        add     x8, x8, :lo12:PGTA_STR
        str     x8, [sp, #0x78]
        mov     x0, x22
        mov     w1, w24
        add     x2, sp, #0x78
        ldr     x8, [x22]
        ldr     x8, [x8, #0xe0]             // find shader param "p_glass_truth_alpha"
        blr     x8
        cmn     w0, #1
        b.eq    3f
        mov     w2, w0
        fmov    s0, w26
        fneg    s1, s0
        cmp     w27, #0
        fcsel   s0, s1, s0, eq              // L0 -> -v, L1 -> +v
        tbnz    w25, #1, 2f
        movi    d0, #0                      // lens off -> 0
2:      mov     x0, x22
        mov     w1, w24
        ldr     x8, [x22]
        ldr     x8, [x8, #0x128]            // set shader param
        blr     x8
3:      mov     x0, x22
        mov     w1, w24
        ldr     x8, [x22]
        ldr     x8, [x8, #0x1d0]            // isMaterialVisible
        blr     x8
        cmp     w27, #0
        cset    w2, eq
        orr     w2, w2, w25
        and     w2, w2, #1                  // enabled: L0 always, L1 only when ready
        and     w0, w0, #1
        cmp     w0, w2
        b.eq    h_mat
        mov     x0, x22
        mov     w1, w24
        ldr     x8, [x22]
        ldr     x8, [x8, #0x1c8]            // setMaterialVisible
        blr     x8
        b       h_mat
h_out:
        ldp     x0,  x1,  [sp, #0x60]
        ldr     d0,       [sp, #0x70]
        ldp     x27, x28, [sp, #0x50]
        ldp     x25, x26, [sp, #0x40]
        ldp     x23, x24, [sp, #0x30]
        ldp     x21, x22, [sp, #0x20]
        ldp     x19, x20, [sp, #0x10]
        ldp     x29, x30, [sp], #0x80
        pacibsp                             // displaced original instruction
        b       ORIG_CONT

// =================================================================== leaf helpers
// The helpers below (except lens_state) only touch x11-x17, so the shape-filter stubs can use them
// without saving anything: at those sites x11-x17 and the flags are dead (see the stubs).
// lens_state: w0 = ready (lens on && v != 0), w1 = on, w2 = v bits.   clobbers x8
lens_state:
        mov     w0, #0
        mov     w1, #0
        mov     w2, #0
        adrp    x8, GOT_GFX
        ldr     x8, [x8, :lo12:GOT_GFX]
        ldr     x8, [x8]
        cbz     x8, 9f
        ldr     x8, [x8, #0x1e8]
        cbz     x8, 9f
        ldr     x8, [x8, #0xb90]            // lens controller
        cbz     x8, 9f
        ldr     w2, [x8, #0xc]              // iris value
        ldr     w8, [x8, #0x10]
        cmp     w8, #0
        cset    w1, gt                      // on: ctrl+0x10 > 0
        tst     w2, #0x7fffffff
        cset    w0, ne
        and     w0, w0, w1
9:      ret

// dict_of: x11 model -> x11 material ResDic (0 if none)
dict_of:
        ldr     x11, [x11, #0xd8]
        cbz     x11, 9f
        ldr     x11, [x11, #0x60]
        cbz     x11, 9f
        ldr     x11, [x11, #0x10]
        cbz     x11, 9f
        ldr     x11, [x11, #0x40]
9:      ret

// mat_kind: x11 model, w16 material index -> w16 = 0 (L0_), 1 (L1_), > 1 (other).   clobbers x11, x17
mat_kind:
        mov     x17, x30
        bl      dict_of
        mov     x30, x17
        cbz     x11, 8f
        ldr     w17, [x11, #4]
        cmp     w16, w17
        b.hs    8f
        add     x11, x11, w16, uxtw #4
        ldr     x11, [x11, #0x20]           // name (u16 length + chars)
        cbz     x11, 8f
        ldur    w16, [x11, #2]
        and     w16, w16, #0xffffff
        sub     w16, w16, #0x5f3, lsl #12
        sub     w16, w16, #0x4c             // - "L0_"
        ror     w16, w16, #8
        ret
8:      mov     w16, #2
        ret

// has_L: x0 model -> w0 = 1 if any material is L0_/L1_.   clobbers x9-x13, x16, x17
has_L:
        mov     x10, x30
        mov     x9, x0
        mov     x11, x0
        bl      dict_of
        mov     w0, #0
        cbz     x11, 9f
        ldr     w12, [x11, #4]
        mov     w13, #0
1:      cmp     w13, w12
        b.hs    9f
        mov     x11, x9
        mov     w16, w13
        bl      mat_kind
        add     w13, w13, #1
        cmp     w16, #1
        b.hi    1b
        mov     w0, #1
9:      mov     x30, x10
        ret

// core_partner: x12 renderer, w13 slot A -> x12 = pool entry of partner B (0 if none), x16 = unit B.
// clobbers x11, x16, x17.  The A<->B link lives in the pool entries' padding (+0x1c):
// A = 0xB000_0000|slotB, B = 0xA000_0000|slotA.
core_partner:
        ldr     w11, [x12, #0xa88]          // pool count
        cmp     w13, w11
        b.hs    9f
        ldr     x16, [x12, #0xa90]          // pool entries (0x20 each)
        cbz     x16, 9f
        add     x17, x16, x13, lsl #5      // (w13 is always written as a 32-bit value)
        ldr     w17, [x17, #0x1c]
        lsr     w12, w17, #16
        cmp     w12, #0xb, lsl #12
        b.ne    9f
        and     w17, w17, #0xffff           // slot B
        cmp     w17, w11
        b.hs    9f
        add     x12, x16, x17, lsl #5       // entry B
        ldr     w16, [x12, #0x1c]
        mov     w11, #0xa0000000
        orr     w11, w11, w13
        cmp     w16, w11
        b.ne    9f
        ldr     x16, [x12, #0x10]           // unit B
        cbz     x16, 9f
        ret
9:      mov     x12, #0
        ret

// drop_partner: x0 renderer, w1 slot A: unlink and free unit B (if any)
drop_partner:
        stp     x29, x30, [sp, #-0x10]!
        mov     x29, sp
        mov     x12, x0
        mov     w13, w1
        bl      core_partner
        cbz     x12, 9f
        str     wzr, [x12, #0x1c]
        ldr     w1, [x12, #8]               // slot B
        ldr     x8, [x0, #0xa90]
        add     x8, x8, x13, lsl #5
        str     wzr, [x8, #0x1c]
        bl      orig_free
9:      ldp     x29, x30, [sp], #0x10
        ret

// =================================================================== unit B lifetime
// init_hook replaces "bl 0xdce3a0" in the shadow component init (0x2e5359c): allocate unit A as the
// game does, then a partner unit B with the same arguments (actor heap, type, name).
        .global init_hook
init_hook:
        stp     x29, x30, [sp, #-0x40]!
        mov     x29, sp
        stp     x19, x20, [sp, #0x10]
        stp     x21, x22, [sp, #0x20]
        stp     x23, x24, [sp, #0x30]
        mov     x19, x0                     // renderer
        mov     x20, x1                     // heap
        mov     w21, w2
        mov     w22, w3                     // type
        mov     x23, x4                     // name
        bl      UNIT_ALLOC
        mov     w24, w0                     // slot A (returned to the game)
        tbnz    w24, #31, 9f
        mov     x0, x19
        mov     x1, x20
        mov     w2, w21
        mov     w3, w22
        mov     x4, x23
        bl      UNIT_ALLOC
        tbnz    w0, #31, 9f
        ldr     w8, [x19, #0xa88]
        cmp     w0, w8
        b.hs    8f
        cmp     w24, w8
        b.hs    8f
        ldr     x9, [x19, #0xa90]
        mov     w10, w0
        add     x10, x9, x10, lsl #5        // entry B
        mov     w11, w24
        add     x11, x9, x11, lsl #5        // entry A
        movz    w12, #0xb000, lsl #16
        orr     w12, w12, w0
        str     w12, [x11, #0x1c]
        movz    w12, #0xa000, lsl #16
        orr     w12, w12, w24
        str     w12, [x10, #0x1c]
        b       9f
8:      mov     w1, w0                      // cannot link -> give B back
        mov     x0, x19
        bl      orig_free
9:      mov     w0, w24
        ldp     x23, x24, [sp, #0x30]
        ldp     x21, x22, [sp, #0x20]
        ldp     x19, x20, [sp, #0x10]
        ldp     x29, x30, [sp], #0x40
        ret

// attach_hook replaces "bl 0x4efb60" in the actor gfx setup loop (0x4ee6ac; caller x22 = model
// holder, x23 = count, x24 = index; x0 = unit A, x1 = model). After the last model: if no model of the
// holder uses L materials, free unit B.
        .global attach_hook
attach_hook:
        stp     x29, x30, [sp, #-0x40]!
        mov     x29, sp
        stp     x19, x20, [sp, #0x10]
        stp     x21, x22, [sp, #0x20]
        stp     x23, x24, [sp, #0x30]
        mov     x19, x0                     // unit A
        mov     x20, x22                    // holder
        mov     x21, x23                    // count
        mov     x22, x24                    // index
        bl      UNIT_ATTACH
        add     x8, x22, #1
        cmp     x8, x21
        b.ne    9f                          // not the last model yet
        mov     x23, #0
1:      cmp     x23, x21
        b.ge    2f
        ldr     x8, [x20, #0x28]
        ldr     x8, [x8, x23, lsl #3]
        add     x23, x23, #1
        cbz     x8, 1b
        ldr     x0, [x8]
        cbz     x0, 1b
        bl      has_L
        cbnz    w0, 9f                      // keep unit B
        b       1b
2:      ldr     x0, [x19, #0x868]           // renderer
        cbz     x0, 9f
        ldr     w1, [x19, #0x824]           // slot A
        bl      drop_partner
9:      ldp     x23, x24, [sp, #0x30]
        ldp     x21, x22, [sp, #0x20]
        ldp     x19, x20, [sp, #0x10]
        ldp     x29, x30, [sp], #0x40
        ret

// free_hook replaces the first instruction (pacibsp) of the unit free function 0x98a4a8(renderer, slot)
        .global free_hook
free_hook:
        pacibsp
        stp     x29, x30, [sp, #-0x20]!
        mov     x29, sp
        stp     x19, x20, [sp, #0x10]
        mov     x19, x0
        mov     w20, w1
        bl      drop_partner
        mov     x0, x19
        mov     w1, w20
        bl      orig_free
        ldp     x19, x20, [sp, #0x10]
        ldp     x29, x30, [sp], #0x20
        retab
orig_free:
        pacibsp
        b       UNIT_FREE_CONT

// =================================================================== shadow registration
// core_dir: x0 model, x1 renderer, x2 R, x3 unit A, x4 entry A, w5 material mask -> w0 = 1 if handled.
// While the lens is on and unit A has a partner: A -> Disappear; B <- A's per-frame state;
// L1 + shared shapes -> B (Appear), B on the active-unit list.
core_dir:
        stp     x29, x30, [sp, #-0x70]!
        mov     x29, sp
        stp     x19, x20, [sp, #0x10]
        stp     x21, x22, [sp, #0x20]
        stp     x23, x24, [sp, #0x30]
        stp     x25, x26, [sp, #0x40]
        stp     x27, x28, [sp, #0x50]
        mov     x19, x0                     // model
        mov     x20, x1                     // renderer
        mov     x21, x2                     // R
        mov     x22, x3                     // unit A
        mov     w24, w5                     // material mask
        str     wzr, [sp, #0x64]            // "B got entries"
        bl      lens_state
        cbz     w0, 90f
        mov     x12, x20
        ldr     w13, [x21, #0x28]
        bl      core_partner
        cbz     x12, 90f
        mov     x25, x12                    // entry B
        mov     x26, x16                    // unit B
        add     x8, x22, #0x5f8             // unit A: Disappear
        mov     w9, #0x20
        ldclr   w9, w9, [x8]
        mov     w9, #0x40
        ldset   w9, w9, [x8]
        ldr     w8, [x22, #0x5f8]           // B flags <- A (keep B's bits 2, 5, 6)
        ldr     w9, [x26, #0x5f8]
        mov     w10, #0x64
        bic     w8, w8, w10
        and     w9, w9, w10
        orr     w8, w8, w9
        str     w8, [x26, #0x5f8]
        mov     x8, #0x5fc                  // copy 0x5fc-0x6d0, 0x7b0-0x834 except 0x824 (slot)
1:      ldr     w9, [x22, x8]
        str     w9, [x26, x8]
2:      add     x8, x8, #4
        cmp     x8, #0x6d0
        b.ne    3f
        mov     x8, #0x7b0
3:      cmp     x8, #0x824
        b.eq    2b
        cmp     x8, #0x834
        b.lo    1b
        ldr     w27, [x25, #8]              // slot B
        ldrsw   x8, [x20, #0xc60]
        adrp    x9, PER_GROUP_TBL
        add     x9, x9, :lo12:PER_GROUP_TBL
        ldr     w8, [x9, x8, lsl #2]        // units per group
        sdiv    w10, w27, w8
        msub    w27, w10, w8, w27           // sub index
        ldr     w11, [x20, #0xb10]
        cmp     w10, w11
        csel    w10, w10, wzr, lo
        ldr     x11, [x20, #0xb18]
        add     x11, x11, w10, sxtw #4
        ldr     x28, [x11, #8]              // B's group draw list
        ldr     x8, [x19, #0x40]
        ldrb    w8, [x8, #0x64]
        ubfiz   w8, w8, #6, #4
        str     w8, [sp, #0x60]
        ldrh    w23, [x19, #0x24]           // shape count
        mov     x21, #0
4:      cmp     x21, x23
        b.ge    6f
        ldr     x8, [x19, #0x30]
        ldrh    w1, [x8, x21, lsl #1]
        mov     x0, x19
        ldr     x8, [x19]
        ldr     x8, [x8, #0x1f0]
        blr     x8                          // shape
        cbz     x0, 5f
        mov     x15, x0
        ldrh    w14, [x15, #0x1a]           // material index
        ldr     x10, [x19, #0x38]
        ldr     x10, [x10, #8]
        mov     w11, #0x14
        umaddl  x10, w14, w11, x10
        ldrh    w12, [x10, #0xe]
        tst     w12, w24
        b.eq    5f
        mov     x11, x19
        mov     w16, w14
        bl      mat_kind
        cbz     w16, 5f                     // L0_ stays out of unit B
        add     x8, x20, #0xb48
        mov     w9, #1
        ldadd   w9, w8, [x8]
        cmp     w8, #2, lsl #12
        b.ge    5f
        ldr     x9, [x20, #0xb40]
        ldr     w10, [x9, #8]
        ldr     x9, [x9, #0x10]
        cmp     w8, w10
        csel    w8, w8, wzr, lo
        mov     w10, #0x18
        smaddl  x8, w8, w10, x9             // draw entry
        mov     w9, #-1
        str     x15, [x8, #0x10]
        str     w9, [x8, #8]
        str     xzr, [x8]
        ldr     x10, [x15, #8]
        ldrh    w11, [x15, #0x1a]
        ldrh    w9, [x15, #0x1e]
        ldr     x10, [x10, #0x38]
        lsl     w9, w9, #2
        and     w9, w9, #0x10
        ldr     x10, [x10, #8]
        mov     w12, #0x14
        umaddl  x10, w11, w12, x10
        ldrb    w10, [x10, #0x10]
        and     w10, w10, #0xf
        orr     w9, w9, w10
        ldr     w10, [sp, #0x60]
        orr     w9, w9, w10
        strh    w9, [x8, #0xe]
        strh    w27, [x8, #0xc]
        ldr     x10, [x28, #0x20]
        add     x9, x28, #0x2c
        mov     w11, #1
        ldadd   w11, w9, [x9]
        str     x8, [x10, w9, sxtw #3]
        mov     w9, #1
        str     w9, [sp, #0x64]
5:      add     x21, x21, #1
        b       4b
6:      ldr     w8, [sp, #0x64]
        cbz     w8, 80f
        add     x8, x26, #0x5f8
        mov     w9, #0x40
        ldclr   w9, w9, [x8]
        mov     w9, #0x20                   // unit B: Appear
        ldset   w9, w9, [x8]
        mov     w9, #4
        ldset   w9, w9, [x8]
        tbnz    w9, #2, 80f
        add     x8, x20, #0xc40
        mov     w9, #1
        ldadd   w9, w8, [x8]
        ldr     w10, [x20, #0xc44]
        cmp     w8, w10
        b.ge    80f
        ldr     x10, [x20, #0xc48]
        str     x25, [x10, w8, sxtw #3]     // active-unit list
80:     mov     w0, #1
        b       99f
90:     mov     w0, #0
99:     ldp     x27, x28, [sp, #0x50]
        ldp     x25, x26, [sp, #0x40]
        ldp     x23, x24, [sp, #0x30]
        ldp     x21, x22, [sp, #0x20]
        ldp     x19, x20, [sp, #0x10]
        ldp     x29, x30, [sp], #0x70
        ret

// ---- site stub frame: [sp] = lr, [sp+0x10 .. 0xa0) = x0-x17
save_rest:
        stp     x0,  x1,  [sp, #0x10]
        stp     x2,  x3,  [sp, #0x20]
        stp     x4,  x5,  [sp, #0x30]
        stp     x6,  x7,  [sp, #0x40]
        stp     x8,  x9,  [sp, #0x50]
        stp     x10, x11, [sp, #0x60]
        stp     x12, x13, [sp, #0x70]
        stp     x14, x15, [sp, #0x80]
        stp     x16, x17, [sp, #0x90]
        ret
restore_rest:
        ldp     x0,  x1,  [sp, #0x10]
        ldp     x2,  x3,  [sp, #0x20]
        ldp     x4,  x5,  [sp, #0x30]
        ldp     x6,  x7,  [sp, #0x40]
        ldp     x8,  x9,  [sp, #0x50]
        ldp     x10, x11, [sp, #0x60]
        ldp     x12, x13, [sp, #0x70]
        ldp     x14, x15, [sp, #0x80]
        ldp     x16, x17, [sp, #0x90]
        ret
        .macro ENTER
        str     x30, [sp, #-0xa0]!
        bl      save_rest
        .endm
        .macro LEAVE
        bl      restore_rest
        ldr     x30, [sp], #0xa0
        .endm

// ---- shape filter stubs (replace "ldrh wN, [xN, #0xe]" = material entry flags).
// L1_ shapes never cast through unit A when the unit has a partner B.
// These run for every shadow-casting shape every frame, so they build no frame and save nothing:
// each site sits right after the engine's "blr getShape" (which by the ABI leaves x9-x17 and the
// flags dead), and nothing between that call and the site sets x11-x17. Only x11-x17 are used here.
        .global fstub1
fstub1:                                     // 0x4fa9a0: shape x0, model x1, renderer x19, R x24 -> w8
        ldrh    w8, [x8, #0xe]
        tbz     w8, #1, 9f
        mov     x11, x1
        mov     x12, x19
        mov     x13, x24
        mov     x14, x30
        bl      f_l1b
        mov     x30, x14
        cbz     x12, 9f
        and     w8, w8, #0xfffffffd
9:      ret
        .global fstub2
fstub2:                                     // inline copy in 0x7bb80: model x19, renderer x20, R x23 -> w8
        ldrh    w8, [x8, #0xe]
        tbz     w8, #1, 9f
        mov     x11, x19
        mov     x12, x20
        mov     x13, x23
        mov     x14, x30
        bl      f_l1b
        mov     x30, x14
        cbz     x12, 9f
        and     w8, w8, #0xfffffffd
9:      ret
        .global fstub3
fstub3:                                     // 0x31c5540: model x8, renderer x28, R x21, mask w25 -> w9
        ldrh    w9, [x9, #0xe]
        tst     w9, w25
        b.eq    9f
        mov     x11, x8
        mov     x12, x28
        mov     x13, x21
        mov     x14, x30
        bl      f_l1b
        mov     x30, x14
        cbz     x12, 9f
        bic     w9, w9, w25
9:      ret
// f_l1b: x0 shape, x11 model, x12 renderer, x13 R -> x12 != 0 if the shape's material is L1_ and the
// unit has a partner B.   clobbers x11-x13, x15-x17
f_l1b:
        mov     x15, x30
        ldrh    w16, [x0, #0x1a]            // shape's material index
        bl      mat_kind
        mov     x30, x15
        cmp     w16, #1
        b.ne    8f                          // only L1_ shapes are moved out of unit A
        ldr     w13, [x13, #0x28]           // slot A
        b       core_partner                // no unit B -> v8 behaviour
8:      mov     x12, #0
        ret

// ---- direction stubs (replace "ldrb w8, [xR, #0x8a]"): handled -> continue after the engine's
// bit5/6 clear; not handled -> re-execute the original load.
        .global dstub1
dstub1:                                     // 0x4fa9a0: renderer x19, R x24, unit x22, entry x23
        ENTER
        ldur    x0, [x29, #-8]
        mov     x1, x19
        mov     x2, x24
        mov     x3, x22
        mov     x4, x23
        mov     w5, #2
        bl      core_dir
        cbnz    w0, 1f
        LEAVE
        ldrb    w8, [x24, #0x8a]
        ret
1:      adrp    x8, CONT1
        add     x8, x8, :lo12:CONT1
        b       dir_handled
        .global dstub2
dstub2:                                     // inline: model x19, renderer x20, R x23, unit x25, entry x26
        ENTER
        mov     x0, x19
        mov     x1, x20
        mov     x2, x23
        mov     x3, x25
        mov     x4, x26
        mov     w5, #2
        bl      core_dir
        cbnz    w0, 1f
        LEAVE
        ldrb    w8, [x23, #0x8a]
        ret
1:      adrp    x8, CONT2
        add     x8, x8, :lo12:CONT2
        b       dir_handled
        .global dstub3
dstub3:                                     // 0x31c5540: renderer x28, R x21, unit x19, entry x20, mask w25
        ENTER
        ldur    x0, [x29, #-8]
        mov     x1, x28
        mov     x2, x21
        mov     x3, x19
        mov     x4, x20
        mov     w5, w25
        bl      core_dir
        cbnz    w0, 1f
        LEAVE
        ldrb    w8, [x21, #0x8a]
        ret
1:      adrp    x8, CONT3
        add     x8, x8, :lo12:CONT3
dir_handled:
        str     x8, [sp]                    // return to the continuation instead
        LEAVE
        ret
