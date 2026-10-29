"""Candidate-only coordinate adapter; no ground validity constructor is bypassed."""
import copy
import itertools
import numpy as np

RAW = 'innolidar'
RAW_VERSION = 'RAW_UNVERIFIED_INSTALLATION/v1'


def valid_xyz(p):
    p = np.asarray(p)
    return np.isfinite(p).all(axis=-1) & np.any(p != 0, axis=-1)


def plane_basis(normal, d, reference_axis):
    n = np.asarray(normal, dtype=float)
    a = np.asarray(reference_axis, dtype=float)
    if n.shape != (3,) or a.shape != (3,) or not np.isfinite(n).all() or not np.isfinite(a).all() or not np.isfinite(d):
        raise ValueError('Nonfinite/invalid plane or reference')
    norm = np.linalg.norm(n)
    if norm < 1e-12:
        raise ValueError('Degenerate normal')
    n, d = n/norm, float(d)/norm
    u = a-np.dot(a,n)*n
    if np.linalg.norm(u) < 1e-8:
        raise ValueError('Reference axis degeneracy; no registered fallback')
    u /= np.linalg.norm(u)
    R = np.vstack([u,np.cross(n,u),n])
    return R, -R@(-d*n), n, d


class Transform:
    def __init__(self, artifact):
        self.artifact = copy.deepcopy(artifact)
        self.R = np.asarray(artifact['R'], dtype=float)
        self.t = np.asarray(artifact['t'], dtype=float)
        self.id = artifact['transform_id']
        self.version = artifact['coordinate_version']
        if (artifact['from_frame'] != RAW or artifact['to_frame'] != 'candidate_local' or
                artifact['units'] != 'm' or not self.id or not self.version):
            raise ValueError('Wrong transform direction/units/version')
        if (self.R.shape != (3,3) or self.t.shape != (3,) or not np.isfinite(self.R).all() or not np.isfinite(self.t).all() or
                not np.allclose(self.R@self.R.T,np.eye(3),atol=1e-10,rtol=0) or abs(np.linalg.det(self.R)-1)>1e-10):
            raise ValueError('Nonfinite, reflection or nonorthogonal transform')
        plane = artifact['plane']
        n=np.asarray(plane['normal']);d=plane['d_m']
        if not np.allclose(self.R[2],n,atol=1e-12,rtol=0) or abs(self.t[2]-d)>1e-12:
            raise ValueError('Plane/transform direction mismatch')
        if (artifact.get('state') != 'CANDIDATE_PLANE_PREVIEW' or artifact.get('mode') != 'OFFLINE_REVIEW' or
                any(artifact['qualification'].values())):
            raise ValueError('Candidate cannot gain geometry/identity/physical/runtime qualification')

    def tag(self, fi, local=True):
        return dict(fi=fi, frame='candidate_local' if local else RAW,
                    transform_id=self.id if local else None,
                    coordinate_version=self.version if local else RAW_VERSION)

    def require_raw(self, tag, fi):
        if tag != self.tag(fi,False):
            raise ValueError('Wrong frame/version/fi or repeated transform')

    def points(self, xyz, tag, fi, source_validity=False):
        self.require_raw(tag,fi)
        p = np.asarray(xyz,dtype=float)
        if p.shape[-1:] != (3,):
            raise ValueError('Expected XYZ')
        result = p.copy()
        if source_validity:
            mask=valid_xyz(p)
            result[mask]=p[mask]@self.R.T+self.t
        else:
            if not np.isfinite(p).all():
                raise ValueError('Nonfinite object coordinate')
            result=p@self.R.T+self.t
        return result

    def inverse(self,xyz):
        return (np.asarray(xyz)-self.t)@self.R

    def vectors(self,v):
        a=np.asarray(v,dtype=float)
        if a.shape[-1:]!=(3,) or not np.isfinite(a).all():
            raise ValueError('Invalid direction/velocity')
        return a@self.R.T

    def covariance(self,sigma):
        s=np.asarray(sigma,dtype=float)
        if s.shape[-2:]!=(3,3) or not np.isfinite(s).all():
            raise ValueError('Invalid covariance')
        return self.R@s@self.R.T

    def box(self,lo,hi,fi):
        lo,hi=np.asarray(lo),np.asarray(hi)
        if lo.shape!=(3,) or hi.shape!=(3,) or np.any(lo>hi):
            raise ValueError('Invalid box')
        corners=np.array(list(itertools.product(*zip(lo,hi))))
        return self.points(corners,self.tag(fi,False),fi)

    def object(self,obj,fi):
        self.require_raw({k:obj[k] for k in self.tag(fi,False)},fi)
        out=copy.deepcopy(obj)
        for key in ['center','position','predicted_center']:
            if out.get(key) is not None:
                out[key]=self.points(out[key],self.tag(fi,False),fi).tolist()
        for key in ['velocity','direction']:
            if out.get(key) is not None:
                out[key]=self.vectors(out[key]).tolist()
        if out.get('covariance') is not None:
            out['covariance']=self.covariance(out['covariance']).tolist()
        if 'min' in out or 'max' in out:
            out['obb_corners']=self.box(out.pop('min'),out.pop('max'),fi).tolist()
        out.update(self.tag(fi))
        if out.get('version'):
            out['historical_version']=out['version']
            out['version']=out['version']+'/'+self.id
        if 'identity_source' in out:
            out['historical_identity_source']=out.pop('identity_source')
        out.update(identity_valid_for_coordinate_version=False,human_confirmation=False)
        return out


def check_points(T, raw, local):
    mask=valid_xyz(raw)
    p,q=raw[mask],local[mask]
    e64=np.linalg.norm(T.inverse(q)-p,axis=1)
    e32=np.linalg.norm(q.astype('f4').astype(float)-q,axis=1)
    norm=np.linalg.norm(p,axis=1)
    tol64=np.maximum(1e-8,1e-12*norm)
    tol32=np.maximum(1e-5,1e-6*norm)
    plane=p@T.R[2]+T.t[2]
    if (np.any(e64>tol64) or np.any(e32>tol32) or not np.allclose(q[:,2],plane,atol=1e-12,rtol=1e-12) or
            not np.array_equal(raw[~mask].view('u8'),local[~mask].view('u8'))):
        raise ValueError('Coordinate conservation/tolerance failure')
    return dict(valid=int(mask.sum()),invalid=int((~mask).sum()),
        roundtrip_max_m=float(e64.max(initial=0)), display_float32_max_m=float(e32.max(initial=0)),
        z_equation_max_m=float(np.abs(q[:,2]-plane).max(initial=0)))
