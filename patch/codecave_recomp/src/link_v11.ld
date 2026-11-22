/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt. */
SECTIONS { . = 0x3c46400; .text : { *(.text) } }
GOT_GFX = 0x4c7e740;
ORIG_CONT = 0x2e1eb14;
PGTA_STR = 0x3db413c;
PER_GROUP_TBL = 0x3c834e0;
UNIT_ATTACH = 0x4efb60;
UNIT_ALLOC = 0xdce3a0;
UNIT_FREE_CONT = 0x98a4ac;
CONT1 = 0x4faef4;
CONT2 = 0x830d4;
CONT3 = 0x31c58f0;
F1_BACK = 0x4fae20;
F2_BACK = 0x82ff8;
F3_BACK = 0x31c57c8;
D1_BACK = 0x4faedc;
D2_BACK = 0x830bc;
D3_BACK = 0x31c5890;
