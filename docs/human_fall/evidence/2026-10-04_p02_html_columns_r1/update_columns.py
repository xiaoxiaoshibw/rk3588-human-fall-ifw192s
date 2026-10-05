"""Layout-only update of the requested offline preview."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
TARGET = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_level_preview_r1/06_PREVIEW.html'
html = TARGET.read_text(encoding='utf-8')
assert TARGET.read_bytes() == (HERE / '00_PREVIEW_BEFORE.html').read_bytes()
start = html.index('const DATA=') + len('const DATA=')
end = html.index(';\nconst frame=', start)
data = json.loads(html[start:end])
html = html.replace('max-width:1400px;', 'max-width:2100px;', 1)
html = html.replace('<h1>点云离线配平：沿用 annotator 方式</h1>', '<h1>点云配平：三算法横向对比</h1>', 1)
html = html.replace('右侧默认先 R_y(+26°)，再沿 Z 平移 +1.340 m。', 'TLS、SVD、RANSAC 使用同一帧并排显示；也可切回 annotator 方式。', 1)
html = html.replace('右侧模型', '展示方式', 1)
html = html.replace('<option value="local">算法配平（#3 地面点集）</option>', '<option value="local" selected>三算法横排（#3 地面点集）</option>', 1)
html = html.replace('<label>算法估计器 <select id="estimator"><option value="tls">TLS（默认）</option><option value="svd">SVD</option><option value="ransac">RANSAC</option></select></label>', '', 1)
cards = []
for name in ['tls', 'svd', 'ransac']:
    m = data['algorithm_models'][name]
    cards.append('<article style="padding:12px;background:white;border:1px solid #d6dee7;border-radius:6px">'
        f'<b>{name.upper()}</b><p style="margin:8px 0;font-size:14px">pitch {m["pitch_deg"]:.4f}° · roll {m["roll_deg"]:.4f}°<br>'
        f'Z 平移 {m["translation_m"][2]:.6f} m<br>RMS {100*m["rms_m"]:.2f} cm · P95 {100*m["p95_m"]:.2f} cm</p></article>')
cards_html = '<div id="algorithmStats" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:2100px;margin:12px 0">' + ''.join(cards) + '</div>'
html = html.replace('<p id="info"></p>', cards_html + '<p id="info"></p>', 1)
html = html.replace('const frame=', 'const frame=', 1)
html = html.replace("estimator=document.querySelector('#estimator'),", "algorithmStats=document.querySelector('#algorithmStats'),", 1)
html = html.replace("zmin=before.value==='source'?-2:-.55", "zmin=mode.value==='local'?-.55:(before.value==='source'?-2:-.55)", 1)
begin = html.index('function draw(){')
finish = html.index('\n</script>', begin)
html = html[:begin] + '''function draw(){
 const f=DATA.frames[Number(frame.value)],p=Number(pitch.value),h=Number(tz.value),algorithm=mode.value==='local',plot=document.querySelector('#plot');
 plot.width=algorithm?2100:1400;plot.height=820;ctx.clearRect(0,0,plot.width,plot.height);
 algorithmStats.style.display=algorithm?'grid':'none';
 pitch.disabled=tz.disabled=before.disabled=algorithm;
 algorithmButton.textContent=algorithm?'✓ 三算法横排':'算法配平';
 if(!algorithm&&(pitch.value.trim()===''||tz.value.trim()===''||!Number.isFinite(p)||!Number.isFinite(h)||p < -90||p > 90||h < -3||h > 3)){document.querySelector('#info').textContent='请输入合法角度和平移量';return}
 if(algorithm){
  ['tls','svd','ransac'].forEach((name,column)=>{
   const points=algorithmPoints(f.source,name);
   for(let axis=0;axis<2;axis++)panel(points,f.roi3,axis,column*700,axis*400,name.toUpperCase()+' · '+(axis?'YZ':'XZ'));
  });
  document.querySelector('#info').textContent=`${f.name} · TLS / SVD / RANSAC 同帧横排；三列坐标范围相同，橙色为同一批 #3 源点。`;
 }else{
  const a=p*Math.PI/180,c=Math.cos(a),s=Math.sin(a),right=f.source.map(q=>[c*q[0]+s*q[2],q[1],-s*q[0]+c*q[2]+h]);
  for(let axis=0;axis<2;axis++){panel(f[before.value],f.roi3,axis,0,axis*400,before.value==='source'?'原始雷达':'原名义显示');panel(right,f.roi3,axis,700,axis*400,'annotator 方式配平')}
  document.querySelector('#info').textContent=`${f.name} · R_y(${p.toFixed(2)}°)，再 Z += ${h.toFixed(3)}m；实测记录仍为 1.14m。`;
 }
 document.querySelector('#algorithmInfo').textContent=`三种估计器使用 A/C 的同一批 ${DATA.metrics.confirmed_roi3_A_C_count.toLocaleString()} 个 #3 地面点。仅 #3 局部验证，实测高度记录仍为 1.14m。`;
}
algorithmButton.onclick=()=>{mode.value='local';draw()};frame.onchange=before.onchange=mode.onchange=draw;pitch.oninput=tz.oninput=draw;draw();''' + html[finish:]
assert 'id="estimator"' not in html
TARGET.write_text(html, encoding='utf-8')
