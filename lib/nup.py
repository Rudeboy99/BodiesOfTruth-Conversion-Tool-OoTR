# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""Read-only access to .nup game archives (the "NX Package" format packed by Eglantine / Eden-family emulators).

A .nup holds the loose ExeFS/RomFS trees of a base game, its updates and DLC in one file:
  superblock (0x80, magic "NUP\\x01") -> table of contents (SHA-256 checked) -> blob region (raw or zstd extents).
All integers little-endian. Layout follows Eglantine src/core/file_sys/nup_container.cpp.

NupRomfs gives BodiesOfTruth a romfs folder: the update's romfs laid over the base romfs, with each file
copied out of the .nup into a cache folder only when the tool first asks for it (a few MB per run, not 25 GB).
BodiesOfTruth deletes the cache when it exits."""
import os, struct, hashlib, json
import zstandard

MAGIC = b'NUP\x01'
TOC_MAGIC = b'TOC\x01'
NO_DIR = 0xFFFFFFFF
KIND = {0: 'base', 1: 'update', 2: 'dlc'}
CHUNK = 4 << 20


class NupError(Exception):
    pass


class Nup:
    """Parsed .nup: packages, and per-package romfs path -> file record."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.f = open(self.path, 'rb')
        sb = self.f.read(0x80)
        if len(sb) < 0x80 or sb[:4] != MAGIC:
            raise NupError('%s is not a .nup archive' % os.path.basename(self.path))
        hsize, _hver, toc_off, toc_size = struct.unpack_from('<HHQQ', sb, 4)
        toc_sha = sb[0x18:0x38]
        self.blob_off, fsize, pkg_count, flags = struct.unpack_from('<QQII', sb, 0x38)
        self.uuid = sb[0x50:0x60].hex()
        if hsize < 0x80 or flags != 0:
            raise NupError('unsupported .nup header (newer format?)')
        if fsize != os.path.getsize(self.path):
            raise NupError('.nup size does not match its header: the file is incomplete or damaged')
        self.f.seek(toc_off)
        toc = self.f.read(toc_size)
        if len(toc) != toc_size or hashlib.sha256(toc).digest() != toc_sha:
            raise NupError('.nup table of contents is damaged (SHA-256 mismatch)')
        if toc[:4] != TOC_MAGIC:
            raise NupError('.nup table of contents not found')
        n_pkg, n_dir, n_file, pool_off, pool_size = struct.unpack_from('<IQQQQ', toc, 4)
        if n_pkg != pkg_count:
            raise NupError('.nup package count mismatch')
        pos = 0x30
        self.packages = []
        for _ in range(n_pkg):
            tid, root, exefs, romfs, ver, kind, pflags = struct.unpack_from('<QIIIIBB', toc, pos)
            self.packages.append(dict(title_id='%016X' % tid, version=ver, kind=KIND.get(kind, kind),
                                      root=root, exefs=exefs, romfs=romfs))
            pos += 0x40
        pool = toc[pool_off:pool_off + pool_size]
        name = lambda o, n: pool[o:o + n].decode('utf-8')
        self.dirs = []
        for no, nl, first, count, _r in struct.iter_unpack('<IIIIQ', toc[pos:pos + 0x18 * n_dir]):
            self.dirs.append((name(no, nl), first, count))
        pos += 0x18 * n_dir
        self.files = []
        for rec in struct.iter_unpack('<IIQQQ32sBB14x', toc[pos:pos + 0x50 * n_file]):
            no, nl, size, eoff, esize, sha, codec, cflags = rec
            if codec > 1 or cflags:
                raise NupError('.nup uses an unknown compression codec %d' % codec)
            self.files.append((name(no, nl), size, eoff, esize, sha, codec))
        pos += 0x50 * n_file
        self.children = struct.unpack_from('<%dI' % ((pool_off - pos) // 4), toc, pos)
        self.n_dir = n_dir

    def walk(self, dir_index, prefix=''):
        """yield (relative path, file index) under a directory node"""
        _n, first, count = self.dirs[dir_index]
        for c in self.children[first:first + count]:
            if c < self.n_dir:
                yield from self.walk(c, prefix + self.dirs[c][0] + '/')
            else:
                fi = c - self.n_dir
                yield prefix + self.files[fi][0], fi

    def romfs_map(self, pkg):
        return {} if pkg['romfs'] == NO_DIR else dict(self.walk(pkg['romfs']))

    def extract(self, fi, dst):
        """copy one member file out (decompressing if needed), checking its size and SHA-256"""
        _n, size, eoff, esize, sha, codec = self.files[fi]
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + '.part'
        h = hashlib.sha256(); out = 0
        dobj = zstandard.ZstdDecompressor().decompressobj() if codec == 1 else None
        with open(tmp, 'wb') as o:
            self.f.seek(eoff); left = esize if size else 0
            while left:
                chunk = self.f.read(min(CHUNK, left))
                if not chunk:
                    break
                left -= len(chunk)
                data = dobj.decompress(chunk) if dobj else chunk
                h.update(data); o.write(data); out += len(data)
        if out != size or h.digest() != sha:
            os.remove(tmp)
            raise NupError('%s is damaged inside the .nup (checksum mismatch)' % self.files[fi][0])
        os.replace(tmp, dst)


class NupRomfs:
    """update romfs over base romfs from a .nup, extracted on demand into <cache_root>/<archive id>/romfs"""

    def __init__(self, path, cache_root, want_version=None):
        self.nup = Nup(path)
        p = self.nup.packages
        base = [x for x in p if x['kind'] == 'base']
        ups = sorted((x for x in p if x['kind'] == 'update'), key=lambda x: x['version'])
        self.version = ups[-1]['version'] if ups else 0
        if want_version is not None and self.version != want_version:
            raise NupError('the .nup holds update %d, but update %d is needed (install the right update and re-pack it)'
                           % (self.version, want_version))
        self.map = {}
        for pkg in base[:1] + ups[-1:]:          # update files win over base files
            self.map.update({rel: fi for rel, fi in self.nup.romfs_map(pkg).items()})
        if not self.map:
            raise NupError('the .nup contains no RomFS')
        top = os.path.join(cache_root, self.nup.uuid[:16])
        self.dir = os.path.join(top, 'romfs')
        os.makedirs(self.dir, exist_ok=True)
        json.dump(dict(source=os.path.basename(self.nup.path), size=os.path.getsize(self.nup.path),
                       update=self.version, note='Game files copied out of the .nup. Do not share.'),
                  open(os.path.join(top, 'nup_source.json'), 'w', encoding='utf-8'), indent=1)

    def has(self, rel):
        return rel in self.map

    def path(self, rel):
        """local path of a romfs file (extracted on first use), or None if the game has no such file"""
        fi = self.map.get(rel)
        if fi is None:
            return None
        dst = os.path.join(self.dir, *rel.split('/'))
        if not (os.path.isfile(dst) and os.path.getsize(dst) == self.nup.files[fi][1]):
            self.nup.extract(fi, dst)
        return dst


_OPEN = {}   # cache romfs dir -> NupRomfs


def find_nup(g):
    """a .nup file, or the only .nup directly inside a folder; else None"""
    if os.path.isfile(g):
        return g if g.lower().endswith('.nup') else None
    if os.path.isdir(g):
        c = sorted(f for f in os.listdir(g) if f.lower().endswith('.nup') and os.path.isfile(os.path.join(g, f)))
        return os.path.join(g, c[0]) if len(c) == 1 else None
    return None


def open_romfs(path, cache_root, want_version=None, need=()):
    """open a .nup, pre-extract the files in `need`, and return the cache romfs folder"""
    r = NupRomfs(path, cache_root, want_version)
    for rel in need:
        if not r.path(rel):
            raise NupError('%s is missing from the .nup' % rel)
    _OPEN[os.path.normcase(os.path.abspath(r.dir))] = r
    return r.dir


def close_all():
    """close every open .nup (so its cache folder can be deleted on Windows)"""
    for r in _OPEN.values():
        try: r.nup.f.close()
        except OSError: pass
    _OPEN.clear()


def source(romfs):
    """the NupRomfs behind a cache romfs folder returned by open_romfs, else None"""
    return _OPEN.get(os.path.normcase(os.path.abspath(romfs))) if romfs else None
