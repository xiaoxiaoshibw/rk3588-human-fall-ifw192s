# HUMAN-UNIFY-FUSION-R2 会话契约与 Demo 统一验收 v1

2026-10-11 · writer: Claude Code · ISOLATED 研究轮 · 唯一 writer=Claude（本轮）。
范围：SESSION 契约归一 + Demo V1 深链/回退 + GEOMETRY 插件 + 全量确定性回归 + 浏览器实测。
生产 human_core/human_replay/Console 本轮零改动；无部署/采集/提交/推送。

| ID | 要求 | 结果 | 证据 |
|---|---|---|---|
| C01 | 分支差异审计：closeout worktree 相对 master 无未回流提交 | PASS | `merge-base --is-ancestor 347a5bf master`=true；`rev-list 347a5bf --not master`=0；逐文件 diff 仅 2 处（valid_sid 后缀/长度、message 空值）master 更严 |
| C02 | master 会话同步能力为准，closeout 无缺失行为需吸收 | PASS | closeout `session_selection.js` 仅接受裸 sid；master 接受受限后缀+限长100+严谨空 message，超集 |
| C03 | 无 sid 选最新有效；合法显式 sid 尊重；非法 sid 可见回退；损坏会话不作默认 | PASS | `session_adapter.js` choose()；`test_session_contract.js` 9/9（S01-S12镜像+F01/F02 SHA守卫）|
| C04 | S9(eligible=false/SHA不符)不作默认且显式标 UNKNOWN·⚠SHA | PASS | `/api/sessions` default_session=S8，`sha_mismatch=[S9]`；浏览器 option 标 ⚠SHA |
| C05 | GEOMETRY 作为可切换 detector 显式存在 | PASS | `detector.js` geometry→`geometry(post)`（detector层决策覆盖，RF分留scores.rf51对照，不伪装engine原生）；60帧decisions=HUMAN_CANDIDATE:110/NON_HUMAN:27 |
| C06 | RF51基线 + ≥1 替代模型可切换，同 Proposal 契约 | PASS | 6 detector 菜单；模型对拍 max_err=9.18e-8（6模型×200样本）；缺模型显式回退 PASS |
| C07 | 逆序拖动/切会话不污染 tracker | PASS | `./api/frame` generation 随 rewind/切会话递增；S9显式打后回S8 idx0 tracks=0 generation 递增 |
| C08 | Demo V1 真实浏览器端到端（非单测） | PASS | headless `--dump-dom --virtual-time-budget`：default/deeplink/badsid 三场景 counter/算法/回退全对，`LAB_E2E_UNIFY.json` 5/5 verdicts；截图 `DEMO_V1_UNIFY_E2E.png` |
| C09 | 统一回归全绿 | PASS | `run_unify_tests.js` 7/7：lab session/lab R5(2605帧/43联合)/lab 模型对拍/unique tracker/human_core R4审计/human_core 7套件/master S01-S12 |
| C10 | 生产/EXE/部署/采集 零改动 | PASS | 本轮仅写 sidequests/human_fusion_lab/（隔离研究区）；`git status pc_apps/` 的 M 全为上一轮 Codex 遗留，本轮未触碰 |
| C11 | Console 写死旧 sid 阻断项核实 | CLOSED | `dist/.../console.html` 两入口裸链无 `?sid=`；`session_selection.test.js:66` 断言 `doesNotMatch(html,/\?sid=cap_/)` 防腐回归。缺陷此前已修复，非本轮新修 |
| Q01 | 独立审查者验收 | NOT_RUN | 本轮自验 SUBMITTED，未 ACCEPTED；同 HUMAN-FUSION-R5-R8 规矩 |
| D01 | 设备/物理/现场识别验收 | NOT_RUN | 本轮纯本地隔离研究，无 RK3588/NPU/采集 |

证据根：`sidequests/human_fusion_lab/results/UNIFY_REGRESSION.json`、`LAB_E2E_UNIFY.json`、
`e2e_dom/{default,deeplink,badsid}.html`、`DEMO_V1_UNIFY_E2E.png`、`R5_TEST.json`、`MODEL_PARITY.json`。
已知限制：S9 双人/未标区间/陌生人员/独立家具泛化仍为 UNKNOWN；几何插件为 detector 层覆盖非 engine 原生几何模式。
