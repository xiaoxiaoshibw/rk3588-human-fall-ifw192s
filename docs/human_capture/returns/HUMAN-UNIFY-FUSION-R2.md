# HUMAN-UNIFY-FUSION-R2 回传

SUBMITTED / 未 ACCEPTED。2026-10-11 用户输入 HUMAN-FUSION-UNIFY-R1 连续实施提示词（主干统一/算法可插拔/历史分支选择性吸收/生产与研究隔离），授权连续执行不逐阶段暂停。本轮 writer=Claude Code。

唯一验收 ../HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md v1；统一回归证据 `sidequests/human_fusion_lab/results/UNIFY_REGRESSION.json`（7/7）；浏览器实测 `LAB_E2E_UNIFY.json`（5/5）+ 截图。

## 集中诊断结论（分支真相）

不存在可整体 merge 的两个分支。**SESSION-SYNC-CLOSEOUT 是 detached worktree**（`ldiar-session-closeout @ 347a5bf`），`347a5bf` 是 master(026e063) 祖先，`--not master`=0：git 层已无未回流提交；逐文件 diff 仅 2 处，master `session_selection.js` 为超集（受限后缀+限长100+严谨空 message）。**会话支线已被 master 吸收，且 master 更严**。HUMAN-FUSION R4–R8 不在分支上，就在 master dirty tree + untracked `sidequests/human_fusion_lab/`。融合的真实形态=给 lab 接契约适配层，非 merge。

## 本轮变更（全部在隔离研究区 sidequests/human_fusion_lab/）

- 新增 `session_adapter.js`：移植 master choose() 语义为后端纯函数，特化 S04→SHA 守卫（sha不符会话不作默认、显式仍可浏览标 UNKNOWN）。
- 新增 `test_session_contract.js`：S01-S12 镜像 + F01/F02，9/9 PASS。
- `server.js`：`/api/sessions` 走 choose() 暴露 default_session/sha_mismatch/sha_ok；`/api/frame` 非法/不存在 sid 走契约回退消息。
- `demo.html`：`?sid=`/`?model=` 深链，非法 sid 显式回退提示，SHA 失格会话标 ⚠SHA。
- `detector.js`：新增 `geometry` 插件（detector 层决策覆盖，标 `geometry(post)`，RF 分留对照，不伪装 engine 原生几何模式）。
- 新增 `cdp_e2e.js/cdp_probe.js/cdp_eval.js`（CDP 探针）、`dom_extract.js/dom_summary.js`、`build_e2e_artifact.js`、`run_unify_tests.js`（7/7 统一回归）。
- `results/DEMO_CONFIG.json` 注册 geometry（六 detector）。

## 自验逐条

见验收表 C01-C11。关键实测：默认=S8(非SHA失格S9)；深链 sid+model 尊重；坏sid回退；generation 随 rewind/切会话递增（tracker 不污染）；geometry/rf51_baseline/xgb69 60帧决策分布各异（插件真可切换）；R5 2605帧/43联合对拍 PASS；模型对拍 max_err 9.18e-8；headless chrome 三场景 DOM/截图真实渲染（候选 c-95/t-73 ✓ 等）。human_core 全套件 7/7、master S01-S12 全绿。

Console 写死旧 sid 阻断项：**CLOSED**——dist 与源码 console.html 均无 `?sid=`，`session_selection.test.js:66` 断言防腐。非本轮新修。

## 未闭合 / 诚实声明

- Q01 独立审查 NOT_RUN → 本轮 SUBMITTED，不称 ACCEPTED。
- D01 设备/物理/RK3588/NPU NOT_RUN；无现场识别验收。
- S9 双人、未标区间、陌生人员/独立家具/新场景泛化 UNKNOWN（承袭 R5-R8，本轮未新增 GT/采集）。
- geometry 插件为 detector 层覆盖，非 engine 原生 FUSION 几何模式（engine.js:100 原生未实现）；不用于生产判定。
- 生成式 CDP `Runtime.evaluate` 在本机 Chrome154 headless 两实例返回 500（环境死结）；浏览器证据改用 `--dump-dom --virtual-time-budget` 独立路径，正功能已证，interactive CDP 自动化受限标注。

复审入口：验收表 + `results/UNIFY_REGRESSION.json`、`LAB_E2E_UNIFY.json`、`e2e_dom/*.html`、`DEMO_V1_UNIFY_E2E.png`、`R5_TEST.json`、`MODEL_PARITY.json`。
