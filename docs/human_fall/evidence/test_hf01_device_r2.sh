#!/bin/bash
# HF-01 round 2: run the package's regression tests inside the slam-localization container.
set -u
inner=/tmp/hf01_test_inner_r2.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
cd /root/catkin_ws
timeout 300 python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v
echo "unittest exit=$?"
INNER
docker cp "$inner" slam-localization:/tmp/hf01_test_inner_r2.sh
echo "docker cp exit=$?"
timeout 400 docker exec slam-localization bash /tmp/hf01_test_inner_r2.sh
echo "exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_test_inner_r2.sh
echo "cleanup exit=$?"
rm -f "$inner"
