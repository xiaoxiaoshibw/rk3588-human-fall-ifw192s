/* 离线runner。要求显式新outdir，拒绝覆盖任何已存在的输出。 */
"use strict";
var fs=require('fs'),path=require('path'),crypto=require('crypto'),os=require('os');
var D=require('./data_loader.js'),E=require('./engine.js'),S=require('./schema.js'),L=require('./leveling.js');
function parse_args(argv){
    var o={modes:['BASE_A'],frames_max:0,leveling:'ref'};
    for(var i=2;i<argv.length;i++){
        var a=argv[i];
        if(!['--session','--modes','--outdir','--frames-max','--leveling'].includes(a) || i+1===argv.length)throw new Error('未知参数/缺值 '+a);
        var value=argv[++i];
        if(a==='--modes')o.modes=value.split(',');else if(a==='--frames-max')o.frames_max=Number(value);else o[a.slice(2)]=value;
    }
    if(!['ref','identity'].includes(o.leveling))throw new Error('leveling仅支持ref/identity');
    if(!Number.isSafeInteger(o.frames_max)||o.frames_max<0)throw new Error('frames-max非法');
    if(new Set(o.modes).size!==o.modes.length)throw new Error('重复mode');
    return o;
}
function source_sha(){
    var files=['engine.js','schema.js','leveling.js','data_loader.js','runner.js'].map(function(n){return path.join(__dirname,n);});
    ['human_pipe_lib.js','detect_overlay.js','rf_person.js','rf_person_v1.json','bg_envelope.json'].forEach(function(n){files.push(path.join(__dirname,'../human_replay',n));});
    var hashes={};files.forEach(function(f){hashes[path.relative(path.join(__dirname,'../..'),f).replace(/\\/g,'/')]=E.hash_file(f);});return hashes;
}
function run_mode(s,mode,opts){
    var frozen_source=source_sha();
    opts=opts||{};var cfg={mode:mode};
    if(!['BASE_A','BASE_B','U1','U2','U3','U6','FUSION'].includes(mode))throw new Error('未实现mode '+mode);
    var choice=opts.leveling||'ref';if(!['ref','identity'].includes(choice))throw new Error('未知leveling');
    cfg.leveling_rt=choice==='identity'?L.IDENTITY_RT:L.REF_RT;
    var eng=new E.UnifiedEngine(cfg),sid=path.basename(s.session_dir),generation=eng.begin_session(sid);
    if(mode!==E.MODE.BASE_B)eng.set_online_background(s.frames.map(function(f){return f.xyzi;}),{meta:s.meta});
    var n=opts.frames_max>0?Math.min(opts.frames_max,s.frames.length):s.frames.length;
    var gt=S.gt_attestation(s.session_dir,s.meta),started=Date.now(),peak={heap_mb:0,rss_mb:0,external_mb:0};
    for(var i=0;i<n;i++){
        var f=s.frames[i];var d=eng.tick(S.make_frame_context({session_id:sid,session_generation:generation,frame_index:i,timestamp:f.timestamp,xyzi:f.xyzi,meta:s.meta}));
        peak.heap_mb=Math.max(peak.heap_mb,d.peak_heap_mb);peak.rss_mb=Math.max(peak.rss_mb,d.rss_mb);peak.external_mb=Math.max(peak.external_mb,d.external_mb);
    }
    var rep=eng.report(),rows=rep.rows,sum=0,max=0,accepted=0,rejected=0,confirmed_frames=0;
    if(JSON.stringify(source_sha())!==JSON.stringify(frozen_source))throw new Error('实现文件在运行期间改变，拒绝生成证据');
    if(fs.existsSync(path.join(s.session_dir,'points.bin')) && (E.hash_file(path.join(s.session_dir,'points.bin'))!==s.points_sha256 || E.hash_file(path.join(s.session_dir,'meta.json'))!==s.meta_sha256))throw new Error('输入文件在运行期间改变，拒绝生成证据');
    rows.forEach(function(r){sum+=r.total_ms;max=Math.max(max,r.total_ms);if(r.n_accepted_cand>0)accepted++;if(r.n_rejected_cand>0)rejected++;if(r.n_tracks_confirmed_current>0)confirmed_frames++;});
    return {format_version:2,run_meta:{sid:sid,mode:mode,started_iso:new Date(started).toISOString(),elapsed_sec:(Date.now()-started)/1000,n_frames_run:n,gt_level:gt.level,node:process.version,platform:process.platform,arch:process.arch,cpu:os.cpus()[0].model,source_sha256:frozen_source,input_sha256:{points:s.points_sha256,meta:s.meta_sha256},coordinate_contract:rep.coordinate_contract,rf_model_sha:rep.rf_model_sha,ref_env_sha:rep.ref_env_sha},
        config:eng.cfg,frames:rows,tracks:rep.tracks,ever_confirmed_track_ids:rep.ever_confirmed_track_ids,
        session_summary:{n_frames:n,mean_ms_per_frame:+(sum/n).toFixed(2),max_ms_per_frame:max,frames_with_accepted_cand:accepted,frames_with_rejected_cand:rejected,frames_with_confirmed_tracks:confirmed_frames,n_tracks_total:rep.track_ids.length,n_tracks_confirmed_current:rep.tracks.filter(function(t){return t.active&&t.human_confirmed&&t.lost===0;}).length,n_tracks_ever_confirmed:rep.ever_confirmed_track_ids.length,peak_memory:peak},
        prf:{level:gt.level,measurable:false,status:'BLOCKED',reason:'未执行可信GT逐点/逐目标匹配；候选接受/拒绝不代表真人/家具'}};
}
function main(){
    var opts=parse_args(process.argv);if(!opts.session||!opts.outdir)throw new Error('--session和新--outdir必传');
    if(fs.existsSync(opts.outdir)&&fs.readdirSync(opts.outdir).length)throw new Error('outdir非空，拒绝覆盖');
    var s=D.load_session(opts.session),frozen_source=source_sha(),manifest={format_version:2,generated_iso:new Date().toISOString(),session_sha:{points:s.points_sha256,meta:s.meta_sha256},sessions:[]};
    fs.mkdirSync(opts.outdir,{recursive:true});
    opts.modes.forEach(function(m){
        if(JSON.stringify(source_sha())!==JSON.stringify(frozen_source))throw new Error('实现文件在模式间改变，停止本批证据');
        var result=run_mode(s,m,opts),name=path.basename(s.session_dir)+'__'+m+'.json',file=path.join(opts.outdir,name);
        fs.writeFileSync(file,JSON.stringify(result,null,1),{encoding:'utf8',flag:'wx'});
        var csvName=path.basename(s.session_dir)+'__'+m+'.csv',csvFile=path.join(opts.outdir,csvName),keys=Object.keys(result.frames[0]);
        fs.writeFileSync(csvFile,[keys.join(',')].concat(result.frames.map(function(r){return keys.map(function(k){return r[k]===undefined?'':r[k];}).join(',');})).join('\n')+'\n',{encoding:'utf8',flag:'wx'});
        manifest.sessions.push({mode:m,file:name,sha256:E.hash_file(file),csv:csvName,csv_sha256:E.hash_file(csvFile),summary:result.session_summary});
        console.log(m+' '+result.session_summary.n_frames+'frames '+result.session_summary.mean_ms_per_frame+'ms/f');
    });
    fs.writeFileSync(path.join(opts.outdir,'manifest.json'),JSON.stringify(manifest,null,1),{encoding:'utf8',flag:'wx'});
}
if(require.main===module)main();
module.exports={run_mode:run_mode,parse_args:parse_args,source_sha:source_sha};
