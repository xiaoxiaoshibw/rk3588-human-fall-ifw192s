# HFUS-TCMS-01 回传

## 2026-10-16 r1 本轮信息

- 执行者：Codex唯一writer；用户“开始开发”授权隔离实施，附件中的仅规划要求不作为阻止本轮实施的命令。
- 状态：SUBMITTED；人体效果BLOCKED，设备/物理/独立复审NOT_RUN，非ACCEPTED。
- 当前唯一验收：[TC01–TC10 v1](../evidence/2026-10-16_hfus_tcms_01_r1/ACCEPTANCE_V1.md)；SHA256 `b9db77bd089f9c328956610bb6981ea467945a6f787730c9fb7964cd4f0d8037`。
- 起点：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；tracked+untracked共12950路径SHA见BASELINE。结束保护检查仅docs/human_capture/README.md有外部并行差异，本项未写它；本项仅在检查后追加WORKFLOW/REVIEW_LOG记录，不覆盖历史。
- 技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（已读/full）；`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`及matplotlib参考技能。执行Python3.12.10 / NumPy1.26.4；无新增依赖、CLI/代理派工、模型切换。

## 集中诊断与根因覆盖

[00_DIAG](../evidence/2026-10-16_hfus_tcms_01_r1/00_DIAG.md)：已有时序模块均从候选开始；本项从RAW建立噪声与支撑解释，不重复HMM。固定RAW避免不可信配平高度；源缺失不取代理；UNKNOWN不变free；原数据只读。矩阵涵盖startup/空帧/缺支撑/gap/非法时间/新会话/caller集合修改/非法layout/截断/重复输出/首尾源漂移；原生产入口与其他工单保留。

## 实际变更

| 文件 | 用途 | 用户差异区分/版本 |
|---|---|---|
| sidequests/hfus_tcms/tcms.py | 命中支撑、双窗、静态/有限平移解释、CAL门 | 全新目录；主执行源码SHA见run_r1/MANIFEST |
| run_experiment.py | 9源绑定/6配置/输出账本/首尾保护 | 同上 |
| audit_static.py | 同体素漂移、命中率、条件点数方差 | 新离线工具 |
| verify_run.py | 全候选源行核对及前缀重算 | 新验证工具；最终VERIFICATION在run_r1内，父目录初次结果保留 |
| plot_report.py / test_tcms.py / README.md | 图表、边界验证、复现入口 | 新目录；最终源SHA见DELIVERY_SHA |
| 本轮evidence / WORKFLOW / REVIEW_LOG / 本回传 | 新证据与追加记录 | 不修改旧证据/旧回传 |

## 逐条验收

| ID | 类型 | 结果 | 检查与证据 |
|---|---|---|---|
| TC01 | offline | PASS | 12950路径首尾保护；18源+3执行代码SHA一致；BASELINE/FINAL_TREE_CHECK/run_r1/INTEGRITY |
| TC02 | synthetic/offline | PASS | 六项边界测试exit0；meta/layout/time/stride/成员验证，TEST_FINAL |
| TC03 | synthetic/offline | PASS | UNKNOWN/gap/reset/caller mutation、首帧和小支撑测试 |
| TC04 | synthetic/offline | PASS | 合成静态/平移、1672帧前缀重放；VERIFY exit0；尚无三窗持续性 |
| TC05 | offline | PASS | 连续FIT[0,90)/CAL[90,181)/REPORT[181,272)，独立窗口状态；阈值不使用REPORT/动作GT |
| TC06 | offline | PASS | 2206源帧×6=13236记录；NOISE/STATIC_AUDIT/SUMMARY/plots；主实验exit0，484.65秒 |
| TC07 | offline | PASS | 831区域、24499点成员关系全核对；源行可回查，全UNKNOWN |
| TC08 | semantic | BLOCKED | 动态人工GT/独立采集组不足，人体P/R/恢复/纯度无法证明 |
| TC09 | research | PASS | RESEARCH_AND_GATES、REPORT；主来源链接/许可/扫描差异/失败退路与人工包 |
| TC10 | device/physics/review | NOT_RUN | 未进行设备、物理、采集部署或独立复审 |

## 未闭合与限制

空场B3区域激活0–0.067%，动作输出也稀疏（082829在0.12m/W5仅11/174可评分帧）；低假激活不能替代召回。固定块/±1格/双窗解释有几何盲区，不等于完整人体恢复；统计分母排除启动与UNKNOWN。空场身份仅历史声明，源数据均开发暴露，物理相位未验证。同作者验证非独立验收。

当前下一步是同源ROI人工核对与网格/可见性盲区分析，B4融合/身份保持/学习/生产晋级BLOCKED；不以本项授权采集或训练。未触碰数据、GT、模型、板端/driver/network，无commit/push/clean/reset。

## 交给独立复审

可审查包：[REPORT](../evidence/2026-10-16_hfus_tcms_01_r1/REPORT.md)、唯一验收、00_DIAG、源码、MANIFEST、逐帧压缩账本、VERIFICATION与FINAL_TREE_CHECK。未冒称已完成独立复审。当前工单首版离线实验交付，算法效果门仍待证据。


## 2026-10-16 r1 追加：用户查看效果

按用户“我看看效果”新增只读冻结结果预览，不改算法/数据/GT。入口 http://127.0.0.1:52947/viewer.html ，本机绑定临时端口；显示动作082829全183帧与空场272帧的B1/B2/B3对照、播放/逐帧/旋转/缩放，灰点抽样但高亮成员完整。默认f138是该动作B3点数最多帧（25点），不是随机代表样本，未形成完整人体；B2同帧295点，B1为0。浏览器实际播放前进、暂停/返回和最终25红点可见已验；旋转/缩放人工检查NOT_RUN。新证据preview_r1/FINAL_PREVIEW.json与VIEWER_PREVIEW.png；原交付SHA保留，预览独立绑定。TC07显示扩展，TC08仍BLOCKED，软件/物理结论不升级。技能沿用ponytail与matplotlib；源两会话SHA首尾一致。


## 2026-10-16 追加：按用户指定切换受控躺下_正向

由meta.name核实cap_20261013_082623，295帧/30.579739秒，用户明确说明该会话有人运动。新增preview_r2仅消费既有冻结结果和原始文件，主预览切至http://127.0.0.1:60449/，原preview_r1保留。实际浏览器f100：B1=171/B2=2846/B3=0；已切B2供查看。此会话B3全程26/286可评分帧激活，表明运动响应弱，不能因缺少完整GT否认用户确认的人体运动。没有据此推断所有高亮点的人体身份。两个源会话SHA首尾相等，算法/阈值/GT/数据不变；新VIEW_CHECK.json和截图绑定结果。TC07显示检查通过，TC08定量语义效果仍BLOCKED。
