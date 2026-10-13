# HF-REAL-02 R1 全过程原型 / SUBMITTED，完整人体/关节尚未验收

2026-10-13用户提供空场131958，并要求完整人体与骨架锁定、跌倒检测过程。Codex唯一writer，隔离新源码r02，旧r01/输入/生产/GT/模型只读。唯一验收ACCEPTANCE_V1.md。

回放 http://127.0.0.1:8931/ ：同一目标框/轨迹、13槽粗骨架、节点支撑表与点选高亮，锁定→骨架→下降→低位→告警保持→起身恢复。支持关键阶段跳转/单步/播放暂停/时间轴/3D/侧面/俯视/全场前景/空场对照。真实浏览器检查与截图browser_v2；旧8929不改。

## 数据与背景

上午094333/164帧，沿用原R1三法/holdout通过且SHA仍匹配的配平；用户指定空场131958/97帧/9.942s/133436996bytes，单独调用原floor v3与三法同域/留帧门，GOOD/tls。空场不是随意假定的前10帧，背景冻结于用户指定实际会话。

原未配准静态匹配仅.6519676，REFERENCE_COMPATIBILITY.json FAIL保留。注册方案实跑前REGISTRATION_PLAN登记：拟合只上午0–4帧稳定且排除人物活动区域的体素，5/10留出。复用fixedICP数学，不用其旧ICP_SAVED pass作为本次门（该字段false保留）。结果旋转2.003167°、位移.225698m、1290源/884目标体素、迭代>0，静态匹配.9476884；留出5/10分别通过原.70兼容门。没有放大.12m背景匹配半径或降低.5占用率。此为离线场景参考对齐，不证明硬件安装没动或物理外参准确。参考使用当前会话前5帧完成离线初始化，不能冒称从frame0未校准就实时因果运行。

全164+97帧保留原源行映射：094333前景852876点，空场前景2011点。数学审计从28B原始XYZ独立重算各R/t（参考再应用ICP），误差<3e-6m；无修改原点文件。地面<.1m仍剔除，可能损失近地人体部分，完整身体召回未知。

## 锁定、骨架、事件

人物起点XY(2.2,1.6)m沿用助手视觉指定，非全自动人体分类。新空场允许frame0开始候选关联，164/164都有REAL-01；无人工身份真值，不报追踪精度。初始站姿门+持续关联，空场自身97帧0锁定/0事件，只是self-reference sanity，非独立负例资格。

初次PROCESS_SIDE/TOP f10存在家具条带混入目标组件；原track/process/source/图保留。TARGET_REFINEMENT_PLAN先登记站姿躯干XY中位数.50m半径单因素；新track_v2/process_v2共11帧裁掉一些远离躯干点，非站姿不裁该圆。f10仍有静态残留，**未完整解决纯人体成员问题**；UI明确“家具粘连风险、本帧骨架不可靠”。.50m未标定且可能截断伸展手臂，不冒称完整全身召回。

骨架复用原SKO normalize/observe：局部body-axis分带/侧分支均有当前源点支撑，再反变换到原地面坐标。所有有效节点support_rows属于当前目标，低支撑不画；符号只用过去方向，解剖头脚/左右未知。13槽是顶部、躯干/胸/骨盆/下部及A/B上侧/外侧/下侧/末端的**几何部位**，不是已标定13关节。45/164帧13槽均有支撑，47/109/118三帧轴歧义0节点，其余缺槽公开。看起来像骨架不能证明肘/膝/腕/头真实位置，完整解剖骨架BLOCKED。

原HF06状态确认开关始终false。upright首次f5/.5147s，低位f42/4.3701s，suspected f57/5.9109s，recovering f122/12.6455s，最后upright。未标定prototype_fall_alert一次：f72/7.460271s，P90约.39m/1842目标点；持续告警f72–131，恢复后撤销。事件依据同目标测量下降、原suspected及当前P90<=.65m/全Z范围<=.75m连续1.5s，不能识别动作意图。当前骨架用于支撑检查与显示，不用未标定骨架代替下降/低位门。

实际视觉：看两版target side/top contact sheets和真实Edge站姿/下降/倒地告警/低位/轴歧义/恢复/空场截图。发现f10污染后保留失败、限定修正，未假称完全闭合；47/109/118 UNKNOWN不补画。辅助视觉不是human GT。

## 逐ID自验

| ID | 状态 | 证据/边界 |
|---|---|---|
| RS01 | PASS | BASELINE_BEFORE19253文件全SHA，master/026e06303f60ed1bbe4ddc4d037836db68da6d27，errors/drift空；non-atomic/.git excluded；源与结束绑定另manifest |
| RS02 | PASS（离线参考） | 空场三法/留帧GOOD；原兼容FAIL保留，注册/留出.70原门不降，当前.947688；物理站位未验证 |
| RS03 | PASS（工具） / BLOCKED（完整人体保留） | 原源行+独立全261帧几何审计，空场0锁定/0事件；.1m近地裁剪和人体GT缺失公开，不报告真保留率 |
| RS04 | FAIL（完整纯人体） | 164同ID候选关联，但f10家具残留仍污染；视觉初始化/框/失联UNKNOWN工具存在，不以同ID覆盖代替完整锁定 |
| RS05 | PASS（显示/支撑） / BLOCKED（完整解剖骨架） | 实际13槽/支持源行/未知，45帧全槽有点不是关节准确；3帧轴歧义0节点；肘膝腕头脚/左右未标定 |
| RS06 | PASS（开发原型） | 一次prototype事件/持续告警/恢复、seek固定结果；不启core confirmed，不报真实意外跌倒精度 |
| RS07 | PASS | 最终browser_v2八阶段+empty/控件/节点支撑点击；实际headless Edge WebGL，console errors空，4非法HTTP400；人体/骨架/证据/阶段可查看 |
| RS08 | PASS（已跑数学/core） / NOT_RUN（真人失联/重置） | verify2测试+261帧源行支撑审计；非有限/稀疏/重复行/歧义反例；HF06原gap/重置等20项exit0；新真实目标长遮挡失联/身份重置没有相应会话，不冒称实证 |
| RS09 | BLOCKED / NOT_RUN | 真实完整人体与解剖GT/泛化BLOCKED；未参与作者的独审NOT_RUN；设备/物理/板端实时/部署NOT_RUN。整单未ACCEPTED |

## 运行与验证

prepare_reference.py exit0；foreground未配准exit1保留；登记后foreground配准exit0；track/track_v2人体与空场分别exit0；skeleton/skeleton_v2与render两版exit0，旧版本不覆盖。verify.py（-B -W error）2tests exit0，VERIFY.log/SOURCE_AND_SKELETON_AUDIT；HF06 20tests exit0 HF06_REGRESSION.log；JS语法与Python3.8 AST检查；browser_check及browser_check_v2实际exit0，v2单独目录、8阶段。前端来源/API失败清旧图/暂停，非法输入4个真实400。旧服务67134在本轮改支撑高亮后Ctrl+C停止，实际8931服务工具session81131保留。

原Python/lib/JS/输入与新输出实际SHA见SOURCE_AND_END_BOUNDARY.json；结束仅载入依赖/输入/新source和产物实SHA，不是第二次全树原子冻结；扫描时新准备文件可能入before。最后报告/return/入口记录另FINAL_ARTIFACT_SHA。没有commit/push/reset/checkout/clean/设备/生产/GT/模型/原captures写入。

ponyTail实际 C:/Users/30680/.codex/skills/ponytail/SKILL.md。用户所需**过程展示已提供，完整准确的人体成员和解剖关节锁定仍未完成**。后续需先闭合家具污染/身体支撑，再以人工关节及困难负例验证，而不是为画完整骨架放宽支撑门。
