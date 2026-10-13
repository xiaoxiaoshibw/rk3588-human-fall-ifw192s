#!/usr/bin/env node
// HFUS-D04: S9 (cap_20261010_180751) GT_V2 session_sha256.points 占位('aaaa...')的 rebind 补丁生成器。
// 不修改 GT、不留 --apply；只产 待人工签名 的 patch 记录。
// 用法:
//   node s9_rebind.js --check <gt_path> <manifest_dir>
//   node s9_rebind.js --emit  <gt_path> <manifest_dir> [out_dir]
// 默认: --check。期望 NODE 18+ (fs.open 'wx')。
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const SESSION_DIR = 'D:/Code/ldiar/captures/remote/cap_20261010_180751';
const OUT_DIR = 'D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_d04_r1/s9_rebind';
const NOTE = '本补丁不修改 GT；仅生成待人工填写签名后 apply 的 patch 记录；未 apply。';

function sha256File(p) {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

function findSidRecord(dir, sid) {
  // ponytail: 只认 FINAL_MANIFEST*.json 平铺 JSON，递归找第一个 {sid:<sid>}；
  // 若 D03 换结构会返回 null 并在 patch 里记 manifest_record_found:false。
  if (!fs.existsSync(dir)) return null;
  const stack = fs.readdirSync(dir).filter(f => /^FINAL_MANIFEST.*\.json$/i.test(f)).map(f => path.join(dir, f));
  for (const f of stack) {
    let doc;
    try { doc = JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { continue; }
    const hit = (function walk(o) {
      if (Array.isArray(o)) { for (const v of o) { const r = walk(v); if (r) return r; } return null; }
      if (o && typeof o === 'object') {
        if (o.sid === sid) return { record: o, file: f };
        for (const v of Object.values(o)) { const r = walk(v); if (r) return r; }
      }
      return null;
    })(doc);
    if (hit) return hit;
  }
  return null;
}

function buildPatch(gtPath, manifestDir) {
  const gtAbs = path.resolve(gtPath);
  const gt = JSON.parse(fs.readFileSync(gtAbs, 'utf8'));
  const sid = gt.session_id;
  if (!sid) throw new Error('GT 缺 session_id');
  const before = gt.session_sha256 || {};
  const pointsFile = path.join(SESSION_DIR, 'points.bin');
  const metaFile = path.join(SESSION_DIR, 'meta.json');
  const pointsSha = sha256File(pointsFile);
  const metaSha = sha256File(metaFile);
  const hit = findSidRecord(manifestDir, sid);
  const patch = {
    action: 'rebind_session_sha256_points',
    gt_path: gtAbs.split(path.sep).join('/'),
    before: { meta: before.meta === undefined ? null : before.meta, points: before.points },
    after: { meta: before.meta === undefined ? null : before.meta, points: pointsSha },
    points_file: pointsFile.split(path.sep).join('/'),
    points_file_sha256: pointsSha,
    meta_file_sha256: metaSha,
    evidence_d03_final_manifest_sect: hit ? hit.record : null,
    manifest_record_found: !!hit,
    note: NOTE,
    signed_off_by_human: null,
    apply_authorized: false
  };
  const checks = {
    before_points_is_placeholder: before.points === 'a'.repeat(64),
    meta_key_present_in_gt: before.meta !== undefined,
    d03_points_match: hit ? hit.record.sha256 && hit.record.sha256.points === pointsSha : null,
    d03_meta_match: hit ? hit.record.sha256 && hit.record.sha256.meta === metaSha : null
  };
  return { patch, checks, metaSha, pointsSha };
}

function main() {
  const args = process.argv.slice(2);
  const mode = args[0] === '--emit' ? '--emit' : '--check';
  const pos = args.filter(a => !a.startsWith('--'));
  if (pos.length < 2) {
    console.error('usage: node s9_rebind.js [--check|--emit] <gt_path> <manifest_dir> [out_dir]');
    process.exit(64);
  }
  const outDir = pos[2] || OUT_DIR;
  let r;
  try { r = buildPatch(pos[0], pos[1]); } catch (e) {
    console.error('ERROR:', e.message);
    process.exit(2);
  }
  const giraffeStatus =
    !r.checks.before_points_is_placeholder ? 'GT points 不是 aaaa 占位，补丁不适用' :
    !r.checks.d03_points_match ? 'D03 manifest 记录与实算 points sha 不一致或缺记录' :
    'GT_V2 仍 INVALID_BINDING；补丁已生成、未 apply（BLOCKED 保持）';
  console.log(JSON.stringify({ mode, checks: r.checks, status: giraffeStatus }, null, 1));
  if (mode === '--emit') {
    fs.mkdirSync(outDir, { recursive: true });
    const out = path.join(outDir, 'rebind_patch.json');
    const fd = fs.openSync(out, 'wx'); // 不覆盖既有
    try { fs.writeFileSync(fd, JSON.stringify(r.patch, null, 1) + '\n'); }
    finally { fs.closeSync(fd); }
    console.log('WROTE ' + out.split(path.sep).join('/'));
  }
  process.exit(r.checks.before_points_is_placeholder ? 0 : 3);
}

main();
