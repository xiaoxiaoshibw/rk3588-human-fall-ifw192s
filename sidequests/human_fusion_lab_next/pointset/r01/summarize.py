"""Add XYZ-model scores and independent per-session deliverables to the measured run."""
import json
import pickle

import numpy as np
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix

from run import HERE, ROOT, OUT, EVIDENCE, LAB, dump


def main():
    cfg = yaml.safe_load((HERE/'config.yaml').read_text(encoding='utf-8'))
    catalog = json.loads((OUT/'catalog.json').read_text(encoding='utf-8'))
    audit = json.loads((LAB/'results/AUDIT.json').read_text(encoding='utf-8'))
    objects = json.loads((OUT/'reference_object_features.json').read_text(encoding='utf-8'))
    rows = json.loads((OUT/'candidate_features.json').read_text(encoding='utf-8'))
    s1 = 'cap_20261010_175227'
    train = [r for r in objects if r['sid'] in audit['splits']['train'] and (r['sid'] != s1 or r['fi'] % 3 == 0)]
    model = RandomForestClassifier(n_estimators=cfg['rf_trees'], max_depth=cfg['rf_max_depth'], min_samples_leaf=cfg['rf_min_samples_leaf'], class_weight='balanced', random_state=cfg['seed'], n_jobs=2)
    model.fit([r['features'] for r in train], [r['label'] for r in train])
    with (OUT/'rf_xyz_shadow.pkl').open('wb') as f:
        pickle.dump(model, f)
    probabilities = model.predict_proba([r['features'] for r in rows])[:, list(model.classes_).index(1)]
    probs = {(r['sid'], r['fi'], r['scope'], r['id']): float(p) for r, p in zip(rows, probabilities)}
    compared = {'training': 'XYZ_DESCRIPTORS_ON_EXISTING_MANUAL_OBJECTS', 'train_sessions': audit['splits']['train'],
                'S1_train_rule': 'fi % 3 == 0; calibration/holdout excluded', 'splits': {},
                'limits': ['Prior development-exposed sessions; no new-actor/generalization claim.',
                           'Candidate specificity unavailable when negative_rows=0; UNKNOWN is not negative.',
                           'Reference-object evaluation is not end-to-end detection performance.']}
    for name, sessions in audit['splits'].items():
        chosen = [(r, p) for r, p in zip(rows, probabilities) if r['sid'] in sessions and r['label'] is not None and r['scope'] == 'full_3d']
        if chosen:
            y = [r['label'] for r, _ in chosen]
            compared['splits'][name] = {'n': len(y), 'negative_rows': y.count(0), 'positive_rows': y.count(1),
                                       'rf_xyz_confusion_tn_fp_fn_tp': confusion_matrix(y, [p >= cfg['model_probability_threshold'] for _, p in chosen], labels=[0, 1]).ravel().tolist(),
                                       'pointnet_confusion_tn_fp_fn_tp': confusion_matrix(y, [r['pointnet_prob'] >= cfg['model_probability_threshold'] for r, _ in chosen], labels=[0, 1]).ravel().tolist()}
    neg_holdout = [r for r in objects if r['sid'] == s1 and r['fi'] % 3 == 2 and r['label'] == 0]
    if neg_holdout:
        pred = model.predict_proba([r['features'] for r in neg_holdout])[:, 1]
        compared['S1_reference_object_holdout'] = {'n': len(neg_holdout), 'false_person_predictions': int(np.sum(pred >= cfg['model_probability_threshold'])),
                                                  'status': 'SAME_RECORDING_OBJECT_CLASSIFICATION_ONLY'}
    dump(OUT/'model_comparison.json', compared)
    stats = []
    markdown = ['# 九会话人体动作独立目录', '', '动作名称是录制说明，未逐帧确认；自动候选和已有人工参照分开。骨架为源点支撑的区域估计，不是经过标定的解剖关节。', '',
                '| 会话动作 | 帧数 | 有人工参照的帧 | 小ROI有候选帧 | 全场最佳簇参照覆盖 | XY对照覆盖 | 未标身份点比例 | 状态 |',
                '|---|---:|---:|---:|---:|---:|---:|---|']
    for s in catalog['sessions']:
        sid = s['session_id']
        summary = json.loads((OUT/sid/'summary.json').read_text(encoding='utf-8'))
        coverage, xycoverage, unassigned, roi_cover, xy_unassigned = [], [], [], [], []
        retained_num = retained_den = 0
        ref_outside = 0
        full_clusters, roi_frames = 0, 0
        keyframes = []
        for fi in range(s['frame_count']):
            path = OUT/sid/f'{fi:04d}.json'
            row = json.loads(path.read_text(encoding='utf-8'))
            full_clusters += len(row['full_3d'])
            roi_frames += bool(row['roi_3d'])
            for scope in ['full_3d', 'roi_3d', 'full_2d']:
                for c in row[scope]:
                    c['rf_xyz_prob'] = probs[(sid, fi, scope, c['id'])]
                    q = c['independence']
                    q['separation_status'] = 'GEOMETRICALLY_SEPARATE' if q['dense_core_fraction'] >= cfg['independence_strong_core_fraction'] and q['near_background_fraction'] <= cfg['independence_max_near_background_fraction'] and (q['nearest_other_cluster_gap_m'] is None or q['nearest_other_cluster_gap_m'] >= cfg['independence_min_other_cluster_gap_m']) else 'CONTACT_OR_FRAGMENT_RISK'
            for o in row['reference']:
                ref_outside += o['roi_point_fraction'] < .5
            for m in row['metrics']['full_3d']['persons']:
                coverage.append(m['reference_coverage'])
                retained_num += m['fg_kept']
                retained_den += m['reference_count']
                if m['best_cluster_point_count']:
                    unassigned.append(m['unannotated_points']/m['best_cluster_point_count'])
            xycoverage += [m['reference_coverage'] for m in row['metrics']['full_2d']['persons']]
            xy_unassigned += [m['unannotated_points']/m['best_cluster_point_count'] for m in row['metrics']['full_2d']['persons'] if m['best_cluster_point_count']]
            roi_cover += [m['reference_coverage'] for m in row['metrics']['roi_3d']['persons']]
            if row['reference'] and len(keyframes) < 5 and fi % max(1, s['frame_count']//5) == 0:
                keyframes.append(fi)
            dump(path, row)
        refs = sum(f['reference_persons'] > 0 for f in summary['frames'])
        result = {'session_id': sid, 'action_description': s['activity'], 'frames': s['frame_count'],
                  'reference_frames': refs, 'roi_candidate_frames': roi_frames, 'total_full_clusters': full_clusters,
                  'background_reference_retention': retained_num/retained_den if retained_den else None,
                  'mean_best_cluster_reference_coverage_3d': float(np.mean(coverage)) if coverage else None,
                  'mean_best_cluster_reference_coverage_2d': float(np.mean(xycoverage)) if xycoverage else None,
                  'mean_roi_cluster_reference_coverage': float(np.mean(roi_cover)) if roi_cover else None,
                  'mean_unannotated_membership_fraction': float(np.mean(unassigned)) if unassigned else None,
                  'mean_unannotated_membership_fraction_2d': float(np.mean(xy_unassigned)) if xy_unassigned else None,
                  'reference_objects_majority_outside_roi': ref_outside,
                  'reference_status': s['reference_status'], 'skeleton_accuracy': 'BLOCKED_NO_JOINT_GT',
                  'pure_human_accuracy': 'NOT_EVALUATED_NONEXHAUSTIVE_LABELS', 'keyframes': keyframes}
        dump(OUT/sid/'action_report.json', result)
        stats.append(result)
        fmt = lambda v: '—' if v is None else f'{100*v:.1f}%'
        markdown.append(f"| {s['activity']} | {s['frame_count']} | {refs} | {roi_frames} | {fmt(result['mean_best_cluster_reference_coverage_3d'])} | {fmt(result['mean_best_cluster_reference_coverage_2d'])} | {fmt(result['mean_unannotated_membership_fraction'])} | {s['reference_status']} |")
    markdown += ['', 'S1空场为304帧，只有HOLDOUT帧用于背景空场留帧验收；S9旧标签源绑定失败，不生成所谓纯人体参照、不计算GT分数。',
                 '', '若静立/远距会话在小ROI无候选但全场有人，不扩大圈线，不把区外丢失报成背景算法失败。需审核截图ROI坐标与所有旧会话是否同布局。',
                 '', '运动粘连诊断采用当前单帧、近背景比例、紧半径连通碎片、其他簇间距、已标家具混入和未标身份比例；未把“雷达吸引点”当已验证物理机制。']
    dump(OUT/'action_catalog.json', stats)
    (EVIDENCE/'ACTION_CATALOG.md').write_text('\n'.join(markdown)+'\n', encoding='utf-8')
    dump(EVIDENCE/'MEASURED_SUMMARY.json', {'sessions': stats, 'model_comparison': compared})
    empty = json.loads((OUT/s1/'summary.json').read_text(encoding='utf-8'))
    bg = json.loads((OUT/'background.json').read_text(encoding='utf-8'))
    hold = [empty['frames'][i] for i in bg['holdout']]
    dump(EVIDENCE/'EMPTY_HOLDOUT.json', {'frames': len(hold), 'max_foreground_points': max(f['fg'] for f in hold),
                                       'full_clusters_total': sum(f['full_clusters'] for f in hold),
                                       'roi_clusters_total': sum(f['roi_clusters'] for f in hold),
                                       'status': 'SAME_RECORDING_HELDOUT_BACKGROUND_ONLY', 'index_split': bg['holdout']})
    print('Independent session reports and XYZ model scores written')


if __name__ == '__main__':
    main()
