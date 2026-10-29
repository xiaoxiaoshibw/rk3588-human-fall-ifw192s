const http=require('http');
const CDP='http://127.0.0.1:9223';
function req(method,p){return new Promise((res,rej)=>{const u=new URL(CDP+p);const r=http.request({hostname:u.hostname,port:u.port,path:u.pathname+u.search,method},x=>{let b='';x.on('data',d=>b+=d);x.on('end',()=>res(JSON.parse(b)))});r.on('error',rej);r.end()})}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const t=await req('PUT','/json/new?'+encodeURIComponent('http://127.0.0.1:59387/?fi=0'));
 const ws=new WebSocket(t.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
 let id=0;const pend=new Map();const evs=[];
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const p=pend.get(m.id);pend.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result)} else if(m.method){evs.push(m)}};
 const send=(method,params={})=>new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method,params}))});
 const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true});return r.exceptionDetails?('ERR '+JSON.stringify(r.exceptionDetails).slice(0,400)):r.result.value};
 await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
 await sleep(6000);
 console.log('url', await ev('location.href'));
 console.log('ready', await ev('document.readyState'));
 console.log('s2', await ev('typeof window.__s2'));
 console.log('statusText', await ev("document.getElementById('status') ? document.getElementById('status').textContent : 'none'"));
 console.log('body', (await ev('document.body.innerText')).slice(0,300));
 console.log('perf', JSON.stringify(await ev("performance.getEntriesByType('resource').map(r=>[r.name.split('/').pop(), r.responseStatus])")));
 for (const e of evs.filter(x=>x.method==='Runtime.exceptionThrown'||x.method==='Log.entryAdded')) console.log('EV', JSON.stringify(e.params).slice(0,600));
 ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
