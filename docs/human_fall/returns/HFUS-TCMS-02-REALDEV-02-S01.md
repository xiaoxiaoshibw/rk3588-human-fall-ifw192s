# HFUS-TCMS-02-REALDEV-02-S01

## 本轮信息

- 工单/轮次/执行者/时间：HFUS-TCMS-02-REALDEV-02-S01/r1/Codex唯一实现writer/2026-10-17。
- 唯一验收：docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s01_r1/ACCEPTANCE_V1.md，SHA e59479755053eb64c3a4b44ae0ee07c18610fac5de404b720c87871ef290348c；协议v1 SHA 589a103b3e357241b504d2892a8d10566adcd005105fae24db59d069ad007d72。
- 执行方式/模型：本机PowerShell、Python3.12/NumPy1.26.4/psutil7.2.2、Node、真实Codex IAB；系统身份GPT-6，精确运行ID不可得，未切模型。两个助手只读，无OpenCode writer派发。
- 策略：RESEARCH=测量定义及未知几何；ENGINEERING=坐标、来源、回放。实际读取ponytail路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific路径 C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。
- 状态：**SUBMITTED，非ACCEPTED，源码停写**。软件逐C作者自验见下，正式独审NOT_RUN；物理/设备/效果分别保留。
- 起始branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a，原脏树保留；30965 tracked/untracked逐SHA基线与最终保护见BASELINE_FILES/PRESERVATION_SUMMARY。输入SHA与输出MANIFEST独立，不把data当工作区。

## 集中诊断与根因覆盖

| 缺陷/ID | 根因 | 入口/消费者 | 修复/证据 | 保留行为 |
|---|---|---|---|---|
| OB06/07及C02 | 符号、距离变量、行对分母与结论越界 | 旧E1五态/公式与三报告 | 新MEASUREMENT_RECHECK、CORRECTIONS | 旧协议/旧PASS/旧失败不改；旧holdout门不动 |
| C03/05/06 | r01仅RAW，未完整应用R/t | 当前源/M0/候选/框/轨迹 | 新r02坐标适配与full_final | 冻结成员/关联/分母/旧失败不重跑 |
| C07/08 | 输出和变换未绑定、迟到回包、顶层RAW版本歧义 | 服务启动/frame/source/surface及页面 | INDEX/tag绑定、serial/fi/version守卫、source_payload；定向测试 | 无身份/物理资格提升；候选/OFFLINE_REVIEW |

## 实际变更

| 文件 | 用途/用户差异区分 | 提交源码SHA |
|---|---|---|
| sidequests/hfus_tcms_02/realdev/r02/app.js | 新增隔离实现/验证；旧源码不动 | 623d42cab87f4365d88f2bd80f9e623a62d9ca8ebf39fdf2f67986f9c2d1f1f6 |
| sidequests/hfus_tcms_02/realdev/r02/bootstrap.py | 新增隔离实现/验证；旧源码不动 | d880edd8de1185828f9d89445022d313143dcf2c975d5152ea14011a73a03c64 |
| sidequests/hfus_tcms_02/realdev/r02/browser_contract.test.js | 新增隔离实现/验证；旧源码不动 | 84d18770180cb358a492ecd5d480f0abac89578a5966d612de11fd06504c707f |
| sidequests/hfus_tcms_02/realdev/r02/command.py | 新增隔离实现/验证；旧源码不动 | 6ac9b916d1b8f6e1ed1a278a19a561be8b851c02a44cc38dfe419e68d69de343 |
| sidequests/hfus_tcms_02/realdev/r02/coordinates.py | 新增隔离实现/验证；旧源码不动 | cd19a4923c0340c801db569d0f1940d25c61d536bdcc354efb6780ef7f7b460f |
| sidequests/hfus_tcms_02/realdev/r02/index.html | 新增隔离实现/验证；旧源码不动 | 1486f1b7b4d97e8e9e0c90446f1a1dc1fc2c5ef4828f3d258b8fb3fc9aa68d1b |
| sidequests/hfus_tcms_02/realdev/r02/preview.py | 新增隔离实现/验证；旧源码不动 | 77a0896feca33ed643d67f60603c1cd3b1d02be2833480e1382fe494c1d8ea2a |
| sidequests/hfus_tcms_02/realdev/r02/process.py | 新增隔离实现/验证；旧源码不动 | 1e9c300100f2b2461d2f2aa748cea1fb6810a6df223be6faf997d848ae005e11 |
| sidequests/hfus_tcms_02/realdev/r02/README.md | 新增隔离实现/验证；旧源码不动 | 74fa897816e355ac6aaa545b4726806ca34d92f40b7cf297bb62facdec070ce9 |
| sidequests/hfus_tcms_02/realdev/r02/recheck_measurements.py | 新增隔离实现/验证；旧源码不动 | 78fe523ca2347801807d8a9e47d7817c285b34f44878b94e1d261aacf46a9c97 |
| sidequests/hfus_tcms_02/realdev/r02/regression.py | 新增隔离实现/验证；旧源码不动 | 3b6beb816da7a9d71c00bd484dcf505cb8d6e9ed9dab73edf734dfb748f73376 |
| sidequests/hfus_tcms_02/realdev/r02/server.py | 新增隔离实现/验证；旧源码不动 | cb6ca44a234a0c2d8921eee0821df13dda18e8174ae90b7c09ff076a76e24095 |
| sidequests/hfus_tcms_02/realdev/r02/test_coordinates.py | 新增隔离实现/验证；旧源码不动 | 08e335bb6afe74807ef1683d28cebe5c4463deb420aecd09dccd2f173accf5da |
| sidequests/hfus_tcms_02/realdev/r02/verify.py | 新增隔离实现/验证；旧源码不动 | 53abb50c78ae9963439ad16d748ded3004b5073ad14db53bf663306033e96d15 |

新证据仅本项evidence，回传本文件；WORKFLOW顶部追加实际授权/收口、REVIEW_LOG末尾追加开发期检查。历史原文保持字节一致；data/生产/模型/GT/旧源码与旧证据只读。输入28B只解XYZ；尾16B opaque。米；列R@p+t/行p@R.T+t；源与版本变化拒绝复用输出/身份。

## 逐条验收

| ID | 作者自验 | 覆盖与边界 | 证据 |
|---|---|---|---|
| C01 | PASS | 30965 tracked/untracked基线全SHA复核，源双SHA/size/mtime一致；data只读、输出新根；WORKFLOW/REVIEW原文分别suffix/prefix保持。 | BASELINE_FILES.jsonl、PRESERVATION_SUMMARY.json、full_final_SOURCE_SHA.json |
| C02 | PASS | OB01–10逐ID复核；新定义/符号勘误，旧OB FAIL/旧PASS均不回写。 | MEASUREMENT_RECHECK.md、measurement/CORRECTIONS.json |
| C03 | PASS | 完整历史R/t及report SHA匹配，不用nominal_R、不新拟合；方向/米/源/版本绑定。 | TRANSFORM_V1.json、PROTOCOL_V1.json |
| C04 | PASS | 错误方向/反射/非正交/参考退化/错frame/重复配平/版本拒绝；det=1，正逆与z方程。 | math_final.stderr、FULL_DIRECT_CHECK.json |
| C05 | PASS | 全部780帧38298918行；29049839有效、9249079无效/零，原始行序/opaque/raw28和双XYZ可查。 | full_final/FRAME_CHECKS.jsonl、FULL_DIRECT_CHECK.json |
| C06 | PASS | 适用冻结对象全部数值转换；1371候选1098901成员；35033面7181833支持行，八角OBB、冻结轨迹/预测；无重跑。真实速度/完整协方差字段不存在，实测分支NOT_RUN，合成公式通过。 | FULL_DIRECT_CHECK.json、full_final/map/MAP.json、math_final.stderr |
| C07 | PASS | 15帧实际IAB、画布点选430/37881、0行不动、M0支持反查、4相机；HTTP15帧+6负例，最终静态字节绑定。 | BROWSER_RESULTS.json、BROWSER_*.jpg、HTTP_CHECK.json、DELIVERY_BINDING.json |
| C08 | PASS | 候选/OFFLINE_REVIEW；无身份/几何/物理/runtime资格，无物理身高/硬删；193前不显图；版本/迟到包拒绝。 | math_final.stderr、js_race_final.stdout、BROWSER_RESULTS.json |
| C09 | PASS | 17新Python+25/17旧断言+5旧测量+JS契约；最终全量107.47s，RSS/全项输出低于预算。 | *.command.json、full_final/SUMMARY.json、MANIFEST.json |
| C10 | PASS | 实际命令工具导出、日志/失败、源码冻结、SHA清单、回传和正式只读复审交接。正式复审本身NOT_RUN。 | ACTUAL_COMMAND_EXPORT*.json、COMMAND_RECORDS.md、MANIFEST.json、HANDOFF.md |


详尽命令/exit/耗时/RSS和原日志位于COMMAND_RECORDS、*.command.json、ACTUAL_COMMAND_EXPORT；源meta=eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4，points=254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1。唯一输入development_seen/dev-tainted，非独立D。

回归：17新Python、25PREDEV/17REALDEV旧断言（仅fixture IO迁移）、旧测量5、JS纯契约/handler/语法，均exit0；HTTP15帧+6负例；浏览器15指定帧、原生点选、4相机和支持反查。全780帧38298918行，独立公式往返6.466e-15m；最终全量107.47s，预算通过，失败及旧服务错误保留。

## 未闭合与限制

- 本轮C自验无未通过项；不能换算PLAN G05/G06整体PASS，逐G NOT_RUN见REPORT。S1仅旧R/t冻结诊断分支，不是S1整体完成。
- 地面身份/本段空间时间几何/物理高度/独立D BLOCKED；人体效果NOT_RUN/BLOCKED；设备NOT_RUN。解除条件见REPORT，不自动派发后续。
- 真实冻结资产无速度/完整协方差字段，真实数值项NOT_RUN；适配器合成覆盖，不伪造输入；M0噪声矩阵为对角代理。
- 旧带/全场残差均非审核地面质量；旧mask415格勘误不提升身份。并集增长与理论概率不等于实测人体能力。
- 初次full缺运行前代码SHA如实保留；最终full_final已前置冻结且持久数值SHA完全一致。准备工具超长输出既有截断保留，命令原记录后来导出，不倒填过去独立日志。

## 交给Codex独立复审

- 现行验收/根因/全入口证据：ACCEPTANCE_V1、PROTOCOL_V1、REPORT、MEASUREMENT_RECHECK、READONLY_ASSISTANT_CHECKS。
- 源码差异/SHA：AUTHOR_CODE_FREEZE、MANIFEST、PRESERVATION；输出SHA链FINAL_SEAL.sha256→FINAL_SEAL→MANIFEST。
- 原日志：*.stdout/*.stderr/*.command.json、ACTUAL_COMMAND_EXPORT、FRAME_CHECKS、BROWSER_RESULTS及截图。
- 正式独审NOT_RUN；按HANDOFF在fresh Codex会话只读复审，不把本人/助手自验称独审。当前下一步仅独审；本轮停止，不S2/S3/人体/E2–E4/训练/HR09/设备/部署/采集/驱动网络/Git写。
