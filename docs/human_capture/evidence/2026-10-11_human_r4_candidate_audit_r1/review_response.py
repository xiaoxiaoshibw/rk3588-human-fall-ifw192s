"""Separate human/propagated observations; do not infer independent sample counts."""
import collections
import json
import pathlib

HERE = pathlib.Path(__file__).parent
rows = []
for p in sorted((HERE / 'runs_03').glob('cap_*.json')):
    run = json.loads(p.read_text(encoding='utf-8'))
    groups = collections.defaultdict(list)
    for f in run['frames']:
        for roi in f['roi']:
            groups[(roi['class_name'], roi['source'])].append(roi)
    rows.append({'sid': run['sid'], 'model': run['model'], 'gt_warnings': run['gt_source']['warnings'],
                 'roi_by_source': [{'class_name': k[0], 'source': k[1], 'observations': len(v),
                                    'above_055': sum(o['prob'] >= .55 for o in v)} for k, v in groups.items()]})
with (HERE / 'ROI_SOURCE_DISCLOSURE.json').open('x', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
text = '''# 独审反馈处理

Go Flash独审exit0/362.59秒，探针exit0/13.36秒；只读，无可复现功能缺陷。原始全文见OPENCODE_INDEPENDENT_REVIEW.md，不改审核原文。

1. 传播ROI统计是逐帧观测，不是独立样本。新增ROI_SOURCE_DISCLOSURE.json按human/propagated分开；S1每模型FURNITURE仅5条human原始观测、1515条传播观测，BACKGROUND为1+303。两类均保留诊断，不能把传播观测用于宣称训练样本独立性/泛化。原汇总保留不覆盖。
2. GT旧gt_level=UNKNOWN继续保留；资格由实际reviewed/schema/对象和会话SHA审计确定，warnings在来源分组中进一步外显。本轮只核对三会话，不继承R3全九会话解锁声明。
3. uncertain_intervals三份当前快照均为空。非空区间真实行为NOT_RUN，缺结构契约/覆盖，不能宣称该边界已全面验证；不影响本轮数据。后续扩展前须先冻结区间结构并补非法区间检查。
4. 独审时尚未形成after范围记录与最终报告。REPORT/OBSERVATIONS/FINDINGS已在自验完成后写出，closeout补after/SCOPE_AUDIT/MANIFEST；结束审计不冒称由独审复跑。
5. 新测试按仓库独立运行习惯保持单独命令，不改已有run_all_tests.js。合成联合点集/越界检查PASS；真实联合点集重建由独审核对源码/7个merged候选顺序及映射，未宣称存在全引擎旧新评分逐值自动对拍测试。

范围外已发现的engine A+B公开点集契约缺口仍保留待修复，本工具只读重建评分点集，不写入engine。审稿未宣称ACCEPTED，作者保持SUBMITTED。

归档审核stdout时临时python -c未用with关闭输出文件，引发ResourceWarning（原文件已写完整，进程exit0）；本轮已核验归档文字与原始JSONL的text完全一致。此警告不作为成功测试证据，最终文件操作均使用with。
'''
(HERE / 'CODEX_REVIEW_RESPONSE.md').write_text(text, encoding='utf-8')
raw = [json.loads(l) for l in (HERE / 'opencode_review_01.jsonl').read_text(encoding='utf-8').splitlines() if l.startswith('{')]
expected = '\n'.join(r.get('part', {}).get('text', '') for r in raw if r.get('type') == 'text')
assert (HERE / 'OPENCODE_INDEPENDENT_REVIEW.md').read_text(encoding='utf-8') == expected
print('source disclosure and review archive integrity PASS')
