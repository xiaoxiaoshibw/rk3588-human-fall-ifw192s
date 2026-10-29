const http=require('http');
const CDP='http://127.0.0.1:9223';
function req(method,p){return new Promise((res,rej)=>{const u=new URL(CDP+p);const r=http.request({hostname:u.hostname,port:u.port,path:u.pathname+u.search,method},x=>{let b='';x.on('data',d=>b+=d);x.on('end',()=>res(JSON.parse(b)))});r.on('error',rej);r.end()})}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const t=await req('PUT','/json/new?'+encodeURIComponent('http://127.0.0.1:59387/?fi=0'));
 const ws=new WebSocket(t.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
 let id=0;const pend=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const p=pend.get(m.id);pend.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result)}};
 const send=(method,params={})=>new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method,params}))});
 const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true,awaitPromise:true});return r.exceptionDetails?('ERR '+JSON.stringify(r.exceptionDetails).slice(0,500)):r.result.value};
 await send('Runtime.enable'); await send('Page.enable');
 for(let i=0;i<60;i++){await sleep(300); if(await ev('!!window.__s2 && !!__s2.state.data')) break;}
 const info=await ev("({dpr:devicePixelRatio, rect:(()=>{const r=document.getElementById('p3').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})(), n:__s2.state.data.raw.length/3, fi:__s2.state.fi})");
 console.log('info', JSON.stringify(info));
 const idx=await ev("(()=>{const p=__s2.state.data.patch; for(let i=0;i<p.length;i++) if(p[i]) return i; return -1;})()");
 console.log('idx', idx, 'patchval', await ev('__s2.state.data.patch['+idx+']'));
 const s=await ev('__s2.screenOf('+idx+')');
 console.log('screen', JSON.stringify(s));
 const r=info.rect;
 const px=r.x+s.x, py=r.y+s.y;
 console.log('click at', px, py);
 await send('Input.dispatchMouseEvent',{type:'mousePressed',x:px,y:py,button:'left',clickCount:1});
 await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:px,y:py,button:'left',clickCount:1});
 await sleep(1200);
 console.log('sel', await ev('__s2.state.sel'));
 console.log('pointText', (await ev("document.getElementById('point').textContent")).slice(0,500));
 console.log('status', await ev("document.getElementById('status').textContent"));
 ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
