const http=require('http');
function req(method,p){return new Promise((res,rej)=>{const u=new URL('http://127.0.0.1:9223'+p);const r=http.request({hostname:u.hostname,port:u.port,path:u.pathname+u.search,method},x=>{let b='';x.on('data',d=>b+=d);x.on('end',()=>res({status:x.statusCode,body:b.slice(0,400)}))});r.on('error',rej);r.end()})}
(async()=>{
 console.log('version', (await req('GET','/json/version')).status);
 const l=await req('GET','/json/list'); console.log('list', l.status, l.body.slice(0,600));
 for (const m of ['PUT','GET','POST']) { try { const r=await req(m,'/json/new?'+encodeURIComponent('http://127.0.0.1:59387/')); console.log(m, r.status, r.body.slice(0,200)); } catch(e){ console.log(m,'ERR',e.message);} }
})();
