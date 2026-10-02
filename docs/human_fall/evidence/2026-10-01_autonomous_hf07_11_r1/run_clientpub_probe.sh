#!/bin/bash
set -u
echo "== clientPublish probe: advertise + publish std_msgs/String over foxglove bridge =="
docker cp /tmp/hf11_probe_clientpublish.py slam-localization:/tmp/probe_clientpublish.py
docker exec slam-localization bash -lc "
source /opt/ros/noetic/setup.bash
rostopic echo -n2 /hf11_clientpub_test > /tmp/hf11_echo.txt 2>&1 &
ECHO=\$!
sleep 1
python3 /tmp/probe_clientpublish.py
sleep 1
kill \$ECHO 2>/dev/null
wait \$ECHO 2>/dev/null
echo '--- rostopic echo of client-published topic ---'
cat /tmp/hf11_echo.txt
"
echo CLIENTPUB_WRAP_EXIT=$?
echo SCRIPT_DONE
