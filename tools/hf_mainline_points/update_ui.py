from pathlib import Path
p=Path('sidequests/human_fusion_lab_next/pointset/r01')
s=(p/'app.js').read_text(encoding='utf8')
def change(a,b):
 global s
 assert a in s,a[:100]
 s=s.replace(a,b)
change('let reviewedParts=new Map(), diagnostic=null, experiment=null, baselineRecord=null, r2CompareRecord=null;', 'let reviewedParts=new Map(), diagnostic=null, experiment=null, baselineRecord=null, r2CompareRecord=null, r3CompareRecord=null;')
# Clear the third comparison on navigation as well.
change('baselineRecord=null;r2CompareRecord=null;reviewedParts.clear();','baselineRecord=null;r2CompareRecord=null;r3CompareRecord=null;reviewedParts.clear();')
change("['r2Compare',r2CompareRecord?.body_3d?.[0],'R2 component20']", "['r2Compare',r2CompareRecord?.body_3d?.[0],'R2 component20'],['r3Compare',r3CompareRecord?.body_3d?.[0],'R3 signed']")
change('const [data,labels,diag,exp,r2]=await Promise.all([', 'const [data,labels,diag,exp,r2,r3]=await Promise.all([')
change("api('/api/diagnostic?'+binding):null", "api((variant.startsWith('ret_')?'/api/retention-diagnostic?':'/api/diagnostic?')+binding+'&variant='+variant):null")
change("api('/api/experiment?'+binding+'&variant=component20'):null]);", "api('/api/experiment?'+binding+'&variant=component20'):null,isActions&&$('compare').checked?api('/api/experiment?'+binding+'&variant=r3_signed'):null]);")
change('r2CompareRecord=r2;record=', 'r2CompareRecord=r2;r3CompareRecord=r3;record=')
change("$('sourceDownload').href='/api/source-members?'+binding+'&dataset=actions';", "$('sourceDownload').href=(variant.startsWith('ret_')?'/api/retention-members?':'/api/source-members?')+binding+'&variant='+variant+'&dataset=actions';")
change("unselected:'未选碎片/噪声'", "unselected:'未选碎片/噪声',domain_rejected:'域外删除（有限XYZ）',cluster_rejected:'聚类噪声/资格/未选',candidate_pool:'当前背景候选池 UNKNOWN',recovered:'背景恢复 UNKNOWN'")
change("unselected:'#bb83ca'", "unselected:'#bb83ca',domain_rejected:'#758096',cluster_rejected:'#b495db',candidate_pool:'#ffcc66',recovered:'#ff9b43'")
change("for(const id of ['r1Compare','r2Compare'])", "for(const id of ['r1Compare','r2Compare','r3Compare'])")
change("if(hit){const m=experiment?", "if(hit){showSource(hit.id);const m=experiment?")
change("if(best>=0)$('sourceHover').textContent=", "if(best>=0){showSource(layer.display_source_indices[best]);$('sourceHover').textContent=")
change("· 身份UNKNOWN`;};}", "· 身份UNKNOWN`;} };}")
s += "\nasync function showSource(index){const token=request;try{const variant=$('variant').value.startsWith('ret_')?$('variant').value:'ret_combined';const d=await api(`/api/retention-source?sid=${current.session_id}&fi=${fi}&index=${index}&variant=${variant}`);if(token===request)$('sourceLedger').textContent=JSON.stringify(d,null,2);}catch(e){if(token===request)$('sourceLedger').textContent=e.message;}}\n"
(p/'app.js').write_text(s,encoding='utf8')
s=(p/'index.html').read_text(encoding='utf8')
s=s.replace('<option value="r3_signed_feedback">','<option value="ret_combined">新候选：当前背景保留 · UNKNOWN</option><option value="ret_feedback">新候选：独立tracker反馈</option><option value="ret_r3">新候选：接固定R3对照</option><option value="r3_signed_feedback">')
s=s.replace('grid-template-columns:1fr 1fr;gap:8px','grid-template-columns:1fr 1fr 1fr;gap:8px')
s=s.replace('<canvas id="cloud"', '<div><p id="r3CompareTitle">R3 signed</p><canvas id="r3Compare" style="height:310px"></canvas></div>\n<canvas id="cloud"')
s=s.replace('五层同帧对照 · 原始/删除/前景/旧目标/未选','删除层对照 · 原链五层＋新候选池/恢复/域外')
s=s.replace('<div id="metrics"></div>', '<details><summary>完整逐点删除账本查询</summary><pre id="sourceLedger">点击主图或删除层的点查询源行、终态及opaque字节。</pre></details><div id="metrics"></div>')
s=s.replace('同帧R1 / R2整碎片 / 当前方案','同帧R1 / R2 / R3 / 当前方案')
(p/'index.html').write_text(s,encoding='utf8')

