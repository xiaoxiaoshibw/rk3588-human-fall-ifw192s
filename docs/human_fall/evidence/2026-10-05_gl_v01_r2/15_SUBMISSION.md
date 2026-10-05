# R2 提交 / 2026-10-05

Codex唯一writer，SUBMITTED；使用 C:/Users/30680/.codex/skills/ponytail/SKILL.md 与 C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。当前唯一GLV01 v2；R1“数值PASS即完成”判断撤回，原始数值/失败保留。用户明确算法自己找，00人工门方案已被00b自动设计覆盖，没有让用户重新画区。

新floor_detector只从FIT点云发现空间均衡的多平面，选低处近水平连通面；完整XY格内所有高度参与厚度/局部法向/障碍检查，混入物体整格拒绝。按连通面内四个空间分区选安全格，不按点密度选四个大框，不读人工ROI。三估计器、所有质量门与全帧导出数学保持。

| 原三输入 | 新自动job | 三法与一致性 |
|---|---|---|
| cap_20261004_203349 | c9712acad48c4fb7a78cb119c08d4cdb | PASS / 推荐TLS |
| cap_20261004_203135 | 500314ff11484be58f44b3cf11ad033f | PASS / 推荐TLS |
| cap_20261004_202456 | a480b987d176479a89e1730f9d6b7c09 | PASS / 推荐TLS |

202456人工原job27f870...保持。独立后置对照角差1.586309789°、offset差0.005015254m，不用参考值选择/拟合。检测ground_confirmed=false / algorithm_candidate，physical/extrinsics/runtime始终false，不伪造人工或物理验证。

基线01–03；设计00/00b；实际数据04；纯算法03综合反例检查05b exit0（密集桌面/人体混入/无地面/零散小平面）；实际HTTP/数学/导出回归06c四项exit0；来源/重启/损坏负例07b两项exit0；panel/45既有JS与console四项10系列exit0。旧05/06失败原文与预期变化记录06_regression_semantics，未降低原数值门。09九套数据全部逐记录XYZ精确重放、nonXYZ/invalid XYZ/frames/源行不变，exit0。旧129文件SHA全部保持；原meta/bin大小/mtime/SHA完全保持，14。

新UI同步实际自动ROI，XZ/YZ侧视与当前帧所有选区点高度范围；白色虚线表示人工参考。自动开始/失败清空旧框，换会话清高度统计，不继续显示“默认四格”。旧未经地面识别的数值候选不自动预览/衍生下载；回放入口额外验证身份/source绑定。数学报告仍保留原PASS/FAIL。

编译08c完成/exit0，新exe pc_apps/console/dist/gl_v01_floor_r2/Console.exe；12确认算法、后端、两HTML、JS与源码逐字节一致；桌面链接13已更新、旧lnk备份/旧exe保留。生成阶段leveling.py精确字节保留09_producer_leveling.py，与报告code_hash一致；之后仅改消费者，未伪造旧生产版本。

共享树另行新增第四会话cap_20261002_223757，非本轮差异保留；04动态清单意外多检查一次该源，候选拒绝、无新配平产物/源改写，scope遗漏已如实记录。v2 V02原“只3”列表要求现在FAIL，不把外部扩展静默归为本轮PASS，也不擅自撤销用户差异。此项不等于原三自动地面算法失败。

V01/V03–V06/G01–G04与作者流程自验PASS；V02范围FAIL；独审NOT_RUN；D01设备/物理/未曝光泛化NOT_RUN，整体未ACCEPTED。使用已曝光录制留帧，只作诊断。候选高度边界/名义方向是声明先验，不等于真实安装原点/高度已核验。未ROS/driver/webui/冻结config/设备/采集/部署/commit/push/reset/clean。
