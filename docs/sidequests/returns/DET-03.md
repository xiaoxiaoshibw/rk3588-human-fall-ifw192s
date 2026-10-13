
## DET-03 R1 — 2026-10-08 / Codex / SUBMITTED

- 唯一验收：`docs/sidequests/DET03_ACCEPTANCE.md` v1，SHA `1b8b9a7502d75fc1132074e7499c8c2d1136d71bd782d7e2ec404b65685d7b2a`。
- 起始/结束分支 `codex/human-detector-models`，HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`；独立实验工作树，原主线只读。
- ponytail实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 先行计划/全量基线→实现→同帧单因素→冻结细分→yaw修复→复验；本轮无部署/采集/提交/推送。

### 集中诊断与实际变更

已证实CPU NMS、位置包含及BEV绘图的yaw方向与固定上游相反；实验适配器已修正，45°负例与host原kernel几何吻合，74组原始cls/reg/dir头完全不变。历史结果保持不回填。源解码、零XYZ/行身份、prepared/foreground逐值、encoder特征、strict权重、ICP互逆均通过软件检查。

同32点上限的覆盖采样在506对同帧中明显增分；前三组B全帧增分，第四组B有2帧下降。仅替换局部相交柱即可复现前三组增益；仅删外部场景、冻结局部完整柱，四代表帧仍降分。采样偏置和上下文有因果支持，但单一主因尚未确定。无人模板覆盖采样后全场行人分0.50–0.52，是必须保留的假阳性负例。有限强度/z替代无稳定收益，参数未被宣布标定正确。

新增诊断/核对/汇总脚本在sidequests/human_detectors；修复cpu_pointpillars.py、audit_truth.py、plot_static.py，补test_experiment.py斜框回归，README同步。代码SHA和核心修复diff见17_run_manifest.json与17_code_diff.patch；全部实验输出逐文件SHA见17_artifact_index.json。原树5169项中观察到3项外部文档/日志变化，本轮未写入或回滚；3211项源/模型/变换/旧消费资产不变，见18_integrity.json。

### 逐条作者自验

| ID | 状态 | 证据 |
|---|---|---|
| E01 | PASS | 00基线、计划、范围与18完整性；本轮只写实验树 |
| E02 | PASS（实验修复后） | 07输入307帧/1265组、严格权重/特征/逆矩阵，11/20b斜框 |
| E03 | BLOCKED（原包运行等价） | host体素18例/80框/222候选及KITTI子检查PASS；原ATen扩展缺MSVC |
| E04 | PASS | 1012全帧前向/506对、24次局部/外部冻结，负例全保留 |
| E05 | PASS（实验）；物理定义未闭合 | 代表帧有限单因素，强度定义/z来源与范围截点 |
| E06 | PASS（代表帧） | 圆柱点+相交柱逐值固定，外围删除仍降分 |
| E07 | PASS | 每次trace最终输出复现，rank/top100/decoded/NMS/max50 |
| E08 | PASS | 15摘要/16逐帧CSV/17命令与SHA/原始日志/19头不变 |
| G01 | BLOCKED | CPU torch无CUDA；host kernel不冒充GPU逐值等价 |
| L01 | NOT_RUN | 无精确框/点GT及物理标定 |
| D01 | NOT_RUN | 无设备/新采集/部署/生产接管 |

### 限制和下一步

1192次实际PointPillars CPU前向含复验，8回归-W error通过；05 DLL加载失败及20旧上游docstring解析失败原日志保留，分别在05_r2/20b修复诊断后通过。不报告准确率/P/R；CenterPoint仍BLOCKED。最高区分力下一项为精确人体/家具点标注下固定外围编码，仅改变纯人体柱覆盖，另以独立无人/不同人姿态验证假阳性；本轮不启动采集、微调或生产接管。

复审入口：[完整报告](../evidence/2026-10-08_det03_r1/README.md)，[验收v1](../DET03_ACCEPTANCE.md)。报告SHA `87cdaba1e3c894b8b27279a50927d76347244baa111d81c7fb53763889da4067`。未自行ACCEPTED。
