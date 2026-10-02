#!/bin/bash
# HF-02 R3: read-only unified diff between the round-2 and round-3 isolated
# trees still present on the board. diff exit 1 simply means "files differ".
set -u
docker exec slam-localization bash -lc 'sha256sum /tmp/hf02_r2_verify/src/human_fall_detection/core/timebase.py /tmp/hf02_r2_verify/src/human_fall_detection/core/sensor_quality.py /tmp/hf02_r2_verify/src/human_fall_detection/tests/test_hf02_timebase.py; echo HASH_R2_TREE_EXIT=$?'
docker exec slam-localization bash -lc 'diff -u /tmp/hf02_r2_verify/src/human_fall_detection/core/timebase.py /tmp/hf02_r3_verify/src/human_fall_detection/core/timebase.py; echo DIFF_TIMEBASE_EXIT=$?'
docker exec slam-localization bash -lc 'diff -u /tmp/hf02_r2_verify/src/human_fall_detection/core/sensor_quality.py /tmp/hf02_r3_verify/src/human_fall_detection/core/sensor_quality.py; echo DIFF_SENSOR_QUALITY_EXIT=$?'
docker exec slam-localization bash -lc 'diff -u /tmp/hf02_r2_verify/src/human_fall_detection/tests/test_hf02_timebase.py /tmp/hf02_r3_verify/src/human_fall_detection/tests/test_hf02_timebase.py; echo DIFF_TESTS_EXIT=$?'
echo DIFF_SCRIPT_DONE
