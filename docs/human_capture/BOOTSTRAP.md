# RK3588 板启动恢复手册

**更新时间**：2026-10-02（SSD 迁移后，容器重建版）
**适用**：板子重启 / 容器崩 / 数据链断

## 一句话概要

板子只有**容器 `slam-localization`** 里跑数据链（roscore → foxglove_bridge → inno_lidar_node）、webui（8090）、capture_server（8766）。**容器不自启**，板重启后必须手动按顺序拉起。

## 前置事实（不要重复干）

- SSD：`/dev/sda1` 已通过 `/etc/fstab` 挂为 `/mnt/captures`（119GB），**板重启后内核自动挂，无需人工**。
- 宿主机源副本：`/home/wel/slam_localization_wuhan/{src,webui}/`
- 容器镜像（做了冻结）：`slam-localization:noetic`——**不要 docker build / docker pull**
- 旧容器（**不要删，是 devel 备份**）：`slam-localization-old`（已 Exited）
- 容器配置备份：`/home/wel/container_backup_20261002_*.json`
- sudo 密码：`welcomtech`

## 启动顺序（必须按序）

### 1. 起容器

```bash
ssh wel@192.168.3.125
echo "welcomtech" | sudo -S docker start slam-localization
sleep 2
sudo docker ps | grep slam-localization
```

### 2. 起 roscore

```bash
sudo docker exec -d slam-localization bash -c '
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
nohup roscore > /var/log/roscore.log 2>&1 &'
sleep 3
```

### 3. 起 foxglove_bridge（PC Foxglove 用，8765）

```bash
sudo docker exec -d slam-localization bash -c '
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
nohup rosrun foxglove_bridge foxglove_bridge \
  --port 8765 --address 0.0.0.0 \
  > /var/log/foxglove_bridge.log 2>&1 &'
sleep 2
```

### 4. 起雷达驱动

```bash
sudo docker exec -d slam-localization bash -c '
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
nohup rosrun inno_lidar_ros inno_lidar_node \
  __name:=inno_lidar_node \
  _config_path:=/root/catkin_ws/src/inno_lidar_ros/config/config.yaml \
  > /var/log/inno_lidar.log 2>&1 &'
sleep 8
```

### 5. 起 8090 webui（包含 human_capture 控制台）

```bash
sudo docker exec -d slam-localization bash -c '
cd /root/catkin_ws/webui
nohup python3 -m http.server 8090 > /var/log/http8090.log 2>&1 &'
```

### 6. 起 capture_server（8766，采集控制台 API）

```bash
sudo docker exec -d slam-localization bash -c '
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash 2>/dev/null
cd /root/catkin_ws/src/human_capture
nohup python3 -u scripts/capture_server.py \
  --config config/capture.yaml \
  > /var/log/capture_server.log 2>&1 &'
```

## 验证清单（PC 侧）

```bash
curl -s http://192.168.3.125:8766/healthz                # 应有 ok:true
curl -s http://192.168.3.125:8766/api/v1/status          # ros:"up", disk_free_mb>100000
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.3.125:8090/          # 200
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.3.125:8090/human_capture/  # 200

# 深入查
ssh wel@192.168.3.125 "sudo docker exec slam-localization bash -c '
  source /opt/ros/noetic/setup.bash
  source /root/catkin_ws/devel/setup.bash
  rosnode list                    # 应有 /foxglove_bridge /inno_lidar_node /rosout
  timeout 3 rostopic hz /innolidar_points | tail -2   # 应 ~9.7 Hz
'"
```

## 故障排查

| 症状 | 可能原因 | 解法 |
|---|---|---|
| roslaunch/rosnode 卡在 checking log | 网络/hostname 卡 | 等 1 分钟，或 `/etc/hosts` 应有 `127.0.1.1 welcomtech` |
| `rosbag record` 报 not found | 子进程未继承 ROS env | 用 `bash -c "source /opt/ros/noetic/setup.bash && source $HOME/catkin_ws/devel/setup.bash && exec ..."` 包一层 |
| `Cannot load message class` | 忘了 `source devel/setup.bash` | 见上面命令模板 |
| `ros2 domain id conflict` | 无，本板是 ROS1 | — |
| 8090 起不来 | 上一次 python http.server 没杀干净 | `sudo docker exec slam-localization pkill -f http.server；重跑第 5 步` |
| 8766 起不来 | capture_server 崩了 or 端口占 | `sudo docker exec slam-localization cat /var/log/capture_server.log` |
| HF 节点不在 | 它不由本手册管（见下） | `/root/catkin_ws/human_fall_deploy/scripts/deploy_human_fall.sh` 单独走 |

## HF 节点（human_fall_node）

**不在本手册范围**。它由 `/root/catkin_ws/human_fall_deploy/scripts/deploy_human_fall.sh` 管理（版本化发布 + symlink 回滚）。如需要它跑，单独执行那个脚本，**不要 `rosrun` 手动起**。

## 不要做的事

- 不要 `docker rm slam-localization-old`（里面 devel/lib/inno_lidar_node 是唯一编好的 driver 二进制，新容器重建时要从它 `docker cp`）
- 不要 `docker pull / build` slam-localization 镜像（镜像是历史固化，源 Dockerfile 不在仓里）
- 不要动 `/etc/fstab` 里 sda1 那一行，除非 SATA 更换
- 不要在 capture_server 录制时强杀 capture_server 进程（会让 sessions.json 卡在 recording）
