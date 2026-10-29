const http=require('http');
const CDP='http://127.0.0.1:9223';
function json(port,p,method='GET'){return new Promise((res,rej)=>{const u=new URL(CDP+p);const req=http.request({hostname:u.hostname,port:u.port,path:u.pathname+u.search,method},r=>{let b='';r.on('data',d=>b+=d);r.on('end',()=>{try{res(JSON.parse(b))}catch(e){rej(new Error(b.slice(0,300)))}})});req.on('error',rej);req.end()})}
(async()=>{
 for (const u of ['http://127.0.0.1:59387/?fi=0','http://127.0.0.1:59387/']) {
  try { const t=await json(0,'/json/new?'+encodeURIComponent(u),'PUT'); console.log('ok', u, t.id, t.url); } catch(e){ console.log('err', u, e.message); }
 }
})();
