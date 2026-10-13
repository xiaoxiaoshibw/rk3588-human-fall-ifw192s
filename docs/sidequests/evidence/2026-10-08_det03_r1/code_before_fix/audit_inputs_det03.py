"""Independent source-row and encoder audit against frozen DET-02 inputs."""
import ast
import json
from pathlib import Path
import struct

import numpy as np
import torch
from cpu_pointpillars import load_model
from experiment import read_frame, adapt, sha

ROOT=Path(__file__).resolve().parent


def main(out):
    prep=ROOT/'artifacts/det02_prepared_r1';fg=ROOT/'artifacts/det02_foreground_r1'
    m=json.loads((prep/'manifest.json').read_text(encoding='utf-8'))
    fm=json.loads((fg/'manifest.json').read_text(encoding='utf-8'))
    rows=[]
    for s in m['sessions']:
        rawdir=Path(s['raw_directory']);tf=json.loads(Path(s['transform_path']).read_text(encoding='utf-8'))
        assert sha(rawdir/'meta.json')==s['source']['meta_sha256'] and sha(rawdir/'points.bin')==s['source']['bin_sha256']
        assert sha(Path(s['transform_path']))==s['transform_sha256'] and tf['source']==s['source']
        meta=json.loads((rawdir/'meta.json').read_text(encoding='utf-8'));stride=meta['point_stride_bytes']
        for fr in s['frames']:
            orig,info=read_frame(rawdir,fr['index'])
            # Separate struct decoder, not np.ndarray striding: prove XYZI offsets.
            with (rawdir/'points.bin').open('rb') as f:
                f.seek(info['offset_points']*stride);data=f.read(info['count_points']*stride)
            independent=np.array([struct.unpack_from('<4f',data,i*stride) for i in range(len(orig))],dtype='f4')
            np.testing.assert_array_equal(independent,orig)
            valid=np.any(orig[:,:3]!=0,axis=1)
            prepared=np.fromfile(prep/s['sid']/fr['file'],dtype='<f4').reshape(-1,4)
            assert sha(prep/s['sid']/fr['file'])==fr['sha256']
            np.testing.assert_array_equal(prepared,adapt(orig,tf,0,1))
            source_rows=np.fromfile(prep/s['sid']/(fr['file']+'.rows'),dtype='<i8')
            np.testing.assert_array_equal(source_rows,np.flatnonzero(valid)+info['offset_points'])
            variants=0
            target=next((t for t in fm['sessions'] if t['sid']==s['sid']),None)
            if target:
                for name,rec in target['frames'][fr['index']]['variants'].items():
                    p=fg/s['sid']/rec['file'];ids=np.fromfile(str(p)+'.ids',dtype='<u4')
                    assert sha(p)==rec['sha256'] and sha(Path(str(p)+'.ids'))==rec['ids_sha256']
                    np.testing.assert_array_equal(np.fromfile(p,dtype='<f4').reshape(-1,4),prepared[ids]);variants+=1
            rows.append(dict(sid=s['sid'],index=fr['index'],stride=stride,source_points=len(orig),zero_xyz=int((~valid).sum()),
                             intensity_percentiles=np.percentile(orig[valid,3],[0,50,99,100]).tolist(),variants_checked=variants,
                             source_rows_equal=True,decode_equal=True,leveling_equal=True))
    up=ROOT/'artifacts/upstream';model=load_model(up/'epoch_160.pth',up);torch.set_num_threads(4)
    tensor=torch.from_numpy(np.fromfile(up/'000134.bin',dtype='<f4').reshape(-1,4))
    captured=[];hook=model.pillar_encoder.conv.register_forward_pre_hook(lambda m,i:captured.append(i[0].clone()))
    with torch.inference_mode():
        v,c,n=model.pillar_layer([tensor]);model.pillar_encoder(v,c,n)
        mean=v[:,:,:3].sum(1,keepdim=True)/n[:,None,None]
        enc=model.pillar_encoder
        ox=v[:,:,:1]-(c[:,None,1:2]*enc.vx+enc.x_offset)
        oy=v[:,:,1:2]-(c[:,None,2:3]*enc.vy+enc.y_offset)
        features=torch.cat([v,v[:,:,:3]-mean,ox,oy],-1);features[:,:,:1]=ox;features[:,:,1:2]=oy
        features*=(torch.arange(32)[None,:]<n[:,None])[:,:,None]
        np.testing.assert_array_equal(captured[0].numpy(),features.permute(0,2,1).contiguous().numpy())
    hook.remove()
    state=torch.load(up/'epoch_160.pth',map_location='cpu',weights_only=True)
    assert state.keys()==model.state_dict().keys()
    assert all(torch.equal(value,model.state_dict()[name]) for name,value in state.items())
    regs=[]
    for s in fm['sessions']:
        r=json.loads((fg/(s['sid']+'_registration.json')).read_text(encoding='utf-8'));rot=np.array(r['R']).reshape(3,3);t=np.array(r['t'])
        forward=np.array(r['fixedICP']['R']).reshape(3,3);ft=np.array(r['fixedICP']['t'])
        np.testing.assert_allclose(rot@forward,np.eye(3),atol=1e-6);np.testing.assert_allclose(rot@ft+t,0,atol=1e-6)
        assert r['direction']=='current_to_reference' and r['formal_production_eligible']==False
        regs.append(dict(sid=s['sid'],inverse_verified=True,gate=s['registration_gate'],leveling_recommended=s['leveling_recommended']))
    result=dict(frames=rows,source_frames=len(rows),foreground_groups=sum(r['variants_checked'] for r in rows),
                encoder_features_exact=True,encoder_coordinate_order='batch,x,y,z; upstream CPU kernel flips zyx at wrapper',
                strict_state_keys=len(state),strict_state_values_equal=True,registration=regs,
                geometry='bottom x/y/z; w/l/h; clockwise yaw (KITTI camera ry retained); class0=Pedestrian',
                source_intensity='SDK uint16 copied without scale into ROS float32; radiometric meaning/calibration not established',
                upstream_training='KITTI reads XYZI float32; no our /1023 or z leveling applied',
                scope='Software/current-coordinate checks only; TLS607 and ICP WARN do not become physical or formal gate PASS')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['source_frames','foreground_groups','encoder_features_exact','strict_state_keys','strict_state_values_equal','registration']},indent=2))


if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
