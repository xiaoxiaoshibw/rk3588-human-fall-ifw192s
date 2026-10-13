"""Summarize diagnostic observations, without inferring candidate identities."""
import json
import pathlib
import statistics

HERE = pathlib.Path(__file__).parent


def stats(values):
    if not values:
        return None
    values = sorted(values)
    return {'n': len(values), 'min': values[0], 'p50': statistics.median(values),
            'p95': values[int((len(values) - 1) * .95)], 'max': values[-1]}


rows = []
for p in sorted((HERE / 'runs_03').glob('cap_*.json')):
    run = json.loads(p.read_text(encoding='utf-8'))
    groups, roi = {}, {}
    for frame in run['frames']:
        if frame['status'] == 'UNKNOWN':
            continue
        for candidate in frame['candidates']:
            classes = sorted(set(h['class_name'] for h in candidate['overlaps']))
            key = '+'.join(classes) or 'NO_OVERLAP'
            groups.setdefault(key, []).append(candidate)
        for obj in frame['roi']:
            roi.setdefault(obj['class_name'], []).append(obj)
    groups = {k: {'observations': len(v), 'point_count': stats([c['point_count'] for c in v]),
                  'probability': stats([c['prob'] for c in v]),
                  'strong_observations': sum(c['decision'] == 'CONFIRMED_HUMAN' for c in v),
                  'scoring_pointset_differs': sum(c['scoring_pointset_differs'] for c in v),
                  'scoring_point_count': stats([c['scoring_point_count'] for c in v]),
                  'foreground_sources': {s: sum(c['foreground_source'] == s for c in v)
                                         for s in sorted(set(c['foreground_source'] for c in v))},
                  'fusion_sources': {s: sum(c['source'] == s for c in v)
                                     for s in sorted(set(c['source'] for c in v))}}
              for k, v in groups.items()}
    roi = {k: {'observations': len(v), 'point_count': stats([o['point_count'] for o in v]),
               'probability': stats([o['prob'] for o in v]),
               'above_055': sum(o['prob'] >= .55 for o in v),
               'propagated': sum(o.get('source') == 'propagated' for o in v)}
           for k, v in roi.items()}
    rows.append({'sid': run['sid'], 'model': run['model'], 'totals': run['totals'],
                 'overlap_groups': groups, 'full_roi': roi})
with (HERE / 'OBSERVATIONS.json').open('x', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
text = ['# R4 候选归因观察', '',
        '仅当前三会话已标帧。交叠类别表示与人工ROI的点交叠，不是候选真实语义；NO_OVERLAP保持UNKNOWN。',
        'GT compact索引逐帧映射回raw。S1明确无人协议才统计空场输出；传播对象不作为独立样本。', '',
        '| 会话 | 模型 | 已标/UNKNOWN帧 | 全帧接受/强分类/当前确认观测 | 空场确认观测 |',
        '|---|---|---|---|---|']
for r in rows:
    t = r['totals']
    text.append(f"| {r['sid']} | {r['model']} | {t['evaluated_frames']}/{t['unknown_frames']} | "
                f"{t['accepted']}/{t['strong']}/{t['current_confirmed_tracks']} | {t['zero_person_confirmed']} |")
text += ['', '完整ROI与实际候选交叠分组的概率/点数分布见OBSERVATIONS.json，逐帧来源见runs_03。',
         'A+B评分采用联合点集；公开point_indices仅保留A点，本工具只读重建联合评分点集再计算交叠，公开索引不被改写。',
         '这些计数是逐帧观测之和，不能解释为人数，也不是对象级recall。',
         '原R3“v2空场candidate fp=600”混合了生成候选与接受候选；本轮重新分别实测，不改旧记录。',
         '空场v1/v2/v3均出现真实确认观测，支持继续检查负例覆盖及融合判定；不能据此判定RF无关或51维本质不可分。',
         '实际簇与完整ROI的概率差异需按同帧点交叠和污染量解释；不以点数区间单独确定根因。',
         '未进行训练、阈值选择、GT修改、采集或生产接入。']
(HERE / 'REPORT.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
print('summarized', len(rows), 'runs')
