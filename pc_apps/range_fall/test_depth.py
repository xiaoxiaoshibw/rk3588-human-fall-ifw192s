import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import zlib

import numpy as np

from analysis import AnalysisStore
from depth import export_depth


def pixels(raw):
    width,height,bits,color,_,_,_=struct.unpack('>IIBBBBB',raw[16:29])
    compressed=b'';pos=8
    while pos<len(raw):
        n=struct.unpack('>I',raw[pos:pos+4])[0];kind=raw[pos+4:pos+8];data=raw[pos+8:pos+8+n]
        if kind==b'IDAT':compressed+=data
        pos+=n+12
    stride=width*(3 if color==2 else 1)*(bits//8)
    rows=np.frombuffer(zlib.decompress(compressed),dtype=np.uint8).reshape(height,stride+1)
    assert (rows[:,0]==0).all()
    data=rows[:,1:].copy().tobytes()
    return np.frombuffer(data,dtype='>u2' if bits==16 else 'u1').reshape(height,-1)


class TestDepth(unittest.TestCase):
    def fixture(self,root):
        ranges=np.full((192,256),np.nan);ranges[0,:4]=[1.2344,65.534,65.535,22.35]
        rows=np.full((192,256),-1,dtype=int);rows[0,:4]=[5,1,7,2]
        frame=SimpleNamespace(valid=rows>=0,range_m=ranges,source_rows=rows,grid=SimpleNamespace(sha256='grid'))
        identity={'session':'sid','grid_sha256':'grid'}
        return export_depth(frame,[1,7],root,3,100.3,'raw',identity)

    def test_png16_big_endian_invalid_overflow_and_exact_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=self.fixture(root)
            a=pixels((root/d['metric']['path']).read_bytes())
            self.assertEqual(a[-1,-5:].tolist(),[0,22350,65535,65534,1234])
            self.assertEqual(int(a[0,0]),0)
            self.assertEqual((d['version'],d['nativeTransform']),(2,'rotate180'))
            mask=pixels((root/d['mask']['path']).read_bytes())
            self.assertEqual(mask[-1,-5:].tolist(),[0,0,255,255,0])
            self.assertEqual((d['validPixels'],d['targetPixels'],d['overflowPixels']),(4,2,1))
            meta=json.loads((root/d['metadata']['path']).read_bytes())
            self.assertEqual(meta['rawSha256'],'raw')

    def test_asset_integrity_binding_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=self.fixture(root)
            row=dict(frameIndex=3,stampSec=100.3,rawSha256='raw',depth=d)
            store=AnalysisStore([],root);store.roots['sid']=root
            store.frame=lambda sid,index:dict(frame=row,manifest={'sourceBinding':{'session':'sid','grid_sha256':'grid'}})
            self.assertTrue(store.asset('sid',3,'metric').startswith(b'\x89PNG'))
            d['gridSha256']='other'
            with self.assertRaises(ValueError):store.asset('sid',3,'metric')
            d['gridSha256']='grid'
            for path in ('../secret','C:/secret','/secret'):
                old=d['metric']['path'];d['metric']['path']=path
                with self.assertRaises(ValueError):store.asset('sid',3,'metric')
                d['metric']['path']=old
            (root/d['metric']['path']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):store.asset('sid',3,'metric')
            d['frameIndex']=4
            with self.assertRaises(ValueError):store.asset('sid',3,'preview')


if __name__=='__main__':unittest.main()
