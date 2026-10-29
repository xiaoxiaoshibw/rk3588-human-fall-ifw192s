# HFUS-TCMS-02-REALDEV-01 r01

PC offline RESEARCH algorithm; ENGINEERING source/streaming/replay. No data writes,
model/GT, board, production integration or independent effectiveness result.

`run.py --manifest <explicit manifest> --out <new item directory>` processes all
780 frames with scalable_reference/main and B2/B3. `--probe` is first10 frames;
`--frozen-probe` processes the registered307 frames including all193 build frames.
All output paths are exclusive and restricted to this item's new evidence root.
`server.py --run <completed run> --cases <case file> --port 0 --process-record <new file>`
starts a new localhost GET-only service without stopping any existing process.
Startup checks the full source SHA. Every requested frame additionally checks its
original28B byte SHA (opaque bytes included) and meta SHA, even when size/mtime are
preserved. Unrequested frames are not rehashed on each query.

The source adapter reuses PREDEV strict 28B/meta/SHA checks. XYZ alone is decoded;
tail16 bytes stay opaque. All raw rows have compact label/flag/surface/candidate
records, including invalid and zero rows. Global row/byte offset are losslessly
derived from the source meta. Current ledgers and map supports never substitute.
Map: 5cm occupied voxels, observed centroid/AABB/axis noise/counts/time support;
all original mapping rows are indexed by frame and reverse CSR. Matching uses a
frozen eligible centroid KDTree and finite observed AABB+8cm envelope. This changes
the old plane-neighborhood semantics. Voxel component connectivity also changes
old raw-radius components. Neither full run is claimed numerically equivalent to
original PREDEV. `scalable_reference` retains its synthetic numeric thresholds;
`main` removes the 0.8m RAW-axis transverse extent restriction because orientation
is unverified. Both retain all current rows and the 2.4m extent gate.

Before20s: MAP_BUILDING, no completed map. At20s: freeze from build only.20–28s
validation never calibrates thresholds and never changes earlier records.
Unknown layout keeps qualified_M0/static boundary false; static rescue and
growth disabled. Once explicit user layout evidence and unchanged registered M0
numeric criteria pass, only frames AFTER validation may use the finite M0 boundary.
Ground qualification remains separate. Candidate matching alone is diagnostic; there is no physical
ground or height inference, strong free/occlusion, automatic human or fall label.
All unconfirmed candidates are UNKNOWN/mixed. Disabled ablations are BLOCKED,
not evidence of no benefit. no_frozen runs only registered development windows.

DIAGNOSTIC requires null pass_lines/matching_rules, declared-zero annotation
coverage and explicit development split. LABELLED rejects missing/fake protocol;
actual labelled scoring remains blocked pending a registered audited schema and
real numeric protocol. No no-label effectiveness numbers are emitted.

UI selection opens the exact candidate version and pending confirmation template.
Only an actual user response based on that URL/version can be saved as
HUMAN_CONFIRMATION. `continue_confirmed.py --run <frozen package> --request
<actual user request> --out <new continuation output>` replays the same frozen run
with added user evidence. The request includes the template plus actual user
review evidence and candidate_url; changed code/source/config/run invalidates it.
It supports current measured association and device TTL to zero-member prediction
then LOST. It cannot validate human identity without the user or supply point GT.
2026-10-17 user explicitly delegated visual judgment to the AI. With the separate
`--allow-ai-visual-review` flag, a bound AI_VISUAL_REVIEW request may condition a
diagnostic track. This requires recorded user delegation and visual evidence,
sets human_confirmation=false, and never satisfies HUMAN_CONFIRMATION/GT criteria.

Tests: `python -B -W error -m unittest discover -s
sidequests/hfus_tcms_02/realdev/r01/tests -p "test_*.py"`; `node --check
sidequests/hfus_tcms_02/realdev/r01/app.js`; `node
sidequests/hfus_tcms_02/realdev/r01/tests/replay.test.js` (set REALDEV_URL for live
source/map/frame assertions). The25 old assertions are imported read-only with
only fixture IO/import bindings adapted; they validate the old numerical reference,
not equivalence of the research representation. Failures stay in new evidence.
