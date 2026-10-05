"""Cross-frame candidate association for one locked target (HF-05).

Pure geometry: candidates are associated in the same calibrated 3D reference
frame (falling back to the source frame only when the caller supplies its own
coordinates) using a distance gate, a constant-velocity-consistent gate and
geometric-continuity (size) checks. There is no camera projection and no image
box. Ambiguity is explicit: two near candidates, or two tracks competing for one
candidate (a merge), are reported as ``ambiguous`` and never silently resolved,
so a pose/size jump can never swap the person.
"""

import numpy as np

DEFAULT_SETTINGS = {
    "gate_m": 0.8,
    "ambiguity_margin_m": 0.2,
    "max_speed_m_s": 2.5,
    "max_size_ratio": 3.0,
}
_POSITIVE = ("gate_m", "ambiguity_margin_m", "max_speed_m_s", "max_size_ratio")


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown association setting: " + str(key))
        resolved[key] = value
    for key in _POSITIVE:
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] <= 0.0:
            raise ValueError(key + " must be a positive finite number")
    return resolved


def _position(record):
    value = record.get("position_m")
    if value is None:
        return None
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError("position_m must be three finite numbers")
    return array


def _size_ok(track, candidate, settings):
    track_size = track.get("size_m")
    candidate_size = candidate.get("size_m")
    if track_size is None or candidate_size is None:
        return True
    track_size, candidate_size = float(track_size), float(candidate_size)
    if min(track_size, candidate_size) <= 1e-6:
        return True
    ratio = max(track_size, candidate_size) / min(track_size, candidate_size)
    return ratio <= settings["max_size_ratio"]


def associate_tracks(tracks, candidates, dt_s=0.0, settings=None):
    """Greedy gated association with explicit ambiguity.

    ``tracks`` and ``candidates`` are lists of dicts carrying ``track_id`` /
    ``candidate_id`` and ``position_m`` (the track position is the *predicted*
    position when the caller has one). Only unique, unambiguous assignments are
    returned in ``matches``; competing or near-equal candidates are surfaced
    instead of being resolved silently.
    """
    resolved = resolve_settings(settings)
    gate = resolved["gate_m"] + resolved["max_speed_m_s"] * max(0.0, float(dt_s))
    candidate_positions = {}
    for candidate in candidates:
        position = _position(candidate)
        if position is None:
            continue
        candidate_positions[candidate["candidate_id"]] = position

    tentative = []
    ambiguous_tracks = set()
    ambiguous_candidates = set()
    unmatched_tracks = []
    for track in sorted(tracks, key=lambda item: str(item["track_id"])):
        track_id = track["track_id"]
        position = _position(track)
        if position is None:
            unmatched_tracks.append(track_id)
            continue
        scored = []
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            candidate_position = candidate_positions.get(candidate_id)
            if candidate_position is None or not _size_ok(track, candidate, resolved):
                continue
            distance = float(np.linalg.norm(candidate_position - position))
            if distance <= gate:
                scored.append((distance, candidate_id))
        scored.sort(key=lambda item: (item[0], str(item[1])))
        if not scored:
            unmatched_tracks.append(track_id)
            continue
        if len(scored) >= 2 and (scored[1][0] - scored[0][0]) < resolved["ambiguity_margin_m"]:
            ambiguous_tracks.add(track_id)
            ambiguous_candidates.add(scored[0][1])
            ambiguous_candidates.add(scored[1][1])
            continue
        tentative.append((track_id, scored[0][1], scored[0][0]))

    assigned = {}
    for track_id, candidate_id, distance in tentative:
        if candidate_id in assigned:
            other = assigned[candidate_id][0]
            ambiguous_tracks.add(track_id)
            ambiguous_tracks.add(other)
            ambiguous_candidates.add(candidate_id)
        else:
            assigned[candidate_id] = (track_id, distance)

    matches = []
    for candidate_id, (track_id, distance) in sorted(assigned.items(),
                                                     key=lambda item: str(item[1][0])):
        if track_id in ambiguous_tracks:
            continue
        matches.append({"track_id": track_id, "candidate_id": candidate_id,
                        "distance_m": float(distance)})
    matched_tracks = {match["track_id"] for match in matches}
    unmatched_tracks = [track_id for track_id in unmatched_tracks
                        if track_id not in matched_tracks]
    used_candidates = {match["candidate_id"] for match in matches}
    unmatched_candidates = [candidate_id for candidate_id in candidate_positions
                            if candidate_id not in used_candidates
                            and candidate_id not in ambiguous_candidates]
    return {
        "matches": matches,
        "ambiguous_track_ids": sorted(ambiguous_tracks, key=str),
        "ambiguous_candidate_ids": sorted(ambiguous_candidates),
        "unmatched_track_ids": sorted(unmatched_tracks, key=str),
        "unmatched_candidate_ids": sorted(unmatched_candidates),
        "gate_m": gate,
        "settings": resolved,
    }
