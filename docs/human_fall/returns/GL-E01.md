# GL-E01 回传 / R1 / Codex / 2026-10-04

SUBMITTED / STOPPED；验收GLE01_ACCEPTANCE.md v1。用户本轮继续推进主线，恢复已有原件并只读取证；不是部署/新采集/网络配置。ponytail已读C:/Users/30680/.codex/skills/ponytail/SKILL.md，单证据writer。master/cbd0be1，00全树baseline；生产/原captures/NPZ/draft/旧证据不变。

| ID | 自验 | 证据 |
|---|---|---|
| A01 | PASS | 02原bag实际存在/magic/SHA；03首尾SHA |
| A02 | PASS | 03原PointCloud2布局26→28全量；04b headers精确/既定bag time6位舍入 |
| A03 | PASS | 原bag canonical完整bytesSHA=本地bin；89frames/4372400points逐帧SHA与NPZ XYZ一致 |
| A04 | PASS | 03数值转换loss0.007811、06反例；不校验单位/不声称微秒 |
| A05 | PASS | 05当前config/log SHA/mtime/摘录未知绑定；不解B02 |
| S01 | BLOCKED（待独审） | 范围/原始command-exit/3.8 AST、待实际指定模型二审 |
| B01 | BLOCKED（待独审） | 源链自验通过，待独审，不是物理标定 |
| B02 | BLOCKED | source-world/recording config/ground ROI身份未知 |
| D01 | NOT_RUN | 未run跌倒算法/性能/测量/部署/采集 |
| D02 | BLOCKED | 真实DPR控制接口不足；旧GL04实际项仍NOT_RUN |
| Q01–Q05 | PASS（自验） | 06身份/帧负例及03–05实证 |
| Q06 | BLOCKED（待独审） | 提交停写，新probe后独审 |

命令与exit详07_READONLY_COMMANDS_AND_BOUNDARIES.md；设备只读01/02/03/05 exit0；04首版audit误把raw bag时间与已6位舍入meta作位级比较exit1，原日志保留；04b修复精确既定转换exit0，06负例exit0。旧timestamp微秒精度注释不作为证据。不改旧NPZ里的source_bag_hash_verified=false，追加独立来源链审计sidecar。准备交Go Flash/defaultDB独立复核，不宣称ACCEPTED。


## 2026-10-04 GL-E01 R1独审收口

GLE01_ACCEPTANCE.md v1：A01–A05/S01/Q01–Q06 PASS，B01仅原bag→bin→NPZ来源链PASS；B02物理BLOCKED，D01 NOT_RUN，D02 DPR环境BLOCKED。用户继续主线后用既有SSH只读恢复原bag，89frames/4372400points/全量bytes与XYZ及headers精确对应，既定bag time round6原义保持；不回填旧NPZ/旧GL-I05当时来源未核字段。指定Go Flash/defaultDB probe11.468s/exit0，独审1099.531s/exit0/stop，session ses_efcf6b467ffewHbmcPqpeFNz16（15_review_session.json）；source/decoder/scope首尾不变；无新部署/采集/driver/网络配置/算法设备测试。timestamp逐点f64→f32最大数值误差0.007811已独立测得，不声称单位/微秒精度/同步；header精确保持。收口evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md；GL-I05软件PASS保持，当前来源缺口已补，录制外参/ROI身份与GL04真实DPR仍待证据。
