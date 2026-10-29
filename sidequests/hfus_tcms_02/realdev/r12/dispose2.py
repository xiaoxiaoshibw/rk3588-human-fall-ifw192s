"""Author disposition of the S07F read-only review findings."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

from common2 import EV, save, read


def main():
    st = read(EV / 'OPENCODE_REVIEW_STATUS.json')
    save('REVIEW_DISPOSITION.json', dict(
        review_result='No blocking code/evidence defects in the single read-only static review; fix criteria PASS; frozen gate remains 8/10 with two pre-existing unrelated fails; NO_PROMOTION retained; independent execution NOT_RUN',
        blocking_findings_open=0,
        exit_code=st['exit_code'], actual_models=st['actual_models'], source_unchanged=st['source_unchanged'],
        request_read_observed=st['request_read_observed'], read_only_tools=st['read_only_tools'], tool_calls=st['tool_calls'], seconds=st['seconds'],
        independent_execution='NOT_RUN',
        findings={
            'NB1_REPORT_ROWS': 'FIXED_BEFORE_SEAL: AUTHOR_REPORT run table now lists REPORT/R2/R3/R4 plus ERRATA/OPENCODE_REVIEW rows with the retained-failure note; the table update postdates the review snapshot and is disclosure-only (no algorithm or numeric change).',
            'NB2_ERRATA_TYPO': "ACKNOWLEDGED_NO_FILE_CHANGE: the REGION_PROTOCOL_V2_ERRATA.json impact text says '0.60-0.86 m'; the same file's outer_a.min=0.4128 and AUTHOR_REPORT say 0.41-0.86. Written files stay untouched; this disposition is authoritative: use 0.41-0.86 m.",
            'NB3_REQUEST_RANGE': 'ACKNOWLEDGED: the review request wording said f188-192; the actual case frames are f190-192 (f188-189 belongs to the earlier POS-JITTER item). Request text retained, not rewritten.',
            'NB4_DELTA_ARGMAX': 'FIXED_BEFORE_SEAL: VERIFY2_DELTA_ARGMAX.json now stores the argmax frame (f191, 925.9 mm) for the hardcoded report sentence.',
            'NB5_OLD_MECHANISM_COUNTS': 'ACKNOWLEDGED_RETENTION: MECHANISM_SUPPORT_RULES.json (R2 round) carries a mislabeled hold/full multicomponent count; the _R3 file (hold 148, full 166) is authoritative, both retained.',
            'NB6_SHA_RECHECK': 'ACKNOWLEDGED_INHERENT: a no-shell review cannot recompute hashes; this session performs byte-level seal checks with shell access (MANIFEST/FINAL_SEAL), and later reviewers with execution rights can recompute.',
        },
        post_review_changes='After the review snapshot only these changed or were added: AUTHOR_REPORT.md disclosure rows; r12/report2.py kept in sync; VERIFY2_DELTA_ARGMAX.json plus its RUN/log; this disposition; and the delivery records (RESULTS/HANDOFF/MANIFEST/FINAL_SEAL/DOCUMENT_APPEND/EXECUTED_SOURCE). deliver2 cross-checks every pre-existing file against the review snapshot and refuses to seal on any other difference.',
        final_boundaries=dict(fix='PASS: OUTER_A hold max step 85.0 mm, valid 145/151, drops 6 (<=10, each listed), spanning <= 52.6 mm, connectivity 150/151', frozen_gate='8/10; remaining fails: common-node regression, six-edge calibration', promotion='NO_PROMOTION', joint_accuracy='BLOCKED', human_effect='BLOCKED', purity='UNKNOWN', recall='UNKNOWN', independent_execution='NOT_RUN'),
    ))
    print('disposition written', flush=True)


if __name__ == '__main__':
    main()
