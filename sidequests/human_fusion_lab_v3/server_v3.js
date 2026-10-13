'use strict';
/* server_v3.js — HUMAN-FUSION-BG-V3 Demo V3 HTTP 入口 (与 V2 并行, 不动 V2).
 *
 * 路由: 同 V2 外加 /api/frame 返回 v3 注入字段 (bg_masks, bg_diff_per_group, point_trace, foreground_A/B/C).
 */
const http=require('http'),fs=require('fs'),path=require('path');
const {Runtime,audit,MODELS}=require('./v3_runtime');
const runtime=new Runtime(),out=path.resolve(__dirname,'../../docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1');
const server=http.createServer(async(req,res)=>{try{
 const u=new URL(req.url,'http://127.0.0.1');res.setHeader('Cache-Control','no-store');
 if(req.method!=='GET'){res.writeHead(405);return res.end();}
 if(u.pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(fs.readFileSync(path.join(__dirname,'demo_v3.html')));}
 if(u.pathname==='/api/sessions'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({version:3,sessions:audit.sessions.map(r=>({sid:r.sid,activity:r.activity,frames:r.total_frames,gt:r.eligible?'BOUND_REVIEWED':'UNKNOWN',sha_ok:require(path.join(__dirname,'../human_fusion_lab/session_adapter')).is_sha_match(r)})),detectors:MODELS,default:'xgb69_candidate',default_session:'cap_20261010_180235'}));}
 if(u.pathname==='/api/reset'){runtime.reset();return res.end('{}');}
 if(u.pathname==='/api/cases'){res.setHeader('Content-Type','application/json');
   return res.end(fs.existsSync(path.join(out,'CASES.json'))?fs.readFileSync(path.join(out,'CASES.json')):'[]');}
 if(['/api/frame','/api/cloud'].includes(u.pathname)){
  const r=runtime.frame(u.searchParams.get('sid'),u.searchParams.get('model')||'xgb69_candidate',Number(u.searchParams.get('index')));
  if(u.pathname==='/api/cloud'){res.setHeader('Content-Type','application/octet-stream');return res.end(Buffer.from(r.xyzi.buffer,r.xyzi.byteOffset,r.xyzi.byteLength));}
  delete r.xyzi;res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(r));
 }
 res.writeHead(404);res.end('not found');
}catch(e){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({error:e.message}));}});
if(require.main===module)server.listen(Number(process.argv[2]||8800),'127.0.0.1',()=>console.log('Demo V3 http://127.0.0.1:'+Number(process.argv[2]||8800)));
module.exports={server};
