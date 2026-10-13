'use strict';
/* build_baseline_v3.js — HUMAN-FUSION-BG-V3: 生成 V3_BASELINE.json (整树文件 SHA).
 *
 * 与 V2 BASELINE.json 同构, 但:
 *  - 明确列出 V3 新增/有意修改的文件 (sidequests/human_fusion_lab_v3/**);
 *  - 保护: 既有 V2 基线文件 + 生产 src/pc_apps/webui/captures
 *  - Q01 等四个外部已改文件不前进 — 记录其"当前 SHA"作为 V3 对账基线 (不回写)。
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const V2_BASE=path.join(REPO,'docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1/BASELINE.json');
const v2=JSON.parse(fs.readFileSync(V2_BASE));
const SKIP_DIRS=new Set(['.git','node_modules','__pycache__']);
function sha(p){return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
function walk(dir,base){
  const out=[];
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){
    const p=path.join(dir,e.name),rel=path.relative(base,p).replace(/\\/g,'/');
    if(e.isDirectory()){if(!SKIP_DIRS.has(e.name))out.push(...walk(p,base));}
    else out.push(rel);
  }
  return out;
}
const all=walk(REPO,REPO);
const files={};
for(const rel of all){
  const p=path.join(REPO,rel);
  try{files[rel]={sha256:sha(p)};}catch(e){files[rel]={error:e.message};}
}
const v3Files=Object.keys(files).filter(f=>f.startsWith('sidequests/human_fusion_lab_v3/'));
const result={
  task:'HUMAN-FUSION-BG-V3 整树基线',date:'2026-10-11',
  branch:'master',
  v2_baseline_head:v2.head,
  v2_protected_unchanged_check:'V2_BASELINE.json.files ↔ 当前 SHA 对账 (除 Q01 四个外在文件外)',
  files,
  v3_added_or_modified:v3Files,
  externally_changed_at_v2:Object.keys((JSON.parse(fs.readFileSync(path.join(REPO,'docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1/FREEZE_FINAL.json'))).changed||[])),
};
const out=path.join(REPO,'docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1');
fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'V3_BASELINE.json'),JSON.stringify(result,null,1));
console.log('wrote V3_BASELINE.json;',all.length,'files;',v3Files.length,'under human_fusion_lab_v3/');
