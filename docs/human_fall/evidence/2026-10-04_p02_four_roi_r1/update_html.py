"""Use four-ROI results in the existing, user-requested preview HTML."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
TARGET = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_level_preview_r1/06_PREVIEW.html'


def once(text, old, new):
    assert text.count(old) == 1, 'unexpected HTML revision: ' + old[:60]
    return text.replace(old, new, 1)


def main():
    baseline = json.loads((OUT/'00_BASELINE.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(TARGET.read_bytes()).hexdigest() == baseline['target_sha256'], 'concurrent HTML edit'
    html = TARGET.read_text(encoding='utf-8')
    start = html.index('const DATA=') + len('const DATA='); end = html.index(';\nconst frame=', start)
    data = json.loads(html[start:end]); report = json.loads((OUT/'03_RESULTS.json').read_text(encoding='utf-8'))
    assert report['consensus'] == 'PASS'
    models = report['estimators']; data['algorithm_models'] = models
    data['metrics'] = {'confirmed_all_roi_A_C_count': report['identity']['point_count'],
                       'four_roi_counts': report['identity']['roi_counts'],
                       'leave_one_region_out': report['leave_one_region_out'],
                       'joint_tls_stats': {k: models['tls'][k] for k in ['rms_m', 'p95_m', 'support_fraction']},
                       'fitting_frames': 193, 'preview_fragments': len(data['frames']), 'physical_verified': False}
    data['model'].update({'pitch_deg': models['tls']['pitch_deg'], 'roll_deg': models['tls']['roll_deg'],
                         'rotation': models['tls']['rotation'], 'translation_m': models['tls']['translation_m'],
                         'plane_source': {'normal': models['tls']['normal_source'], 'offset_m': models['tls']['d_source_m']},
                         'coverage': 'four user-selected ROI joint observed display plane, extrapolation unverified'})
    data['model']['model_id'] = 'display-four:' + hashlib.sha256(json.dumps(models['tls'], sort_keys=True).encode()).hexdigest()
    bounds = report['identity']['roi_bounds_display']
    for frame in data['frames']:
        frame['roi'] = []
        for point in frame['before']:
            memberships = [int(r) for r, (xl,xh,yl,yh) in bounds.items() if xl <= point[0] <= xh and yl <= point[1] <= yh]
            assert len(memberships) <= 1
            frame['roi'].append(memberships[0] if memberships else 0)
        frame['after'] = (np.array(frame['source']) @ np.array(models['tls']['rotation']).T + models['tls']['translation_m']).tolist()
    assert data['model']['physical_measurement']['height_m'] == 1.14
    html = html[:start] + json.dumps(data, ensure_ascii=True, allow_nan=False).replace('<','\\u003c') + html[end:]
    html = once(html, '三算法横排（#3 地面点集）', '三算法横排（四区联合拟合）')
    old_stats_start = html.index('<div id="algorithmStats"'); old_stats_end = html.index('<p id="info">', old_stats_start)
    cards = []
    for name in ['tls','svd','ransac']:
        m=models[name]
        cards.append(f'<article style="padding:12px;background:white;border:1px solid #d6dee7;border-radius:6px"><b>{name.upper()}</b>'
            f'<p style="font-size:14px">pitch {m["pitch_deg"]:.4f}° · roll {m["roll_deg"]:.4f}°<br>Z 平移 {m["d_source_m"]:.6f} m<br>'
            f'整体 RMS {100*m["rms_m"]:.2f} cm · P95 {100*m["p95_m"]:.2f} cm</p></article>')
    table='<div id="regionReport" style="overflow:auto;margin:12px 0"><b>四区共同平面的逐区残差（参与拟合，非独立验证）</b><table style="border-collapse:collapse;width:100%;max-width:2100px"><thead><tr><th>区域 / 点数</th><th>TLS RMS / P95</th><th>SVD RMS / P95</th><th>RANSAC RMS / P95</th><th>留一区 TLS RMS / P95</th></tr></thead><tbody>'
    for region in ['1','2','3','4']:
        color={'1':'#2ecc71','2':'#d1ab16','3':'#dc7c19','4':'#9b59b6'}[region]
        table+=f'<tr><td style="padding:10px;border-bottom:1px solid #ddd;color:{color}">#{region} / {report["identity"]["roi_counts"][region]:,}</td>'
        for name in ['tls','svd','ransac']:
            r=models[name]['per_region'][region]
            table+=f'<td style="padding:10px;border-bottom:1px solid #ddd">{100*r["rms_m"]:.2f} / {100*r["p95_m"]:.2f} cm · {r["quality"]}</td>'
        r=report['leave_one_region_out'][region]; status_color='#a43b30' if r['quality']=='FAIL' else '#286a3a'
        table+=f'<td style="padding:10px;border-bottom:1px solid #ddd;color:{status_color}">{100*r["rms_m"]:.2f} / {100*r["p95_m"]:.2f} cm · {r["quality"]}</td></tr>'
    table+='</tbody></table><p>留一区验证：该区域不参与当折拟合，使用另外三区预测它。未通过的结果保留；四区都已曝光，此检查不等于最终物理验收。</p></div>'
    html=html[:old_stats_start]+'<div id="algorithmStats" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:2100px;margin:12px 0">'+''.join(cards)+'</div>'+table+html[old_stats_end:]
    html=once(html, '橙色是同一批 #3 VAL 源点，灰色是周边场景。', '绿色 #1、黄色 #2、橙色 #3、紫色 #4 是四个拟合区域的同一批源点，灰色是周边场景。')
    html=once(html, '#3 局部修正仅用于对照，整场适用范围与测距精度尚未确认。', '四区联合修正用于当前观测数据；其他区域适用范围与测距精度尚未确认。')
    html=once(html, "for(let pass=0;pass<2;pass++){ctx.fillStyle=pass?'#dc7c19':'#9ba6b0';points.forEach((p,i)=>{if(flags[i]===pass)ctx.fillRect(px(p[axis])-1,py(p[2])-1,pass?3:2,pass?3:2)})}",
        "for(let pass=0;pass<5;pass++){ctx.fillStyle=['#9ba6b0','#2ecc71','#d1ab16','#dc7c19','#9b59b6'][pass];points.forEach((p,i)=>{if(flags[i]===pass)ctx.fillRect(px(p[axis])-1,py(p[2])-1,pass?3:2,pass?3:2)})}")
    html=html.replace('f.roi3,axis', 'f.roi,axis')
    html=once(html, '三列坐标范围相同，橙色为同一批 #3 源点。', '三列坐标范围相同，四种颜色表示同一批四区源点。')
    html=once(html, '${DATA.metrics.confirmed_roi3_A_C_count.toLocaleString()} 个 #3 地面点。仅 #3 局部验证', '${DATA.metrics.confirmed_all_roi_A_C_count.toLocaleString()} 个四区观测点联合估计。按原始点等权；留一区检查有失败，不代表整场物理标定通过')
    TARGET.write_text(html,encoding='utf-8')
    with (OUT/'04_HTML_UPDATE.json').open('x',encoding='utf-8') as stream:
        json.dump({'target':str(TARGET),'target_sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                   'point_count':report['identity']['point_count'],'physical_height_record_m':1.14,'old_html_preserved':'00_HTML_BEFORE.html'},stream,indent=2)


if __name__ == '__main__':
    main()
