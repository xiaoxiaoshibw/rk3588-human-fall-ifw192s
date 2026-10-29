"""Contract-only evaluation. Raw denominators and explicit session/source binding."""
from contracts import digest


def evaluate(records, labels, kind):
    result = dict(schema='hfus-predev-evaluation/1', kind=kind, contract_only=True,
                  real_effectiveness='BLOCKED', effectiveness_pass=False,
                  point_retention=None, known_background_mixing=None, unknown_fraction=None,
                  first_discovery_delay_s=None, maximum_measured_gap_s=None,
                  id_switches=None, false_track_duration_s=None, point_purity=None,
                  annotation_coverage=None, reviewed_frame_coverage=0., reason=None)
    if not labels:
        result['reason'] = 'NO_LABELS_IS_NOT_ZERO_CONTAMINATION'
        return result
    by_key = {(r['sid'], r['fi']):r for r in records}
    if len(by_key) != len(records):
        raise ValueError('Nonunique session/frame records; select one variant')
    sids = {r['sid'] for r in records}
    def key(label):
        sid = label.get('sid')
        if sid is None and len(sids) == 1:
            sid = next(iter(sids))
        return sid, label['fi']
    if len({key(l) for l in labels}) != len(labels) or any(key(l) not in by_key for l in labels):
        raise ValueError('Duplicate/unknown sid/frame annotation')
    for label in labels:
        if 'source_sha256' in label and label['source_sha256'] != by_key[key(label)]['source_sha256']:
            raise ValueError('Annotation source SHA drift')
    if any(l.get('annotation_kind') != 'points' for l in labels):
        result['reason'] = 'BOX_OR_TRACK_LABELS_CANNOT_REPORT_POINT_PURITY'
        return result
    human_total = retained = background = selected = unannotated = reviewed_rows = all_rows = 0
    unknown = valid_rows = reviewed_frames = 0
    states = {}
    for label in sorted(labels, key=lambda l:(key(l)[0], by_key[key(l)]['time_ns'])):
        r = by_key[key(label)]
        if not label.get('reviewed'):
            continue
        h, b = set(label['human_rows']), set(label['background_rows'])
        domain = set(range(len(r['current_rows'])))
        if h & b or not (h | b).issubset(domain) or any(type(i) is not int for i in h | b):
            raise ValueError('Invalid/overlapping point annotation')
        if h and label.get('identity_present') is False:
            raise ValueError('Visible human rows conflict with identity-absent annotation')
        # Denominator comes from prefilter raw rows, including invalid/filtered humans.
        t = set(r['track']['rows'])
        if not t.issubset(domain) or len(t) != len(r['track']['rows']):
            raise ValueError('Invalid target members')
        human_total += len(h)
        retained += len(t & h)
        background += len(t & b)
        selected += len(t)
        unannotated += len(t - h - b)
        reviewed_rows += len(h | b)
        all_rows += len(domain)
        reviewed_frames += 1
        valid_rows += sum(row['filter_reason'] is None for row in r['current_rows'])
        unknown += sum(row['filter_reason'] is None and (row['label'] == 'AMBIGUOUS' or
                       not row['background_compatible'] and not row['target_member']) for row in r['current_rows'])
        stamp = r['time_ns'] / 1e9
        st = states.setdefault((r['sid'],label.get('identity')), dict(first_visible=None, first_found=None,
            last_measured=None, last_id=None, switches=0, max_gap=0., prev=None,
            fake_duration=0., absence_audited=False))
        visible = bool(h)
        measured = bool(h & t) and r['track']['state'] == 'MEASURED'
        if visible and st['first_visible'] is None:
            st['first_visible'] = stamp
        if visible and any(h & set(c['rows']) for c in r['candidates']) and st['first_found'] is None:
            st['first_found'] = stamp
        if visible or label.get('identity_present') is True:
            anchor = st['last_measured'] if st['last_measured'] is not None else st['first_visible']
            if anchor is not None:
                st['max_gap'] = max(st['max_gap'], stamp - anchor)
        if measured:
            tid = r['track']['track_id']
            if st['last_id'] is not None and tid != st['last_id']:
                st['switches'] += 1
            st['last_id'],st['last_measured'] = tid,stamp
        # No visible rows may mean occlusion. Only explicit absence GT supports fake duration.
        present = label.get('identity_present')
        if present is False:
            st['absence_audited'] = True
            if st['prev'] is not None and st['prev']['present'] is False and st['prev']['fi'] + 1 == r['fi'] and st['prev']['active']:
                st['fake_duration'] += stamp - st['prev']['stamp']
        st['prev'] = dict(present=present,fi=r['fi'],stamp=stamp,active=r['track']['state'] in ('MEASURED','PREDICTED'))
    delays = [s['first_found']-s['first_visible'] for s in states.values()
              if s['first_found'] is not None and s['first_visible'] is not None]
    result.update(human_denominator=human_total, retained_human_rows=retained,
                  selected_rows=selected, known_background_rows=background,
                  point_retention=retained / human_total if human_total else None,
                  known_background_mixing=background / selected if selected else None,
                  unknown_fraction=unknown / valid_rows if valid_rows else None,
                  unannotated_selected_fraction=unannotated / selected if selected else None,
                  point_purity=retained / selected if selected and not unannotated else None,
                  annotation_coverage=reviewed_rows / all_rows if all_rows else None,
                  reviewed_frame_coverage=reviewed_frames / len(records) if records else 0.,
                  first_discovery_delay_s=max(delays) if delays else None,
                  first_discovery_delays_by_identity=[dict(sid=k[0],identity=k[1],
                    delay_s=s['first_found']-s['first_visible'] if s['first_found'] is not None and s['first_visible'] is not None else None,
                    missed=s['first_visible'] is not None and s['first_found'] is None) for k,s in states.items()],
                  maximum_measured_gap_s=max((s['max_gap'] for s in states.values()),default=None),
                  id_switches=sum(s['switches'] for s in states.values()),
                  false_track_duration_s=sum(s['fake_duration'] for s in states.values())
                    if any(s['absence_audited'] for s in states.values()) else None,
                  missed_discovery_groups=sum(s['first_visible'] is not None and s['first_found'] is None for s in states.values()),
                  label_binding_sha256=digest(labels),
                  metric_definitions=dict(unknown='Unresolved or ambiguous valid current rows / valid current rows within reviewed frames',
                    purity='Only with full selected-row point annotations; unknown scope remains unknown',
                    first_discovery_delay_s='Maximum per-session/identity first discovery delay; per-identity values and missed groups reported separately',
                    gap='Device interval since last measured support at reviewed visible or explicitly identity-present frames',
                    fake='Consecutive audited identity-absent intervals only; occlusion is not absence'),
                  reason='CONTRACT_ONLY_NO_REGISTERED_REAL_PASS_LINES; UNKNOWN_OUTSIDE_REVIEW')
    return result
