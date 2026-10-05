"""GL-I05 R1 second review: validate the offline per-frame source view.

Re-generates the author's source_review.html payload into THIS review directory
(never touching the author's output), then checks the embedded payload:
plane identity/origin labels, point lookup keys, all-box x all-frame counts
against the frozen GL-I04 diagnostic, empty handling, and the overwrite
behaviour of the generator. Writes only into this review directory.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHOR = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01"
I04 = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i04_r1" / "12_real_final"

spec = importlib.util.spec_from_file_location("gli05_src_review", AUTHOR / "source_review.py")
src = importlib.util.module_from_spec(spec)
spec.loader.exec_module(src)

results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def extract_payload(html):
    marker = "const D="
    start = html.index(marker) + len(marker)
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(html[start:])
    return payload


def main():
    out1 = HERE / "04_source_review_regen.html"
    out2 = HERE / "04_source_review_regen_twice.html"
    src.OUT = out1
    src.main()
    first_bytes = out1.read_bytes()
    # second call overwrites: verifies whether the generator refuses existing
    # output (it writes with write_text, not exclusive open).
    src.OUT = out2
    src.main()
    second_bytes = out2.read_bytes()

    authored = (AUTHOR / "source_review.html").read_bytes()
    check("regen_matches_authored_bytes", first_bytes == authored,
          {"authored_size": len(authored), "regen_size": len(first_bytes)})
    check("regen_deterministic", first_bytes == second_bytes)
    # overwrite refusal: the generator does NOT use exclusive-create mode.
    overwrote = False
    try:
        src.OUT = out2
        src.main()
        overwrote = True
    except Exception as exc:                                        # noqa: BLE001
        overwrote = False
        check("generator_exception", False, repr(exc))
    check("generator_overwrites_existing_output", overwrote is True,
          {"note": "write_text overwrites; no 'x' exclusive mode"})

    payload = extract_payload(first_bytes.decode("utf-8"))
    check("payload_kind", payload["kind"] == "gli05_source_review", payload["kind"])
    check("payload_physical_false", payload["physical_verified"] is False)
    check("payload_up_axis", len(payload["up_axis"]) == 3, payload["up_axis"])

    # plane identity / origin labels
    planes = payload["planes"]
    check("plane_labels",
          set(planes) == {"approved", "WHAT_IF_negative_X", "WHAT_IF_FIT_PCA_normal"},
          sorted(planes))
    approved = planes.get("approved", {})
    check("approved_origin_label",
          approved.get("origin") == "approved_prior_from_human_draft"
          and approved.get("physical_verified") is False, approved)
    whatif_ok = all(planes[k].get("origin") == "WHAT_IF_posthoc_not_physical"
                    and planes[k].get("physical_verified") is False
                    for k in planes if k != "approved")
    check("whatif_origin_labels", whatif_ok)

    # counts vs frozen diagnostic
    diagnostic = json.loads((I04 / "diagnostic.json").read_text(encoding="utf-8"))
    stats = {(r["box"], r["frame_group"]): r["stats"]["count"]
             for r in diagnostic["box_frame_records"]}
    counts = {tuple(k.split("\n")): v for k, v in payload["counts"].items()}
    mism = {k: (v, stats.get(k)) for k, v in counts.items() if stats.get(k) != v}
    check("counts_match_diagnostic", not mism, {"mismatch": list(mism.items())[:5]})
    check("stats_count_mismatches_zero", payload["stats_count_mismatches"] == 0,
          payload["stats_count_mismatches"])
    check("box_frame_total_356", payload["box_frame_records_total"] == 356,
          payload["box_frame_records_total"])
    check("frames_89", len(payload["frames"]) == 89, len(payload["frames"]))
    line_count = sum(1 for _ in (I04 / "source_indices.jsonl").open(encoding="utf-8"))
    check("jsonl_total_rows", payload["jsonl_total_rows"] == line_count,
          {"payload": payload["jsonl_total_rows"], "file": line_count})

    # point lookup availability: keys are "box\nframe_group"
    records = payload["records"]
    bad_keys = [k for k in records if "\n" not in k]
    check("record_keys_box_frame", not bad_keys, bad_keys[:3])
    check("record_keys_subset_of_counts", set(records) <= set(payload["counts"]))

    displayed = 0
    coord_rows = 0
    short_displayed = []
    for key, rows in records.items():
        for row in rows:
            if row[2] == 1:
                displayed += 1
                if len(row) >= 7:
                    coord_rows += 1
                else:
                    short_displayed.append([key, row])
    check("displayed_rows_have_coordinates", not short_displayed, short_displayed[:3])
    check("displayed_total_matches", displayed == payload["jsonl_displayed_total"],
          {"records": displayed, "payload": payload["jsonl_displayed_total"]})
    check("display_stride_50", payload["display_stride"] == 50)

    # empty selection is representable: some box/frame key may be absent and the
    # renderer handles count 0; verify at least the total keys <= 356 and bounds
    # carry 4 boxes.
    check("bounds_four_boxes", len(payload["bounds"]) == 4, sorted(payload["bounds"]))
    check("records_keys_at_most_356", len(records) <= 356, len(records))

    passed = sum(1 for r in results if r["ok"])
    out = {"kind": "gli05_second_review_source_view",
           "passed": passed, "total": len(results),
           "payload_summary": {
               "frames": len(payload["frames"]),
               "boxes": sorted(payload["bounds"]),
               "planes": sorted(payload["planes"]),
               "records_keys": len(records),
               "jsonl_total_rows": payload["jsonl_total_rows"],
               "displayed_total": payload["jsonl_displayed_total"]},
           "results": results}
    with (HERE / "04_source_review_validate.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"passed": passed, "total": len(results),
                      "regen_matches_authored": first_bytes == authored,
                      "overwrite_allowed": overwrote}, ensure_ascii=False))


if __name__ == "__main__":
    main()
