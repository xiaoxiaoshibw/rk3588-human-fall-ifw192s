#!/bin/bash
set -u
docker exec slam-localization bash -lc "cd /tmp/hf07_verify_r1 && python3 -B -W error -m unittest discover -s src/human_fall_detection/tests > /tmp/hf07_unit_summary.log 2>&1; echo DEVICE_UNIT_EXIT=\$?"
docker exec slam-localization bash -lc "grep -E 'Ran [0-9]+ tests|^OK|^FAILED' /tmp/hf07_unit_summary.log"
echo SCRIPT_DONE
