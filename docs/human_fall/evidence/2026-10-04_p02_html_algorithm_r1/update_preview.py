"""Add an explicit algorithm selector to the user-authorized offline HTML."""
import json
from pathlib import Path
import math
import hashlib

ROOT = Path(__file__).resolve().parents[4]
TARGET = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_level_preview_r1/06_PREVIEW.html'
HERE = Path(__file__).resolve().parent


def once(text, old, new):
    assert text.count(old) == 1, 'unexpected HTML version'
    return text.replace(old, new, 1)


def main():
    html = TARGET.read_text(encoding='utf-8')
    assert TARGET.read_bytes() == (HERE / '02_PREVIEW_BEFORE.html').read_bytes(), 'HTML changed since snapshot'
    start = html.index('const DATA=') + len('const DATA=')
    end = html.index(';\nconst frame=', start)
    data = json.loads(html[start:end])
    record = json.loads((TARGET.parent / '10_SOURCE_SPREAD_AND_ESTIMATORS.json').read_text(encoding='utf-8'))
    models = {}
    for key, plane in record['same_source_domain_estimators'].items():
        p, r = math.radians(plane['pitch_deg']), math.radians(plane['roll_deg'])
        cp, sp, cr, sr = math.cos(p), math.sin(p), math.cos(r), math.sin(r)
        models[key] = {**plane, 'rotation': [[cp, 0, sp], [sr*sp, cr, -sr*cp], [-cr*sp, sr, cr*cp]],
                       'translation_m': [0., 0., plane['d_source_m']]}
    data['algorithm_models'] = models
    html = html[:start] + json.dumps(data, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c') + html[end:]
    html = once(html, '<option value="local">#3 局部平面修正</option>', '<option value="local">算法配平（#3 地面点集）</option>')
    html = once(html, '<p id="info"></p>', '''<button id="algorithmButton" type="button" style="padding:8px 16px;margin:8px;border:1px solid #357059;border-radius:5px;background:#e4f2e8;font:inherit">算法配平</button>
<label>算法估计器 <select id="estimator"><option value="tls">TLS（默认）</option><option value="svd">SVD</option><option value="ransac">RANSAC</option></select></label>
<div id="algorithmInfo" style="margin:12px 0;padding:12px;background:#eef3f7;border-radius:6px"></div>
<p id="info"></p>''')
    html = once(html, "tz=document.querySelector('#tz'),ctx=", "tz=document.querySelector('#tz'),estimator=document.querySelector('#estimator'),algorithmButton=document.querySelector('#algorithmButton'),ctx=")
    html = once(html, 'function draw(){', '''function algorithmPoints(source, name){const m=DATA.algorithm_models[name];return source.map(q=>m.rotation.map((row,i)=>row[0]*q[0]+row[1]*q[1]+row[2]*q[2]+m.translation_m[i]))}
function draw(){''')
    html = once(html, "if(!Number.isFinite(p)||!Number.isFinite(h)||p < -90||p > 90||h < -3||h > 3)", "if(mode.value!=='local'&&(pitch.value.trim()===''||tz.value.trim()===''||!Number.isFinite(p)||!Number.isFinite(h)||p < -90||p > 90||h < -3||h > 3))")
    html = once(html, "right=mode.value==='local'?f.after:f.source.map", "right=mode.value==='local'?algorithmPoints(f.source,estimator.value):f.source.map")
    html = once(html, "mode.value==='local'?'#3 局部修正':'annotator 方式配平'", "mode.value==='local'?'算法配平 '+estimator.value.toUpperCase():'annotator 方式配平'")
    html = once(html, 'const m=DATA.model,r=DATA.metrics.roi3_ground_z_stats;', 'const m=DATA.algorithm_models[estimator.value];')
    html = once(html, "`${f.name} · 局部模型 pitch ${m.pitch_deg.toFixed(4)}° / roll ${m.roll_deg.toFixed(4)}° / Z平移 ${m.translation_m[2].toFixed(4)}m；A/C #3 全点 RMS ${(100*r.rms_m).toFixed(2)}cm / P95 ${(100*r.p95_abs_m).toFixed(2)}cm。`", "`${f.name} · ${estimator.value.toUpperCase()} 算法配平：pitch ${m.pitch_deg.toFixed(4)}° / roll ${m.roll_deg.toFixed(4)}° / Z平移 ${m.translation_m[2].toFixed(4)}m；A/C #3 全点 RMS ${(100*m.rms_m).toFixed(2)}cm / P95 ${(100*m.p95_m).toFixed(2)}cm。`")
    html = once(html, "pitch.disabled=tz.disabled=mode.value==='local';", '''pitch.disabled=tz.disabled=mode.value==='local';
 estimator.disabled=mode.value!=='local';
 algorithmButton.textContent=mode.value==='local'?'✓ 算法配平已启用':'算法配平';
 document.querySelector('#algorithmInfo').textContent=`${estimator.value.toUpperCase()}：使用 A/C 的同一批 ${DATA.metrics.confirmed_roi3_A_C_count.toLocaleString()} 个 #3 地面点估计平面，再计算旋转与 Z 平移。pitch ${m.pitch_deg.toFixed(4)}° / roll ${m.roll_deg.toFixed(4)}° / Z平移 ${m.translation_m[2].toFixed(6)}m；RMS ${(100*m.rms_m).toFixed(2)}cm，P95 ${(100*m.p95_m).toFixed(2)}cm。仅 #3 局部验证；实测高度记录仍为 1.14m。`;''')
    html = once(html, 'frame.onchange=before.onchange=mode.onchange=draw;', "algorithmButton.onclick=()=>{mode.value='local';draw()};frame.onchange=before.onchange=mode.onchange=estimator.onchange=draw;")
    assert '__PAYLOAD__' not in html and data['model']['physical_measurement']['height_m'] == 1.14
    TARGET.write_text(html, encoding='utf-8')
    (HERE / '03_UPDATED_HTML_SHA.json').write_text(json.dumps({'target': str(TARGET), 'sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        'algorithm_source': '10_SOURCE_SPREAD_AND_ESTIMATORS.json', 'production_updated': False}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
