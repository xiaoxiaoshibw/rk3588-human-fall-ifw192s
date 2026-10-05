# GL-I03 R1紧凑实施续接（同指定model/defaultDB、新session）

此为Codex当前放行，覆盖此前要求直接读取仓库外技能路径的措辞：请用原生 `skill(name="ponytail")` 完整读取已安装ponytail并记录工具返回的实际路径，不再read外部 `.codex/skills` 路径。不要更改权限/配置/auth/DB/model。你是唯一生产writer，model opencode-go/deepseek-v4.1-flash/defaultDB，新紧凑session；原长session保留，不重新诊断/协议调参。fresh无工具probe成功后才派此提示。

先读唯一 `docs/human_fall/GLI03_ACCEPTANCE.md` v1、WORKFLOW v2、本轮evidence/04_DESIGN_REVIEW.md、RETURN_TEMPLATE.md。完整矩阵已经阶段一实现前诊断并审查，首尾changed=[]；原wrapperSHA4a4fd0c733cdd608b42c3a11ef926b8c2041a795b1dbdfde3ef826542cad9a3a、原GLI02tests0dad5771f1ac68a175c2075ffe8f8a49e64b50dfce104fc62adf6d499206a9b0。冻结geometry_constrained.yamlSHA1c42c1534cb4ee1a110db44140a59df40f31f985028be4015828495f57267880；master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6。

只改三个生产文件：

1. `src/human_fall_detection/scripts/evaluate_gli02_candidate.py`：可选--constrained-config默认None。None保持resolve_constrained_settings(None)；显式路径在candidate执行处调用_load_constrained_settings，复用sensor_health.load_config和ground.resolve_constrained_settings。mapping顶层/ground_constrained，读取/语法/结构/unknown/非法数值转既有捕获错误、exit2无candidate不fallback；仅捕获边界真实异常，不吞编程错误。emit-draft不消费config，prepared优先/人工draft/gate/exclusive输出/source/physical维持。
2. 新`config/geometry_constrained_gli03_r1.yaml`：复制冻结全文，只spatial_cell_m0.20→0.05/max_points_per_cell4→8，其余键/阈值/预算不变，不默认启用。
3. 新`tests/test_gli03_candidate_override.py`：复用原synthetic fixture，集中CLI成功/配置负例/默认隔离与独占检查，不改旧tests/assertions。

不能写core/其它已有config/原tests、driver/webui/data/captures/pc_apps/HR/旧证据/状态文档。所有新证据只放`docs/human_fall/evidence/2026-10-03_gl_i03_r1/`新文件；已有证据不覆盖。03diag脚本可只读复用但不能覆盖旧输出；无需再读全部历史或整git status。

重要已审诊断：真实NPZ为`docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz`，审定draft为该目录`codex_review_01/work/filled_real_draft.json`；用户up_axis[0.438371,0,0.898794]/height[1.2,1.7]/四区不动。fit1214；defaultsampled80→insufficient；两值变体sampled1193→ground_degenerate（828角度+2高度拒，未进SVD）。只两值不能产真实candidate，K04 REAL BLOCKED，不能改先验/ROI/第三参数/数学/门来通过；也不自动R2。软件接线安全目标仍可完成。ground.status只有valid产candidate；其它状态exit2无artifact，物理false/无ground_derived/source分层。

逐K/P自验按v1：新synthetic/显式冻结/默认/坏path空path坏YAML非mapping缺sectionunknown bool NaN negative floor；重复CLI/同路径改内容/对象不污染默认/已有output字节不变；原GLI02、GLI01、ground回归；真实上述两次CLI落本轮新output（均应exit2无candidate，分别insufficient/degenerate）。Python3.8 AST兼容单列，不冒称设备。

结束按RETURN_TEMPLATE追加`docs/human_fall/returns/GL-I03.md`：SUBMITTED/BLOCKED、实际session/model/defaultDB、native ponytail路径、验收v1/SHA、每K/P/B/D分层、原始命令exit/日志、三file完整SHA/冻结SHA、真实candidate未闭合。不要写验收结果列/工单/WORKFLOW/README/DISPATCH/REVIEW_LOG或ACCEPTED。停写并明确交Codex独审；不reset/checkout/clean/commit/push/设备/部署/采集/网络/GL05。
