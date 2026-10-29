"""One rigid ground transform for every replay object; raw analysis stays bound."""
import json
from pathlib import Path
import numpy as np

class GroundCoordinates:
    def __init__(self,path,sid,binding):
        self.artifact=json.loads(Path(path).read_text(encoding='utf8'))
        a=self.artifact
        if a['sid']!=sid or a['source_sha256']!=binding or a['from_frame']!='RAW/innolidar' or a['units']!='m':
            raise ValueError('ground transform does not match this source')
        self.R=np.asarray(a['R'],float);self.t=np.asarray(a['t'],float)
        if self.R.shape!=(3,3) or self.t.shape!=(3,) or not np.isfinite(self.R).all() or not np.isfinite(self.t).all():
            raise ValueError('invalid ground matrix')
        if not np.allclose(self.R@self.R.T,np.eye(3),atol=1e-10,rtol=0) or abs(np.linalg.det(self.R)-1)>1e-10:
            raise ValueError('ground matrix must be a proper rotation')
        self.frame=a['to_frame']

    def points(self,points,space='ground'):
        p=np.asarray(points,dtype=float)
        if p.size==0:p=p.reshape(0,3)
        if p.shape[-1:]!=(3,) or not np.isfinite(p).all():raise ValueError('finite XYZ required')
        if space=='ground':return p@self.R.T+self.t
        if space=='raw':return p.copy()
        raise ValueError('unknown coordinate space')
