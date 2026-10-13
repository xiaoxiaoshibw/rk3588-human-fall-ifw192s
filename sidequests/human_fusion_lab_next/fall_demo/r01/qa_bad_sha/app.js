'use strict';
const $ = id => document.getElementById(id);
let data, rows, frame = 0, running = false, lastTick = 0, acknowledged = false;
const labels = {unknown:'观测未知', upright:'正常直立', descending:'快速下降', low_posture_unclassified:'低姿态 · 待判断', suspected:'疑似跌倒', confirmed:'跌倒告警 · 模拟', recovering:'正在恢复'};
function pause(){running=false;$('play').textContent='播放';}
function seek(i){pause();frame=Math.max(0,Math.min(rows.length-1,i));render();}
function render(){
  const r=rows[frame],s=r.state,f=s.features,events=rows.slice(0,frame+1).filter(x=>x.state.new_event);
  $('timeline').value=frame;$('clock').textContent=`${r.t.toFixed(1)} / 18.0 秒`;$('frameInfo').textContent=`#${frame} · 合成点云`;
  $('state').textContent=labels[s.state];$('state').className=s.state==='confirmed'?'alarm':'state';
  $('height').textContent=f.height_median_m===null?'—':`${f.height_median_m.toFixed(2)} m`;
  $('speed').textContent=f.descent_rate_m_s===null?'—':`${f.descent_rate_m_s.toFixed(2)} m/s`;
  $('track').textContent=r.observed?'DEMO-01 · 实测样例':'遮挡 · 无观测';
  const reasons={upright:'目标处于直立状态，当前无跌倒告警。',descending:'近期高度下降，正在检查是否持续低姿态。',low_posture_unclassified:'处于低姿态，仅凭这一帧不能判定跌倒。',suspected:'观察到下降且持续低姿态，继续等待确认时长。',confirmed:'规则已触发模拟告警。该结果不代表真实传感器准确率。',recovering:'目标高度回升，正在等待稳定恢复。',unknown:'当前没有可用实测点，暂停姿态判断。'};
  $('reason').textContent=reasons[s.state]+($('scenario').value==='lie_fast'?' 本场景是主动躺下，与跌倒几何相同，因此会误报。':'');
  ['step1','step2','step3'].forEach((id,n)=>$(id).className='step'+((n===0?['descending','suspected','confirmed'].includes(s.state):n===1?['suspected','confirmed'].includes(s.state):s.state==='confirmed')?' on':''));
  $('events').textContent=events.length?`${events[0].t.toFixed(1)} 秒 · DEMO-01 · 模拟跌倒告警（${acknowledged?'已查看':'待查看'}）`:'截至当前帧暂无告警';
  $('ack').disabled=!events.length||acknowledged;$('prev').disabled=frame===0;$('next').disabled=frame===rows.length-1;
  draw(r);
}
function draw(r){
  const c=$('scene'),dpr=window.devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*dpr;c.height=h*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);
  const scale=Math.min(w/5.5,h/3.5),project=(a,b,z)=>[w*.50+(a-b*.55)*scale,h*.79+(b*.3)*scale-z*scale];
  x.strokeStyle='#253c50';x.lineWidth=1;
  for(let n=-4;n<=4;n++){x.beginPath();x.moveTo(...project(n*.5,-2,0));x.lineTo(...project(n*.5,2,0));x.stroke();x.beginPath();x.moveTo(...project(-2,n*.5,0));x.lineTo(...project(2,n*.5,0));x.stroke();}
  x.fillStyle='#6e879f';x.font='12px Segoe UI';x.fillText('合成场景 / 地面 z = 0 m',20,28);x.fillText('非真实雷达采集',20,48);
  const color=r.state.state==='confirmed'?'#ff7d84':r.state.state==='suspected'?'#f0c675':'#68ddc5';
  x.fillStyle=color;for(const p of r.points){const q=project(...p);x.beginPath();x.arc(q[0],q[1],2,0,Math.PI*2);x.fill();}
  x.font='14px Segoe UI';x.fillText(r.observed?'DEMO-01 · 合成已知目标':'UNKNOWN · 遮挡期间无实测点',20,h-22);
  if(r.points.length){const xx=r.points.map(p=>p[0]),zz=r.points.map(p=>p[2]),a=project(Math.min(...xx)-.08,0,Math.max(...zz)+.06),b=project(Math.max(...xx)+.08,0,Math.min(...zz)-.03);x.strokeStyle=color;x.setLineDash([5,4]);x.strokeRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);}
}
function tick(now){if(running&&now-lastTick>=100/Number($('rate').value)){lastTick=now;if(frame<rows.length-1){frame++;render();}else pause();}requestAnimationFrame(tick);}
async function init(){
  try{
    const [m,d]=await Promise.all([fetch('manifest.json'),fetch('data.json')]);if(!m.ok||!d.ok)throw Error('数据读取失败');const manifest=await m.json(),bytes=await d.arrayBuffer();
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');if(digest!==manifest.data_sha256)throw Error('数据 SHA 不匹配，停止展示');data=JSON.parse(new TextDecoder().decode(bytes));
    if(data.provenance!=='SYNTHETIC_KNOWN_TARGET')throw Error('来源类型不符合本演示');
    for(const [id,s] of Object.entries(data.scenarios)){$('scenario').add(new Option(s.name,id));}
    for(const id of ['scenario','play','prev','next','reset','jump','timeline'])$(id).disabled=false;
    $('integrity').textContent=`数据 SHA-256 校验通过 · ${digest.slice(0,16)}…`;
    $('scenario').onchange=()=>{pause();rows=data.scenarios[$('scenario').value].rows;frame=0;acknowledged=false;$('jump').disabled=!rows.some(r=>r.state.new_event);render();};
    $('play').onclick=()=>{if(running)pause();else{if(frame===rows.length-1)frame=0;running=true;lastTick=performance.now();$('play').textContent='暂停';render();}};
    $('prev').onclick=()=>seek(frame-1);$('next').onclick=()=>seek(frame+1);$('reset').onclick=()=>{acknowledged=false;seek(0);};$('timeline').oninput=()=>seek(Number($('timeline').value));
    $('jump').onclick=()=>seek(rows.findIndex(r=>r.state.new_event));$('ack').onclick=()=>{acknowledged=true;render();};window.addEventListener('resize',()=>draw(rows[frame]));
    $('scenario').onchange();requestAnimationFrame(tick);
  }catch(e){pause();$('state').textContent='无法加载';$('error').textContent=e.message;}
}
init();
