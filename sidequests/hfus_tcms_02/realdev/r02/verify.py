"""Independent direct-array and HTTP checks; never invokes the transform adapter."""
import itertools
import json
import math
from pathlib import Path
import urllib.request
import urllib.error
import numpy as np
from bootstrap import ROOT,OUT,sha,write
from preview import load


def get(base,path,expected=200,method='GET'):
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,method=method),timeout=60) as response:
            status=response.status;body=json.load(response)
    except urllib.error.HTTPError as e:
        with e:status=e.code;body=json.load(e)
    assert status==expected,(path,status,body)
    return body


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--http',action='store_true');a=ap.parse_args()
    protocol=load(OUT/'PROTOCOL_V1.json');transform=load(OUT/'TRANSFORM_V1.json')
    R=np.asarray(transform['R']);t=np.asarray(transform['t']);path=OUT/'full_final'
    if a.http:
        service=load(OUT/'SERVICE_FINAL.json');base='http://127.0.0.1:%d'%service['address'][1]
        results=[]
        for fi in protocol['browser_frames']:
            f=get(base,'/api/frame?fi='+str(fi))
            assert f['tag']['transform_id']==transform['transform_id'] and f['state']=='CANDIDATE_PLANE_PREVIEW'
            assert not any(f[k] for k in ['geometry_validated','ground_identity_confirmed','physical_verified','runtime_eligible','near_ground_hard_delete'])
            assert len(f['current'])<=9000 and all(x['fi']<=fi for x in f['trajectory'])
            for row in f['current']:
                assert row['tag']==f['tag'] and row['raw_tag']==f['raw_tag']
                if row['valid']:np.testing.assert_allclose(row['local_xyz'],np.asarray(row['raw_xyz'])@R.T+t,atol=1e-12,rtol=0)
                else:assert row['raw_xyz']==row['local_xyz']
            assert len(f['map'])==(0 if fi<=192 else 3000)
            for m in f['map']:
                assert m['tag']==f['tag']
                np.testing.assert_allclose(m['local_xyz'],np.asarray(m['raw_xyz'])@R.T+t,atol=1e-12,rtol=0)
            row=next(x for x in f['current'] if x['valid'])
            source=get(base,'/api/source?fi=%d&row=%d'%(fi,row['source_row']))
            assert len(source['raw_bytes_hex'])==56 and source['byte_offset']==source['global_row']*28
            assert source['coordinate_version']==source['tag']['coordinate_version'] and source['source_coordinate_version']==source['raw_tag']['coordinate_version']
            decoded=np.frombuffer(bytes.fromhex(source['raw_bytes_hex'])[:12],dtype='<f4')
            np.testing.assert_array_equal(decoded,source['raw_xyz'])
            np.testing.assert_allclose(source['local_xyz'],decoded@R.T+t,atol=1e-12,rtol=0)
            if fi>192:
                m=get(base,'/api/surface?fi=%d&id=0'%fi)
                for s in m['support']:
                    assert s['coordinate_version']==s['tag']['coordinate_version']
                    np.testing.assert_allclose(s['local_xyz'],np.asarray(s['raw_xyz'])@R.T+t,atol=1e-12,rtol=0)
            results.append(dict(fi=fi,rows=f['original_denominator'],shown=len(f['current']),map=len(f['map']),
                boxes=len(f['candidates']),track=f['track']['state'],source_row=source['source_row'],PASS=True))
        for suffix in ['/api/source?fi=430&row=-1','/api/frame?fi=780','/api/frame?fi=430&transform_id=stale',
                '/api/frame?fi=430&coordinate_version=stale','/api/surface?fi=192&id=0']:
            get(base,suffix,400)
        get(base,'/api/frame',405,'POST')
        write(OUT/'HTTP_CHECK.json',dict(url=base,cases=results,negative_checks=6,PASS=True))
        print('PASS HTTP',len(results),'frames + 6 negative checks')
    else:
        source=Path(protocol['source']['path']);meta=load(source/'meta.json')
        buffer=np.memmap(source/'points.bin',mode='r',dtype='u1')
        xyz=np.ndarray((meta['total_points'],3),dtype='<f4',buffer=buffer,strides=(28,4))
        rows=valid=0;maxerror=0.;maxinverse=0.;max32=0.;candidates=0;members=0
        oldrun=ROOT/protocol['frozen_run']
        for fi,frame in enumerate(meta['frames']):
            n=frame['count_points'];offset=frame['offset_points'];assert offset==rows
            p=xyz[offset:offset+n].astype(float);q=np.load(path/('%04d.npy'%fi),allow_pickle=False)
            good=np.isfinite(p).all(axis=1)&np.any(p!=0,axis=1)
            expected=p[good]@R.T+t
            error=np.linalg.norm(q[good]-expected,axis=1)
            norm=np.linalg.norm(p[good],axis=1)
            inv=np.linalg.norm((q[good]-t)@R-p[good],axis=1)
            display=np.linalg.norm(q[good].astype('f4').astype(float)-q[good],axis=1)
            assert np.all(error<=1e-12) and np.all(inv<=np.maximum(1e-8,1e-12*norm)) and np.all(display<=np.maximum(1e-5,1e-6*norm))
            assert np.array_equal(p[~good].view('u8'),q[~good].view('u8'))
            r=load(path/('%04d.json'%fi));old=load(oldrun/('main/%04d.json'%fi))
            assert r['accounting']==old['accounting'] and r['original_denominator']==n
            assert r['candidate_map_exists']==old['candidate_map_exists'] and r['track']['rows']==old['track']['rows']
            assert not r['track']['identity_valid_for_coordinate_version']
            assert len(r['candidates'])==len(old['candidates'])
            for before,after in zip(old['candidates'],r['candidates']):
                assert before['rows']==after['rows'] and before['id']==after['id'] and before['count']==after['count']
                np.testing.assert_allclose(after['center'],np.asarray(before['center'])@R.T+t,atol=1e-12,rtol=0)
                corners=np.array(list(itertools.product(*zip(before['min'],before['max']))))
                np.testing.assert_allclose(after['obb_corners'],corners@R.T+t,atol=1e-12,rtol=0)
                members+=len(before['rows']);candidates+=1
            if old['track']['center'] is not None:
                np.testing.assert_allclose(r['track']['center'],np.asarray(old['track']['center'])@R.T+t,atol=1e-12,rtol=0)
            maxerror=max(maxerror,float(error.max(initial=0)));maxinverse=max(maxinverse,float(inv.max(initial=0)));max32=max(max32,float(display.max(initial=0)))
            rows+=n;valid+=int(good.sum())
        with np.load(oldrun/'map/surfaces.npz') as m:
            support=m['support_global'];saved=np.memmap(path/'map/support_local_xyz.bin',mode='r',dtype='<f8',shape=(len(support),3))
            support_error=0.
            for at in range(0,len(support),50000):
                raw=xyz[support[at:at+50000]].astype(float)
                err=np.linalg.norm(saved[at:at+50000]-(raw@R.T+t),axis=1)
                assert np.all(err<=1e-12);support_error=max(support_error,float(err.max(initial=0)))
            np.testing.assert_allclose(np.load(path/'map/centers.npy'),m['centers']@R.T+t,atol=1e-12,rtol=0)
            np.testing.assert_allclose(np.load(path/'map/matching_tree_xyz.npy'),m['matching_tree_xyz']@R.T+t,atol=1e-12,rtol=0)
            boxes=np.load(path/'map/obb_corners.npy')
            for i,(lo,hi) in enumerate(zip(m['minimum'],m['maximum'])):
                corners=np.array(list(itertools.product(*zip(lo,hi))))
                np.testing.assert_allclose(boxes[i],corners@R.T+t,atol=1e-12,rtol=0)
            support_rows=len(support);surfaces=len(m['centers'])
        result=dict(frames=780,rows=rows,valid=valid,invalid=rows-valid,candidates=candidates,candidate_members=members,
            surfaces=surfaces,support_rows=support_rows,direct_formula_max_m=maxerror,roundtrip_max_m=maxinverse,
            float32_max_m=max32,support_direct_formula_max_m=support_error,
            source_final={k:sha(source/n) for k,n in [('meta','meta.json'),('points','points.bin')]},
            method='independent direct NumPy formulas, all persisted rows/objects, no Transform adapter calls',PASS=True)
        n=np.asarray(transform['plane']['normal']);d=transform['plane']['d_m']
        uv=np.random.RandomState(42).normal(size=(1000,2));plane_points=-d*n+uv@R[:2]
        result.update(det_R=float(np.linalg.det(R)),orthogonal_max=float(np.abs(R@R.T-np.eye(3)).max()),
            historical_plane_math_z_abs_max=float(np.abs((plane_points@R.T+t)[:,2]).max()),
            historical_plane_math_only='self-consistency of historical candidate, not real ground validation')
        write(OUT/'FULL_DIRECT_CHECK.json',result);print(json.dumps(result))
