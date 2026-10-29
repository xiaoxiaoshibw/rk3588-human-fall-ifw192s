const http=require('http');
const CDP='http://127.0.0.1:9223';const BASE='http://127.0.0.1:61470';
function req(method,p){return new Promise((res,rej)=>{const u=new URL(CDP+p);const r=http.request({hostname:u.hostname,port:u.port,path:u.pathname+u.search,method},x=>{let b='';x.on('data',d=>b+=d);x.on('end',()=>res(JSON.parse(b)))});r.on('error',rej);r.end()})}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const fb=await (await fetch(BASE+'/api/firstbin?fi=0')).json(); console.log('firstbin',fb);
 const t=await req('PUT','/json/new?'+encodeURIComponent(BASE+'/?fi=0'));
 const ws=new WebSocket(t.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
 let id=0;const pend=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const p=pend.get(m.id);pend.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result)}};
 const send=(m,p={})=>new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p}))});
 const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true,awaitPromise:true});return r.exceptionDetails?('ERR '+JSON.stringify(r.exceptionDetails).slice(0,400)):r.result.value};
 await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1400,height:1000,deviceScaleFactor:1,mobile:false});
 for(let i=0;i<60;i++){await sleep(300); if(await ev('!!window.__s2 && !!__s2.state.data')) break;}
 console.log('selectBin direct', await ev('__s2.selectBin('+fb.ia+','+fb.ie+').then(x=>JSON.stringify(x))'));
 console.log('bin text', (await ev("document.getElementById('bin').textContent")).slice(0,300));
 ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
