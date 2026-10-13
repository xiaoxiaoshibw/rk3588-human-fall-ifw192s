# HUMAN-UNIFY-FUSION-R1 / R2 收口

2026-10-10，Codex唯一writer；**SUBMITTED / 停写，未ACCEPTED**。本轮授权为离线F3/F4，验收表 `../../HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md` v1。未commit/push/deploy/采集/模型生产切换，不激活ML/HR-09。

| 五判定 | 结果 | 证据与限制 |
|---|---|---|
| FUNCTIONAL | PASS | 新GT边界检查、FUSION16；指定Go Flash独审未发现评估工具逻辑缺陷 |
| GT_EVALUATION | BLOCKED | 7当前稳定会话已有可信已标帧指标；S1 GT外部移走、S9无可用非e2e绑定GT |
| PERFORMANCE | FAIL | 70/72组合通过；S3-far FUSION v1/v2 P95=53.46/53.40ms>50ms，失败原样保留 |
| MODEL_PROMOTION | BLOCKED | 候选明显行走/遮挡回退；缺独立家具负例、新演员/场景与完整GT，保留v1 |
| PRODUCTION_RELEASE | BLOCKED | 未授权，未启动 |

## 已交付

- `pc_apps/human_ml/frozen_gt.py`：最新非e2e冻结版本/SHA/审阅/索引/track校验及精确compact点集导出；同帧同点集家具对象去重。
- `pc_apps/human_ml/train_person_rf_v2.py`：冻结会话划分后训练，新候选保存在 `train_02/rf_person_v2.json`，SHA `1b7a587e8961786f6dec21840e50ff3fb0da8a2b3c52f19aa8058c7fa530a65a`。
- `pc_apps/human_core/evaluate_fusion_gt.js` / `test_fusion_gt.js`：9×4路线×2模型共72完整运行/20840帧tick；逐版本FUSION↔BASE_B 2605同源帧；候选及当前确认track分开匹配，未标帧UNKNOWN。
- `train_02/GT_POS.json` / `GT_FURN_HARD_NEG.json` / `SPLITS.json`：510正例+1216家具负例；S1原1464家具对象去重248；阈值0.55固定，无test调参。
- `runs_03/gt_snapshot/`：实际消费的7份GT及manifest冻结字节；`ARTIFACT_MANIFEST.json` 122文件完整SHA，`SUBMITTED_SOURCE_SHA.json` 五份新代码SHA。

详细结果见 [RF_MODEL_COMPARISON.md](RF_MODEL_COMPARISON.md)、[FUSION_GT_EVALUATION.md](FUSION_GT_EVALUATION.md)、[FRAME_PARITY_REPORT.md](FRAME_PARITY_REPORT.md)、[PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md)、[TRACK_EPISODE_EVALUATION.json](TRACK_EPISODE_EVALUATION.json)。0.5/0.75/1.0m三种匹配门均在各run JSON保存；precision只在协议声明零/单人的已标帧假定真人标注完整，不作全段精度声明。

## 候选模型结论

GT完整对象点集分类中，v2 S1训练样本FP由1216降至0，远场/静止test正例65/65保留；S6压力正例由71/71降至62/71。它不能代表实际候选簇表现。

实际FUSION当前确认track：近场行走已标召回v1 256/258=99.2%，v2 92/258=35.7%；远场行走v1 96/99=97.0%，v2 12/99=12.1%；S6 v1 61/71=85.9%，v2 42/71=59.2%。S8静止两版均51/53=96.2%，v2该会话FP观测51→26，但不足以补偿运动回退。候选不推广，不为了升级而调test阈值。

GT完整ROI与管线实际候选簇的点集分布差异是后续需验证的训练诊断假设，尚未证明为唯一根因。本轮不改聚类/跟踪/特征，也不扩大到新训练轮次或现场采集。

## 数据与外部变化

交接的831帧/2492对象/2420 PERSON与磁盘不符。最初实际832已标帧/2375对象，PERSON545、FURNITURE1464、BACKGROUND366；总录制2605帧，大量抽稀标注，不能把未标帧当无人。

S9最初V2 SHA与manifest匹配，但会话points SHA=64个a、缺meta；随后V2消失，manifest变为e2e V1。S1在样本读取完成后manifest改变并被移走。`01_external_gt_change.md`、train/runs失败日志、train_02/GT_AUDIT与runs_03/gt_source保留全过程。Codex没有写入gt_store或运行会污染它的e2e测试；不恢复/回滚其他任务改动。S9真实双人断点/ID switch BLOCKED，仅合成f1缺P2及gap守卫PASS。

GT `gt_level`为旧UNKNOWN/缺失，消费资格来自实际reviewed对象、schema及会话绑定校验；原字段未改。train_02保留读取时已验证的8会话样本及来源SHA，当前S1源不可复验，推广来源资格继续BLOCKED。

起止branch/HEAD为master/026e06303f60ed1bbe4ddc4d037836db68da6d27。before/after_final全部tracked/untracked文件SHA范围核对见 `SCOPE_AUDIT.json`。外部 `human_replay_lib.py` 改写及board_mode/deploy_board/pull_gt相关新文件不归因于本轮，也不回滚。v1、frame_feature、rf_person原SHA保持；运行期间算法/模型/输入SHA守卫通过。全树冻结S02仍BLOCKED，范围核对完成不洗掉外部变化。

最终快照又记录外部 `config.py`、`gt_server.py`、`gt_server_e2e_test.py` 变化；这些不由本轮修改，且不属于评估器导入路径。完整外部清单保存在SCOPE_AUDIT，五份提交源码在独审后再次核对SHA无变化。

## 检查与独审

命令/真实退出码见 `COMMAND_RESULTS.json`。训练01因S9不再有可用GT exit1；runs01因GT变化exit1；runs02因本轮运行期间补边界代码被源码SHA守卫拒绝exit1；均保留，未冒充有效证据。train02、runs03、GT JS检查、Python2检查、FUSION16、最终产物核验均exit0。

指定OpenCode默认DB/plan/opencode-go/deepseek-v4.1-flash：probe exit0/12.75s，独审exit0/315.64s，session `ses_ed9b3145dffeAnHifopu28e5gy`；原始JSONL及[独审全文](OPENCODE_INDEPENDENT_REVIEW.md)保留。独审独立复跑新JS/Python检查并查源码与产物。复审关于结束快照/退出码记录的附记见[CODEX_REVIEW_RESPONSE.md](CODEX_REVIEW_RESPONSE.md)。旧F0/F1/F2不回填，不靠测试总数宣布ACCEPTED。

## 未闭合

恢复并重新绑定S1/S9的可信冻结GT后，才能补对应真实指标；S9原f1缺P2须继续明确非完整标注。性能两项与候选运动回退保持FAIL/限制记录。缺独立家具/跨人跨景证据，仍不能推广；设备、物理、部署、采集全部NOT_RUN。
