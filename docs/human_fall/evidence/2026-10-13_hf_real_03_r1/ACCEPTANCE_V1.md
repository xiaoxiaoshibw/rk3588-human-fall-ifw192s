# HF-REAL-03 v1：助手视觉排查三单 (f10 家具 / 093958 配平 / P 臂吞人按部位画像)

承接用户要求："你可以自己排除背景，然后找到人的点点，这都是你能干的事情" 并在 h2 授权下 "三项一起做"。
上一单 HF-REAL-02 R1（同日下午）的 f10 家具污染 FAIL、HF-REAL-01 R1 的 093958 配平 FAIL、HR-W03 长期 REWORK 的根因画像均需在隔离 r03 下由助手视觉排查。

本单开发主体为排查、证据与最小可行修正（或如实登记 BLOCKED），不通过关闭工单、不主动修改为生产可用代码、不影响主控工作状态、不部署、不采集、不写入 git。旧 r01/r02 流程过程产物只读。

## 验收表 v1

| ID | 语义 | 标准 | 本单口径 |
|----|----|----|----|
| RS-A | 基线绑定 | 起始 HEAD/branch/工作树量化、读 ponytail SKILL.md | HEAD `026e06303f60ed1bbe4ddc4d037836db68da6d27`，master，树含 267 文件用户末期差异；ponytail 实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md` |
| RS-B | 隔离证据与源码 | 新源码 `sidequests/human_fusion_lab_next/real_fall/r03/`、证据 `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/` 不在 r01/r02 加代码 | 见 SOURCE 清单 |
| RS-C | 任务1：f10 家具污染 | 视觉定位静态家具区、产生 v3、验证 target 是否被污染存在剔除、错误成因是否归到助手或生成因素 | 视觉盒剔除 f18-f23 共 404 点，100% 落入 HF-REAL-01 助手视觉人区；证明盒位猜测错（那是人腿经过区），v3 仅是证伪的生产不参与证据。r02 v2 target 在 f10 未被本单检出含家具残留 → RS04 FAIL 由独审决定是否关闭，本单不自收口 |
| RS-D | 任务2：093958 | 读 leveling.json 主要 estimator 键并交手示例图定位坏源 | 三法 pairwise PASS（TLS/SVD pitch 24.005° 一致、RANSAC 23.84°）但 holdout/同域门 FAIL；f5/f60/f115 快照图显示 side view 无地面斜带，结论 DATA_BAD |
| RS-E | 任务3：215540 P臂按部位吞人 | 划分四个身高带，统计 survive/remove 与 mask 图 | legs/torso/shoulders/head 删除达 97%+；总删 112,903 / 存 2,774；结论 ONLINE_BG_EATS_PERSON 为行为原因 |
| RS-F | 任务3 范围限制 | 215623/215643/233658 本机/板上不在 | 本机 captures/remote/ 与板上 ssh `ls captures_remote` 均仅 215540 一段，其他三段原始点不在任一可达位置；板上 47 段中无 10-07 任何会话； DATA_BLOCKED |
| RS-G | 渗透生产 / GT / 模型 | 不作未授权动作 | NO_TOUCH、不 commit/push （板上 ssh ls 为只读探测） |
| RS-H | 独立复审 / 设备 / 部署 | 不自验收 | 独立复审 NOT_RUN； 设备/部署/生产/GT NOT_RUN |
| RS-I | axis_ambiguous 3 帧（47, 109, 118） | 与任务 1 同级查看 | 见 AMBIG_COMPARE.png；侧面 target 状态在人形走弧区，axis_ambiguous 由人物进入下滑阶段后近接地水平姿态所致； 骨架不接生产， 不为此另行初始化 body tracking |

## 附：界限
- 本单不调用生产服务器、不进行生产服务器部署、不推进生产/GT/模型切换；不修改 r01/r02 源码。
- 以本单为起因的后续动作：
  - 任务1：HF-REAL-02 R1 RS04 FAIL 的关闭理由需在独立复审下确认 v2 target 本身否含家具；
  - 任务2：093958 型判断为 DATA_BAD，不投入追踪；
  - 任务3：fusion v2 / online background shadow 必须追加"人体主干区"保护项，但需另一个授权单独启动；本单仅提供定量证据。
