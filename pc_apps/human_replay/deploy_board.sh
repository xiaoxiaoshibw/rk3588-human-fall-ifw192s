#!/bin/sh
# deploy_board.sh — 把 human_replay 的"只跑 GT 标注台所需"集打包并推到 3588 板上并起服务。
#
# 用法（在 PC 端 Git Bash/或任何能 ssh 到 wel@192.168.31.58 的 shell）：
#   sh pc_apps/human_replay/deploy_board.sh
#
# 安全边界：
# - 只推 GT 标注需要的文件（__pycache__ / *.test.py / gt_store 都不带）；
# - 推到 /home/wel/human_replay_board/，fallback 不进 slam-localization 容器；
# - 8088 监听 0.0.0.0，与 8090(webui) 8765(bridge) 8766(capture) 8901(PC 端本地实例) 都不冲突；
# - 起 systemd unit human-replay-board.service，板重启自动拉起，停了能 systemctl 回滚；
# - 写完问候 GET /api/gt/export 冒烟。
#
# 回滚：ssh wel@192.168.31.58 'sudo systemctl disable --now human-replay-board && rm -rf /home/wel/human_replay_board'
set -eu

BOARD_HOST=${BOARD_HOST:-wel@192.168.31.58}
BOARD_TMP=${BOARD_TMP:-/home/wel/human_replay_board}
PORT=${PORT:-8088}

die() { echo "FATAL: $*" >&2; exit 1; }

[ -d pc_apps/human_replay ] || die "必须在仓库根运行"

# sudo 密码（rk3588-ops-facts 2026-10-10 实测），环境变量覆盖以不落 git
WEL_SUDO=${WEL_SUDO:-"welcomtech"}
SUDO_ESC=$(printf '%s' "$WEL_SUDO" | sed -e "s/'/'\\\\''/g" -e "s/\"/\\\\\"/g")

# ---------- 打包（只挑 GT 标注台用得到的） ----------
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/human_replay"

# 核心 serving + 页面 + JS 库（缺哪个就跳过——[ -f ] 已在循环里过滤）
for f in human_replay_lib.py config.py gt_server.py gt_annotator.html gt_annotator.js \
         gt_lib.js gt_workbench_ops.js gt_live.js fetch.py validation.py leveling.py human_detect.py \
         replay.js human_replay_lib.js three.min.js orbit_controls.js \
         bg_envelope.json; do
    [ -f "pc_apps/human_replay/$f" ] || continue
    cp "pc_apps/human_replay/$f" "$STAGE/human_replay/"
done

# human_core/ 引擎(g/t/auto 预跑; node, 但缺 node 时优雅降级)
mkdir -p "$STAGE/human_replay/../human_core"
if [ -d pc_apps/human_core ]; then
    for f in engine.js schema.js leveling.js runner.js data_loader.js; do
        [ -f "pc_apps/human_core/$f" ] && cp "pc_apps/human_core/$f" "$STAGE/human_replay/../human_core/"
    done
fi

# 目录结构对齐仓库 (gt_server 期待 ../.. 是 REPO —— 板上推到 ~/.human_replay_board/，让顶层等价)
mkdir -p "$STAGE/root/human_replay"
mv "$STAGE/human_replay"/* "$STAGE/root/human_replay/" 2>/dev/null || true
[ -d "$STAGE/human_replay/../human_core" ] && mv "$STAGE/human_replay/../human_core" "$STAGE/root/" 2>/dev/null
rmdir "$STAGE/human_replay" 2>/dev/null || true

# 打包 tar
tar -czf "$STAGE/bundle.tar.gz" -C "$STAGE/root" .

# ---------- 推送板 ----------
echo "[1/4] scp -> $BOARD_HOST"
scp -q "$STAGE/bundle.tar.gz" "$BOARD_HOST:/tmp/human_replay_board.tar.gz"

# ---------- 板上解 + 写 systemd ----------
echo "[2/4] ssh: 解包 + systemd + 首启"
ssh "$BOARD_HOST" "sh -se" <<EOF
set -eu
mkdir -p "$BOARD_TMP"
tar -xzf /tmp/human_replay_board.tar.gz -C "$BOARD_TMP"
rm /tmp/human_replay_board.tar.gz

# staging + store 目录权限
echo "$WEL_SUDO" | sudo -S mkdir -p /mnt/captures/captures_remote /mnt/captures/human_replay_gt_store 2>/dev/null
echo "$WEL_SUDO" | sudo -S chown -R wel:wel /mnt/captures/human_replay_gt_store 2>/dev/null

# 写 systemd 服务（覆盖写,可以重部署）
echo "$WEL_SUDO" | sudo -S tee /etc/systemd/system/human-replay-board.service >/dev/null <<EOS
[Unit]
Description=Human Replay Board (GT annotator) — $PORT
After=network.target

[Service]
User=wel
WorkingDirectory=$BOARD_TMP/human_replay
Environment=HUMAN_REPLAY_BOARD_MODE=1
Environment=HR_PORT=$PORT
Environment=HR_DEST_ROOT=/mnt/captures/captures_remote
Environment=HR_STORE_DIR=/mnt/captures/human_replay_gt_store
ExecStart=/usr/bin/python3 $BOARD_TMP/human_replay/human_replay_lib.py
Restart=on-failure
RestartSec=3
StandardOutput=append:/var/log/human-replay-board.log
StandardError=append:/var/log/human-replay-board.log

[Install]
WantedBy=multi-user.target
EOS

echo "$WEL_SUDO" | sudo -S systemctl daemon-reload
echo "$WEL_SUDO" | sudo -S systemctl enable human-replay-board
# FIX-DEPLOY: enable --now 只对未启动服务生效；重部署必须显式 restart 让新代码生效
echo "$WEL_SUDO" | sudo -S systemctl restart human-replay-board
sleep 2
systemctl is-active --quiet human-replay-board && echo "service:active" || (echo "$WEL_SUDO" | sudo -S journalctl -u human-replay-board -n 30 --no-pager; exit 1)
EOF

# ---------- 冒烟 ----------
echo "[3/4] 从 PC 打 /api/gt/export 冒烟"
IP=$(echo "$BOARD_HOST" | sed 's/.*@//')
curl -fsS --max-time 5 "http://$IP:$PORT/api/gt/export" | head -c 200
echo

echo "[4/4] 完成。"
echo "  浏览器打开: http://$IP:$PORT/gt_annotator.html"
echo "  （或带 sid: http://$IP:$PORT/gt_annotator.html?sid=cap_20261010_175227）"
