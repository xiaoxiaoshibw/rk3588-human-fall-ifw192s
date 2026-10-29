/* Same-layout viewer: real-time spacing, measurement gaps, alarms and camera lifecycle. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const template=fs.readFileSync(path.join(__dirname,'replay_template.html'),'utf8');
const code=template.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace('@@VIEW@@',JSON.stringify({yaw:-1.08,pitch:.42,dist:4.8,tx:1,ty:0,tz:.9}))
  .replace('@@SENSOR_ORIGIN@@','[0,0,131]');
let passed=0;
function test(name,fn){try{fn();passed++;console.log('ok '+name);}catch(e){console.error('FAIL '+name,e);process.exitCode=1;}}
function frames(){return [0,.1,.2,.3].map((t,i)=>({i,t,st:i===2?'suspected':'unknown',rs:['measured_descent'],
  tid:i?'g0_t1':null,n:i?20:0,hm:i?.4:null,ht:i?.6:null,sp:i?.7:null,rt:i?.4:null,vt:null,
  bb:i?[0,0,0,100,50,60]:null,c:i?[50,25]:null,tg:i?[0,0,0,100,50,60]:[],bg:[0,0,0,200,100,100],
  cam:[i,.02],bl:null,generation:0,reset_reason:null,target_reason:i?'selected':'predicted'}));}
function run(data,renderCost=0,live=false){
  const elements={},events={},timers=new Map();let serial=0;
  function element(id){
    const listeners={},attrs={};const ctx={rects:[],arcs:[],strokes:[],current:[],
      clearRect(){this.rects=[];this.arcs=[];this.strokes=[];},fillRect(...a){this.rects.push({style:this.fillStyle,args:a});},
      beginPath(){this.current=[];},moveTo(...a){this.current.push(['M',...a]);},lineTo(...a){this.current.push(['L',...a]);},
      stroke(){this.strokes.push({style:this.strokeStyle,points:this.current.slice()});},fill(){},arc(...a){this.arcs.push(a);},
      fillText(){},setLineDash(){}};
    return {width:id==='chart'?1400:960,height:id==='chart'?150:640,style:{},value:'0',textContent:'',innerHTML:'',className:'',
      classList:{add(){},remove(){}},getContext(){return ctx;},ctx,
      getAttribute(n){return attrs[n]??null;},setAttribute(n,v){attrs[n]=v;},removeAttribute(n){delete attrs[n];},
      setPointerCapture(){},getBoundingClientRect(){return {left:0,top:0,width:1400,height:150};},
      addEventListener(n,f){listeners[n]=f;},emit(n,e={}){listeners[n]?.(e);},click(){listeners.click?.({});}};
  }
  const document={getElementById(id){return elements[id]||(elements[id]=element(id));},querySelector(){return element('verdict');}};
  const window={FRAMES:data,RANGE_RUNTIME:live,addEventListener(n,fn){events[n]=fn;}};
  let clock=0;
  new Function('window','document','setTimeout','clearTimeout','performance',code)(window,document,(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id;},id=>timers.delete(id),{now(){const n=clock;clock+=renderCost;return n;}});
  return {e:elements,timers,events,window,show(i){elements.slider.emit('input',{target:{value:String(i)}});}};
}

test('动态接收保持同款实测框，暂停/历史选择不会被最新帧覆盖',()=>{
  const app=run(frames(),0,true), data=frames();
  app.window.rangeRuntimeAppend({rows:data.map((frame,i)=>({seq:i+1,frame}))});
  assert.equal(app.e.slider.value,'3');assert.equal(app.e.play.textContent,'暂停跟随');
  app.e.play.click();app.show(1);
  app.window.rangeRuntimeAppend({rows:[{seq:5,frame:{...data[3],i:4,t:.4}}]});
  assert.equal(app.e.slider.value,'1');
  app.e.play.click();assert.equal(app.e.slider.value,'4');
  const missing={...data[0],i:5,t:.5};
  app.window.rangeRuntimeAppend({rows:[{seq:6,frame:missing}]});
  assert.equal(app.e.sState.textContent,'未知');assert(!app.e.cloud.ctx.strokes.some(s=>s.style==='#35ff7a'));
  assert.equal(app.timers.size,0);
});
test('动态缓存最多240帧，重复批次不会重复追加，源序号保持',()=>{
  const app=run(frames(),0,true), prototype=frames()[1];
  const rows=Array.from({length:300},(_,i)=>({seq:i+1,frame:{...prototype,i,t:i*.1}}));
  app.window.rangeRuntimeAppend({rows});
  assert.equal(app.window.FRAMES.length,240);assert.equal(app.window.FRAMES[0].i,60);
  app.window.rangeRuntimeAppend({rows:rows.slice(-10)});assert.equal(app.window.FRAMES.length,240);
  assert.equal(app.e.slider.max,'239');assert.equal(app.window.rangeRuntimeSeq,300);
  app.show(10);const pinned=app.window.FRAMES[10];
  app.window.rangeRuntimeAppend({rows:Array.from({length:300},(_,i)=>({seq:i+301,frame:{...prototype,i:i+300,t:(i+300)*.1}}))});
  assert.equal(app.window.FRAMES.length,240);assert.strictEqual(app.window.FRAMES[Number(app.e.slider.value)],pinned);
});
test('首个批次到达前暂停也保留选中帧',()=>{
  const data=frames(),app=run(data,0,true),selected=data[1];
  app.e.play.click();
  app.window.rangeRuntimeAppend({rows:Array.from({length:300},(_,i)=>({seq:i+50,frame:{...selected,i:i+49,t:(i+49)*.1}}))});
  assert.equal(app.window.FRAMES.length,240);
  assert.strictEqual(app.window.FRAMES[Number(app.e.slider.value)],selected);
});
test('动态相机沿用过期和加载失败隐藏',()=>{
  const app=run(frames(),0,true), data=frames();
  app.window.rangeRuntimeAppend({rows:[{seq:1,frame:data[2]}]});
  assert.equal(app.e.cam.getAttribute('src'),'/camera.jpg?i=2');
  app.e.cam.onerror();assert.equal(app.e.cam.style.visibility,'hidden');
  app.window.rangeRuntimeAppend({rows:[{seq:2,frame:{...data[3],cam:[3,.4],cam_status:'stale'}}]});
  assert.equal(app.e.cam.getAttribute('src'),null);
});

test('保留绿框/曲线/报警布局并使用同一实测目标',()=>{
  const {e,show}=run(frames());assert.equal(e.slider.value,'1');assert.equal(e.sTrack.textContent,'g0_t1');
  assert(e.cloud.ctx.strokes.some(s=>s.style==='#35ff7a'));show(2);assert(e.alarm.className.includes('hot'));
  assert(e.alarmText.textContent.includes('measured_descent'));assert(e.metrics.innerHTML.includes('目标点数'));
});
test('图片加载前隐藏，旧加载回调不覆盖新帧，错误时隐藏',()=>{
  const {e,show}=run(frames());assert.equal(e.cam.style.visibility,'hidden');const oldLoad=e.cam.onload;
  show(2);oldLoad();assert.equal(e.cam.style.visibility,'hidden');e.cam.onload();assert.equal(e.cam.style.visibility,'visible');
  assert(e.camNote.textContent.includes('物理同步UNKNOWN'));e.cam.onerror();assert.equal(e.cam.style.visibility,'hidden');
  assert(e.camNote.textContent.includes('加载失败'));
});
test('过期相机不复用旧画面',()=>{
  const data=frames();data[2].cam=[2,.21];const {e,show}=run(data);e.cam.onload();show(2);
  assert.equal(e.cam.getAttribute('src'),null);assert.equal(e.cam.style.visibility,'hidden');assert.equal(e.camMeta.textContent,'相机过期');
});
test('同一图片延迟加载跨帧时显示当前时间差',()=>{
  const data=frames();data[1].cam=[7,.02];data[2].cam=[7,-.08];const {e,show}=run(data);
  show(2);e.cam.onload();assert(e.camNote.textContent.includes('-0.080 s'));
});
test('无目标不是无跌倒，清空测量并抑制旧报警',()=>{
  const data=frames();data[0].st='suspected';const {e,show}=run(data);show(0);
  assert.equal(e.alarmTitle.textContent,'状态未知');assert(!e.alarm.className.includes('hot'));assert.equal(e.sState.textContent,'未知');
  assert.equal(e.chart.ctx.arcs.length,0);assert(e.alarmText.textContent.includes('predicted'));
  assert(e.metrics.innerHTML.includes('状态</span><b>未知'));
});
test('未知高度不画为零米',()=>{
  const data=frames();data[1].hm=null;const {e}=run(data);assert.equal(e.chart.ctx.arcs.length,0);
});
test('时间轴点击按真实时间寻找最近帧',()=>{
  const data=frames();data[3].t=2;const {e}=run(data);
  e.chart.emit('click',{clientX:46+(1400-12-46)*.3,clientY:20});assert.equal(e.slider.value,'2');
});
test('播放保留实际断档时长并在末帧停止',()=>{
  const data=frames();data[3].t=2;const {e,timers,show}=run(data);show(2);e.play.click();
  assert.equal([...timers.values()][0].ms,1800);[...timers.values()][0].fn();assert.equal(e.slider.value,'3');assert.equal(e.play.textContent,'播放');
  assert(e.chart.ctx.rects.some(r=>r.style==='#364252' && r.args[2]>100),'断档区应为未知底色');
});
test('切目标/换代/断档不连高度曲线',()=>{
  const data=frames();data[2].tid='other';data[3].generation=1;const {e}=run(data);
  const curve=e.chart.ctx.strokes.find(s=>s.style==='#57d9ff');assert.equal(curve.points.filter(p=>p[0]==='L').length,0);
});
test('播放截止时间补偿绘制耗时',()=>{
  const {e,timers}=run(frames(),20);e.play.click();assert.equal([...timers.values()][0].ms,80);
});
test('报警红区分段，不涂过恢复间隔，当前起点用本段',()=>{
  const data=frames();data[1].st='suspected';data[2].st='recovering';data[3].st='suspected';const {e,show}=run(data);
  assert.equal(e.chart.ctx.rects.filter(r=>r.style==='rgba(255,77,94,.14)').length,2);show(3);
  assert(e.alarmText.textContent.includes('本段起于 0.30 s'));
});
test('时钟回退显式按帧序显示，曲线断开',()=>{
  const data=frames();data[2].t=-.1;const {e,show}=run(data);show(2);assert(e.tlabel.textContent.includes('时钟回退'));
});
test('原因码通过文本/转义渲染',()=>{
  const data=frames();data[2].rs=['<img src=x onerror=alert(1)>'];const {e,show}=run(data);show(2);
  assert(e.metrics.innerHTML.includes('&lt;img'));assert(!e.metrics.innerHTML.includes('<img'));
});
test('拖动/缩放/复位/键盘/缺相机保持可用',()=>{
  const {e,events,show}=run(frames().map(f=>({...f,cam:null})));assert.equal(e.camMeta.textContent,'无相机');
  e.cloud.emit('pointerdown',{clientX:0,clientY:0,pointerId:1});e.cloud.emit('pointermove',{clientX:20,clientY:30});e.cloud.emit('pointerup');
  e.cloud.emit('wheel',{deltaY:-1,preventDefault(){}});e.cloud.emit('dblclick');e.jump.click();assert.equal(e.slider.value,'2');
  events.keydown({key:'ArrowRight',preventDefault(){}});assert.equal(e.slider.value,'3');show(0);assert.equal(e.slider.value,'0');
});
assert(!code.includes('@@'));console.log(passed+' replay page tests passed');
