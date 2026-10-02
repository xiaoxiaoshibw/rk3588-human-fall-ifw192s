#!/bin/bash
# HF-01 round 2: run the Codex boundary reproduction script against the deployed package
# inside the slam-localization container (temporary path only, same source as on the host).
set -u
inner=/tmp/hf01_boundary_inner_r2.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
mkdir -p /root/catkin_ws/docs/human_fall/evidence
cd /root/catkin_ws
timeout 200 python3 -B -W error docs/human_fall/evidence/review_hf01_codex.py
echo "boundary exit=$?"
INNER
docker exec slam-localization mkdir -p /root/catkin_ws/docs/human_fall/evidence
echo "mkdir exit=$?"
docker cp /tmp/review_hf01_codex.py slam-localization:/root/catkin_ws/docs/human_fall/evidence/review_hf01_codex.py
echo "script cp exit=$?"
docker cp "$inner" slam-localization:/tmp/hf01_boundary_inner_r2.sh
echo "docker cp exit=$?"
timeout 300 docker exec slam-localization bash /tmp/hf01_boundary_inner_r2.sh
echo "exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_boundary_inner_r2.sh \
  /root/catkin_ws/docs/human_fall/evidence/review_hf01_codex.py
docker exec slam-localization rmdir /root/catkin_ws/docs/human_fall/evidence \
  /root/catkin_ws/docs/human_fall /root/catkin_ws/docs 2>/dev/null
echo "cleanup exit=$?"
rm -f "$inner"
