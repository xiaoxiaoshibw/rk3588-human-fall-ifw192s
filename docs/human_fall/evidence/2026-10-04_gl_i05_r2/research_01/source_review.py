"""Exclusive, read-only spatial review of frozen per-frame source evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
from core import ground as g
I04 = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final'


def build_payload(diagnostic, sidecar, display_budget=100):
    if type(display_budget) is not int or not 0 <= display_budget <= 2000:
        raise ValueError('display budget must be integer 0..2000')
    if diagnostic.get('schema') != 1 or diagnostic.get('kind') != 'gli04_geometry_diagnostic' \
            or diagnostic.get('units') != 'm':
        raise ValueError('unsupported diagnostic identity')
    manifest = diagnostic['source_manifest']
    if manifest.get('schema') != 1 or manifest.get('kind') != 'capture_input_adaptation' \
            or manifest['declared']['units'] != 'm' \
            or manifest['declared']['frame'] != diagnostic['frame']:
        raise ValueError('source frame/schema/units mismatch')
    draft = diagnostic['approved_draft']
    bounds = {'FIT': draft['fit_region']['bounds']}
    for region in draft['validation_regions']:
        name = region['region_id']
        if name in bounds:
            raise ValueError('duplicate box alias')
        bounds[name] = region['bounds']
    if len(bounds) != 4:
        raise ValueError('exactly four fixed boxes required')
    groups = manifest['frame_groups']
    frames, used_ordinals, ranges = [], set(), []
    for name, meta in groups.items():
        ordinal, seq = meta['ordinal'], meta['seq']
        lo, hi = meta['rows']
        if any(type(x) is not int for x in (ordinal, seq, lo, hi)) \
                or ordinal < 0 or lo < 0 or hi < lo or ordinal in used_ordinals:
            raise ValueError('invalid or alias frame group')
        used_ordinals.add(ordinal)
        ranges.append((lo, hi))
        frames.append(dict(frame_group=name, ordinal=ordinal, seq=seq))
    for (_, end), (start, _) in zip(sorted(ranges), sorted(ranges)[1:]):
        if start < end:
            raise ValueError('overlapping source frame groups')
    frames.sort(key=lambda f: f['ordinal'])
    stats = {}
    for record in diagnostic['box_frame_records']:
        key = (record['box'], record['frame_group'])
        if key in stats or key[0] not in bounds or key[1] not in groups:
            raise ValueError('duplicate/foreign statistics key')
        if record['frame_ordinal'] != groups[key[1]]['ordinal'] \
                or record['seq'] != groups[key[1]]['seq']:
            raise ValueError('statistics frame identity mismatch')
        stats[key] = record['stats']
    expected_keys = {(box, frame) for box in bounds for frame in groups}
    if set(stats) != expected_keys:
        raise ValueError('missing box/frame statistics including empty selection')
    records = {key: [] for key in sorted(expected_keys)}
    seen = {key: set() for key in expected_keys}
    for item in sidecar:
        key = (item['box'], item['frame_group'])
        if key not in records:
            raise ValueError('foreign sidecar group or box')
        meta = groups[key[1]]
        row, local = item['pooled_row'], item['frame_row']
        if type(row) is not int or type(local) is not int \
                or not meta['rows'][0] <= row < meta['rows'][1] \
                or local != row - meta['rows'][0] or row in seen[key] \
                or item['frame_ordinal'] != meta['ordinal'] or item['seq'] != meta['seq']:
            raise ValueError('invalid/duplicate/cross-group source row')
        xyz = item['source_xyz_m']
        if xyz is not None:
            xyz = g._strict_float_sequence(xyz, 3, 'source_xyz_m').tolist()
            b = bounds[key[0]]
            if any(not b[axis + '_min_m'] <= xyz[i] <= b[axis + '_max_m']
                   for i, axis in enumerate('xyz')):
                raise ValueError('source point outside fixed box')
        seen[key].add(row)
        records[key].append([row, local, xyz])
    for key, rows in records.items():
        if type(stats[key]['count']) is not int or len(rows) != stats[key]['count']:
            raise ValueError('sidecar/full statistics count mismatch')
    planes = {}
    for exp in diagnostic['experiments']:
        p = exp['posthoc_plane']
        normal = g._strict_float_sequence(p['normal'], 3, 'normal').tolist()
        if abs(float(np.linalg.norm(normal)) - 1.) > 1e-8:
            raise ValueError('posthoc normal must be unit')
        origin = p.get('origin')
        if not origin:
            candidates = exp['actual_frozen_fit'].get('competition_candidates', [])
            if not any(c['normal'] == p['normal'] and c['offset_m'] == p['offset_m']
                       for c in candidates):
                raise ValueError('reference plane origin cannot be traced')
            origin = 'frozen_refined_candidate_posthoc_not_physical'
        planes[exp['label']] = dict(normal=normal,
            offset_m=g._finite_number(p['offset_m'], 'offset_m'), origin=origin,
            conditioning=exp['label'], physical_verified=False)
    if not planes:
        raise ValueError('no study reference plane')
    return dict(kind='gli05_source_review', schema=1, physical_verified=False,
        up_axis=draft['up_axis'], recording_extrinsic='unknown', planes=planes,
        bounds=bounds, frames=frames, display_budget=display_budget,
        records={'%s\n%s' % key: value for key, value in records.items()},
        stats={'%s\n%s' % key: value for key, value in stats.items()},
        jsonl_total_rows=sum(len(v) for v in records.values()),
        note='Planes are posthoc study references from FIT PCA or frozen refined candidates. '
             'Approved up is an input prior, not a measured extrinsic. Source XYZ, '
             'model residual and physical ground identity are separate quantities.')


def write_payload(payload, output_dir):
    output = Path(output_dir)
    resolved = output.resolve()
    if output.exists() or output.is_symlink() or HERE not in resolved.parents:
        raise ValueError('require new output directory inside current research root')
    html = _render(payload)
    output.mkdir()
    with (output / 'source_review.html').open('x', encoding='utf8') as handle:
        handle.write(html)
    return output / 'source_review.html'


def _render(payload):
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True).replace('<', '\\u003c')
    return '''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>GL-I05 源点逐帧复核</title><style>
body{margin:14px;font:14px system-ui;background:#111827;color:#e5e7eb}
label{margin-right:15px}canvas{background:#080e18;display:block;margin-top:12px}
pre{white-space:pre-wrap}input{width:110px}</style>
<h2>逐帧固定区域复核 · 研究参考平面 · physical=false</h2>
<label>frame <select id="frame"></select></label>
<label>box <select id="box"></select></label>
<label>posthoc plane <select id="plane"></select></label>
<label>绘制上限 <input id="budget" type="number" min="0" max="2000"></label>
<label>源 pooled row <input id="row" type="number"><button id="lookup">读取</button></label>
<canvas id="c" width="980" height="600"></canvas>
<pre id="meta"></pre><pre id="point">点击绘制点或输入 pooled row 读取 XYZ、frame row、seq、残差。</pre>
<script>const D=__DATA__;</script><script>
const F=document.getElementById('frame'), B=document.getElementById('box'),
P=document.getElementById('plane'), C=document.getElementById('c'), X=C.getContext('2d'),
budget=document.getElementById('budget'), meta=document.getElementById('meta'),
point=document.getElementById('point');let drawn=[];
D.frames.forEach((f,i)=>F.add(new Option('#'+f.ordinal+' seq '+f.seq,i)));
Object.keys(D.bounds).forEach(b=>B.add(new Option(b,b)));
Object.keys(D.planes).forEach(p=>P.add(new Option(p,p)));budget.value=D.display_budget;
function key(){return B.value+'\\n'+D.frames[+F.value].frame_group}
function residual(r){const p=D.planes[P.value];return r[2]==null?null:
r[2].reduce((s,v,i)=>s+v*p.normal[i],p.offset_m)}
function readPoint(r){const f=D.frames[+F.value],p=D.planes[P.value];
point.textContent=r?JSON.stringify({pooled_row:r[0],frame_row:r[1],ordinal:f.ordinal,
seq:f.seq,source_xyz_m:r[2],residual_m:residual(r),plane:P.value,origin:p.origin,
physical_verified:false},null,2):'该 frame/box 未选中该源行；不扩大区域。'}
function draw(){const rows=D.records[key()],s=D.stats[key()],b=D.bounds[B.value],
p=D.planes[P.value],f=D.frames[+F.value];drawn=[];X.clearRect(0,0,C.width,C.height);
const cap=Math.max(0,Math.min(2000,Math.floor(+budget.value||0))),
stride=cap?Math.max(1,Math.ceil(rows.length/cap)):Infinity,
sx=x=>30+(C.width-60)*(x-b.x_min_m)/(b.x_max_m-b.x_min_m),
sy=y=>C.height-30-(C.height-60)*(y-b.y_min_m)/(b.y_max_m-b.y_min_m);
rows.forEach((r,i)=>{if(i%stride||!cap||!r[2])return;const q=residual(r),
t=Math.max(-1,Math.min(1,q/.05));X.fillStyle=t>=0?'rgb(245,90,90)':'rgb(70,160,240)';
const x=sx(r[2][0]),y=sy(r[2][1]);X.fillRect(x-2,y-2,4,4);drawn.push({r,x,y})});
meta.textContent=JSON.stringify({frame:f,box:B.value,full_count:s.count,
shown:drawn.length,full_stats:s,plane:P.value,origin:p.origin,normal:p.normal,
offset_m:p.offset_m,approved_up_input:D.up_axis,recording_extrinsic:D.recording_extrinsic,
physical_verified:false,note:D.note},null,2);point.textContent=rows.length?
'点击绘制点或输入 pooled row；显示预算不改变全统计。':'empty selection，完整统计 count=0。'}
C.onclick=e=>{const rect=C.getBoundingClientRect(),x=(e.clientX-rect.left)*C.width/rect.width,
y=(e.clientY-rect.top)*C.height/rect.height;let best=null,d=100;
drawn.forEach(p=>{const q=(p.x-x)**2+(p.y-y)**2;if(q<d){best=p.r;d=q}});readPoint(best)};
document.getElementById('lookup').onclick=()=>readPoint(D.records[key()].find(
r=>r[0]===+document.getElementById('row').value));
F.onchange=B.onchange=P.onchange=budget.onchange=draw;draw();
</script></html>'''.replace('__DATA__', data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--display-budget', type=int, default=100)
    args = parser.parse_args()
    target = Path(args.output_dir)
    if target.exists() or target.is_symlink() or HERE not in target.resolve().parents:
        raise ValueError('output must be new and inside current research root')
    diagnostic = json.loads((I04 / 'diagnostic.json').read_text(encoding='utf8'))
    with (I04 / 'source_indices.jsonl').open(encoding='utf8') as handle:
        payload = build_payload(diagnostic, (json.loads(line) for line in handle), args.display_budget)
    payload['input_sha256'] = {name: hashlib.sha256((I04 / name).read_bytes()).hexdigest()
                               for name in ('diagnostic.json', 'source_indices.jsonl')}
    result = write_payload(payload, target)
    print(json.dumps(dict(output=str(result), frames=len(payload['frames']),
                         groups=len(payload['stats']), rows=payload['jsonl_total_rows'])))


if __name__ == '__main__':
    main()
