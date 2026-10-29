"""Small diagnostic plots from frozen outputs; no source data or thresholds changed."""
import argparse
import json
from pathlib import Path
import os
import numpy as np
from run_experiment import EMPTY, SESSIONS


def plot(evidence):
    output = evidence/'plots_r1'
    output.mkdir(exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str(output/'mplconfig')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary = json.loads((evidence/'run_r1/SUMMARY.json').read_text(encoding='utf8'))
    audit = json.loads((evidence/'static_r1/STATIC_AUDIT.json').read_text(encoding='utf8'))
    tags = ['v{}_w{}'.format(s, w) for s in (.12, .15) for w in (5, 10, 20)]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    x = np.arange(len(tags))
    for i, method in enumerate(('B1', 'B2', 'B3')):
        values = [100*summary[EMPTY+'_'+t+'_REPORT']['activation_rate_per_eligible_tile'][method] for t in tags]
        axes[0, 0].bar(x+(i-1)*.24, values, width=.24, label=method)
    axes[0, 0].set(xticks=x, xticklabels=[t.replace('v', '').replace('_w', ' / ') for t in tags],
                   ylabel='Active eligible regions (%)', xlabel='Voxel (m) / half-window frames',
                   title='Declared-empty temporal REPORT (same session)')
    axes[0, 0].legend()
    for size, bands in audit['results'].items():
        axes[0, 1].plot(range(3), [100*b['observed_hit_frequency']['p50'] for b in bands], marker='o', label=size+' m')
        axes[1, 0].plot(range(3), [100*b['within_same_voxel_centroid_drift_m']['1']['p95'] for b in bands], marker='o', label=size+' m')
    for ax in (axes[0, 1], axes[1, 0]):
        ax.set(xticks=range(3), xticklabels=['0-4', '4-8', '8-12'], xlabel='Approx. range band (m)')
        ax.legend()
    axes[0, 1].set(ylabel='Median observed-hit frequency (%)', title='Absence is UNKNOWN, not free space')
    axes[1, 0].set(ylabel='P95 conditional centroid drift (cm)', title='Same voxel, adjacent frames; no point correspondence')
    for size in (.12, .15):
        rates = []
        for sid in [EMPTY]+SESSIONS:
            split = 'REPORT' if sid == EMPTY else 'DIAGNOSTIC'
            rec = summary[sid+'_v{}_w5_{}'.format(size, split)]
            rates.append(100*rec['activation_rate_per_eligible_tile']['B3'])
        axes[1, 1].plot(range(9), rates, marker='o', label=str(size)+' m / W5')
    axes[1, 1].set(xticks=range(9), xticklabels=['Empty']+[s[-6:] for s in SESSIONS],
                   ylabel='B3 active eligible regions (%)', title='Action recordings: semantic identity UNKNOWN')
    axes[1, 1].tick_params(axis='x', labelrotation=40)
    axes[1, 1].legend()
    fig.suptitle('HFUS-TCMS-01: RAW support diagnostics, not human detection accuracy')
    fig.savefig(output/'diagnostics.png', dpi=160)
    fig.savefig(output/'diagnostics.svg')
    plt.close(fig)
    table = ['| Session | Grid | Eligible regions | B1 % | B2 % | B3 % | B3 active/scored frames |',
             '|---|---|---:|---:|---:|---:|---:|']
    for sid in [EMPTY]+SESSIONS:
        for tag in tags:
            rec = summary[sid+'_'+tag+('_REPORT' if sid == EMPTY else '_DIAGNOSTIC')]
            rates = rec['activation_rate_per_eligible_tile']
            table.append('| {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {}/{} |'.format(
                sid, tag, rec['counts']['eligible_tiles'], 100*rates['B1'], 100*rates['B2'], 100*rates['B3'],
                rec['active_frames'].get('B3', 0), rec['scored_frames']))
    (output/'TABLES.md').write_text('\n'.join(table)+'\n', encoding='utf8')
    print('PLOTS DONE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('evidence', type=Path)
    plot(parser.parse_args().evidence)
