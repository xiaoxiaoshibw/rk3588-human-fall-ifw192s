# GL-I04 R1 implementation design / Codex sole writer

Read WORKFLOW v2, task, acceptance v1, main prompt, RETURN_TEMPLATE, GL-I03 closeout/plan/evidence and actual loader -> selector -> constrained fitter -> wrapper/config/tests. Read ponytail at C:/Users/30680/.codex/skills/ponytail/SKILL.md. Start manifest: 03_start_baseline.json (2383 tracked/untracked records, master/cbd0be1). Existing planning evidence is preserved. No other GL-I04 writer dispatched.

L01/Q01/Q02: CLI load_adapted reconstructs canonical manifest from actual source bytes; verify draft schema/kind/source identity/review, then group-first selectors, then settings. Compute before exclusive mkdir; no calibration builder. No cache. Capture/config/draft/code hashes captured before and after computation. Existing outputs always refuse.

L02/Q04: conditional active source->world Ry: world-up expressed in source is R.T@[0,0,1]; R@[0,0,1] is rotated source Z in world. 90 degree fixture gives opposite X. Neither establishes actual extrinsic. Approved/negative-X/PCA are separate experiments.

L03/L04/Q03/Q09: gate original disjoint selectors first. Require four spatial boxes, then apply each unchanged box to each canonical source group, including empty frames. No pooled fit: reference diagnostic PCA and frozen fits use only approved FIT frame. Stats include every selected finite point (zero points separately counted); nonfinite count explicitly excluded with reason, no residual selection. Fixed source XYZ bins (0.25m), deterministic stride display only. Sidecar maps pooled row/ordinal/seq/local row, residual and display flag.

L05/Q05: frozen actual result stored intact. New replay generator repeats frozen balanced sample/RNG/triplet/gates; separate replay counters, refinement and bounded baseline staging compared to actual summaries. Posthoc holdout is independently labeled, never native validation. Degenerate reason alone is insufficient evidence of SVD degeneracy.

R01-R05/Q06-Q08: first test hypothesis refine-before-merge. 10deg/0.05m similarity is nontransitive; reject representative-only merge as unsafe by chain fixture. Minimal conservative alternative retains exact refined witnesses, only merges byte-identical planes/support; every other similar witness is retained. All pair comparisons at terminal, storage/refinement/trace/iteration bounds explicit. If a qualifying witness cannot be processed or logged/stored, result stays unresolved. Oracle in evidence tests only stores all same-sequence refined hypotheses; no claim about unseen hypotheses. Costs and positive ability must be measured, no promised speed win.

R06: compare clean/noisy/dual/late/chain/repeated and 3 seeds + permutations, real WHAT_IF. Adopt only if safety and useful positive behavior survive; no automatic runtime integration.

S01/Q10: only new core/ground_diagnostics.py, scripts/diagnose_gli04_geometry.py, tests/test_gli04_geometry.py. Prototype and experiments only this evidence root. Selfcheck -> submission manifest/return -> STOP production writes -> one <=1min model/defaultDB probe -> independent OpenCode review. B01/B02 BLOCKED, D01/D02 NOT_RUN. Target 3.8 AST only; local Python 3.12.10 is not board validation.

ROS hot reload/GL02 lifecycle startup-reload-lock combinations are inapplicable to a one-shot CLI with no persisted state. Repeated file reads, same path changed content, caller mutation, failed computation, empty selection and output collision remain applicable and will be checked. Finite search closure is software evidence, not physical uniqueness.
