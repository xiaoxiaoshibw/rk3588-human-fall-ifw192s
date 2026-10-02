# HF-08 R1 development check failures (retained summary)

These were local evaluator-test failures, not production or device results. The CLI transcript remains in the coding session; this file retains the failing assertions and fixes for review.

1. First targeted run: `test_unlabeled_and_empty_data_never_turn_into_pass_metrics` failed because a pending-label session with zero predictions was classified `no_data`. Fixed so every session with missing human labels is `pending_annotation`, with event metrics null. Added an assertion for that state.
2. First targeted run: duplicate/boundary case expected the less-preferred event to be unmatched. The deterministic matcher correctly matched the closer prediction. Updated the expected unmatched ID and isolated the inclusive boundary check in its own hand-calculable case.
3. A later interval test assertion expected 20 seconds. The actual rule gives 25 seconds: epoch 0 overlapping intervals union to 15 seconds, plus epoch 1's independent 10 seconds. Corrected the manual expected value and false alarms/hour accordingly; evaluator behavior was correct.

Final targeted and full regression results are in `hf08_validation.txt`; all listed checks pass after these corrections.
