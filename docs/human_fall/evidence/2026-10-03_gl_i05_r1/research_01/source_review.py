"""GL-I05 offline per-frame spatial review. Read-only offline artifact only.

Reuses the frozen GL-I04 box/frame statistics and sidecar untouched: this
script only adds a per-(frame, box) localisation view (source XYZ rows,
ordinal/seq, residual) that GL-I04's pooled MD/SVG does not give. It never
recomputes selection, never changes any statistic, and must produce
byte-identical counts to the JSONL source for every (box, frame) pair.
A plane here is a *study reference* (posthoc PCA / WHAT_IF), never a
physical or calibration claim; the approved prior origin stays labelled.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
I04 = HERE.parents[1] / "2026-10-03_gl_i04_r1" / "12_real_final"
OUT = HERE / "source_review.html"

DISPLAY_STRIDE = 50  # at most every 50th point drawn; marker count only


def _compact(item, index):
    """Per-row view payload: coordinates only when displayed or strided.

    Encoded as a positional array ``[pooled_row, frame_row, displayed, x, y, z,
    residual]`` to keep the embedded HTML small; rows without coordinates keep
    only ``[pooled_row, frame_row, displayed]``.
    """
    shown = index % DISPLAY_STRIDE == 0 or item.get("displayed")
    if shown and item["source_xyz_m"] is not None:
        return [item["pooled_row"], item["frame_row"], int(bool(item.get("displayed"))),
                item["source_xyz_m"][0], item["source_xyz_m"][1], item["source_xyz_m"][2],
                item["signed_residual_m"]]
    return [item["pooled_row"], item["frame_row"], int(bool(item.get("displayed")))]


def main():
    diagnostic = json.loads((I04 / "diagnostic.json").read_text(encoding="utf-8"))
    draft = diagnostic["approved_draft"]
    up = draft["up_axis"]
    planes = {
        exp["label"]: {"normal": exp["posthoc_plane"]["normal"],
                       "offset_m": exp["posthoc_plane"]["offset_m"],
                       "origin": ("approved_prior_from_human_draft"
                                  if exp["label"] == "approved"
                                  else "WHAT_IF_posthoc_not_physical"),
                       "physical_verified": False}
        for exp in diagnostic["experiments"]}
    bounds = {"FIT": draft["fit_region"]["bounds"]}
    for r in draft["validation_regions"]:
        bounds[r["region_id"]] = r["bounds"]
    frames = [{"frame_group": key,
               "ordinal": None,
               "seq": value}
              for key, value in diagnostic["source_manifest"]["frame_groups"].items()]
    records = {}
    counts = {}
    display_total = 0
    for line in (I04 / "source_indices.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        key = (item["box"], item["frame_group"])
        index = counts.get(key, 0)
        counts[key] = index + 1
        display_total += int(bool(item.get("displayed")))
        records.setdefault(key, []).append(_compact(item, index))
    order = {}
    rows_by_group = {}
    for line in (I04 / "source_indices.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        rows_by_group.setdefault(item["frame_group"], item["frame_ordinal"])
    for frame in frames:
        frame["ordinal"] = rows_by_group.get(frame["frame_group"])
    frames.sort(key=lambda f: (f["ordinal"] is None, f["ordinal"]))
    stats_records = {(r["box"], r["frame_group"]): r["stats"]["count"]
                     for r in diagnostic["box_frame_records"]}
    mismatches = [{"box": b, "frame_group": g, "jsonl": n,
                   "diagnostic": stats_records.get((b, g))}
                  for (b, g), n in counts.items() if stats_records.get((b, g)) != n]
    payload = {
        "kind": "gli05_source_review", "physical_verified": False,
        "up_axis": up, "planes": planes, "bounds": bounds, "frames": frames,
        "records": {"%s\n%s" % key: value for key, value in records.items()},
        "counts": {"%s\n%s" % key: value for key, value in counts.items()},
        "stats_count_mismatches": mismatches,
        "box_frame_records_total": len(diagnostic["box_frame_records"]),
        "jsonl_total_rows": sum(counts.values()),
        "jsonl_displayed_total": display_total,
        "display_stride": DISPLAY_STRIDE,
        "note": ("source XYZ and residual along an oriented model normal are "
                 "distinct quantities; a model is not proof of world up or "
                 "ground identity. Recording extrinsic/world-up is unknown."),
    }
    html = _render(payload)
    OUT.write_text(html, encoding="utf-8")
    print(json.dumps({"out": str(OUT), "frames": len(frames),
                      "boxes": sorted(bounds), "planes": sorted(planes),
                      "jsonl_total_rows": payload["jsonl_total_rows"],
                      "jsonl_displayed_total": payload["jsonl_displayed_total"],
                      "stats_count_mismatches": len(mismatches)},
                     ensure_ascii=False))


def _render(payload):
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    html = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>GL-I05 数据源逐帧复核</title><style>
body{margin:0;font:13px/1.4 system-ui,monospace;background:#0d1117;color:#e6edf3}
header{padding:8px 14px;background:#161b22;border-bottom:1px solid #30363d;
position:sticky;top:0}
select,span{margin-right:12px}
#c{display:block;cursor:crosshair}
#info{padding:4px 14px;white-space:pre-wrap;background:#161b22;font-size:12px}
.warn{color:#f778ba}
</style></head><body>
<header>
<label>frame <select id="frame"></select></label>
<label>box <select id="box"></select></label>
<label>plane <select id="plane"></select></label>
<label>残差色带 ±m <input id="band" type="number" step="0.01" value="0.05" style="width:5em"></label>
<span id="meta"></span>
</header><canvas id="c" width="980" height="640"></canvas><div id="info"></div>
<script>const D=__DATA__;</script>
<script>
const frameSel=document.getElementById('frame'),boxSel=document.getElementById('box'),
planeSel=document.getElementById('plane'),cv=document.getElementById('c'),ctx=cv.getContext('2d'),
info=document.getElementById('info'),meta=document.getElementById('meta');
D.frames.forEach((f,i)=>frameSel.add(new Option('#'+f.ordinal+' seq '+f.seq,i)));
Object.keys(D.bounds).forEach(b=>boxSel.add(new Option(b,b)));
Object.keys(D.planes).forEach(p=>planeSel.add(new Option(p,p)));
function key(){return boxSel.value+'\\n'+D.frames[+frameSel.value].frame_group}
function color(r,lim){if(r==null)return'#8b949e';const t=Math.max(-lim,Math.min(lim,r))/lim;
return t>=0?`rgb(${200+55*t|0},80,80)`:`rgb(80,${140-60*t|0},200)`}
function draw(){
const rows=D.records[key()]||[],f=D.frames[+frameSel.value],b=D.bounds[boxSel.value],p=D.planes[planeSel.value];
const lim=Math.abs(parseFloat(document.getElementById('band').value))||0.05;
ctx.fillStyle='#0d1117';ctx.fillRect(0,0,cv.width,cv.height);
const xs=rows.filter(r=>r.length>=7).map(r=>r[3]),
ys=rows.filter(r=>r.length>=7).map(r=>r[4]);
if(!xs.length){info.textContent='(empty selection)';meta.textContent='count 0';return}
const x0=Math.min(...xs,b.x_min_m)-0.1,x1=Math.max(...xs,b.x_max_m)+0.1,
y0=Math.min(...ys,b.y_min_m)-0.1,y1=Math.max(...ys,b.y_max_m)+0.1;
const sx=v=>30+(cv.width-60)*(v-x0)/(x1-x0),sy=v=>cv.height-30-(cv.height-60)*(v-y0)/(y1-y0);
ctx.strokeStyle='#58a6ff';ctx.strokeRect(sx(b.x_min_m),sy(b.y_max_m),sx(b.x_max_m)-sx(b.x_min_m),sy(b.y_min_m)-sy(b.y_max_m));
let shown=0;rows.forEach(r=>{if(r.length<7)return;shown++;
ctx.fillStyle=color(r[6],lim);ctx.fillRect(sx(r[3])-1,sy(r[4])-1,2,2)});
meta.innerHTML=`count ${rows.length} shown ${shown} matched_diagnostic ${D.stats_count_mismatches.length===0}`;
info.textContent=`kind ${D.kind} physical_verified ${D.physical_verified}
frame ${f.frame_group} ordinal ${f.ordinal} seq ${f.seq}
box ${boxSel.value} counts_match ${D.stats_count_mismatches.length===0}
plane ${planeSel.value} origin ${p.origin} physical_verified ${p.physical_verified}
normal ${JSON.stringify(p.normal)} offset_m ${p.offset_m}
up_axis ${JSON.stringify(D.up_axis)}
${D.note}`}
frameSel.onchange=boxSel.onchange=planeSel.onchange=draw;
document.getElementById('band').onchange=draw;draw();
</script></body></html>"""
    return html.replace("__DATA__", data)


if __name__ == "__main__":
    main()
