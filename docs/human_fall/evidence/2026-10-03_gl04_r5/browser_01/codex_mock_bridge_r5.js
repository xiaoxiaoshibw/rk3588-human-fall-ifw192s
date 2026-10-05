// Independent localhost-only Foxglove v1 integration fixture. Node stdlib only.
// No device connection, no source writes; all observations are synthetic.
const http=require('http'),crypto=require('crypto'),fs=require('fs'),path=require('path');
const HF=require(path.resolve(__dirname,'../../../../../webui/human_fall_preview/human_fall_lib.js'));
const base=HF.syntheticScenario('normal');
let mode='normal', selectionVersion=1, requests=[],connections=new Set();
const topics=['/innolidar_points','/human_fall/candidates','/human_fall/state','/human_fall/event','/human_fall/selection_ack'];
function frame(op,bytes){bytes=Buffer.from(bytes);let h;if(bytes.length<126){h=Buffer.from([128|op,bytes.length]);}else if(bytes.length<65536){h=Buffer.alloc(4);h[0]=128|op;h[1]=126;h.writeUInt16BE(bytes.length,2);}else{h=Buffer.alloc(10);h[0]=128|op;h[1]=127;h.writeBigUInt64BE(BigInt(bytes.length),2);}return Buffer.concat([h,bytes]);}
function json(c,obj){c.sock.write(frame(1,Buffer.from(JSON.stringify(obj))));}
function wire(c,topic,payload){const sub=c.subs.get(topic);if(sub==null)return;const b=Buffer.alloc(13);b[0]=1;b.writeUInt32LE(sub,1);b.writeBigUInt64LE(1000000000000n,5);c.sock.write(frame(2,Buffer.concat([b,Buffer.from(payload)])));}
function ros(obj){return HF.packRos1String(JSON.stringify(obj));}
function data(){const snap=JSON.parse(JSON.stringify(base.snapshot)),state=JSON.parse(JSON.stringify(base.state));
  const block=snap.ground_render;
  snap.coordinate.ground=JSON.parse(JSON.stringify(block));
  snap.ground.support_polygon=block.support.polygon.map(p=>[p[0],p[1],0]);
  snap.ground.support_polyline=[[-2,-2,0],[2,2,0]];
  snap.ground.support_frame='ground_local';snap.ground.support_schema_version=1;snap.ground.ground_derived_id=block.ground_derived_id;
  delete snap.ground_render;
  state.snapshot_id=snap.snapshot_id;state.coordinate=JSON.parse(JSON.stringify(snap.coordinate));state.ground=JSON.parse(JSON.stringify(snap.ground));
  state.calibration=JSON.parse(JSON.stringify(snap.calibration));state.center_ground_m=snap.candidates[0].center_ground_m;state.ground_derived_id=block.ground_derived_id;
  state.selection_version=selectionVersion;state.queue_dropped=2;
  state.sensor_quality={ground_valid:true,ground_status:'valid',ground_derived_id:block.ground_derived_id,ground_monitor:{status:'ok',reason:null}};
  state.recent_events=[{kind:'fall_event',schema_version:1,event_id:'synthetic-e1',track_id:'t0001',fall_status:'suspected',start_source_s:999,reason_codes:['synthetic_history']}];
  delete state.queue_dropped;
  state.performance={kind:'performance',schema_version:1,enabled:true,queue_dropped:3};
  if(mode==='unknown'||mode==='none'){snap.calibration.ground_status=mode;snap.ground.status=mode;state.calibration.ground_status=mode;state.sensor_quality.ground_status=mode;}
  if(mode==='no_candidates')snap.candidates=[];
  if(mode==='bad_schema'){snap.calibration.schema_version=2;snap.coordinate.ground.geometry_schema_version=2;state.calibration.schema_version=2;}
  if(mode==='new_calibration'){snap.calibration.calibration_id='syn-cal-2';snap.coordinate.ground.calibration_id='syn-cal-2';state.calibration.calibration_id='syn-cal-2';}
  if(mode==='snapshot_new_calibration'){snap.calibration.calibration_id='syn-cal-2';snap.coordinate.ground.calibration_id='syn-cal-2';}
  if(mode==='state_new_calibration')state.calibration.calibration_id='syn-cal-2';
  if(mode==='unrelated'){const c=snap.candidates[0];c.candidate_id='other';c.center_source_m=[12,0,-.7];c.center_ground_m=[12,0,.8];c.bbox_source_min_m=[11.85,-.1,-1.5];c.bbox_source_max_m=[12.15,.3,.1];c.bbox_ground_min_m=[11.85,-.1,0];c.bbox_ground_max_m=[12.15,.3,1.6];state.center_ground_m=null;state.bbox_ground_from='unavailable';state.bbox_ground_min_m=null;state.bbox_ground_max_m=null;}
  if(mode==='verifier_unavailable')state.sensor_quality.ground_monitor={status:'unknown',reason:'verifier_unavailable'};
  if(mode==='foreign_frame'){snap.source.frame_id='foreign';snap.coordinate.source_frame='foreign';snap.coordinate.ground.from_frame='foreign';state.source.frame_id='foreign';}
  return {snap,state};
}
function push(c){if(mode==='silent'||mode==='disconnect')return;const f=data();wire(c,topics[0],base.cloud);wire(c,topics[1],ros(f.snap));wire(c,topics[2],ros(f.state));}
function receive(c,op,payload){if(op===8){c.sock.end(frame(8,payload));return;}if(op===9){c.sock.write(frame(10,payload));return;}
  if(op===1){let m;try{m=JSON.parse(payload.toString());}catch{return;}if(m.op==='subscribe'){for(const s of m.subscriptions||[])c.subs.set(topics[s.channelId-1],s.id);push(c);}return;}
  if(op===2&&payload[0]===1){try{const len=payload.readUInt32LE(5),r=JSON.parse(payload.subarray(9,9+len));requests.push(r);fs.appendFileSync(path.join(__dirname,'40_wire_requests.jsonl'),JSON.stringify(r)+'\n');
    if(r.action==='select')selectionVersion++;
    wire(c,topics[4],ros({kind:'selection_ack',schema_version:1,request_id:r.request_id,action:r.action,session_id:'syn',time_epoch:0,accepted:true,reason:null,track_id:'t0001',candidate_id:r.candidate_id,selection_version:selectionVersion}));push(c);
  }catch(e){console.error('request decode',e.message);}}
}
const server=http.createServer((req,res)=>{if(req.method==='POST'&&req.url==='/control'){let b='';req.on('data',d=>b+=d);req.on('end',()=>{try{mode=JSON.parse(b).mode;if(mode==='disconnect'){for(const c of connections)c.sock.destroy();}else for(const c of connections)push(c);res.end(JSON.stringify({mode}));}catch(e){res.statusCode=400;res.end(e.message);}});return;}
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify({mode,connections:connections.size,requests}));});
server.on('upgrade',(req,sock)=>{const accept=crypto.createHash('sha1').update(req.headers['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');sock.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+'\r\nSec-WebSocket-Protocol: foxglove.websocket.v1\r\n\r\n');
  const c={sock,subs:new Map(),buffer:Buffer.alloc(0)};connections.add(c);
  sock.on('close',()=>connections.delete(c));sock.on('error',()=>{});
  sock.on('data',d=>{c.buffer=Buffer.concat([c.buffer,d]);while(c.buffer.length>=2){const b=c.buffer;let n=b[1]&127,o=2;if(n===126){if(b.length<4)return;n=b.readUInt16BE(2);o=4;}else if(n===127){if(b.length<10)return;n=Number(b.readBigUInt64BE(2));o=10;}const mask=(b[1]&128)!==0;if(b.length<o+(mask?4:0)+n)return;const key=mask?b.subarray(o,o+4):null;if(mask)o+=4;const payload=Buffer.from(b.subarray(o,o+n));if(key)for(let i=0;i<n;i++)payload[i]^=key[i%4];c.buffer=b.subarray(o+n);receive(c,b[0]&15,payload);}});
  json(c,{op:'serverInfo',name:'GL04 synthetic/offline mock bridge',capabilities:['clientPublish'],supportedEncodings:['ros1']});
  json(c,{op:'advertise',channels:topics.map((topic,i)=>({id:i+1,topic,encoding:'ros1',schemaName:i===0?'sensor_msgs/PointCloud2':'std_msgs/String',schemaEncoding:'ros1msg',schema:i===0?'':'string data\n'}))});
});
setInterval(()=>{for(const c of connections)push(c);},250);
server.listen(18091,'127.0.0.1',()=>console.log('GL04 synthetic/offline mock bridge at 127.0.0.1:18091'));
