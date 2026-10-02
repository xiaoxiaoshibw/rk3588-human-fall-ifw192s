printf '\n[CURRENT_CONFIG_AND_PUBLISHERS]\n'
docker exec slam-localization bash -c 'source /opt/ros/noetic/setup.bash; source /root/catkin_ws/devel/setup.bash; grep -nE "msg_source|lidar_type|cloud_port|check_lidar_ip" /root/catkin_ws/src/inno_lidar_ros/config/config.yaml; timeout 5 rostopic info /inno_imu'
printf '\n[SDK_RELEVANT_SYMBOLS]\n'
lib=/home/wel/slam_localization_wuhan/src/inno_lidar_ros/third_party/inno_driver/lib/aarch64/libinno_driver.so
nm -D -C "$lib" | grep -Ei 'DecodeImu|ParseImu|GetImu|IMUBlock|IsImuSame|DecoderIFW192S.*DecodeMsopPacket' | head -n 28
printf '\n[LOADED_SDK]\n'
docker exec slam-localization bash -c 'pid=$(pgrep -x inno_lidar_node | head -n 1); if [ -n "$pid" ]; then grep libinno_driver /proc/$pid/maps | head -n 3; fi'
printf '\n[MEASUREMENT_START]\n'
docker exec -i slam-localization bash -c 'source /opt/ros/noetic/setup.bash; source /root/catkin_ws/devel/setup.bash; exec python3 -' <<'PY'
import time, math, json, threading
import rospy
from sensor_msgs.msg import Imu, PointCloud2
rospy.init_node('codex_readonly_imu_probe', anonymous=True, disable_signals=True)
lock=threading.Lock()
imu=[]
cloud=[]
def on_imu(m):
    row={'arrival':time.monotonic(),'stamp':m.header.stamp.to_sec(), 'frame':m.header.frame_id,
         'acc':[m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z],
         'gyro':[m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z],
         'q':[m.orientation.x,m.orientation.y,m.orientation.z,m.orientation.w],
         'orientation_covariance0':m.orientation_covariance[0]}
    with lock: imu.append(row)
def on_cloud(m):
    with lock: cloud.append((time.monotonic(),m.header.stamp.to_sec()))
s1=rospy.Subscriber('/inno_imu',Imu,on_imu,queue_size=1000)
s2=rospy.Subscriber('/innolidar_points',PointCloud2,on_cloud,queue_size=2,buff_size=2**24)
started=time.monotonic()
while time.monotonic()-started<4.0: time.sleep(0.05)
s1.unregister();s2.unregister()
with lock:
    rows=list(imu);points=list(cloud)
report={'window_s':round(time.monotonic()-started,3),'imu_messages':len(rows),'point_messages':len(points)}
if len(rows)>1:
    dt=[b['stamp']-a['stamp'] for a,b in zip(rows,rows[1:])]
    report.update(imu_arrival_hz=round((len(rows)-1)/(rows[-1]['arrival']-rows[0]['arrival']),3),
                  imu_stamp_delta_min_s=min(dt),imu_stamp_delta_max_s=max(dt),
                  imu_stamps_strictly_increasing=all(x>0 for x in dt),
                  all_measurements_finite=all(math.isfinite(x) for r in rows for x in r['acc']+r['gyro']),
                  acceleration_norm_min=min(math.sqrt(sum(x*x for x in r['acc'])) for r in rows),
                  acceleration_norm_max=max(math.sqrt(sum(x*x for x in r['acc'])) for r in rows),
                  nonzero_quaternions=sum(any(x!=0 for x in r['q']) for r in rows),
                  orientation_covariance0_values=sorted(set(r['orientation_covariance0'] for r in rows)))
if len(points)>1: report['point_arrival_hz']=round((len(points)-1)/(points[-1][0]-points[0][0]),3)
for name,idx in (('first_imu',0),('last_imu',-1)):
    if rows: report[name]={k:v for k,v in rows[idx].items() if k!='arrival'}
print(json.dumps(report,indent=2,allow_nan=False))
rospy.signal_shutdown('read-only probe complete')
PY
printf '\n[END]\n'
