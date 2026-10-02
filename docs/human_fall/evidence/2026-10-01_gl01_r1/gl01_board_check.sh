#!/usr/bin/env bash
# GL-01 isolated board compatibility check (LF script, run on wel@192.168.3.125).
# Extracts a read-only copy into /tmp and runs the pure suite inside the
# slam-localization container. Never touches the deployed release or the repo.
CONTAINER=slam-localization
rm -rf /tmp/gl01_check && mkdir -p /tmp/gl01_check
tar -xzf /tmp/gl01_pkg.tar -C /tmp/gl01_check
echo "HOST_PY3=$(python3 --version 2>&1)"
docker exec "$CONTAINER" rm -rf /tmp/gl01_check
docker cp /tmp/gl01_check "$CONTAINER":/tmp/gl01_check
docker exec "$CONTAINER" bash -c 'python3 --version; python3 -c "import numpy; print(\"numpy\", numpy.__version__)"; cd /tmp/gl01_check/human_fall_detection && python3 -B -W error -m unittest discover -s tests -p "test_*.py"'
echo "BOARD_INNER_RC=$?"
