# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""zstd + SARC helpers. Game zstd frames must carry Frame_Content_Size (write_content_size=True)."""
import struct, os, zstandard as z
def sarc_files(d):
    ds=struct.unpack_from('<I',d,0xc)[0]; sf=0x14; n=struct.unpack_from('<H',d,sf+6)[0]
    nodes=[struct.unpack_from('<IIII',d,sf+0xc+16*i) for i in range(n)]; names=sf+0xc+16*n+8; out={}
    for h,attr,s,e in nodes:
        no=names+(attr&0xffff)*4; out[d[no:d.index(b'\0',no)].decode()]=d[ds+s:ds+e]
    return out
class Zs:
    """Loads the game's dictionaries from <romfs>/Pack/ZsDic.pack.zs."""
    def __init__(self, romfs):
        self.d={k:z.ZstdCompressionDict(v) for k,v in sarc_files(z.ZstdDecompressor().decompressobj().decompress(
            open(os.path.join(romfs,'Pack','ZsDic.pack.zs'),'rb').read())).items()}
    def _dict(self,path):
        if path.endswith('.rsizetable.zs'): return None
        if path.endswith('.pack.zs'): return self.d['pack.zsdic']
        if path.endswith('.bcett.byml.zs'): return self.d['bcett.byml.zsdic']
        return self.d['zs.zsdic']
    def read(self,path):
        dd=self._dict(path); dz=z.ZstdDecompressor(dict_data=dd) if dd else z.ZstdDecompressor()
        return dz.decompressobj().decompress(open(path,'rb').read())
    def write(self,path,data,level=19):
        dd=self._dict(path); c=z.ZstdCompressor(level=level,dict_data=dd,write_content_size=True,write_checksum=False).compress(data)
        assert z.get_frame_parameters(c).content_size==len(data)
        os.makedirs(os.path.dirname(path),exist_ok=True); open(path,'wb').write(c); return len(c)
