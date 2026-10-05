"""GL-E01 R1 independent Python 3.8 AST and read-only boundary scan.

Parses every author/review script under the run with Python 3.8 grammar and
scans for live-ROS / board-write patterns. Read-only; no execution.
"""
import ast
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
AUTHOR = ["02_board_file_probe.py", "03_read_bag_chain.py", "04_local_chain_audit.py",
          "05_recording_context_probe.py", "06_chain_negative_checks.py",
          "08_submit.py", "run_cli.py", "export_session.py", "snapshot.py"]
MINE = ["01_remote_raw_probe.py", "02_local_chain_verify.py", "02b_local_chain_verify.py",
        "03_remote_timestamp_loss.py", "04_fixture_checks.py",
        "05_remote_context_probe.py", "06_manifest_scope_check.py"]
FORBIDDEN = ["import rospy", "rospy.", "Publisher(", "Subscriber(", "Popen(",
             "os.system", "shutil.", "os.remove", "os.unlink", "unlink(",
             "open(..., 'w')", "sudo", "deploy", "apt-get", "pip install"]


def scan(path):
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path), feature_version=(3, 8))
    hits = [tok for tok in FORBIDDEN if tok in text]
    return dict(file=str(path.relative_to(RUN)), parsed_38=True, forbidden_hits=hits)


def main():
    records = []
    for name in AUTHOR:
        p = RUN / name
        if p.is_file():
            records.append(scan(p))
    for name in MINE:
        p = OUT / name
        if p.is_file():
            records.append(scan(p))
    result = dict(kind="gle01_r1_independent_ast_boundaries", schema=1,
                  scripts=records,
                  all_parse_py38=all(r["parsed_38"] for r in records),
                  any_forbidden=any(r["forbidden_hits"] for r in records),
                  note="remote scripts additionally executed on board python3.8 "
                       "via docker exec stdin with exit 0")
    (OUT / "07_ast_and_boundaries.json").write_text(json.dumps(result, indent=2),
                                                    encoding="utf-8")
    print(json.dumps(dict(scripts=len(records),
                          all_py38=result["all_parse_py38"],
                          forbidden=[r for r in records if r["forbidden_hits"]])))


if __name__ == "__main__":
    main()
