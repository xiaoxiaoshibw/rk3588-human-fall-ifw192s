#!/usr/bin/env python3
"""Deterministic event-level HF session evaluation using only standard library JSON."""

import argparse
import hashlib
import json
import math
import os
import sys

SCHEMA_VERSION = 1
MATCH_TOLERANCE_S = 1.0
MATCHING_METHOD = "maximum_cardinality_deterministic_augmenting_paths_v1"
SHA256_LENGTH = 64
SCRIPT_PATH = os.path.abspath(__file__)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value, field):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value))):
        raise ValueError("{} must be a finite number".format(field))
    return float(value)


def _integer(value, field):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("{} must be a non-negative integer".format(field))
    return value


def _required_text(value, field):
    if not isinstance(value, str) or not value:
        raise ValueError("{} must be a non-empty string".format(field))
    return value


def _validate_artifacts(session, dataset_kind, labels_status, prefix):
    artifacts = session.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError(prefix + ".artifacts must be an object")
    required = []
    if dataset_kind != "synthetic":
        required.extend(("prediction_source", "frozen_parameters", "prediction_data"))
        if labels_status == "human_reviewed":
            required.append("human_labels")
    for role in required:
        if role not in artifacts:
            raise ValueError(prefix + ".artifacts missing " + role)
    for role, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            raise ValueError(prefix + ".artifacts.{} must be an object".format(role))
        _required_text(artifact.get("path"), prefix + ".artifacts.{}.path".format(role))
        digest = artifact.get("sha256")
        if (not isinstance(digest, str) or len(digest) != SHA256_LENGTH
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError(prefix + ".artifacts.{}.sha256 must be lowercase SHA256".format(role))
    if labels_status == "pending" and "human_labels" in artifacts:
        raise ValueError(prefix + " pending labels cannot claim a human label artifact")
    return artifacts


def _read_prediction_events(session, input_path, prefix):
    if not isinstance(session, dict):
        return session
    reference = session.get("predicted_events_path")
    if reference is None:
        return session
    _required_text(reference, prefix + ".predicted_events_path")
    if session.get("predicted_events") is not None:
        raise ValueError(prefix + " use inline predictions or predicted_events_path, not both")
    path = reference if os.path.isabs(reference) else os.path.join(
        os.path.dirname(os.path.abspath(input_path)), reference)
    events = []
    with open(path, encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("{}:{} must contain a JSON object".format(reference, line_number))
            if event.get("session_id", session.get("session_id")) != session.get("session_id"):
                raise ValueError("{}:{} event belongs to another session".format(reference, line_number))
            event_time = event.get("time_s", event.get("start_source_s"))
            if event_time is None:
                raise ValueError("{}:{} needs time_s or start_source_s".format(reference, line_number))
            normalized = dict(event)
            normalized["time_s"] = event_time
            events.append(normalized)
    artifacts = session.get("artifacts", {})
    prediction_data = artifacts.get("prediction_data") if isinstance(artifacts, dict) else None
    if (not isinstance(prediction_data, dict)
            or prediction_data.get("sha256") != sha256_file(path)):
        raise ValueError(prefix + " prediction JSONL SHA256 does not match prediction_data artifact")
    loaded = dict(session)
    loaded["predicted_events"] = events
    return loaded


def _percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return _metric_float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _metric_float(value):
    rounded = round(float(value), 12)
    return 0.0 if rounded == 0 else rounded


def _union_duration(intervals):
    by_epoch = {}
    for interval in intervals:
        epoch, start, end = interval if len(interval) == 3 else (0, interval[0], interval[1])
        by_epoch.setdefault(epoch, []).append((start, end))
    total = 0.0
    for spans in by_epoch.values():
        spans.sort()
        if not spans:
            continue
        start, end = spans[0]
        for next_start, next_end in spans[1:]:
            if next_start <= end:
                end = max(end, next_end)
            else:
                total += end - start
                start, end = next_start, next_end
        total += end - start
    return total


def _validate_intervals(value, field, epoch_default):
    if not isinstance(value, list):
        raise ValueError("{} must be a list".format(field))
    intervals = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError("{}[{}] must be an object".format(field, index))
        start = _number(item.get("start_s"), field + "[].start_s")
        end = _number(item.get("end_s"), field + "[].end_s")
        epoch = _integer(item.get("time_epoch", epoch_default), field + "[].time_epoch")
        if end < start:
            raise ValueError("{}[{}] ends before it starts".format(field, index))
        intervals.append((epoch, start, end))
    return intervals


def _validate_session(session, index, capture_groups, event_time_domain):
    prefix = "sessions[{}]".format(index)
    if not isinstance(session, dict):
        raise ValueError(prefix + " must be an object")
    session_id = _required_text(session.get("session_id"), prefix + ".session_id")
    prediction_domain = _required_text(session.get("prediction_time_domain"),
                                       prefix + ".prediction_time_domain")
    if prediction_domain != event_time_domain:
        raise ValueError(prefix + " prediction time domain differs from dataset domain")
    split_role = _required_text(session.get("split_role"), prefix + ".split_role")
    split_group = _required_text(session.get("split_group"), prefix + ".split_group")
    dataset_kind = session.get("dataset_kind")
    if dataset_kind not in ("synthetic", "offline", "device"):
        raise ValueError(prefix + ".dataset_kind must be synthetic/offline/device")
    if dataset_kind == "synthetic" and split_role != "synthetic":
        raise ValueError(prefix + " synthetic data must use split_role=synthetic")
    if dataset_kind != "synthetic" and split_role == "synthetic":
        raise ValueError(prefix + " real/offline data cannot use split_role=synthetic")
    prior_role = capture_groups.setdefault(split_group, split_role)
    if prior_role != split_role:
        raise ValueError("split_group {!r} appears in multiple split roles".format(split_group))

    epoch_default = _integer(session.get("time_epoch"), prefix + ".time_epoch")
    labels_status = session.get("labels_status")
    if labels_status not in ("human_reviewed", "known_synthetic", "pending"):
        raise ValueError(prefix + ".labels_status is invalid")
    if dataset_kind == "synthetic" and labels_status != "known_synthetic":
        raise ValueError(prefix + " synthetic labels must be marked known_synthetic")
    if dataset_kind != "synthetic" and labels_status == "known_synthetic":
        raise ValueError(prefix + " known_synthetic labels cannot score offline/device data")
    artifacts = _validate_artifacts(session, dataset_kind, labels_status, prefix)

    labels = session.get("labeled_events")
    negatives = session.get("negative_intervals")
    observations = session.get("track_observations")
    if labels_status == "pending":
        if (labels is not None or negatives is not None or observations is not None
                or session.get("labels_time_domain") is not None):
            raise ValueError(prefix + " pending labels must remain null, not inferred empty")
    else:
        if session.get("labels_time_domain") != event_time_domain:
            raise ValueError(prefix + " prediction/label time domains must match exactly")
        if not all(isinstance(value, list) for value in (labels, negatives, observations)):
            raise ValueError(prefix + " human-reviewed labels need event, negative and track lists")

    prediction_target_bindings = {}
    raw_bindings = session.get("event_target_bindings", [])
    if not isinstance(raw_bindings, list):
        raise ValueError(prefix + ".event_target_bindings must be a list")
    for binding in raw_bindings:
        if not isinstance(binding, dict):
            raise ValueError(prefix + ".event_target_bindings entries must be objects")
        event_id = _required_text(binding.get("event_id"),
                                  prefix + ".event_target_bindings.event_id")
        target_id = _required_text(binding.get("target_id"),
                                  prefix + ".event_target_bindings.target_id")
        if event_id in prediction_target_bindings:
            raise ValueError(prefix + " duplicate event target binding: " + event_id)
        prediction_target_bindings[event_id] = target_id

    predictions = session.get("predicted_events")
    if not isinstance(predictions, list):
        raise ValueError(prefix + ".predicted_events must be a list")
    normalized_predictions = []
    prediction_ids = set()
    for row, event in enumerate(predictions):
        field = "{}.predicted_events[{}]".format(prefix, row)
        if not isinstance(event, dict):
            raise ValueError(field + " must be an object")
        event_id = _required_text(event.get("event_id"), field + ".event_id")
        if event_id in prediction_ids:
            raise ValueError(prefix + " duplicate predicted event_id: " + event_id)
        prediction_ids.add(event_id)
        track_id = _required_text(event.get("track_id"), field + ".track_id")
        epoch = _integer(event.get("time_epoch", epoch_default), field + ".time_epoch")
        normalized_predictions.append({
            "event_id": event_id,
            "track_id": track_id,
            "target_id": prediction_target_bindings.get(event_id),
            "time_epoch": epoch,
            "time_s": _number(event.get("time_s"), field + ".time_s"),
        })
    unknown_binding_ids = set(prediction_target_bindings) - prediction_ids
    if unknown_binding_ids:
        raise ValueError(prefix + " target bindings refer to missing events: "
                         + ", ".join(sorted(unknown_binding_ids)))

    normalized_labels = []
    if labels_status in ("human_reviewed", "known_synthetic"):
        label_ids = set()
        for row, event in enumerate(labels):
            field = "{}.labeled_events[{}]".format(prefix, row)
            if not isinstance(event, dict):
                raise ValueError(field + " must be an object")
            event_id = _required_text(event.get("event_id"), field + ".event_id")
            if event_id in label_ids:
                raise ValueError(prefix + " duplicate labeled event_id: " + event_id)
            label_ids.add(event_id)
            start_s = _number(event.get("start_s"), field + ".start_s")
            end_s = (_number(event["end_s"], field + ".end_s")
                     if event.get("end_s") is not None else start_s)
            if end_s < start_s:
                raise ValueError(field + " ends before it starts")
            normalized_labels.append({
                "event_id": event_id,
                "target_id": _required_text(event.get("target_id"), field + ".target_id"),
                "time_epoch": _integer(event.get("time_epoch", epoch_default), field + ".time_epoch"),
                "time_s": start_s,
                "end_s": end_s,
            })
        observed_subject_times = set()
        for row, item in enumerate(observations):
            field = "{}.track_observations[{}]".format(prefix, row)
            if not isinstance(item, dict):
                raise ValueError(field + " must be an object")
            target_id = _required_text(item.get("target_id"), field + ".target_id")
            _required_text(item.get("track_id"), field + ".track_id")
            epoch = _integer(item.get("time_epoch", epoch_default), field + ".time_epoch")
            time_s = _number(item.get("time_s"), field + ".time_s")
            key = (epoch, target_id, time_s)
            if key in observed_subject_times:
                raise ValueError(prefix + " duplicate target observation timestamp")
            observed_subject_times.add(key)
        negative_spans = _validate_intervals(negatives, prefix + ".negative_intervals",
                                             epoch_default)
        for label in normalized_labels:
            label_end = label["end_s"]
            if any(epoch == label["time_epoch"] and start <= label_end
                   and end >= label["time_s"] for epoch, start, end in negative_spans):
                raise ValueError(prefix + " positive event overlaps a labeled negative interval")
    else:
        negative_spans = None

    valid_observation = session.get("observation_intervals")
    if valid_observation is None:
        observation_spans = None
    else:
        if not isinstance(valid_observation, list):
            raise ValueError(prefix + ".observation_intervals must be a list or null")
        observation_spans = {"all": [], "valid": []}
        observation_rows = []
        for row, item in enumerate(valid_observation):
            field = "{}.observation_intervals[{}]".format(prefix, row)
            if not isinstance(item, dict):
                raise ValueError(field + " must be an object")
            start = _number(item.get("start_s"), field + ".start_s")
            end = _number(item.get("end_s"), field + ".end_s")
            epoch = _integer(item.get("time_epoch", epoch_default), field + ".time_epoch")
            if end < start:
                raise ValueError(field + " ends before it starts")
            if item.get("observability") not in ("valid", "degraded", "invalid"):
                raise ValueError(field + ".observability is invalid")
            observation_rows.append((epoch, start, end, item["observability"]))
            observation_spans["all"].append((epoch, start, end))
            if item["observability"] == "valid":
                observation_spans["valid"].append((epoch, start, end))
        for index, first in enumerate(observation_rows):
            for second in observation_rows[index + 1:]:
                if (first[0] == second[0] and first[3] != second[3]
                        and max(first[1], second[1]) < min(first[2], second[2])):
                    raise ValueError(prefix + " observation intervals overlap with conflicting quality")

    return {
        "session_id": session_id,
        "split_role": split_role,
        "split_group": split_group,
        "dataset_kind": dataset_kind,
        "artifacts": artifacts,
        "labels_status": labels_status,
        "predictions": normalized_predictions,
        "labels": normalized_labels if labels_status != "pending" else None,
        "negative_spans": negative_spans,
        "track_observations": observations if labels_status != "pending" else None,
        "epoch_default": epoch_default,
        "observation_spans": observation_spans,
    }


def _match_events(labels, predictions, tolerance):
    edges = {}
    for label_index, label in enumerate(labels):
        choices = []
        for prediction_index, prediction in enumerate(predictions):
            if (label["time_epoch"] != prediction["time_epoch"]
                    or label["target_id"] != prediction["target_id"]
                    or prediction["target_id"] is None):
                continue
            delta = prediction["time_s"] - label["time_s"]
            if abs(delta) <= tolerance:
                choices.append((abs(delta), prediction["time_s"], prediction["event_id"],
                                prediction_index))
        edges[label_index] = [choice[-1] for choice in sorted(choices)]

    # Deterministic augmenting paths preserve maximum cardinality in conflict cases.
    prediction_to_label = {}

    def assign(label_index, visited):
        for prediction_index in edges[label_index]:
            if prediction_index in visited:
                continue
            visited.add(prediction_index)
            prior = prediction_to_label.get(prediction_index)
            if prior is None or assign(prior, visited):
                prediction_to_label[prediction_index] = label_index
                return True
        return False

    for label_index in sorted(range(len(labels)),
                              key=lambda i: (labels[i]["time_s"], labels[i]["event_id"], i)):
        assign(label_index, set())

    matches = []
    for prediction_index, label_index in sorted(prediction_to_label.items(),
                                                key=lambda pair: pair[1]):
        label = labels[label_index]
        prediction = predictions[prediction_index]
        matches.append({"label_event_id": label["event_id"],
                        "prediction_event_id": prediction["event_id"],
                        "target_id": label["target_id"],
                        "time_epoch": label["time_epoch"],
                        "latency_s": _metric_float(prediction["time_s"] - label["time_s"])})
    matched_labels = {item["label_event_id"] for item in matches}
    matched_predictions = {item["prediction_event_id"] for item in matches}
    unmatched_labels = [event for event in labels if event["event_id"] not in matched_labels]
    unmatched_predictions = [event for event in predictions
                             if event["event_id"] not in matched_predictions]
    return matches, unmatched_labels, unmatched_predictions


def _evaluate_session(session, tolerance):
    predictions = session["predictions"]
    if session["labels_status"] == "pending":
        return {
            "session_id": session["session_id"], "dataset_kind": session["dataset_kind"],
            "split_role": session["split_role"], "split_group": session["split_group"],
            "artifacts": session["artifacts"],
            "status": "pending_annotation",
            "prediction_count": len(predictions),
            "tp": None, "fp": None, "fn": None, "precision": None, "recall": None,
            "negative_fp_count": None, "negative_duration_s": None,
            "false_alarms_per_hour": None, "matches": None,
            "unmatched_predictions": None, "unmatched_labels": None,
            "latency_s": None, "track_switches": None,
            "effective_observation_s": None, "observation_window_s": None,
            "effective_observation_fraction": None,
        }

    labels = session["labels"]
    matches, unmatched_labels, unmatched_predictions = _match_events(
        labels, predictions, tolerance)
    tp = len(matches)
    fp = len(unmatched_predictions)
    fn = len(unmatched_labels)
    negative_spans = session["negative_spans"]
    negative_duration = _union_duration(negative_spans)
    negative_fp = sum(1 for event in unmatched_predictions
                      if any(epoch == event["time_epoch"] and start <= event["time_s"] <= end
                             for epoch, start, end in negative_spans))
    precision_denominator = tp + fp
    recall_denominator = tp + fn
    latency = sorted(item["latency_s"] for item in matches)

    switches = 0
    last_track = {}
    for item in sorted(session["track_observations"],
                       key=lambda row: (row.get("time_epoch", session["epoch_default"]),
                                        row["target_id"], row["time_s"], row["track_id"])):
        key = (item.get("time_epoch", session["epoch_default"]), item["target_id"])
        track_id = item["track_id"]
        if key in last_track and last_track[key] != track_id:
            switches += 1
        last_track[key] = track_id

    observation_spans = session["observation_spans"]
    if observation_spans is None:
        effective_s = window_s = fraction = None
    else:
        effective_s = _union_duration(observation_spans["valid"])
        window_s = _union_duration(observation_spans["all"])
        fraction = effective_s / window_s if window_s > 0 else None

    return {
        "session_id": session["session_id"], "dataset_kind": session["dataset_kind"],
        "split_role": session["split_role"], "split_group": session["split_group"],
        "artifacts": session["artifacts"],
        "status": "metrics_available" if labels or negative_duration > 0 else "no_data",
        "prediction_count": len(predictions),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": _metric_float(tp / precision_denominator) if precision_denominator else None,
        "recall": _metric_float(tp / recall_denominator) if recall_denominator else None,
        "negative_fp_count": negative_fp,
        "negative_duration_s": _metric_float(negative_duration),
        "false_alarms_per_hour": (_metric_float(negative_fp * 3600.0 / negative_duration)
                                   if negative_duration > 0 else None),
        "matches": matches,
        "unmatched_predictions": [event["event_id"] for event in unmatched_predictions],
        "unmatched_labels": [event["event_id"] for event in unmatched_labels],
        "latency_s": {"count": len(latency), "p50": _percentile(latency, 0.50),
                      "p95": _percentile(latency, 0.95), "values": latency},
        "track_switches": switches,
        "effective_observation_s": _metric_float(effective_s) if effective_s is not None else None,
        "observation_window_s": _metric_float(window_s) if window_s is not None else None,
        "effective_observation_fraction": (_metric_float(fraction)
                                            if fraction is not None else None),
    }


def _aggregate_sessions(results):
    groups = {}
    for row in results:
        key = (row["dataset_kind"], row["split_role"])
        groups.setdefault(key, []).append(row)
    aggregates = []
    for (dataset_kind, split_role), rows in sorted(groups.items()):
        pending = [row for row in rows if row["status"] == "pending_annotation"]
        labeled = [row for row in rows if row["status"] != "pending_annotation"]
        if pending:
            metrics = {"tp": None, "fp": None, "fn": None, "precision": None, "recall": None,
                       "negative_fp_count": None, "negative_duration_s": None,
                       "false_alarms_per_hour": None, "latency_s": None,
                       "track_switches": None, "effective_observation_s": None,
                       "observation_window_s": None, "effective_observation_fraction": None}
            status = "pending_annotation"
        else:
            tp = sum(row["tp"] for row in labeled)
            fp = sum(row["fp"] for row in labeled)
            fn = sum(row["fn"] for row in labeled)
            negative_fp = sum(row["negative_fp_count"] for row in labeled)
            negative_duration = sum(row["negative_duration_s"] for row in labeled)
            latencies = sorted(value for row in labeled
                               for value in row["latency_s"]["values"])
            switches = sum(row["track_switches"] for row in labeled)
            observation_complete = all(row["effective_observation_s"] is not None
                                       and row["observation_window_s"] is not None
                                       for row in labeled)
            effective = (sum(row["effective_observation_s"] for row in labeled)
                         if observation_complete else None)
            window = (sum(row["observation_window_s"] for row in labeled)
                      if observation_complete else None)
            metrics = {
                "tp": tp, "fp": fp, "fn": fn,
                "precision": _metric_float(tp / (tp + fp)) if tp + fp else None,
                "recall": _metric_float(tp / (tp + fn)) if tp + fn else None,
                "negative_fp_count": negative_fp,
                "negative_duration_s": _metric_float(negative_duration),
                "false_alarms_per_hour": (_metric_float(negative_fp * 3600.0 / negative_duration)
                                           if negative_duration > 0 else None),
                "latency_s": {"count": len(latencies), "p50": _percentile(latencies, 0.50),
                              "p95": _percentile(latencies, 0.95), "values": latencies},
                "track_switches": switches,
                "effective_observation_s": effective,
                "observation_window_s": window,
                "effective_observation_fraction": (_metric_float(effective / window)
                                                    if window else None),
            }
            status = ("metrics_available" if any(row["status"] == "metrics_available"
                                                   for row in labeled) else "no_data")
        aggregates.append({"dataset_kind": dataset_kind, "split_role": split_role,
                           "status": status, "session_count": len(rows),
                           "ground_truth_available_session_count": len(labeled),
                           "pending_session_count": len(pending), **metrics})
    return aggregates


def evaluate_document(document, input_path):
    if (not isinstance(document, dict)
            or type(document.get("schema_version")) is not int
            or document["schema_version"] != SCHEMA_VERSION):
        raise ValueError("input schema_version must be 1")
    _required_text(document.get("dataset_version"), "dataset_version")
    _required_text(document.get("event_time_domain"), "event_time_domain")
    tolerance = document.get("match_tolerance_s")
    if _number(tolerance, "match_tolerance_s") != MATCH_TOLERANCE_S:
        raise ValueError("match_tolerance_s is fixed at {} s".format(MATCH_TOLERANCE_S))
    sessions = document.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("sessions must be a list")
    capture_groups = {}
    normalized = [_validate_session(_read_prediction_events(session, input_path,
                                                              "sessions[{}]".format(index)),
                                    index, capture_groups, document["event_time_domain"])
                  for index, session in enumerate(sessions)]
    ids = [session["session_id"] for session in normalized]
    if len(set(ids)) != len(ids):
        raise ValueError("session_id values must be unique")
    results = [_evaluate_session(session, tolerance) for session in normalized]
    if not normalized:
        status = "no_data"
    elif any(row["status"] == "pending_annotation" for row in results):
        status = "pending_annotation"
    elif not any(row["status"] == "metrics_available" for row in results):
        status = "no_data"
    else:
        status = "evaluated"
    return {
        "kind": "hf_session_evaluation", "schema_version": SCHEMA_VERSION,
        "status": status,
        "dataset_version": document["dataset_version"],
        "event_time_domain": document["event_time_domain"],
        "parameters": {"match_tolerance_s": tolerance, "matching_method": MATCHING_METHOD,
                       "match_binding": "session_id + time_epoch + reviewed target_id",
                       "delay_definition": "prediction time minus human-labeled onset, same declared event time domain; not host/browser end-to-end latency",
                       "false_alarm_denominator": "union of human-reviewed negative intervals"},
        "provenance": {"input_path": os.path.abspath(input_path),
                       "input_sha256": sha256_file(input_path),
                       "evaluator_path": SCRIPT_PATH,
                       "evaluator_sha256": sha256_file(SCRIPT_PATH),
                       "split_roles": sorted(set(row["split_role"] for row in normalized))},
        "aggregates": _aggregate_sessions(results),
        "sessions": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="versioned evaluation dataset JSON")
    parser.add_argument("--output", required=True, help="write deterministic report JSON")
    args = parser.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as source:
            document = json.load(source)
        report = evaluate_document(document, args.input)
        text = json.dumps(report, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, indent=2) + "\n"
        with open(args.output, "w", encoding="utf-8", newline="\n") as target:
            target.write(text)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("evaluation failed: {}".format(exc), file=sys.stderr)
        return 2
    print("wrote {} ({})".format(os.path.abspath(args.output), report["status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
