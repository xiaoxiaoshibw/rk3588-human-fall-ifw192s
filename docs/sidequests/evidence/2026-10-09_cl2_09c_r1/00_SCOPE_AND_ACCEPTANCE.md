# CL2-09C 唯一验收表 v1

2026-10-09 Asia/Shanghai。依据本聊天用户的 CL2-09B 阶段裁定及 CL2-09C 建议执行离线等价性能优化。Codex 唯一源码 writer；OpenCode CLI `opencode-go/deepseek-v4.1-flash` 只读独审。ponytail 实际路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

冻结基线为 ../2026-10-09_cl2_09b_r1 的 FINAL_REPORT.md、02_fix.patch、candidate 和测试。仅本目录中的 candidate/floor_sheet.py 可改变算法实现；原生产、历史证据和原始会话只读。不得设置搜索数量上限、近似阈值、放宽门控或改变并列决策。所有耗时为本机真实测量，不推断板端或生产准入。

| ID | 要求 |
|---|---|
| C01 | 起始 branch/HEAD、全树含 untracked/ignored 文件 SHA 库存；复算 09B manifest；冻结输入和源码起止 SHA |
| C02 | 对冻结基线进行组合枚举、距离/间距、SVD、排序耗时剖析，明确测量开销及未拆分部分 |
| C03 | 精确优化四区搜索；完整保留旧成功/失败完整 dict、最大间距和稳定并列；不截断搜索、不改质量门 |
| C04 | 与 09B 穷举实现差分：小/大、成功/无解、重复、并列、输入反序、阈值边界；完全相等而非近似 |
| C05 | 冻结 35 项回归及新增差分检查 -W error；v1/v2/v3/15cm 路由、纯度/身份保持；3.8 语法兼容 |
| C06 | 同输入同环境 25/60/100 候选有解和非共线无解真实基准，记录冷/重复耗时、环境及源码 SHA；本地性能比较，生产时延验收 NOT_RUN |
| C07 | 原 121647 clean cells 与 ROI 完全相同；原 TLS 50mm P95 门控与 BLOCKED 保持，不重拟合/替代物理验收 |
| C08 | 指定 OpenCode CLI 真实独审；版本、权限、原始 IO、退出码、session export 和 actual model 保留，作者作交叉裁决 |
| C09 | 最终证据 manifest、原资产起止 SHA、append-only 本工单 return；失败尝试保留；状态 SUBMITTED/STOPPED |
| E01 | 生产接入/CL2-10/发布/部署 BLOCKED，未授权 |
| D01 | 设备/物理/B2/B3/采集 NOT_RUN；121647 有效 TLS BLOCKED |

本轮优化优先复用冻结控制流，只去掉重复距离工作及可证明无效的搜索分支；SVD 的数值输入及比较保持原样。此表不回填 CL2-07～09B，也不授予后续阶段许可。
