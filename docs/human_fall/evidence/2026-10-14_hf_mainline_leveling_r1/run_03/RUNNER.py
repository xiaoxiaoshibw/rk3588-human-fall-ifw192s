"""M3-prime: frozen shared-patch experiment, using existing offline algorithms."""
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pc_apps/human_replay"))
import leveling
from leveling_quality import compare, rotation

SESSIONS = ("cap_20261013_094333", "cap_20261013_131958")
OLD_FOLDERS = ("2026-10-13_hf_real_01_r1", "2026-10-13_hf_real_02_r1")
BASE = "docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1"
CODE = ("human_pipe_lib.js", "human_replay_lib.js", "registration.js", "registration_method.js")

# node argv avoids shell quoting; production module is read-only, all writes stay in sandbox.
NODE_RUN = r"""
const fs=require('fs'),path=require('path'),REG=require(process.argv[1]);
const [root,sj,rj,out]=process.argv.slice(2);
const result=REG.writeJob({root,source:'cap_20261013_094333',reference:'cap_20261013_131958',
    sourceJob:sj,referenceJob:rj,outdir:out});
const a=REG.load(out,{root});
const summary={...result,loader_state:a.state,loader_reasons:a.reasons,
    full_gate:a.diagnostics.gate, residual:a.diagnostics.residual,
    support:a.diagnostics.support, sanity:a.diagnostics.sanity,
    rotation:a.registration.euler_deg_zyx,translation:a.registration.translation_m,
    fusion_default_closed:REG.fusionKeys(false,a,{root})===null,
    fusion_explicit_enabled:REG.fusionKeys(true,a,{root})!==null};
fs.writeFileSync(path.join(out,'EXPERIMENT_SUMMARY.json'),JSON.stringify(summary,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({loader_state:a.state,quality:result.quality}));
"""


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    leveling.dump(Path(path), value)


def original_reports():
    return [read(ROOT / "docs/human_fall/evidence" / folder / (sid + "_leveling.json"))
            for sid, folder in zip(SESSIONS, OLD_FOLDERS)]


def plan(reports):
    configs = []
    for report in reports:
        old = report["config"]
        configs.append({"pitch_deg": old["pitch_deg"], "roll_deg": old["roll_deg"],
                        "physical_height_m": old["physical_height_m"], "regions": old["regions"],
                        "mode": "frozen_shared_patch_experiment", "ground_confirmed": False,
                        "ground_identification": "algorithm_candidate_unreviewed",
                        "basis": "M3-prime frozen historical XY candidate; not reviewed physical floor"})
    if any(c[k] != configs[0][k] for c in configs for k in ("pitch_deg", "roll_deg", "physical_height_m")):
        raise ValueError("Historical nominal coordinate configurations differ")
    return {"original_patches": copy.deepcopy(configs),
            "shared_source_patches": [copy.deepcopy(configs[0]), copy.deepcopy(configs[0])],
            "shared_reference_patches": [copy.deepcopy(configs[1]), copy.deepcopy(configs[1])]}


def protected_paths():
    # Capture concurrent edits as changes; never rewrite another writer's results.
    replay = ROOT / "pc_apps/human_replay"
    files = [p for p in replay.iterdir() if p.is_file() and p.suffix in (".py", ".js")]
    files += list((replay / "leveling_estimators").glob("*.py"))
    files += [ROOT / "AGENTS.md", Path(__file__)]
    for sid, folder in zip(SESSIONS, OLD_FOLDERS):
        files += [ROOT / "captures/remote" / sid / n for n in ("meta.json", "points.bin")]
        files.append(ROOT / "docs/human_fall/evidence" / folder / (sid + "_leveling.json"))
    files += list((ROOT / BASE / "registration_094333_131958_v1").glob("*.json"))
    old = read(ROOT / BASE / "REGISTRATION_REBUILD_RUN.json")
    for job in old["jobs"].values():
        directory = ROOT / "captures/leveled" / job["job_id"]
        files += list(directory.rglob("*"))
    return sorted({p for p in files if p.is_file()})


def snapshot(paths):
    return {str(p.relative_to(ROOT)).replace("\\", "/"): leveling.sha(p) for p in paths}


def preflight(configs):
    rows = {}
    for sid, config in zip(SESSIONS, configs):
        directory, meta, _ = leveling.source(ROOT / "captures/remote", sid)
        try:
            xyz, ids, codes, ordinals, held, invalid, anchor = leveling.freeze_domain(directory, meta, config)
            result = compare(xyz, codes, held, anchor)
            tls = result["estimators"]["tls"]
            rows[sid] = {"recommended": result["recommended"], "consensus": result["consensus"],
                         "fit_points": len(ids), "fit_frames": len(set(ordinals.tolist())),
                         "holdout_ordinals": [h["ordinal"] for h in held],
                         "fit_holdout_disjoint": all(not np.intersect1d(ids, h["rows"]).size for h in held),
                         "roll_deg": tls["roll_deg"], "pitch_deg": tls["pitch_deg"],
                         "offset_source_m": tls["offset_source_m"], "comparison": result}
        except (ValueError, np.linalg.LinAlgError) as exc:
            rows[sid] = {"recommended": None, "error": str(exc)}
    return rows


def common_clean_plan(reports, out):
    """Reuse existing full-height cell gates; only FIT frames select new shared ROI."""
    from floor_detector import PROFILE as FLOOR_PROFILE
    from floor_sheet import SHEET_PROFILE, _clean_cells, _roi_metrics
    clean, evidence = [], {}
    for sid, report in zip(SESSIONS, reports):
        directory, meta, binding = leveling.source(ROOT / "captures/remote", sid)
        raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
        xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
        n = len(meta["frames"])
        held = {(n - 1) // 3, 2 * (n - 1) // 3, n - 1}
        chunks, frame_ids = [], []
        for ordinal, frame in enumerate(meta["frames"]):
            if ordinal in held:
                continue
            points = xyz[frame["offset_points"]:frame["offset_points"] + frame["count_points"]].astype("f8")
            valid = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1) & (np.abs(points) <= 100).all(axis=1)
            chunks.append(points[valid])
            frame_ids.append(np.full(int(valid.sum()), ordinal, dtype="i4"))
        fit, ids = np.concatenate(chunks), np.concatenate(frame_ids)
        del chunks, frame_ids
        tls = report["estimators"]["tls"]
        plane = {"normal": tls["normal_source"], "offset_m": tls["offset_source_m"]}
        config = report["config"]
        cells = _clean_cells(fit, ids, rotation(config["pitch_deg"], config["roll_deg"]), plane)
        clean.append(cells)
        evidence[sid] = {"source": binding, "fit_frames": sorted(set(ids.tolist())),
                         "excluded_holdout_ordinals": sorted(held), "prior_plane": plane, "clean_cells": cells}
        del fit, ids, raw, xyz
    intersection = set(tuple(c["key"]) for c in clean[0]) & set(tuple(c["key"]) for c in clean[1])
    shared = [{"key": list(key)} for key in sorted(intersection)]
    roi = _roi_metrics(shared)
    evidence.update(floor_profile=FLOOR_PROFILE, roi_profile=SHEET_PROFILE,
                    shared_keys=sorted(intersection), roi=roi,
                    policy="existing clean-cell and separation gates; full-height FIT-only; no registration ranking")
    dump(out / "FIT_DISCOVERY.json", evidence)
    if not roi["ok"]:
        return {}
    cell = FLOOR_PROFILE["cell_m"]
    regions = [[x * cell, (x + 1) * cell, y * cell, (y + 1) * cell] for x, y in roi["selected"]]
    config = copy.deepcopy(plan(reports)["original_patches"][0])
    config.update(regions=regions, mode="fit_only_common_clean_cells",
                  basis="Shared nominal XY from intersection of FIT-only full-height clean cells; physical identity UNKNOWN")
    return {"shared_clean_fit_only": [copy.deepcopy(config), copy.deepcopy(config)]}


def check_export(raw_path, derived_path, transform, chunk_rows=65536):
    """Full-record check; all opaque bytes and invalid XYZ must survive unchanged."""
    if raw_path.stat().st_size != derived_path.stat().st_size:
        raise ValueError("Derived source row count changed")
    R, t = np.asarray(transform["R"]), np.asarray(transform["t"])
    maximum, total, invalid = 0.0, 0, 0
    with raw_path.open("rb") as a, derived_path.open("rb") as b:
        while True:
            raw, derived = a.read(28 * chunk_rows), b.read(28 * chunk_rows)
            if not raw:
                if derived:
                    raise ValueError("Derived file has extra rows")
                break
            if len(raw) % 28 or len(raw) != len(derived):
                raise ValueError("Truncated record")
            n = len(raw) // 28
            rb, db = np.frombuffer(raw, dtype="u1").reshape(n, 28), np.frombuffer(derived, dtype="u1").reshape(n, 28)
            if not np.array_equal(rb[:, 12:], db[:, 12:]):
                raise ValueError("Non-XYZ bytes changed")
            xyz = np.ndarray((n, 3), dtype="<f4", buffer=raw, strides=(28, 4))
            out = np.ndarray((n, 3), dtype="<f4", buffer=derived, strides=(28, 4))
            good = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
            if not np.array_equal(rb[~good], db[~good]):
                raise ValueError("Invalid XYZ record changed")
            expected = xyz[good].astype("f8") @ R.T + t
            if not np.array_equal(expected.astype("<f4"), out[good]):
                raise ValueError("Derived XYZ does not match transform")
            if good.any():
                maximum = max(maximum, float(np.max(np.abs(expected - out[good]))))
            total += n
            invalid += int((~good).sum())
    return {"status": "PASS", "rows": total, "invalid_preserved": invalid,
            "opaque_bytes_preserved": True, "float32_max_abs_error_m": maximum}


def run(out, shared_clean=False):
    out.mkdir()  # Exclusive run path. Old/failed results remain intact.
    shutil.copyfile(Path(__file__), out / "RUNNER.py")
    start = time.monotonic()
    protected = protected_paths()
    before = snapshot(protected)
    versions = {"python": sys.version, "numpy": np.__version__,
                "node": subprocess.check_output(["node", "--version"], text=True).strip(),
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
                "argv": sys.argv, "cwd": str(Path.cwd()), "environment": "WINDOWS_LOCAL_OFFLINE",
                "skills": ["C:/Users/30680/.codex/skills/ponytail/SKILL.md",
                           "C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md"]}
    dump(out / "BASELINE.json", {"versions": versions, "sha256": before})
    (out / "GIT_STATUS_BEFORE.txt").write_text(subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True, encoding="utf-8"), encoding="utf-8")
    reports = original_reports()
    configs = common_clean_plan(reports, out) if shared_clean else plan(reports)
    dump(out / "FROZEN_CONFIG.json", {"arms": configs, "id": leveling.identity(configs),
                                     "selection": "historical templates fixed before new registration",
                                     "physical_patch_equivalence": "UNKNOWN"})
    results, jobs = {}, {}
    try:
        # Keep derivatives out of captures/leveled, so latest-selection cannot change.
        sandbox = out / "workspace"
        for sid in SESSIONS:
            target = sandbox / "captures/remote" / sid
            target.mkdir(parents=True)
            for name in ("meta.json", "points.bin"):
                shutil.copyfile(ROOT / "captures/remote" / sid / name, target / name)
        target_code = sandbox / "pc_apps/human_replay"
        target_code.mkdir(parents=True)
        for name in CODE:
            shutil.copyfile(ROOT / "pc_apps/human_replay" / name, target_code / name)
        for arm, config_pair in configs.items():
            armout = out / arm
            armout.mkdir()
            print("PREFLIGHT", arm, flush=True)
            pre = preflight(config_pair)
            dump(armout / "PREFLIGHT.json", pre)
            results[arm] = {"preflight": {sid: {k: v for k, v in row.items() if k != "comparison"}
                                               for sid, row in pre.items()}}
            if not all(row.get("recommended") == "tls" for row in pre.values()):
                results[arm]["status"] = "BLOCKED_LEVELING_QUALITY"
                print("BLOCKED", arm, results[arm]["status"], flush=True)
                continue
            pair_jobs = {}
            for sid, config in zip(SESSIONS, config_pair):
                source = leveling.source(sandbox / "captures/remote", sid)[2]
                if source != leveling.source(ROOT / "captures/remote", sid)[2]:
                    raise ValueError("Sandbox source copy differs")
                job = uuid.uuid4().hex
                # Record UUID before computation, including incomplete failures.
                dump(armout / (sid + "_REQUEST.json"), {"job_id": job, "source": source, "config": config})
                report, _ = leveling.run_job(sandbox / "captures/remote", sandbox / "captures/leveled",
                    {"sid": sid, "source": source, "config": config}, job,
                    lambda msg: print(arm, sid, msg, flush=True))
                if report["recommended"] != "tls":
                    raise ValueError("Preflight/actual leveling disagree")
                jobdir = sandbox / "captures/leveled" / job
                check = check_export(sandbox / "captures/remote" / sid / "points.bin",
                                     jobdir / "tls/points.bin", read(jobdir / "tls/transform.json"))
                domain = np.load(jobdir / "domain.npz", allow_pickle=False)
                with domain:
                    if np.intersect1d(domain["source_rows"], domain["holdout_rows"]).size:
                        raise ValueError("FIT/holdout row overlap")
                pair_jobs[sid] = {"job_id": job, "export_check": check,
                                  "transform": str(jobdir / "tls/transform.json")}
            jobs[arm] = pair_jobs
            cmd = ["node", "-e", NODE_RUN, str(ROOT / "pc_apps/human_replay/registration.js"),
                   str(sandbox), pair_jobs[SESSIONS[0]]["job_id"], pair_jobs[SESSIONS[1]]["job_id"],
                   str(armout / "registration")]
            print("REGISTRATION", arm, flush=True)
            completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            (armout / "REGISTRATION.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
            dump(armout / "COMMAND.json", {"argv": cmd, "exit_code": completed.returncode})
            results[arm]["jobs"] = pair_jobs
            if completed.returncode:
                results[arm]["status"] = "REGISTRATION_ERROR"
                print("ERROR", arm, completed.stderr[-1500:], flush=True)
                continue
            results[arm]["registration"] = read(armout / "registration/EXPERIMENT_SUMMARY.json")
            results[arm]["status"] = results[arm]["registration"]["loader_state"]
            print("RESULT", arm, results[arm]["status"],
                  results[arm]["registration"]["residual"]["fit"], flush=True)
    finally:
        after = snapshot(protected)
        changed = [p for p in before if before[p] != after[p]]
        dump(out / "IMMUTABILITY.json", {"status": "PASS" if not changed else "FAIL",
                                        "changed": changed, "sha256_after": after})
        dump(out / "RESULTS.json", {"arms": results, "jobs": jobs, "protected_changed": changed,
                                   "elapsed_s": time.monotonic() - start,
                                   "physical_truth": "UNKNOWN", "production_promotion": "BLOCKED"})
    if changed:
        raise ValueError("Protected dependencies changed: " + str(changed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new exclusive directory")
    parser.add_argument("--shared-clean", action="store_true", help="FIT-only common clean-cell follow-up")
    args = parser.parse_args()
    run(args.out.resolve(), shared_clean=args.shared_clean)
