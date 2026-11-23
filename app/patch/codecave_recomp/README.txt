Lens Outfit Swap v11 build 6 - recompiler-safe code cave (Longshot / Hookshot)
STATUS: WORKING in-game on Longshot nightly-612-89c3d21e (2026-11-20, Gerudo Fortress, lens swap OK).
  Known issue: at non-16:9 aspect ratios (Longshot widescreen/ultrawide) the lens iris is
  misaligned. The iris shape comes from the game's lens system, not this patch; not fixed yet.
==========================================================================

Same lens behaviour as build 5 (patch/codecave), rewritten for static recompilers that
translate the game's code ahead of time (Longshot's a64-kit lift). Build 5 crashes there:
its helpers passed values in x11/x12/x9 and its direction stubs returned by rewriting x30,
which a lift that turns BL into a C call and RET into a C return does not keep.

Build 6:
  - helpers are ordinary AAPCS64 functions (args x0-x7, result x0/x1, no return tricks)
  - the 6 mid-function sites (shape filter + direction) are reached by B, not BL, and
    branch back to site+4 / the engine continuation; they save x0-x17 and x30 themselves
  - cave 0x3C46400-0x3C46EB4 (2,740 bytes, 332 free); same 10 hook sites
  - also correct on hardware and emulators (same results as build 5)

Install for Longshot (BodiesOfTruth README 2b): the converter's LensPatch folder holds
only E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348.ips (no build-5 .ips/.pchtxt next to it: the
later file would overwrite bytes). Place the mod(s) at <build version>\mods\<mod name>\
and rebuild once (Longshot Builder --update) to install the lens swap. Swapping converted
model mods needs no rebuild.

Checked: test/difftest_longshot.py runs every scenario of build 5's difftest (8,892) through
build 5 as a console runs it and build 6 under a model of Longshot's lift; 0 differences, and
build 6 keeps every register at the stub sites. Build 5 under the same model crashes at
cave+0x1EC, the address in Longshot's crash log.
  python3 test/difftest_longshot.py <build5 dir> <build6 dir>          (Longshot model)
  python3 test/difftest_longshot.py <build5 dir> <build6 dir> --emu    (console model)
Each dir needs v11.elf + cave11.bin (src/build_patch_v11.py makes them).
