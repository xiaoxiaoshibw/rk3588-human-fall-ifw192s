const http=require('http');
const get=p=>new Promise((res,rej)=>http.get('http://127.0.0.1:9223'+p,r=>{let b='';r.on('data',d=>b+=d);r.on('end',()=>res(JSON.parse(b)))}).on('error',rej));
(async()=>{
 const l=await get('/json/list'); const page=l.find(t=>t.type==='page');
 const ws=new WebSocket(page.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
 let id=0; const pend=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const p=pend.get(m.id);pend.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result)}};
 const send=(method,params={})=>new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method,params}))});
 const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true});return r.exceptionDetails?('ERR '+JSON.stringify(r.exceptionDetails).slice(0,300)):r.result.value};
 console.log('url', await ev('location.href'));
 console.log('ready', await ev('document.readyState'));
 console.log('status', await ev("document.getElementById('status') ? document.getElementById('status').textContent : 'no-status'"));
 console.log('scripts', await ev("Array.from(document.scripts).map(s=>s.src)"));
 console.log('s2', await ev('typeof window.__s2'));
 ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
