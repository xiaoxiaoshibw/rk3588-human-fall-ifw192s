"""Read-only independent checks of the stopped GL-I05 R1 submission."""
import ast
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
AUTHOR = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i05_r1/research_01'
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'), str(AUTHOR)]
from core.ground import resolve_constrained_settings
from oracle_analysis import oracle
from search_prototype import search_events


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plane(deg, support=100):
    rad = math.radians(deg)
    return dict(normal=[math.sin(rad), 0., math.cos(rad)],
                offset_m=1., support_count=support)


def scalar_metrics(items, settings):
    pairs = []
    for i, j in itertools.combinations(range(len(items)), 2):
        dot = sum(a * b for a, b in zip(items[i]['normal'], items[j]['normal']))
        angle = math.degrees(math.acos(max(-1., min(1., dot))))
        if angle > settings['distinct_normal_deg'] or abs(
                items[i]['offset_m'] - items[j]['offset_m']) > settings['distinct_offset_m']:
            pairs.append([i, j])
    maximum = max((item['support_count'] for item in items), default=0)
    near = {i for i, w in enumerate(items)
            if w['support_count'] >= maximum * settings['support_close_ratio']}
    top = {i for i, w in enumerate(items) if w['support_count'] == maximum}
    return dict(ALL=pairs, NEAR=[p for p in pairs if set(p) <= near],
                BEST_ONLY=[p for p in pairs if set(p) <= near and set(p) & top])


def main():
    result = {'kind': 'codex_gli05_independent_audit', 'checks': {}}
    manifest = json.loads((AUTHOR / '11_submission_manifest.json').read_text(encoding='utf8'))
    result['manifest_sha'] = sha(AUTHOR / '11_submission_manifest.json')
    result['manifest_mismatches'] = [rel for rel, expected in manifest['files'].items()
                                     if sha(ROOT / rel) != expected]
    result['python38_ast'] = []
    for path in AUTHOR.glob('*.py'):
        ast.parse(path.read_text(encoding='utf8'), feature_version=(3, 8))
        result['python38_ast'].append(path.name)
    settings = resolve_constrained_settings()
    mismatches = []
    for perm in itertools.permutations([plane(0., 90), plane(13., 100), plane(6., 85)]):
        expected = scalar_metrics(perm, settings)
        actual = oracle(list(perm), settings)
        for metric in ('ALL', 'NEAR', 'BEST_ONLY'):
            if actual['metrics'][metric]['distinct_pairs'] != expected[metric]:
                mismatches.append(dict(order=[w['support_count'] for w in perm],
                                       metric=metric, expected=expected[metric],
                                       actual=actual['metrics'][metric]['distinct_pairs']))
    result['scalar_metric_mismatches'] = mismatches
    invalid = []
    for normal in ([0., 0., 0.], [0., 0., 2.]):
        try:
            actual = oracle([dict(plane(0.), normal=normal)], settings)
            invalid.append(dict(normal=normal, status=actual['status']))
        except ValueError:
            pass
    result['accepted_nonunit_witnesses'] = invalid
    malformed_settings = []
    for name, value in [('distinct_normal_deg', float('nan')),
                        ('distinct_offset_m', float('nan')),
                        ('support_close_ratio', float('nan'))]:
        try:
            actual = oracle([plane(0.), plane(30.)], dict(settings, **{name: value}))
            malformed_settings.append(dict(key=name, status=actual['status']))
        except ValueError:
            pass
    result['accepted_nonfinite_settings'] = malformed_settings
    independent_cases = []
    for angles, supports in [([0., 4., 8.], [100, 100, 100]),
                             ([0., 6., 12.], [90, 100, 90]),
                             ([0., 20.], [100, 79]), ([0., 20.], [100, 80])]:
        for order in itertools.permutations(range(len(angles))):
            items = [plane(angles[i], supports[i]) for i in order]
            expected = scalar_metrics(items, settings)
            state = ('unresolved' if expected['NEAR'] else
                     'seen_dominant_pool_closed' if expected['ALL'] else 'seen_pairwise_closed')
            events = [dict(w, stage='qualified', iteration=i) for i, w in enumerate(items)]
            actual = search_events(events, lambda e: (e, 'fixture'), settings)
            independent_cases.append(dict(order=list(order), expected=state,
                                          actual=actual['status'], matched=state == actual['status']))
    result['independent_terminal_cases'] = independent_cases
    html = (AUTHOR / 'source_review.html').read_text(encoding='utf8')
    payload = json.loads(html.split('<script>const D=', 1)[1].split(';</script>', 1)[0])
    source = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final'
    diagnostic = json.loads((source / 'diagnostic.json').read_text(encoding='utf8'))
    first = next((source / 'source_indices.jsonl').open(encoding='utf8'))
    first = json.loads(first)
    xyz = first['source_xyz_m']
    residuals = {label: sum(a * b for a, b in zip(p['normal'], xyz)) + p['offset_m']
                 for label, p in payload['planes'].items()}
    result['spatial_payload'] = dict(frames=len(payload['frames']),
        boxes=len(payload['bounds']), records=len(payload['records']),
        statistics_records=len(diagnostic['box_frame_records']),
        jsonl_total_rows=payload['jsonl_total_rows'], residuals_for_first_point=residuals,
        stored_residual=first['signed_residual_m'],
        point_lookup_handler=('onclick' in html or 'addEventListener' in html),
        selected_plane_used_for_color='color(r[6],lim)' in html,
        posthoc_labeled_approved_prior=payload['planes']['approved']['origin'])
    result['ledger_cost_fields'] = list(json.loads(
        (AUTHOR / 'experiment_results_final.json').read_text(encoding='utf8'))['synthetic'][0]['elapsed_s'])
    with (OUT / '04_codex_audit.json').open('x', encoding='utf8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('independent_terminal_cases', 'python38_ast')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
