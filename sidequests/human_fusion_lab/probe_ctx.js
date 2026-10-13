const http=require('http');function httpJson(m,p){return new Promise((res,rej)=>{const r=http.request({host:'127.0.0.1',port:9223,path:p,method:m},x=>{let d='';x.on('data',c=>d+=c);x.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})});r.on('error',rej);r.end();});}
const net=require('net'),crypto=require('crypto');
class WS{constructor(u){const m=/^ws:\/\/([^:/]+):(\d+)(\/.*)$/.exec(u);this.host=m[1];this.port=+m[2];this.path=m[3];this.buf=Buffer.alloc(0);this.frags=[];this.onmsg=()=>{};}
connect(){return new Promise((res,rej)=>{const k=crypto.randomBytes(16).toString('base64');this.sock=net.connect(this.port,this.host,()=>{this.sock.write('GET '+this.path+' HTTP/1.1\r\nHost: '+this.host+':'+this.port+'\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+k+'\r\nSec-WebSocket-Version: 13\r\n\r\n');});let s=false,acc=Buffer.alloc(0);this.sock.on('data',ch=>{if(!s){acc=Buffer.concat([acc,ch]);const i=acc.indexOf('\r\n\r\n');if(i<0)return;s=true;this.buf=acc.slice(i+4);this._drain();res();}else{this.buf=Buffer.concat([this.buf,ch]);this._drain();}});this.sock.on('error',rej);});}
_f(op,p){const P=Buffer.isBuffer(p)?p:Buffer.from(p),mk=crypto.randomBytes(4);let h;if(P.length<126)h=Buffer.from([0x80|op,0x80|P.length]);else if(P.length<65536){h=Buffer.alloc(4);h[0]=0x80|op;h[1]=0xFE;h.writeUInt16BE(P.length,2);}else{h=Buffer.alloc(10);h[0]=0x80|op;h[1]=0xFF;h.writeBigUInt64BE(BigInt(P.length),2);}const m=Buffer.alloc(P.length);for(let i=0;i<P.length;i++)m[i]=P[i]^mk[i&3];this.sock.write(Buffer.concat([h,mk,m]));}
send(s){this._f(1,s);}
_drain(){for(;;){if(this.buf.length<2)return;const b=this.buf[0],fi=!!(b&0x80),op=b&0x0f;let l=this.buf[1]&0x7f,off=2;if(l===126){if(this.buf.length<4)return;l=this.buf.readUInt16BE(2);off=4;}else if(l===127){if(this.buf.length<10)return;l=Number(this.buf.readBigUInt64BE(2));off=10;}if(this.buf.length<off+l)return;const pay=this.buf.slice(off,off+l);this.buf=this.buf.slice(off+l);if(op===9){this._f(10,pay);continue;}if(op===8)continue;this.frags.push(pay);if(fi){const m=Buffer.concat(this.frags).toString();this.frags=[];this.onmsg(m);}}}}
class CDP{constructor(ws){this.id=0;this.p=new Map();this.ev={};ws.onmsg=s=>{const m=JSON.parse(s);if(m.id!==undefined&&this.p.has(m.id)){const q=this.p.get(m.id);this.p.delete(m.id);m.error?q.rej(new Error(m.error.message)):q.res(m.result);}else if(m.method)(this.ev[m.method]||[]).forEach(f=>f(m.params));};this.ws=ws;}
call(m,p){const id=++this.id;return new Promise((res,rej)=>{this.p.set(id,{res,rej});this.ws.send(JSON.stringify({id,method:m,params:p||{}}));});}
on(m,f){(this.ev[m]=this.ev[m]||[]).push(f);}
async evalIn(e,ctxId){const pr={expression:e,returnByValue:true};if(ctxId)pr.contextId=ctxId;const r=await this.call('Runtime.evaluate',pr);return r.exceptionDetails?('EXC:'+JSON.stringify(r.exceptionDetails).slice(0,150)):r.result.value;}}
(async()=>{
 const t=await httpJson('PUT','/json/new?about:blank');const ws=new WS(t.webSocketDebuggerUrl);await ws.connect();const cdp=new CDP(ws);
 await cdp.call('Page.enable');
 const contexts=[];
 cdp.on('Runtime.executionContextCreated',p=>{contexts.push({id:p.context.id,name:p.context.name,origin:p.context.origin,aux:(p.context.auxData||{}).frameId?1:0});});
 await cdp.call('Runtime.enable');
 await cdp.call('Page.navigate',{url:'http://127.0.0.1:8797/'});
 await new Promise(r=>setTimeout(r,3500));
 console.log('execution contexts:',JSON.stringify(contexts,null,1));
 for(const c of contexts){
   const u=await cdp.evalIn('location.href',c.id);
   const fr=await cdp.evalIn('window.frame',c.id);
   console.log('ctx',c.id,u,'-> window.frame=',JSON.stringify(fr));
 }
 // default (no contextId)
 console.log("default(noCtx) window.frame=",JSON.stringify(await cdp.evalIn("window.frame",contexts.length?contexts[contexts.length-1].id:undefined)));
 console.log('default(noCtx) location=',JSON.stringify(await cdp.evalIn('location.href')));
 await httpJson('GET','/json/close/'+t.id).catch(()=>{});process.exit(0);
})().catch(e=>{console.error('FATAL',e.message);process.exit(1);});
