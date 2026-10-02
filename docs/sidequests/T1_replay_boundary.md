# T1 回放边界盘点：无板开发链路现状（2026-10-02）

背景：板端 192.168.3.125 SSH 超时不可达。本报告只盘点事实，不产新框架；回答"无板时 Windows 上现有回放/预览/评测链路能通到哪、缺口在哪"。

## 1. 现有链路图（事实）

```
[数据源]
  真实 bag/pcap —— 只在板端 /root/catkin_ws/human_fall_sessions/（docs/human_fall/AI_PROMPT_GL_START.md:30 明述本地无 captures/、无 bag/PCAP）
  本地唯一 npz —— docs/human_fall/evidence/2026-10-01_autonomous_hf03_r1/synthetic_plane.npz（points 8000×3，单帧平面）
        │
        ▼
[采集] scripts/record_session.py ── 子进程调 rosbag record（record_session.py:219），
        回读 import rosbag（record_session.py:201）→ 需 ROS1 + 板端话题，Windows 不可用
        │
        ▼
[离线回放] scripts/fall_replay.py ── 纯 Python+NumPy（fall_replay.py:10-22），
        输入 .npz（frames/points+可选 times，fall_replay.py:38-48）+ 可选 ground/baseline JSON，
        走 core.pipeline.ReplayPipeline → 严格 JSON 输出
        │
        ▼
[评测] scripts/evaluate_sessions.py ── 纯 stdlib JSON（evaluate_sessions.py:4-9），
        输入版本化 dataset JSON，输出报告 JSON
        │
        ▼
[可视化] webui/human_fall_preview/ ── 纯渲染层（human_fall.js:1-9），
        数据面直连 ws://…:8765 foxglove_bridge（index.html:129,242,827），
        无离线/回放分支→无板浏览器只显示重连
```

## 2. 可运行性矩阵

| 环节 | 文件 | Windows 纯 Python/node | 需 ROS | 需板端 |
|---|---|---|---|---|
| fall_replay.py --help | scripts/fall_replay.py:52 | 通过(exit 0) | 否 | 否 |
| record_session.py --help | scripts/record_session.py | 通过(exit 0) | 实际录制需 rosbag 子进程(:219) | 是 |
| evaluate_sessions.py --help | scripts/evaluate_sessions.py | 通过(exit 0) | 否 | 否 |
| HF 单测 | tests/（59 个用例） | 通过(exit 0) | 否（hf07 用假 rosbag 桩） | 否 |
| fall_replay 闭环 | test_hf06 场景夹具 | 通过(exit 0) | 否 | 否 |
| evaluate hf08 夹具 | tests/hf08_synthetic_events.json | 通过(exit 0) | 否 | 否 |
| preview node 测试 | human_fall_lib.test.js | 通过 18/18(exit 0) | 否 | 否 |
| preview 页面打开 | index.html:827 | 可开但只报重连 | — | 是（bridge 在板） |
| driver pcap 回放 | config/config.yaml:2 msg_source=2, :21 pcap_file=/home/wenjie/... | 否 | 必须（ROS driver 节点 libinno_driver） | 板上/容器 |
| 本地 PCAP/bag 素材 | captures/ | 不存在（find 全仓 0 个 .pcap/.bag） | — | 是 |

## 3. 实测命令与退出码（Windows 本机，2026-10-02）

```
python -B src/human_fall_detection/scripts/fall_replay.py --help            → exit 0
python -B src/human_fall_detection/scripts/record_session.py --help         → exit 0
python -B src/human_fall_detection/scripts/evaluate_sessions.py --help      → exit 0
python -B -W error -m unittest discover -s src/human_fall_detection/tests -v → exit 0（全过，含 hf07 的 rosbag 桩测试）
cd webui/human_fall_preview && node human_fall_lib.test.js                  → exit 0, "HF lib checks: 18 passed"
# 最小离线闭环（夹具由 test_hf06._scene 生成，7 帧 站立→跌倒）：
python gen.py （np.savez frames/times + ground.json + baseline.json）       → exit 0
python -B fall_replay.py --frames %T%/frames.npz --ground %T%/ground.json
       --baseline %T%/baseline.json --auto-select --output %T%/replay.json   → exit 0，replay.json 29 KB（kind:fall_replay）
python -B evaluate_sessions.py --input tests/hf08_synthetic_events.json
       --output %T%/eval_report.json                                        → exit 0（evaluated，FP=2/FN=0 合成标签）
```
产物位于 %TEMP%/t1_loop/（本机）；仓库内未写入任何文件（本报告除外）。

## 4. 已存在的本地回放夹具

- tests/test_hf06_fall_state.py:313-336 `_scene()` 内存构造 7 帧 npz 场景并以脚本入口 main() 跑通，test_hf06:338-362 即现成的脚本级闭环测试。
- tests/test_hf07_node.py:128-193 内存构造 candidate_snapshot/state dict 走 schema。
- tests/hf08_synthetic_events.json（2 KB）是 evaluate_sessions.py 的现成输入。
- evidence/…/synthetic_plane.npz 仅单帧 points(8000,3)，fall_replay.py:42 支持 points 分支（单帧），可做烟测输入但不是跌倒过程。

## 5. 缺口与最小建议

链路在算法层（HF-04..08）已闭合：npz→replay→严格 JSON→评测，今天就能全程 Windows 跑。真正缺口只有两个：

1. **无真实点云数据**：captures/ 不存在、仓内 0 个 pcap/bag；唯一 npz 是单帧合成平面。真实数据在板端，板不可达期间无法取得。bpcap 回放链 msg_source=2（config.yaml:2）指向 /home/wenjie 绝对路径且必须经 ROS driver 节点+libinno_driver（仅板/容器构建可跑）。→ 这是素材缺口，不是工具缺口；等板恢复后 scp 回 bag/pcap 即可，无需现在补工具。
2. **可在 bag→npz 之间补一个"bag 转 npz"一步？** 不值得现在做（ponytail）：record_session/evaluate 已有约定，bag 内容只有 board 可读，等板回来自有已有流程；提前写转换器是无输入的臆测。

preview 页面无离线模式是唯一"看到东西"的缺口，但其 lib 层 18 测试已把 wire/帧对齐逻辑钉死；给页面加本地回放模式会动冻结的 webui 资产，不在授权范围，不建议。

## 结论

无板期间可继续 HF 算法/评测/页面 lib 层的全部离线开发与验证；阻塞在真实数据素材与驱动级 pcap 回放，两者本质依赖板端恢复。

完成：T1
