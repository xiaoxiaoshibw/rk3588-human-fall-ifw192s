# P03 R1 Codex 独立终审 / 范围硬门收口

- 日期：2026-10-05（Asia/Shanghai）
- 角色：`CODEX_FINAL_REVIEW / INDEPENDENT`
- 状态：`SUBMITTED`（待用户确认；不回填验收表现行列）
- 唯一判据：`P03_ACCEPTANCE.md` v1，P03-A/B/C/D/E、S01、D01。
- 最终整体建议：**REWORK**。范围硬门 FAIL，未完成算法逐 ID 验收，不能宣称软件 ACCEPTED。

## 结论与停止依据

当前 `pc_apps/console/dist/Console.exe` 已包含 P03 最终提交版本，与“console exe 不重打包”的明确边界不符。独立读取 CArchive 数据成员，不启动 exe、不执行内嵌代码，得到以下结果：

| 成员 | 当前 exe 内嵌 SHA256 | 与 P03 当前源码逐字节一致 |
|---|---|---|
| human_replay/leveling.py | cd0ef407916f1b24ff66303236bdd6ad8f2e8af94d7221f9b45688e92e7da148 | 是 |
| human_replay/leveling.js | 6ad79b1c99f5bfe13fa5d097bf56ac2f193c09492103bde27b0e69bd599f6abd | 是 |
| human_replay/leveling.html | 49e97085060daa4d36f8e918c09faa835193865869c1c0cac7cee9216e0b2d7f | 是 |
| human_replay/replay.js | b7ed9c8dea71ce234e83e36f1170ceb2364b59a4083f6efbb14aee3e35939b20 | 是 |

当前 exe 为 **64427868 bytes**，SHA256 `4a31b3c9b1d913c8edf9dda9717d90f293fae24f05bc36eecf1d1c2ebf337b36`，文件修改时间为 2026-10-05 14:31:10（本机显示）。旧 GL-W01 诊断包内 leveling.py 为 `05b234ea...e101072`，逐字节匹配 GL-W01 `22_final_source_sha.json` 记录；旧 leveling.js/html 也匹配其记录，均与当前 P03 内嵌文件不同。这是 P03 代码已进入打包程序的证据，不依赖作者声明或文件时间单独推断。

**基线身份说明：** GL-W01 最终 SHA `463889ef...19d2203` 对应 `pc_apps/console/dist/gl_w01/Console.exe`，该文件本轮实查仍匹配原记录。它不是旧 `dist/Console.exe` 的写前快照；07_boundary_checks.json 中的 `previous_exe_sha256` 应读作 GL-W01 参考包 SHA，不能据此断言同一路径从这个 SHA 被改写。本次阻断的直接证据是当前 dist/Console.exe 已内嵌新增 P03 源码。旧诊断包只用于确认旧源码版本。本轮未损坏或替换任何包。

目前证据**不能确定打包动作的执行者**，也没有本会话对这一动作的额外授权。不把它归咎于 Claude Code，不把共享脏树的所有差异归为 P03。但作者报告/manifest 声明“console exe 不重打包”与当前交付事实不一致，必须先澄清并收敛提交边界。

用户终审提示 §1.2 明确要求：“若越界：直接 REWORK，写明越界文件，不继续逐 ID”。该条件已命中，优先于 §2 的一般全表执行要求以及 §5 的至少三项算法独立检查要求。因此后续 suite、坐标语义反例、transform 篡改 HTTP、manual 对照均 **NOT_RUN**。未用作者测试替代独审，也未将未跑项标 PASS。

## 逐 ID 结果

| ID | 结果 | 要求来源与预期 | 本轮触发/实际结果 | 根因/最小返工或恢复建议 |
|---|---|---|---|---|
| P03-A | NOT_RUN | v1 P03-A；纯函数候选门、3会话锚点、K=3～8及名义系 ROI | 范围门先失败；未执行 auto suite/真实会话/坐标反例 | 先解决范围；之后完成包括第三会话的独立核验；不改门 |
| P03-B | NOT_RUN | v1 P03-B；显式 invalid、可回手动、不降阈 | 未执行 n_z=.84、d=.5、ROI不足负例或前端状态检查 | 范围恢复后逐例实跑；当前无独立 PASS 证据 |
| P03-C | NOT_RUN | v1 P03-C 及表头人工确认；一次性变换、旧会话兼容 | 已初步阅读 load/fetch，但未执行 HTTP/e2e/SHA 篡改/Node 检查 | 保留用户确认语义和回放入口要求，后续集中验证；本轮不基于初读下算法结论 |
| P03-D | NOT_RUN | v1 P03-D；同域三法 seed20261001/861/.05、R2差值如实公开 | 已读 compare/ransac/detect，但未运行 auto job/检查实际 report 数值 | 范围恢复后完整记录三法与真实会话对照；不以作者 AUTO_ANCHOR 代验 |
| P03-E | NOT_RUN | v1 P03-E；suite和GL-W01 manual行为保留 | Python/Node未跑；manual旧6字段路径未做独立对照 | 范围恢复后从已保留旧包源码进行 manual 结构/产物对照 |
| S01 | FAIL（范围）；其余 NOT_RUN | v1 S01范围自验、声明；终审提示§1.2硬禁止 console 重打包 | CArchive直接读取发现四个P03成员逐字节一致；边界脚本 exit1 | 交付范围和实际二进制不一致；补真实动作/授权来源和提交清单，先收敛为批准范围；不得自行删除/回滚包 |
| D01 | FAIL（打包边界）；设备/部署运行 NOT_RUN | v1 D01和终审提示§1.2/§2 D01；不重打包、不设备/采集/部署等 | 本审未进行任何设备/部署动作；当前exe包含P03代码，与不重打包边界矛盾 | 不以预期NOT_RUN掩盖实际边界失败；打包归属/授权及修正由用户确认，未归因执行者 |

提示要求的 D01=NOT_RUN 是未执行设备/部署的预期记录。本次**设备运行层仍 NOT_RUN**，但范围核查实际出现了“不得重打包”反证，因此该边界如实 FAIL；这是同一 v1 要求的失败，未提高验收门槛。

## 范围检查

1. HEAD/branch：`master / 3fc1338fc306444959433a41bdeaeefd705f58ec`，与作者 manifest 一致。
2. P03 `13_SHA.txt` 的16项源码/文档/旧证据全部匹配；`14_MANIFEST.json` 已读取。说明源码提交身份明确；SHA匹配不能免除范围失败。
3. 共享树原有 tracked 与 untracked 差异完整保留，见 06_scope_status.txt；`src/human_fall_detection/` 的 untracked 文件参与首尾记录。没有 reset/checkout/clean/commit/push。
4. `git diff --stat` 因 Windows `src/CMakeLists.txt` reparse/symlink 表示报 exit128；保留失败快照。追加排除这一个路径的 stat（exit0），未修复/替换 symlink；untracked 范围由 status 与 SHA 补足。
5. 旧包与当前包的 annotator、quality、三 estimator 源文件及其余主要 replay资源一致；一个 __pycache__ 成员不同，不把缓存差异作源码违规证据。未发现足以归因 P03 的 driver/src/webui变更。此结论不等于这些脏树文件相对HEAD无差异。
6. 本审仅写本 evidence 子目录和最后追加 REVIEW_LOG；源码/测试/原captures/历史证据/包/验收表/DISPATCH均未写入。

## 首尾 SHA

- `01_sha_before.txt` / `02_sha_after.txt`：各记录4437个 tracked/untracked 文件及显式 ignored exe和原session meta/bin；SOURCE清单16项首尾均匹配作者SHA，HEAD不变。
- P03提交、leveling依赖、当前exe、原captures及旧证据首尾没有变化，范围证据有效，无需重复受影响算法检查。
- 两个不属于P03范围的文件在期间被外部修改：`文档收集（人工）/跌倒检测文献/README.md` 和同目录 `manifest.json`。首尾值均保留；本审未写它们，也没有使用它们作为判定依据。该外部变化不使本次exe范围证据失效。
- `src/CMakeLists.txt` 的 WinError1920首尾同样记录；未将不可读取路径伪报成成功hash。
- REVIEW_LOG追加发生在after快照完成之后，是本轮明确授权的唯一范围外文档写入。

## 命令、技能与未跑项

ponytail **full** 实际已读取：`C:\Users\30680\.codex\skills\ponytail\SKILL.md`。作者报告声明路径 `C:\Users\30680\.claude\skills\ponytail\SKILL.md` 已在本轮报告中核见；不冒称核验作者当时读取行为。

执行命令与真实退出码详见 08_commands.md；`05_independent_checks.py before/after` exit0，boundary exit1是明确scope FAIL而非脚本崩溃。Python环境盘点为3.12.10 / NumPy1.26.4，未安装任何依赖。03/04日志明确保存NOT_RUN和N/A，不能读成测试失败或测试通过。

| 层级 | 本轮状态 |
|---|---|
| 本指定 Codex 独立终审 | 已执行范围门、提交身份和首尾核对；SUBMITTED / 建议REWORK；算法全表未执行 |
| Python作者suite独立复跑 | NOT_RUN |
| Node suite/页面请求检查 | NOT_RUN |
| 坐标语义 / transform SHA篡改 / manual旧路径三项独立检查 | NOT_RUN（范围硬门停止） |
| 真实browser | NOT_RUN；未借用作者headless截图冒称本轮浏览器验证 |
| 设备/采集/部署/板端网络/driver验证 | NOT_RUN |
| Console启动/重打包 | 本审NOT_RUN；仅只读取现存archive，发现打包边界FAIL |
| 物理/外参/runtime资格 | 未验证；未升级任何资格标志 |

## 返工集中建议与后续审查

首先澄清当前 `dist/Console.exe` 的打包来源及是否存在独立授权，提交准确的范围/动作清单；若无授权，按批准范围提交，不自动覆盖或删除当前共享包。保留本次SHA与全部旧证据。仅用户确认不能替代后续算法审查。

范围恢复后仍需按原v1完成全部ID。预读的待核点包括：回放选择会话是否实际启动/复用auto流程，auto设置ground_confirmed=True是否绕过人工确认，第三会话、research_display输出及实际report差值是否覆盖；这些是既有要求的待核事项，**本轮不将初读推测充作算法FAIL或新增需求**。坐标语义、transform完整性、manual对照仍须独立复现。

本轮未派返工writer或后续工单。验收表“当前结果”和DISPATCH不动；完成REVIEW_LOG追加后停写，等待用户确认。
