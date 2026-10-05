// Independent GL04 runtime harness. No production-file writes; real Three.js
// camera/matrix/geometry math, a minimal DOM/wire/clock for lifecycle assertions.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.resolve(__dirname, '../../../..');
const THREE = require(path.join(root, 'webui/three.min.js'));
const HF = require(path.join(root, 'webui/human_fall_preview/human_fall_lib.js'));
function createWorld(query = '') {
  let now = 1000, raf = [], intervals = [], sent = [], logs = [];
  const nodes = {};
  class Element {
    constructor() { this.textContent = ''; this.className = ''; this.style = {}; this.children = []; this.disabled = false;
      this.clientWidth = 800; this.clientHeight = 600; this.width = 800; this.height = 600;
      this.classList = {toggle(){},add(){},remove(){}}; this.listeners = {}; }
    appendChild(c) { this.children.push(c); return c; }
    addEventListener(k, f) { this.listeners[k] = f; }
    getBoundingClientRect() { return {left:0, top:0, width:this.clientWidth, height:this.clientHeight}; }
    getContext() { return new Proxy({}, {get(t,k){ if(k==='measureText')return s=>({width:String(s).length*6}); return t[k] || (()=>{});},set(t,k,v){t[k]=v; return true;}}); }
  }
  function $(id) { return nodes[id] || (nodes[id] = new Element()); }
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 800/600, .05, 2000);
  camera.up.set(0,0,1); camera.position.set(6,-6,5); camera.lookAt(3,0,0);
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array([2.8,-.2,-1,3.2,.2,.5]);
  geo.setAttribute('position', new THREE.BufferAttribute(positions,3)); geo.setDrawRange(0,2);
  const pointsObj = new THREE.Points(geo,new THREE.PointsMaterial()); scene.add(pointsObj);
  const grid = new THREE.GridHelper(20,20); grid.rotation.x=Math.PI/2;scene.add(grid);
  scene.add(new THREE.AxesHelper(.6));
  const context = {$,THREE,HF,scene,camera,geo,positions,pointsObj,controls:{target:new THREE.Vector3(3,0,0),update(){},enabled:true},
    renderer:{domElement:$('gl'),setPixelRatio(){},setSize(){},render(){}},
    document:{createElement:()=>new Element()},location:{search:query},URLSearchParams,TextEncoder,TextDecoder,
    performance:{now:()=>now},devicePixelRatio:1,console,Map,Set,Float32Array,Uint8Array,DataView,
    TOPICS:[],HF_POINTS_TOPIC:'/innolidar_points',no3d:false,dirty3d:false,
    log:(s,l)=>logs.push({s,l}),recordPointsStats(){},renderPoints(){},handleMessage(){},
    resize3d(){camera.aspect=$('view3d').clientWidth/$('view3d').clientHeight;camera.updateProjectionMatrix();},
    fitView(){},fitCanvases(){},requestAnimationFrame:f=>raf.push(f),setInterval:f=>intervals.push(f),
    clearInterval(){},setTimeout:f=>{},fetch:()=>Promise.reject(new Error('No external fixture loading in runtime harness')),
    client:{live:true,ws:{readyState:1,send:b=>sent.push(b)},send:b=>sent.push(b)},
    FoxgloveClient:function(){},addEventListener(){}};
  context.FoxgloveClient.prototype.onJson=function(){}; context.window=context;
  let source=fs.readFileSync(path.join(root,'webui/human_fall_preview/human_fall.js'),'utf8');
  // Expose closures in this ephemeral test VM only. The source on disk is unchanged.
  source=source.replace(/\}\)\(\);\s*$/, 'window.__review={hfSendSelect,hfCurrentCandidateSnapshot,hfRenderState,hfRenderCandidates,hfFrame,hfFinishDrag,hfSelectCandidate,hfSetMode,hfStateAligned,hfRenderPanel,hfGroundReady,hfDrawSupport,hfResizeOverlay,hfBoxRect,hfBoxes};})();');
  vm.createContext(context);vm.runInContext(source,context,{filename:'human_fall.js'});
  function pack(obj){const b=Buffer.from(JSON.stringify(obj));const p=new Uint8Array(b.length+4);new DataView(p.buffer).setUint32(0,b.length,true);p.set(b,4);return p;}
  function message(kind,obj){context.handleMessage('/human_fall/'+kind,100000000000n,pack(obj));}
  function raw(seq=7,sec=100,nsec=1){const p=new Uint8Array(12);const d=new DataView(p.buffer);d.setUint32(0,seq,true);d.setUint32(4,sec,true);d.setUint32(8,nsec,true);context.handleMessage('/innolidar_points',100000000000n,p);}
  function frame(){const q=raf;raf=[];q.forEach(f=>f());}
  function tick(ms){now+=ms;intervals.forEach(f=>f());frame();}
  return {context,nodes,$,scene,camera,geo,pointsObj,sent,logs,message,raw,frame,tick,now:()=>now};
}
module.exports={createWorld,HF,THREE};
