/* DET-02 offline-only adapter; reuse frozen project reference/foreground/ICP/cleanup. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const CODE=path.join(__dirname,'artifacts/det02_code');
const PL=require(path.join(CODE,'human_pipe_lib.js'));
const M=require(path.join(CODE,'registration_method.js'));
const REG=require(path.join(CODE,'registration.js'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const dump=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2),{flag:'wx'});

function tagged(cloud) {
    const a=cloud.slice();
    // Frame-local row IDs are exact float32 integers (<2^24). Restore real XYZI before model.
    assert(cloud.length/4<2**24);
    for(let i=0;i<a.length/4;i++)a[i*4+3]=i;
    return a;
}
function selectOriginal(original,selection) {
    const ids=new Uint32Array(selection.length/4),out=new Float32Array(selection.length);
    const seen=new Set();
    for(let i=0;i<ids.length;i++) {
        const id=selection[i*4+3];
        assert(Number.isInteger(id)&&id>=0&&id<original.length/4&&!seen.has(id));seen.add(id);
        ids[i]=id;out.set(original.subarray(id*4,id*4+4),i*4);
    }
    return {ids,out};
}
function transform(cloud,R,t) {
    const out=cloud.slice();
    for(let i=0;i<out.length;i+=4) {
        const q=M.m3.apply(R,out[i],out[i+1],out[i+2]);
        for(let j=0;j<3;j++)out[i+j]=q[j]+t[j];
    }
    return out;
}
function frames(input,session) {
    return session.frames.map(f=>{
        const b=fs.readFileSync(path.join(input,session.sid,f.file));
        assert.equal(sha(b),f.sha256,'prepared frame changed');
        const a=new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);
        assert.equal(a.length,f.points*4);
        return a.slice();
    });
}
function tests() {
    const empty=Array.from({length:4},()=>new Float32Array([4,.1,1,10,4.01,.1,1,20]));
    const human=new Float32Array([2,.1,.8,77,2,.1,1.4,88,4,.1,1,10]);
    const ref=PL.build_reference_map(empty),map=new Map([...ref.voxels].filter(([,r])=>r.occ>=PL.PIPE.bg_ref_occ_min));
    const selected=PL.extract_foreground(tagged(human),map).fg_xyzi;
    const out=selectOriginal(human,selected);
    assert.deepEqual([...out.ids],[0,1]);assert.deepEqual([...out.out],[...human.subarray(0,8)]);
    const self=PL.build_static_map(Array.from({length:4},()=>new Float32Array([2,.1,.8,1,2.01,.1,.8,2])));
    assert.equal(PL.extract_foreground(new Float32Array([2,.1,.8,1]),self).n_fg,0);
    const R=M.m3.rodrigues([0,0,.03]),t=[.05,-.02,.01],inv=M.m3.t(R),it=M.m3.apply(inv,...t.map(v=>-v));
    const recovered=transform(transform(human,R,t),inv,it);
    for(let i=0;i<human.length;i++)assert(Math.abs(recovered[i]-human[i])<1e-6);
    assert(REG.matrixOK(R,t));assert(!REG.matrixOK([1,0,0,0,2,0,0,0,1],t));
    assert.throws(()=>selectOriginal(human,new Float32Array([2,0,1,100])));
    console.log('PASS: independent empty reference preserves stationary new person; self-map absorbs; source IDs/intensity restored; inverse direction/invalid matrices');
}

function main(input,outdir) {
    fs.mkdirSync(outdir);
    const manifest=read(path.join(input,'manifest.json'));
    assert.equal(manifest.empty_template_confirmed,true,'empty template not confirmed');
    const reference=manifest.sessions.find(s=>s.role==='empty_reference');
    assert(reference&&manifest.sessions.filter(s=>s.role==='empty_reference').length===1);
    const refFrames=frames(input,reference).map(PL.denoise);
    const ref=PL.build_reference_map(refFrames);
    const refMap=new Map([...ref.voxels].filter(([,r])=>r.occ>=PL.PIPE.bg_ref_occ_min));
    const refRows=[...refMap].sort((a,b)=>a[0]-b[0]);
    const templateDigest=sha(JSON.stringify(refRows));
    dump(path.join(outdir,'reference.json'),{sid:reference.sid,source:reference.source,transform_sha256:reference.transform_sha256,
        confirmed_empty:true,params:PL.PIPE,reference_frames:refFrames.length,voxels:refMap.size,template_sha256:templateDigest});
    const summary=[];
    for(const s of manifest.sessions.filter(s=>s.role==='human_target')) {
        console.log('BEGIN',s.sid);
        const original=frames(input,s),clean=original.map(a=>PL.denoise(tagged(a)));
        const onlineForGeometryOnly=PL.build_static_map(clean);
        const icp=M.fixedICP(onlineForGeometryOnly,ref);
        assert(REG.matrixOK(icp.R,icp.t),'invalid ref-to-current ICP');
        const R=M.m3.t(icp.R),t=M.m3.apply(R,...icp.t.map(v=>-v));
        assert(REG.matrixOK(R,t));
        const tlsR=M.m3.mul(reference.R.flat(),M.m3.t(s.R.flat()));
        const diagnostics=REG.measure(clean,refFrames,R,t,tlsR);
        dump(path.join(outdir,s.sid+'_registration.json'),{direction:'current_to_reference',R,t,
            fixedICP:icp,legacy_saved_pair_check_not_applicable:true,diagnostics,formal_production_eligible:false});
        const dir=path.join(outdir,s.sid);fs.mkdirSync(dir);
        const rows=[];
        for(let i=0;i<original.length;i++) {
            const full=tagged(original[i]);
            const B=PL.extract_foreground(clean[i],null).fg_xyzi;
            const C=PL.extract_foreground(clean[i],refMap).fg_xyzi;
            const aligned=transform(clean[i],R,t);
            const alignedCrop=PL.extract_foreground(aligned,null).fg_xyzi;
            const D=PL.extract_foreground(aligned,refMap).fg_xyzi;
            const E=PL.cleanup_isolated_fg(D).xyzi;
            const selections={A_full:full,B_workspace:B,C_reference:C,D_registered:D,E_cleanup:E},records={};
            for(const [variant,selection] of Object.entries(selections)) {
                const v=selectOriginal(original[i],selection),name=`frame_${String(i).padStart(6,'0')}_${variant}.bin`;
                const bytes=Buffer.from(v.out.buffer),idBytes=Buffer.from(v.ids.buffer);
                fs.writeFileSync(path.join(dir,name),bytes,{flag:'wx'});
                fs.writeFileSync(path.join(dir,name+'.ids'),idBytes,{flag:'wx'});
                records[variant]={file:name,points:v.ids.length,sha256:sha(bytes),ids_sha256:sha(idBytes)};
            }
            rows.push({index:i,seq:s.frames[i].seq,reference_coordinate_crop_points:alignedCrop.length/4,variants:records});
            if(i%20===0)console.log(s.sid,'frame',i,Object.fromEntries(Object.entries(records).map(([k,v])=>[k,v.points])));
        }
        assert.equal(sha(JSON.stringify([...refMap].sort((a,b)=>a[0]-b[0]))),templateDigest,'template mutated by target');
        summary.push({sid:s.sid,source:s.source,transform_sha256:s.transform_sha256,leveling_recommended:s.leveling_recommended,
            registration_gate:diagnostics.gate.status,registration_reasons:diagnostics.gate.reasons,frames:rows});
        console.log('END',s.sid);
    }
    dump(path.join(outdir,'manifest.json'),{input_manifest_sha256:sha(fs.readFileSync(path.join(input,'manifest.json'))),template_sha256:templateDigest,
        parameters:PL.PIPE,code_sha256:Object.fromEntries(['human_pipe_lib.js','human_replay_lib.js','registration_method.js','registration.js'].map(n=>[n,sha(fs.readFileSync(path.join(CODE,n)))])),
        selections_in_current_coordinates:true,intensity_restored:true,sessions:summary});
}
if(require.main===module) {
    if(process.argv[2]==='--self-check')tests();
    else {assert.equal(process.argv.length,4,'node reference_foreground.js prepared_dir new_out_dir');main(path.resolve(process.argv[2]),path.resolve(process.argv[3]));}
}
module.exports={tagged,selectOriginal,transform};
