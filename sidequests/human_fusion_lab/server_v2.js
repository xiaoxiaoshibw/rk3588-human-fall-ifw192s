'use strict';
const http=require('http'),fs=require('fs'),path=require('path');
const {Runtime,audit,MODELS}=require('./v2_runtime');
const runtime=new Runtime(),out=path.resolve(__dirname,'../../docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1');
const server=http.createServer(async(req,res)=>{try{
 const u=new URL(req.url,'http://127.0.0.1');res.setHeader('Cache-Control','no-store');
 if(req.method!=='GET'){res.writeHead(405);return res.end();}
 if(u.pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(fs.readFileSync(path.join(__dirname,'demo_v2.html')));}
 if(u.pathname==='/api/sessions'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({version:2,sessions:audit.sessions.map(r=>({sid:r.sid,activity:r.activity,frames:r.total_frames,gt:r.eligible?'BOUND_REVIEWED':'UNKNOWN',sha_ok:require('./session_adapter').is_sha_match(r)})),detectors:MODELS,default:'xgb69_candidate',default_session:'cap_20261010_175429'}));}
 if(u.pathname==='/api/reset'){runtime.reset();return res.end('{}');}
 if(u.pathname==='/api/cases'){res.setHeader('Content-Type','application/json');return res.end(fs.existsSync(path.join(out,'CASES.json'))?fs.readFileSync(path.join(out,'CASES.json')):'[]');}
 if(['/api/frame','/api/cloud'].includes(u.pathname)){
  const r=runtime.frame(u.searchParams.get('sid'),u.searchParams.get('model')||'xgb69_candidate',Number(u.searchParams.get('index')));
  if(u.pathname==='/api/cloud'){res.setHeader('Content-Type','application/octet-stream');return res.end(Buffer.from(r.xyzi.buffer,r.xyzi.byteOffset,r.xyzi.byteLength));}
  delete r.xyzi;res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(r));
 }
 res.writeHead(404);res.end('not found');
 }catch(e){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({error:e.message}));}});
if(require.main===module)server.listen(Number(process.argv[2]||8798),'127.0.0.1',()=>console.log('Demo V2 http://127.0.0.1:'+Number(process.argv[2]||8798)));
module.exports={server};
