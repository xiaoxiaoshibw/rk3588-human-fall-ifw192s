/* DET-06 offline-only workspace foreground extraction (B_workspace only); reuses the frozen DET-02 project code. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const CODE=path.join(__dirname,'artifacts/det02_code');
const PL=require(path.join(CODE,'human_pipe_lib.js'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const dump=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2),{flag:'wx'});
// Frozen DET-02 copies; refuse to run against different code.
const EXPECTED={
    'human_pipe_lib.js':'af4cdea6d35c73633b12b0d230f3e91f8ba606d9e42fb2ba69bd4083b4af14e5',
    'human_replay_lib.js':'bbcbc547f79da60d0e6f915eeccb403997b1c192a3a37ba00e6d3c4d367cf1cc',
    'registration_method.js':'958f646ff41adbca7840a0a09ae6ba2ed87db7254b2d16f5365b64625caac141',
    'registration.js':'19c1fced9dbeabdefbc20dc8666fec601e3da8a42de68dec2ccdf195865379f5'};

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
function frames(input,session) {
    return session.frames.map(f=>{
        const b=fs.readFileSync(path.join(input,session.sid,f.file));
        assert.equal(sha(b),f.sha256,'prepared frame changed');
        const a=new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);
        assert.equal(a.length,f.points*4);
        return a.slice();
    });
}

function main(input,outdir) {
    fs.mkdirSync(outdir);
    const manifest=read(path.join(input,'manifest.json'));
    assert.equal(manifest.empty_template_confirmed,true,'empty template not confirmed');
    const codeSha=Object.fromEntries(Object.keys(EXPECTED).map(n=>[n,sha(fs.readFileSync(path.join(CODE,n)))]));
    for(const n of Object.keys(EXPECTED))assert.equal(codeSha[n],EXPECTED[n],'frozen code changed: '+n);
    const summary=[];
    for(const s of manifest.sessions) {
        console.log('BEGIN',s.sid);
        const original=frames(input,s);
        const clean=original.map(a=>PL.denoise(tagged(a)));
        const dir=path.join(outdir,s.sid);fs.mkdirSync(dir);
        const rows=[];
        for(let i=0;i<original.length;i++) {
            const B=PL.extract_foreground(clean[i],null).fg_xyzi;
            const v=selectOriginal(original[i],B);
            const name=`frame_${String(i).padStart(6,'0')}_B_workspace.bin`;
            const bytes=Buffer.from(v.out.buffer),idBytes=Buffer.from(v.ids.buffer);
            fs.writeFileSync(path.join(dir,name),bytes,{flag:'wx'});
            fs.writeFileSync(path.join(dir,name+'.ids'),idBytes,{flag:'wx'});
            rows.push({index:i,seq:s.frames[i].seq,points:v.ids.length,file:name,sha256:sha(bytes),ids_sha256:sha(idBytes)});
            if(i%50===0)console.log(s.sid,'frame',i,'points',v.ids.length);
        }
        summary.push({sid:s.sid,name:s.name||null,role:s.role,source:s.source,transform_sha256:s.transform_sha256,frames:rows});
        console.log('END',s.sid,original.length);
    }
    dump(path.join(outdir,'manifest.json'),{input_manifest_sha256:sha(fs.readFileSync(path.join(input,'manifest.json'))),
        parameters:PL.PIPE,code_sha256:codeSha,variant:'B_workspace',
        selections_in_current_coordinates:true,intensity_restored:true,sessions:summary});
}
if(require.main===module) {
    assert.equal(process.argv.length,4,'node det06_foreground.js prepared_dir new_out_dir');
    main(path.resolve(process.argv[2]),path.resolve(process.argv[3]));
}
module.exports={tagged,selectOriginal};
