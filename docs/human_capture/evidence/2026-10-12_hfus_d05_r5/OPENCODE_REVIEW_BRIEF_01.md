# 指定独立只读审核 HFUS-D05-R05

仅read/glob/grep/list，不写文件，不运行评测，不调用网络/代理/生产。主控唯一writer。请先完整读取 D:/Code/ldiar/AGENTS.md、D:/Code/ldiar/docs/human_capture/README.md当前R05入口、C:/Users/30680/.codex/skills/ponytail/SKILL.md，返回实际技能路径。加载本指令完整内容，结束写 REVIEW_COMPLETE。

阅读 docs/human_capture/evidence/2026-10-12_hfus_d05_r5/ACCEPTANCE_V1.md、AUDIT_READY.md、BROWSER_VERIFICATION_V2.json、BROWSER_OPERATIONS_V2.json、BOUNDARY_COMPARISON.json、TOOLING_SOURCES_V3.json、MINIMAL_HUMAN_REVIEW.md、analysis_v2/COMPARISON.json、WIN_LOSS_INDEX.json、PERFORMANCE_PURE.json、PARITY_SUMMARY.json，各 FULL_*_EXIT 与REPLAY_CONTRACTS_EXIT/ENDING_BOUNDARY_EXIT。

源码 sidequests/human_fusion_lab_next/d05/r05/hook_bank_anchor.js、run.js、trace.js、analysis_v2/analyze.py、analyze_bank_events_v2.py、perf_bank.js、demo_v2/server.py与index.html、verify_browser_v2.py。检查真正加载 background/engine_b.js 及retention/tracker的依赖，勿把 core/engine.js当实际实验发动机。可以grep按完整连续片段定位大型ledger，不需要全文输出。

事实边界：control/anchor各九会话TOTAL2605帧，不是9×2605。control全部逐帧精确R04；42赢24输。远行67→84为27赢10输，后十次f43–52回退；near整体184→185但保护f220–224全部TP→FN，算法FAIL不晋级。家具FG高分误接受仍在，原直接retained刷新bank假设已证伪。R05 anchor far剩15FN=2首次确认+13混簇，不是无候选；H4 FG证明不等真人。候选union概率没有重建，Demo明确NOT_RECONSTRUCTED并展示真实model_calls/pre-PA。S9 INVALID_BINDING及未标帧UNKNOWN，不宣称真实ID/退出或负例晋级。perf控制8/9FAIL、新版6/9FAIL；旧R04PASS保留但本轮FAIL，未证明时差因果，不冒充板端。

浏览器tab4真操作26行，3个loading观察排除，23已加载状态九会话同帧同stamp/SHA、console[]；label nine_near220_control实际f51，按实际frame核查，不当220成功。正式near220_control_verified与near220_anchor_actual均实际f220。v1显示错误、跨tab标签错误、分析枚举/NULL错误、浏览器验证器SHA项数错误均保留失败源/exit/log并在新v2修工具，不覆盖原账。原TTL秒再入raw标签不完整由v2派生audit同时检查秒/帧TTL；源码raw不改。

结束全树扫描exit0，BASELINE15463tracked/untracked/ignored，非原子、.git排除；新文件扫描后还追加，结束增量SHA后另回传。不得假定此时已具备最终返回文件。当前审核完成前不得用旧R04审核认定R05完成。

请按P1/P2明确指出工程缺陷、证据不支持的宣称或漏掉的反例，给源码/文件行号及最小修复；另分别裁定工程材料、算法、GT资格、生产接入。正常算法失败不是可伪造PASS的理由。若没有阻碍可审查交付的工程缺陷，可说明，但绝不ACCEPTED。下一轮条件修正尚未运行且有far41 .411m有害更新反例，不能给它成果结论。
