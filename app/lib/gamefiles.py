# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Find the game's update 131072 romfs from whatever folder the user picks (standard library only).

Accepted, for example (all lead to ...\\updates\\131072\\romfs):
  Game Files            the folder holding base\\ and updates\\ (the documented choice)
  Game Files\\updates    updates\\131072    updates\\131072\\romfs    updates\\131072\\exefs
  a folder inside the romfs (e.g. romfs\\Pack), or a parent folder a few levels above Game Files
  an emulator RomFS dump that is already on update 131072
The version is checked with the build ID in exefs/main next to the romfs, not with folder names, so the base
game or another update is refused with a clear reason. Dumps without exefs are accepted when they hold the
needed files (a folder named 131072 is preferred).
.nup game archives are handled by the converter (lib/nup.py), not here."""
import os

BUILD_ID = 'E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348'   # main of update 131072
RESTBL = 'System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs'
MAX_DEPTH = 4            # how far below the picked folder to look
MAX_DIRS = 4000          # stop a search started too high up (e.g. a whole drive)
SKIP = {'converted', 'nup_cache', '__pycache__', '$recycle.bin', 'system volume information', 'windows',
        'program files', 'program files (x86)', 'node_modules', '.git'}


def has_game_files(c):
    return os.path.isfile(os.path.join(c, 'Pack', 'ZsDic.pack.zs')) and os.path.isfile(os.path.join(c, *RESTBL.split('/')))

def build_id(romfs):
    """build ID of exefs/main next to this romfs (upper-case hex), or None when there is no readable exefs"""
    p = os.path.join(os.path.dirname(os.path.abspath(romfs)), 'exefs', 'main')
    try:
        with open(p, 'rb') as f: h = f.read(0x60)
    except OSError: return None
    if len(h) < 0x60 or h[:4] != b'NSO0': return None
    return h[0x40:0x54].hex().upper()

def is_game_romfs(c):
    """any version of this game's romfs (also the base game, which lacks update 131072's size table)"""
    return os.path.isfile(os.path.join(c, 'Pack', 'ZsDic.pack.zs'))

def _rank(c):
    """2 = update 131072 confirmed, 1 = complete romfs without exefs, 0 = another game version, -1 = not usable"""
    b = build_id(c)
    if not has_game_files(c): return (0, b) if b and b != BUILD_ID else (-1, None)
    if b == BUILD_ID: return 2, b
    if b: return 0, b
    return 1, None

def _start(g):
    """the folder to search from: files and exefs/romfs subfolders lead back to the folder that holds them"""
    g = os.path.abspath(os.path.expanduser(g))
    if os.path.isfile(g): g = os.path.dirname(g)
    # inside a romfs (e.g. romfs\Pack\Actor): climb to the romfs so it is found
    p = g
    for _ in range(4):
        if os.path.basename(p).lower() == 'romfs': return os.path.dirname(p)
        if os.path.basename(p).lower() == 'exefs': return os.path.dirname(p)
        q = os.path.dirname(p)
        if q == p: break
        p = q
    return g

def candidates(g):
    """every complete-looking romfs at or below the start folder (depth-limited), nearest first"""
    root = _start(g); out = []; seen = 0
    if is_game_romfs(root): out.append(root)             # an emulator RomFS dump picked directly
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop(0)
        seen += 1
        if seen > MAX_DIRS: break
        try: entries = sorted(os.scandir(d), key=lambda e: e.name.lower())
        except OSError: continue
        for e in entries:
            try:
                if not e.is_dir(): continue
            except OSError: continue
            n = e.name.lower()
            if n == 'romfs':
                if is_game_romfs(e.path): out.append(e.path)
                continue                                    # never search inside a romfs
            if n == 'exefs' or n in SKIP or n.startswith('.'): continue
            if depth + 1 < MAX_DEPTH: stack.append((e.path, depth + 1))
    return out, seen > MAX_DIRS

def find_game_romfs(g):
    """(romfs path or None, message) for a folder the user picked"""
    if not g: return None, 'not set'
    g = os.path.abspath(os.path.expanduser(g))
    if not os.path.exists(g): return None, 'folder not found'
    found, cut = candidates(g)
    ranked = sorted(((_rank(c), i, c) for i, c in enumerate(found)), key=lambda x: (-x[0][0], '131072' not in x[2], x[1]))
    if ranked and ranked[0][0][0] >= 1:
        (r, _), _, c = ranked[0]
        return c, ('update 131072 found' if r == 2 else 'game files found (no exefs to confirm the version)')
    others = [x for x in ranked if x[0][0] == 0]
    if others:
        return None, 'only another game version found here (build %s...); need update 131072' % others[0][0][1][:8]
    if cut: return None, 'update 131072 not found (search stopped: pick a folder closer to the game files)'
    return None, 'update 131072 game files not found here'

def describe(romfs):
    """short form of a found romfs for messages: the last three folders"""
    parts = os.path.normpath(romfs).split(os.sep)
    return os.sep.join(parts[-3:])


if __name__ == '__main__':      # python app/lib/gamefiles.py <folder>: show what would be used
    import sys
    for a in sys.argv[1:] or ['.']:
        p, m = find_game_romfs(a)
        print('%s\n   -> %s%s' % (a, m, ('\n   -> ' + p) if p else ''))
