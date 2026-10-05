# GL04 R5 设计前置与责任审查

当前只一张GL04_ACCEPTANCE v1。连续资格/目标生命周期族R1–R4尚未闭合：R1旧frame/状态、R2旧state-cal与other、R3目标presence、R4nullable缺失/预测/legacy source-only锁定。R4已解决其原4FAIL，新增反例揭示同ID既有C01/C05/C07/C08/C11状态组合遗漏，不改判据。R4独立依据：`../2026-10-02_gl04_r4/{CODEX_REVIEW.md,90_codex_runtime.txt,92_codex_consumers.txt}`，源SHA `94_scope_sha.json`。

| 实际缺口 | 责任分流 | 实施前设计与逐格检查 |
|---|---|---|
| known/null与known/undefined不同处理 | R4实现仅比较已声明state字段；Codex原测试只构造null不构造字段缺失 | 标准化binding的null/undefined：both absent/null legacy匹配；任一侧known而对侧缺/空则不匹配。cal_id、schema、GDID都查；kind1消息的合法旧断言不降低 |
| 目标其他人/预测/legacy消费者同门 | R4实现将选择context独立，但物理观察仍要求有效ground/schema，source-only锁定不显示，预测短路为当前位置；Codex漏首选后状态 | 分别列选择、当前已测source坐标、跌倒高度/GT及预测诊断；first select不需目标，legacy当前实际source几何可显示rawXYZ/track locked，fall仍unknown/颜色unknown；没有对应当前候选时物理position空，预测只在明确诊断处呈现 |
| token漏坐标子字段 | R4实现沿R2的snapshotIdentity只列R/t，不列units或coordinate.source_frame；Codex原frame反例只改source.frame_id | 已声明coordinate field和显式ground block units纳入不可变显示token或提早判invalid；改旧按钮拒绝，新当前按钮仍发原candidate_id。不给客户端配平ID |
| fixture和端到端 | R3静态state缺若干实际Node会提供的GT字段，R4新browser仍未跑 | r5新增离线fixture（新目录，不覆写旧）：从已发布candidate字段复制Node当前实测会提供的state.center_ground_m/GDID、真实performance形状和源plane normal/d；非硬件不冒充验证。真browser六图及本地mock矩阵重跑；DPR能力不足仍NOT_RUN，真实设备/生产消息BLOCKED |

所有旧R0–R7 watcher/lock/ack、历史、告警色、原始点云/IMU/设备面板保留；真实物理设备、core/config/driver、正式页及其它webui冻结。只有OpenCode一个生产写入者，Codex独审；不换模型/DB/认证。R4 exit0已停，无并行写源。
