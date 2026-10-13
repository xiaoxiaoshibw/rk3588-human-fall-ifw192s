# DET-02 唯一现行验收表 v1

来源：2026-10-07用户“静态模板233658、记得配平、先设计开发计划然后再做一次”。入口：[开发计划](DET02_PLAN.md)，[支线README](../../sidequests/human_detectors/README.md)。本单只覆盖模型支线离线对照，不改主线W03或HF/GL判据。

| ID | 要求/预期 | 负例或组合 | 证据入口 |
|---|---|---|---|
| E01 | 先落盘计划/基线后实现，原树只读，独立分支唯一writer | 含未跟踪文件SHA，无旧证据覆盖 | 00_baseline.json / scope |
| E02 | 233658无人模板属性明确；五会话各自有效配平、来源绑定 | 215607冲突保持；源SHA变动拒绝 | leveling / source manifest |
| E03 | 背景只由独立模板建立并冻结；复用当前reference参数/匹配/ICP/cleanup | 含人自建图无删除权；模板不得被四目标更新 | foreground manifest / synthetic |
| E04 | A/B/C/D/E同权重/强度/score/Z/CPU；全部253帧 | workspace/background/alignment/cleanup不得混为一种收益 | five predictions / point counts |
| E05 | 点身份、零XYZ、坐标/强度保持与配准方向正确 | 无效点不生成假点堆；逆变换/非法矩阵拒绝 | source indices / tests |
| E06 | 真人定位点分数与全场最高分区分；圆柱统计非逐点GT | 不把静态点/家具残留称真人，不报无依据P/R | user seeds / report |
| E07 | 合成固定空场保人、自建图吞人、ICP矩阵方向、现有相关回归通过 | 已失败历史保持；每条证据可追溯 | tests logs |
| E08 | 原始数据/模型/核心复用代码SHA前后稳定，所有结果新目录 | reload同ID异内容需拒绝；不读当前可变模块混版本 | final integrity |
| D01 | 设备/采集/部署/物理标定/生产接管 | 本单无授权 | NOT_RUN |

结果只填PASS/FAIL/NOT_RUN/BLOCKED，作者自验不自行ACCEPTED。回传追加到 returns/DET-02.md。
