# CL2-09B 作者分析（独审期间只读，不向模型提供结论）

明确来源：隔离source复制CL2-08源码，当前main floor_sheet仅行尾字节不同、规范化文本完全相同。仅candidate/floor_sheet.py的 `_roi_metrics` 行为改变，其他runtime兄弟文件与冻结copy逐SHA一致。variant cl209b_feasible_roi_v1与源码SHA记录在candidate_version.json。原profile阈值/身份/纯度不变，code_files sibling路径在候选完整copy中解析到实际源码，不冒称冻结字节运行。

根因不是条件数过严，而是量词错误：唯一最大间距/贪心组合不合格，不等价于所有四元组不合格。修复先复用旧选择及完整describe返回；旧成功即返回，只有旧失败才从全部合格组合中最大化min_sep。严格`>`排名保留稳定首个并列组合。完全共线集/完全共线四元组不能满足condition≥0.1，用精确整数格叉积排除；clean keys来自已知有限工作域内整数XY格，不接外部任意浮点key契约。

对≤24和>24皆完整失败兜底搜索，不依赖某个seed。原>24贪心已通过则不换更优组合，目的是保留既有行为。没有额外成功门、epsilon、Z切、残差删除或按结果反选ROI。

测试：五格4种合格替代、25格原贪心失败、70个小候选随机集合对完整oracle、旧成功dict逐字比较、输入反序/不修改caller、原门边界、无足够/近距/低条件数/重复/大共线拒绝，Python3.8语法检查；现有三组floor与leveling数值/真实本地HTTP集成，总32项全部PASS。若数值环境不同仍需重新运行，本轮未实际使用板端Python3.8/NumPy1.17，不冒称板端测试。

真实121647：直接原bin解码并排除原3个holdout构建拟合帧work，用冻结auto_candidate平面重建clean cells（不是重新估计TLS），11格。旧/新selector完整dict一致、四ROI边界与report精确一致。原ordinal72 ROI2 300点，P95=0.05029186936019117m，仍FAIL/有效TLS BLOCKED。没有新report替换旧记录或有效TLS导出。

性能：Windows实测失败且存在可行项，5/25/60/100候选约0.00031/0.11868/4.27084/34.20855秒；完全共线大集合快速拒绝。最坏O(n4)代价是真实限制：本轮候选仅离线，不给生产/板端时延PASS，不隐瞒大规模耗时，也不加数量cap来重新制造假拒绝。未来生产接入前需要单独性能设计与验收，非本轮自动工作。

保留的执行失败：第一次combined suite缺human_replay_lib fixture；第二次sandbox默认temp无法创建子目录；第三次local HTTP被sandbox socket拒绝；第四次已允loopback，实际路由到leveled_latest后缺validation fixture。逐个只补齐原依赖复制并把test temp定位到本目录；第五次完整32项exit0。所有失败日志保留，测试断言未降低、原生产/旧evidence没改。
