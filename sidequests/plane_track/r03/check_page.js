// R3 页面自检：DATA 结构/取值范围/时间单调/视频内嵌；不依赖浏览器。
// 用法：node check_page.js <page.html>
const fs = require("fs");

function main() {
  const path = process.argv[2];
  if (!path) {
    console.error("用法: node check_page.js <page.html>");
    process.exit(2);
  }
  const html = fs.readFileSync(path, "utf8");
  const m = html.match(/const DATA = (\{[\s\S]*?\});\n<\/script>/);
  if (!m) {
    console.error("FAIL 找不到内嵌 DATA");
    process.exit(1);
  }
  const D = JSON.parse(m[1]);
  const fails = [];
  const ok = [];

  function check(name, cond, detail) {
    if (cond) ok.push(name); else fails.push(name + (detail ? " :: " + detail : ""));
  }

  const s = D.session, st = D.stats;
  check("50+ 雷达帧", Array.isArray(D.radar) && D.radar.length === s.frames, "radar=" + (D.radar || []).length);
  check("相机帧数", D.cam.frames.length === s.camera_frames, "cam=" + D.cam.frames.length);
  check("时长>0", s.duration > 0, "duration=" + s.duration);
  check("时间单调", D.radar.every((r, i, a) => i === 0 || r.t >= a[i - 1].t));
  check("相机时间单调", D.cam.frames.every((r, i, a) => i === 0 || r.t >= a[i - 1].t));

  const targets = D.radar.filter((r) => r.box);
  check("检出目标帧数", targets.length === st.target_frames, targets.length + " vs " + st.target_frames);
  check("目标帧有 3D 点", targets.every((r) => Array.isArray(r.p3) && r.p3.length === r.box.n),
        "first=" + (targets[0] ? targets[0].p3.length + "/" + targets[0].box.n : "-"));
  check("包围盒半长正", targets.every((r) => r.box.h.every((h) => h > 0 && h < 1.0)));
  check("包围盒正交", targets.every((r) => {
    const A = r.box.a;
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) {
        let d = 0;
        for (let k = 0; k < 3; k++) d += A[i][k] * A[j][k];
        const want = i === j ? 1 : 0;
        if (Math.abs(d - want) > 2e-3) return false;
      }
    }
    return true;
  }));
  check("目标质心在盒内", targets.every((r) => {
    const C = r.box.c, A = r.box.a, h = r.box.h;
    const d = [r.box.c[0] - C[0], r.box.c[1] - C[1], r.box.c[2] - C[2]];
    return d.every((v) => Math.abs(v) < 1e-9) && r.box.c.every((v) => Number.isFinite(v));
  }));
  check("轨迹 id 一致", (() => {
    const ids = new Set(targets.map((r) => r.track));
    return ids.size >= 1 && targets.every((r) => typeof r.track === "number");
  })());

  const boxes = D.cam.frames.filter((f) => f.box);
  check("相机 2D 框帧数", boxes.length === st.camera_box_frames, boxes.length + " vs " + st.camera_box_frames);
  check("2D 框在画幅内", boxes.every((f) => f.box[0] >= 0 && f.box[1] >= 0 && f.box[2] <= 960 && f.box[3] <= 540));
  check("2D 框非退化", boxes.every((f) => f.box[2] > f.box[0] && f.box[3] > f.box[1]));
  check("2D 框随时间下移", (() => {
    const a = boxes[0], b = boxes[boxes.length - 1];
    return b.box[1] > a.box[1];
  })());

  check("背景点云数量", D.bg.count > 1000, "count=" + D.bg.count);
  const raw = Buffer.from(D.bg.xyz_b64, "base64");
  check("背景 base64 长度", raw.length === D.bg.count * 6, raw.length + " vs " + D.bg.count * 6);
  check("视频内嵌", typeof D.video_uri === "string" && D.video_uri.startsWith("data:video/mp4;base64,"),
        "len=" + (D.video_uri || "").length);
  check("视频体积", D.video_uri.length > 200000, "len=" + D.video_uri.length);
  check("时钟偏移有限", Number.isFinite(s.offset_s) && Math.abs(s.offset_s) < 5, "offset=" + s.offset_s);
  check("检测耗时合理", st.detect_ms_median > 0 && st.detect_ms_median < 100,
        "median=" + st.detect_ms_median);
  check("建背景帧数", st.boot_frames === D.params.bg_frames, st.boot_frames + " vs " + D.params.bg_frames);
  check("相机起点覆盖飞行", (() => {
    const first = boxes[0].t, last = boxes[boxes.length - 1].t;
    const flight = targets.find((r) => r.speed > 0.5);
    return flight && flight.t >= first - 0.2 && flight.t <= last;
  })());

  // 脚本语法：把最后一个 <script> 块当函数体解析
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((x) => x[1]);
  let syntaxOk = true, syntaxErr = "";
  for (const code of scripts) {
    try {
      // eslint-disable-next-line no-new-func
      new Function(code);
    } catch (e) {
      syntaxOk = false;
      syntaxErr = e.message;
    }
  }
  check("内联脚本语法", syntaxOk, syntaxErr);

  console.log("PASS " + ok.length + " / FAIL " + fails.length);
  for (const f of fails) console.log("  FAIL " + f);
  if (fails.length) process.exit(1);
}

main();