# GL-I03 R1阶段二 / Codex设计门放行

先完整读本轮 `evidence/2026-10-03_gl_i03_r1/04_DESIGN_REVIEW.md`、现行 `AI_PROMPT_GLI03_OPENCODE_R1.md` 和唯一 `GLI03_ACCEPTANCE.md` v1。确认已完整读取ponytail，回传记实际路径。阶段一已停写，Codex全manifest changed=[]，本轮fresh probe成功后才续接此提示。

只实施三个生产白名单：wrapper可选显式config入口、新geometry_constrained_gli03_r1.yaml（只两值0.05/8）、新test_gli03_candidate_override.py。不改原GLI02 tests或任何冻结文件。helper放candidate路径，None默认不变、emit-draft不消费config；显式空路径/坏路径/坏YAML/非mapping/缺section/非法参数exit2无candidate不fallback。不要广泛吞Exception。load_config返回值检查+resolve复用，最小根因修改。

设计门明确真实0.05/8仍ground_degenerate，不改变up_axis/ROI/阈值/数学以通过。不承诺真实candidate，不掩盖BLOCKED。只跑既定输入offline CLI并记录exit2/无candidate及sampled1193；physical=false和source分层。没有下一轮调参/采集/部署/网络授权。

按v1逐K/P自验，覆盖配置错误/重复调用隔离/默认/显式冻结与变体/独占输出/原gate/capture只读；原GL-I02+GL-I01+受影响ground回归，必要旧24探针用本轮新路径，旧证据不覆盖。本机环境与目标Python3.8 AST/设备分开。日志全部落本轮新文件，真实命令/exit和完整SHA留档。

按RETURN_TEMPLATE追加returns/GL-I03.md，状态只能SUBMITTED/BLOCKED，逐K/P/B/D分层结果、ponytail路径/实际session/model/defaultDB、范围/sourceSHA/config唯一两值差、所有冻结SHA，真实candidate限制。验收表/工单/状态文档留Codex更新，不写ACCEPTED。结束必须停止writer供独审。
