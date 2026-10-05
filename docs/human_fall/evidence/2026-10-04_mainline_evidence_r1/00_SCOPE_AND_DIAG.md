# 主线已有录制证据核查 / 2026-10-04

用户最新明确“继续与推进主线”，本轮推进已有证据只读恢复，不启动GL-05/新录制/部署/driver/网络配置。Codex单执行者；ponytail已读 C:/Users/30680/.codex/skills/ponytail/SKILL.md。范围：新本目录脚本/日志/报告及允许状态附记，生产/旧证据/原captures冻结；全tracked+untracked基线00_before_baseline.json。

已读WORKFLOW v2。GL-I05 R2软件PASS保持；主线实际缺口为GL04 V04/C12/M03真实DPR-only，V10真实support/实际接入，GL-I05 B01原bag/layout链和B02录制外参/ROI身份。

当前浏览器capability只visibility/viewport(w,h)，与R7证据一致，没有可控DPR接口。历史Ctrl+plus失败不在同条件盲重试，不注入devicePixelRatio、不虚报PASS。V04/C12/M03本轮环境BLOCKED，历史NOT_RUN保留。

已有设备读取使用已登记SSH alias ldiar-wel（wel@192.168.3.125，既有密钥），BatchMode=yes/StrictHostKeyChecking=yes/ConnectTimeout=8。不新增known_hosts、不索取或保留密码、不改任何board设置。01读取hostname/docker ps成功，确认现有slam-localization与-old运行；是恢复既有原件的只读检查，不是新部署/采集。旧GL-I05范围不被追改。

操作矩阵（对应现有ID，不新增物理判据）：
| 行 | ID | 输入/动作/预期 |
|---|---|---|
| E01 | B01 | 既有指定bag路径存在/缺失/Hash不符；先stat/magic/SHA，匹配meta声明才能进入layout/帧校验；不靠声明字段PASS |
| E02 | B01 | 原PointCloud2 fields/point_step/row_step/endian/header×89帧提取索引；原bag→canonical rows/XYZ/layout比对，成功仅提升该证据链，不解物理身份 |
| E03 | B02 | 当时配置/日志存在/缺失×时间绑定；当前config与9/30日志只能分别说明当前/历史，不填10/2配置；未知保持unknown |
| E04 | B01/B02/S01 | 读取日志/哈希/拷贝新证据路径，原capture/NPZ/draft/代码不变；只读访问失败如实BLOCKED，安全独立项继续 |
| E05 | V04/C12/M03 | 当前接口与旧限制核对，不以CSS resize/JS覆盖变量替代真实DPR变化 |

诊断完成后可执行02指定原文件probe。若原bag可读取，追加独立decode/映射证据；若缺失，不生成“真实验证”产物。不会发布或启动ROS话题，不触发human capture/baseline请求。
