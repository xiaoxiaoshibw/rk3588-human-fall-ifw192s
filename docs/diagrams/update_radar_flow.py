"""Extend the user's existing standalone diagram; preserve its original detail."""
from pathlib import Path
import hashlib
import json
import re
from html import escape

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = Path('C:/Users/30680/Desktop/雷达数据流-ROS到跟踪开始.html')
OUT = ROOT / 'docs/diagrams/雷达数据流-完整路线与卡点.html'
EVIDENCE = ROOT / 'docs/evidence/2026-10-23_radar_flow_history'
ORIGINAL = ROOT / 'docs/evidence/2026-10-22_radar_flow_tree/ORIGINAL.html'
HISTORY = ROOT / 'docs/diagrams/radar_flow_history.json'

CSS = '''
.overview{margin:24px 0 32px}.overview h2{font-size:21px}.overview h3{font-size:16px}
.summary{background:#fff1f2;border:1px solid #fecdd3;border-left:5px solid #be123c;padding:18px;border-radius:12px}
.tree{border-left:2px solid #cbd5e1;margin:18px 0 24px 10px;padding-left:22px}
.tree details{margin:12px 0;background:white;border:1px solid #d5dbe3;border-radius:10px;padding:12px 16px}
summary{cursor:pointer;font-weight:650}summary:focus-visible,button:focus-visible{outline:3px solid #2563eb;outline-offset:3px}
.tree .twig{margin:12px 0 8px 10px;padding:10px 14px;border-left:3px solid #b45309;background:#fffbeb}
.tree .twig.bad{border-color:#b91c1c;background:#fff1f2}.tree .twig.ok{border-color:#047857;background:#ecfdf5}
.tree p{margin:8px 0}.tree a{color:#1d4ed8}.status{font-size:12px;color:#475569;font-weight:500}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.panel{background:#fff;border:1px solid #d5dbe3;border-radius:12px;padding:18px;margin:16px 0}
label{display:block;font-weight:600;margin:10px 0 5px}input,select,textarea,button{font:inherit;border:1px solid #cbd5e1;border-radius:6px;padding:8px}
input,select,textarea{width:100%;background:#fff;color:#111827}textarea{min-height:85px;resize:vertical}button{cursor:pointer;background:#eef2ff;color:#1e3a8a;margin:8px 6px 0 0}
.idea{margin:12px 0;padding:12px;border-left:3px solid #6d28d9;background:#f5f3ff;white-space:pre-wrap;overflow-wrap:anywhere}
.idea p{margin:5px 0}.idea small{color:#475569}#save-status{display:block;color:#475569;min-height:26px}
.evidence-list{font-size:13px;overflow-wrap:anywhere}.detail-toggle{margin:25px 0}.detail-toggle>summary{padding:16px;background:#e8efff;border-radius:10px;margin-bottom:20px}
.history-record{padding:10px 14px;margin:12px 0;border-left:3px solid #64748b;background:#f8fafc;overflow-wrap:anywhere}
.history-record h4{margin:0 0 8px;font-size:15px}.history-record p{margin:6px 0}.history-record .stop{color:#991b1b}.history-record .source{font-size:12px;color:#64748b}
.history-brief{padding:12px;background:#eef2ff;border-radius:9px}.history-nav{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
@media(max-width:760px){.grid{grid-template-columns:1fr}.tree{padding-left:12px;margin-left:0}.tree details{padding:10px}.tree .twig{margin-left:0}}
'''

OVERVIEW = '''
<section class="overview" aria-label="完整路线树">
<div class="summary"><strong>最后卡在哪里？可靠识别这一段还没过。</strong>
<p>ROS → 点云 → 候选 → 跟踪 → 离线模型候选的接线已实现；但“这个人真的跌倒了吗”仍有明显漏检和人员泛化问题。最终 IFW192S 真实效果、物理标定和板端整链实时性能均为 UNKNOWN，尚未部署候选模型，confirmed 关闭。</p>
<p>这不是单一代码崩溃：有的路线缺输入，有的路线实验失败，还有的路线尚未验证。下树按停止位置分别展开。</p></div>
<h2>完整路线与研究分支 <span class="status">更新于 2026-10-22 · 离线开发状态</span></h2>
<p>绿＝软件路径已实现；红＝观察到失败或缺口；黄＝待验证想法。已实现不代表人体有效。分支编号用于挂接点子，不是 Git 分支。</p>
<div class="tree">
<details open id="input"><summary>01 输入：雷达 → ROS → 解码 → 时间与质量门 <span class="status">软件已有</span></summary>
<p>保留源行号、源时间、epoch 和标定身份；过期/非法帧不当新观测。原图 01–08 的详细处理保留在下方。</p>
<div class="twig">想法入口：输入稀疏时先核对扫描包与完整扫描的定义，再谈改模型。</div>
<div class="twig bad">已发生：Livox 单包连续有效帧最多 2 帧，首次训练停止。三包因果聚合已修；跨传感器对齐与 IFW192S 迁移仍未证明。</div></details>

<details open id="target"><summary>02 目标：过滤 → 聚类 → 候选历史 → 获取 → 跟踪 <span class="status">几何链已实现 / 人体语义缺口</span></summary>
<p>只把当前 locked、非预测的实测目标行交给下游；换身份、代际、标定或时间断档清历史。几何框与持续运动都不能直接证明是人。</p>
<div class="twig ok">显式空场背景：已有会话能跟踪几何目标，作为开发对照。</div>
<div class="twig bad">固定背景：人在学习阶段会被吸收；不能承担人体识别。无背景候选也可能是家具，静止开机目标仍是必须覆盖的反例。</div>
<div class="twig">变化获取 + 历史保持：已有实验，默认关闭；退出后误锁改善，但移动家具同样可触发，不能升格为人体判别器。</div>
<div class="twig">新点子可挂这里：雷达人体语义、静止目标识别、成员归属。需要真实人/家具及开机静止反例来检验。</div></details>

<details open id="geometry"><summary>03A 几何路线：基线 → 特征 / 区域 / 姿态 → 跌倒状态机 <span class="status">软件已有 / confirmed 关闭</span></summary>
<p>这是既有几何路线，与 ML 候选旁路分开。区域有支撑不等于关节真值，低姿态也可能是蹲下、主动躺下或离场局部可见。</p>
<div class="twig bad">停止位置：物理标定与人体效果未证实。FallStateMachine 默认 mode_verified=false、allow_confirmed=false；打开开关不能补齐证据。</div></details>

<details open id="action"><summary>03B 动作分类：整场景 XYZ → RF / 深度模型 <span class="status">离线实验 / 跨环境退化</span></summary>
<p>MM-Fi 27 类动作不含 fall，动作分类成绩不能当跌倒召回。</p>
<div class="twig bad">整场景深度 v2：同环境序列聚合 95.56%，E04 跨环境 4.07%；多环境训练后 E04 3.70%。环境与人员同时变化，环境几何依赖是待检验解释，不能定为唯一原因。</div>
<div class="twig">分支：改用人体点集、尺度/位置归一化、背景对照。预期减少环境依赖，目前尚无成功证据。</div>
<div class="twig bad">人体 GT 裁剪分支卡在坐标：12 序列 / 3,564 帧，恒等变换裁剪全部 0 点。关节→LiDAR 外参/单位/帧绑定未核实，真实裁剪训练缓存未发布。</div></details>

<details open id="fall"><summary>03C 跌倒候选：实测目标点 → 10–30 帧 → 二分类 → 事件 <span class="status">接线可跑 / 可靠性未过</span></summary>
<p>FallCandidateRuntime：默认高阈值 0.8 连续 3 个窗口触发；低阈值 0.2 连续 5 窗释放。重叠窗口票数不是物理持续时间。事件为 ml_fall_candidate，始终不写回正式 confirmed。</p>
<div class="twig bad">合成集：短窗 RF 检出 437/451、非跌倒触发 112/449；MIL 为 450/451、12/449。动画目录隔离不等于真人人员隔离，不能凭此宣称完成。</div>
<div class="twig bad"><strong>真人公开数据主卡点：</strong>LaserAct Velodyne MIL 官方人员留出检出 8/14；非跌倒触发 1/889 个可观测片段。漏 6 条：2 条无有效连续窗口，4 条有输入却未触发；假阳性为主动躺下 Lying。</div>
<div class="twig bad">训练人员内部 LOPO：原 bag-max 3/16、负片段触发 4/1403。21 组规则无支持发布的校准规则；这是研究预算下的结果，不是现场安全标准。</div>
<div class="twig bad">已尝试的三个分支：连续三窗监督 3/16 + 4/1403；仅动态特征 0/16 + 3/1403；六段有序汇总 3/16 + 4/1403。均未改善、未采用。以上是开发侧消融，不能与官方测试集的 8/14 混成一组结果。</div>
<div class="twig ok">软件缺陷已修：导出校验按 manifest 的 feature_schema 分派，20 份权重完成重校验；修复未改变上述泛化失败结论。</div>
<div class="twig">下一步想法：更充分的时间表示、独立人员的跌倒/主动躺下/低姿态困难负例、有效观测审计。状态均为待实验，当前失败不能证明其中某个想法一定有效。</div></details>

<details open id="runtime"><summary>04 最终目标：IFW192S 现场实时跌倒报警 <span class="status">尚未到达</span></summary>
<p>离线原始 386 帧整链对照已能接入候选；249 个就绪窗口、原几何输出 SHA 保持。这证明接口行为，不证明现场识别效果。</p>
<div class="twig bad">效果缺口：现有目标域动作/跌倒 GT 不足，召回、每小时误报、起点延迟均 UNKNOWN。</div>
<div class="twig bad">实时缺口：历史 10-19 有人板端观测约 4.03 Hz，处理 P95 303.3 ms，并有丢帧；它属于旧几何现场记录，不是本轮 ML 测速。本轮候选原生板端整链性能 UNKNOWN，PC 数字不能代替。</div>
<div class="twig bad">当前边界：候选模型未部署，confirmed=false；不部署、不采集。先解决可观测性与泛化，再做目标域效果与原生板端性能验证。</div></details>
</div>

<div class="panel" id="ideas"><h2>临时想到的点子 → 挂到对应分支</h2>
<p>点子独立保存，默认“待验证”，不会改写上面的事实结论。保存在当前浏览器；换浏览器、清理缓存或搬文件前请导出 JSON。可导入继续整理。</p>
<form id="idea-form"><div class="grid"><div><label for="idea-parent">挂在哪一步</label><select id="idea-parent"><option value="input">01 输入</option><option value="target">02 人体 / 跟踪</option><option value="geometry">03A 几何状态机</option><option value="action">03B 动作 / 人体点集</option><option value="fall" selected>03C 跌倒模型</option><option value="runtime">04 现场实时验证</option></select></div>
<div><label for="idea-state">点子状态（个人记录，不代表验证结论）</label><select id="idea-state"><option>待验证</option><option>实验中</option><option>有收益待复现</option><option>失败保留</option><option>暂缓</option></select></div></div>
<label for="idea-title">点子</label><input id="idea-title" required maxlength="180" placeholder="例如：只比较同一目标跌倒前后的高度变化？">
<label for="idea-note">怎么检验 / 结果 / 最后卡在哪</label><textarea id="idea-note" maxlength="4000" placeholder="记录需要什么输入、对照是什么、什么结果支持或否定它。"></textarea>
<button type="submit">添加分支点子</button><button type="button" id="export-ideas">导出点子 JSON</button>
<label for="import-ideas">导入点子 JSON（合并，不覆盖现有记录）</label><input type="file" id="import-ideas" accept="application/json,.json"></form>
<output id="save-status" aria-live="polite"></output><div id="idea-list"></div></div>

<details class="panel evidence-list"><summary>结论来源与证据边界</summary>
<p>截至 2026-10-22 的仓库记录与源码；不是新做的现场实验。原图的细节与历史行号保留作导航，配置以实际运行清单为准。</p>
<ul><li>docs/PROJECT_STATE.md · docs/PROGRESS.md</li><li>ML/docs/fall_recognition_20261022.md · fall_training_ablation_20261022.md · human_pointset_20261022.md · deep_lidar_v2_20261022.md</li>
<li>docs/evidence/2026-10-22_fall_candidate/LASERACT_PRIMARY_FAILURES.json</li><li>docs/evidence/2026-10-22_fall_sustained/COMPARISON.json</li><li>docs/evidence/2026-10-22_fall_schema_fix/FINAL.json</li>
<li>ML/src/fall_candidate_runtime.py · src/human_fall_detection/core/fall_state.py</li></ul>
<p>没有点级/动作真值时效果写 UNKNOWN。公开数据跨人员、合成数据、IFW192S 目标域及 PC / 板端性能分别解释。</p></details>
</section>
'''

JS = '''
(() => {
  'use strict';
  const key = 'ldiar.radar.flow.ideas.v1';
  const $ = id => document.getElementById(id);
  const parents = Object.fromEntries([...$('idea-parent').options].map(o => [o.value, o.text]));
  const states = [...$('idea-state').options].map(o => o.value);
  let ideas = [], storageOK = true;
  const valid = x => x && typeof x.id === 'string' && x.id.length <= 120 &&
    Object.hasOwn(parents, x.parent) && states.includes(x.state) &&
    typeof x.title === 'string' && x.title.trim().length > 0 && x.title.length <= 180 &&
    typeof x.note === 'string' && x.note.length <= 4000;
  function message(t) { $('save-status').textContent = t; }
  try {
    const saved = JSON.parse(localStorage.getItem(key) || '[]');
    if (!Array.isArray(saved) || saved.length > 500 || !saved.every(valid)) throw Error('invalid');
    ideas = saved;
  } catch (_) { storageOK = false; message('本地记录不可用或格式损坏；请使用导出保存本次点子。'); }
  function render() {
    $('idea-list').replaceChildren();
    for (const x of ideas) {
      const article = document.createElement('article'); article.className = 'idea';
      const a = document.createElement('a'); a.href = '#' + x.parent; a.textContent = parents[x.parent];
      const title = document.createElement('h3'); title.textContent = x.title;
      const state = document.createElement('small'); state.textContent = x.state + ' · 个人点子记录';
      const note = document.createElement('p'); note.textContent = x.note;
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '删除此点子';
      remove.onclick = () => { ideas = ideas.filter(v => v.id !== x.id); save(); };
      article.append(a, title, state, note, remove); $('idea-list').append(article);
    }
  }
  function save() {
    if (storageOK) {
      try { localStorage.setItem(key, JSON.stringify(ideas)); message('已保存 ' + ideas.length + ' 个点子到当前浏览器。'); }
      catch (_) { storageOK = false; }
    }
    if (!storageOK) message('点子仅保留在当前页面内存，请立即导出 JSON 保存。');
    render();
  }
  $('idea-form').onsubmit = e => {
    e.preventDefault();
    if (ideas.length >= 500) { message('最多保存 500 个点子，请先导出整理。'); return; }
    const title = $('idea-title').value.trim(); if (!title) return;
    ideas.push({id: crypto.randomUUID(), parent: $('idea-parent').value, state: $('idea-state').value,
      title, note: $('idea-note').value});
    $('idea-title').value = ''; $('idea-note').value = ''; save();
  };
  $('export-ideas').onclick = () => {
    const blob = new Blob([JSON.stringify({version:1, ideas}, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = '雷达路线点子.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    message('已请求下载点子 JSON，请保留下载文件。');
  };
  $('import-ideas').onchange = async e => {
    try {
      const file = e.target.files[0]; if (!file) return;
      if (file.size > 4000000) throw Error('文件过大');
      const doc = JSON.parse(await file.text());
      if (doc.version !== 1 || !Array.isArray(doc.ideas) || !doc.ideas.every(valid)) throw Error('格式或字段不合法');
      const merged = new Map(ideas.map(x => [x.id, x]));
      for (const x of doc.ideas) if (!merged.has(x.id)) merged.set(x.id, x);
      if (merged.size > 500) throw Error('超过 500 个点子');
      ideas = [...merged.values()]; save();
    } catch (err) { message('导入失败，已有点子保持：' + err.message); }
    e.target.value = '';
  };
  render();
})();
'''

def build_overview():
    records = json.loads(HISTORY.read_text(encoding='utf-8'))
    ids = ('input', 'target', 'geometry', 'action', 'fall', 'runtime')
    required = {'date', 'parent', 'title', 'status', 'attempt', 'result', 'stop', 'source', 'section'}
    sources = {}
    for record in records:
        if set(record) != required or record['parent'] not in ids:
            raise ValueError('Invalid history record: ' + repr(record))
        path = ROOT / record['source']
        content = path.read_text(encoding='utf-8')
        if record['section'] not in content:
            raise ValueError('Missing source section: ' + record['section'])
        sources[record['source']] = hashlib.sha256(path.read_bytes()).hexdigest()
    overview = OVERVIEW.replace('更新于 2026-10-22', '更新于 2026-10-23')
    overview = overview.replace('<p>绿＝',
        '<div class="history-brief"><strong>已从实际开发记录补入 ' + str(len(records)) + ' 条历史分支（10-10 至 10-22）。</strong>'
        '<p>每个节点下展开“历史上在这里试过什么”，看尝试 → 结果 → 最后卡点 → 来源。'
        '旧侧链、当前实现、失败实验与仅设计路线分开；旧工单与审批用语只当历史，不作为现行流程。'
        '这份树是有来源的开发路线整理，不宣称穷尽仓库全部实验。</p>'
        '<nav class="history-nav"><a href="#input">输入</a><a href="#target">获取/跟踪</a>'
        '<a href="#geometry">几何/姿态</a><a href="#action">动作模型</a>'
        '<a href="#fall">跌倒模型</a><a href="#runtime">板端性能</a></nav></div><p>绿＝', 1)
    overview = overview.replace('最后卡在哪里？可靠识别这一段还没过。',
        '最后卡在哪里？事件输入与评测口径先卡住，可靠识别仍未完成。')
    overview = overview.replace('但“这个人真的跌倒了吗”仍有明显漏检和人员泛化问题。',
        '但输入是否包含可观测跌倒过程、人体成员是否可靠以及人员泛化均未解决。')
    overview = overview.replace('这不是单一代码崩溃：有的路线缺输入，有的路线实验失败，还有的路线尚未验证。下树按停止位置分别展开。',
        '最新输入审计：30条 Falling 中26条无直立帧，仅4条含完整直立→卧倒。此前8/14只表示标签片段触发，不能叫跌倒事件检出率。'
        '当前先卡在有效事件数据与评测口径，其次是人体成员/泛化；目标域验证与板端ML实时性还未完成。')
    overview = overview.replace('LaserAct Velodyne MIL 官方人员留出检出 8/14；',
        'LaserAct Velodyne MIL 官方人员留出在 Falling 标签片段上触发 8/14（不是跌倒事件检出率）；')
    overview = overview.replace('漏 6 条：2 条无有效连续窗口，4 条有输入却未触发；',
        '6条标签片段未触发：2条无有效连续窗口，4条有窗口却未触发；')
    overview = overview.replace('训练人员内部 LOPO：原 bag-max 3/16、',
        '训练人员内部 LOPO：原 bag-max 在 Falling 标签片段上触发3/16（亦非事件召回）、')
    overview = overview.replace('软件缺陷已修：',
        '最新解释修正：上述片段分数不能证明识别了下降事件。新增几何准入闸门复核30条为26条NEVER_UPRIGHT、4条OK；'
        '这是开发集的观测筛选，不是独立真实跌倒GT。数据总计划与事件标注接口已落地，新的几何时序链和独立事件验证仍待做。</div>'
        '<div class="twig ok">软件缺陷已修：', 1)
    overview = overview.replace('实时缺口：历史 10-19 有人板端观测约 4.03 Hz，处理 P95 303.3 ms，并有丢帧；它属于旧几何现场记录，不是本轮 ML 测速。本轮候选原生板端整链性能 UNKNOWN，PC 数字不能代替。',
        '实时历史：10-19有人约4.03Hz后已做CPU优化；10-22旧几何软件发布有原生板端整段验证，固定输入step P95由30.920增至55.413ms，'
        '约6.78小时累计丢43帧。不能把早期4Hz当最新版本结果；该发布不含ML候选，新候选板端整链性能仍UNKNOWN。')
    overview = overview.replace('当前边界：候选模型未部署，',
        '版本边界：既有几何软件已在历史授权中发布；本次未操作设备，新的ML候选模型未部署，')
    counts = {}
    for parent in ids:
        selected = [r for r in records if r['parent'] == parent]
        counts[parent] = len(selected)
        additions = ['<details class="history-group"><summary>历史上在这里试过什么 · %d条分支</summary>' % len(selected)]
        for r in selected:
            additions.append('<article class="history-record"><h4>%s · %s</h4><span class="tag">%s</span>' %
                (escape(r['date']), escape(r['title']), escape(r['status'])))
            for key, label in [('attempt', '当时的想法 / 做法'), ('result', '实际结果'), ('stop', '最后卡点 / 限定')]:
                additions.append('<p class="%s"><b>%s：</b>%s</p>' % (key, label, escape(r[key])))
            additions.append('<p class="source">来源：%s · %s</p></article>' % (escape(r['source']), escape(r['section'])))
        additions.append('</details>')
        pattern = r'(<details open id="' + parent + r'">.*?)(</details>)'
        overview, n = re.subn(pattern, lambda m: m[1] + ''.join(additions) + m[2], overview, count=1, flags=re.S)
        assert n == 1, parent
    return overview, {'branches': len(records), 'by_parent': counts, 'source_sha256': sources}


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    backup = EVIDENCE / 'PREVIOUS.html'
    if not backup.exists():
        backup.write_bytes(DESKTOP.read_bytes())
    source = ORIGINAL.read_text(encoding='utf-8')
    overview, history_manifest = build_overview()
    source = source.replace('LiDAR 点云 → 跟踪开始 · 完整数据流', '雷达 → 实时跌倒识别 · 路线、分支与卡点')
    source = source.replace('LiDAR 点云 → 跟踪开始\n', '雷达 → 实时跌倒识别：走到哪，卡在哪\n')
    source = source.replace('从 ROS /innolidar_points 输出开始，到 TargetTracker.select / update 为止的完整链路',
        '完整路线树 + 实验失败分支 + 可保存的临时点子；原始 ROS→跟踪细节保留')
    source = source.replace('</style>', CSS + '\n</style>')
    source = source.replace('<div class="legend">', overview + '\n<details class="detail-toggle"><summary>展开原始 ROS → 跟踪开始的 17 步细节（历史参数与行号）</summary>\n<div class="legend">', 1)
    source = source.replace('从这里往下</b>：基线采集 → 特征 → 跌倒状态机（不在本图范围）。',
        '从这里往下</b>：基线采集 → 特征 → 几何跌倒状态机；ML 候选走独立旁路，详见上方完整路线树。')
    source = source.replace('</footer>', '</footer>\n</details>')
    source = source.replace('</body>', '<script>' + JS + '</script>\n</body>')
    # Avoid an unqualified historical claim that 3D connectivity separates touching objects.
    source = source.replace('能把紧贴的人/家具在高度上分开。', '可分离未连通的三维表面；相接的人/家具仍可能误并，不保证语义分离。')
    OUT.write_text(source, encoding='utf-8')
    DESKTOP.write_bytes(OUT.read_bytes())
    scripts = re.findall(r'<script>(.*?)</script>', source, re.S)
    (EVIDENCE / 'page_script.js').write_text(scripts[0], encoding='utf-8')
    paths = [backup, ORIGINAL, OUT, DESKTOP, HISTORY, Path(__file__)]
    (EVIDENCE / 'ARTIFACT_SHA.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, ensure_ascii=False, indent=2), encoding='utf-8')
    (EVIDENCE / 'HISTORY_MANIFEST.json').write_text(json.dumps(history_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(OUT))

if __name__ == '__main__':
    main()
