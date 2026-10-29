# 事前地面与背景参考入口（2026-10-23）

为解决片内预热和初始人体进入背景的问题，新增 `urfall_scene_reference.py`，接入单段与批量原始深度运行器。没有改算法门限、生产配置或设备，没有把其他片段擅自当作已知事前背景。

参考包同时绑定源/目标 ZIP、两份时间表、相机文件、采样步长、米制深度栅格、来源帧及其 SHA。地面复用既有拟合器和同一验证标准；加载时再核对原有门限和支持统计。包内空场/安装/时钟声明只标为 metadata_declared，物理资格保持 false。

`clock.json` 使用 `recording_clock_pair_v1`，含共同 `clock_id`、`installation_id`、源/目标 ZIP SHA、`source_origin_s`、`target_origin_s`、`uncertainty_s`、`empty_source_prefix_declared=true` 与 `qualification=metadata_declared`。原点用于把各片段相对秒映射到声明的共同时间轴。源前缀结束时间加不确定度，必须严格小于目标开始时间减不确定度；不得把同一录制、片段编号、ZIP 日期或两个相对零点当作事前证据。

上述校验只证明声明、绑定和输入顺序自洽，不证明声明本身是独立真值。调用者必须保留实际录制时钟/安装/空场依据；缺失时不编造原点来通过校验。

```powershell
python -B -W error ML/src/urfall_scene_reference.py --source-archive <source.zip> --source-sync <source-data.csv> --target-archive <target.zip> --target-sync <target-data.csv> --calibration <camera.json> --clock <clock-pair.json> --output <new_reference_directory>
python -B -W error ML/src/urfall_raw_depth.py --archive <target.zip> --sync <target-data.csv> --calibration <camera.json> --scene-reference <reference_directory>/REFERENCE.json --output <new_run_directory>
```

原始文件仍使用现有 cam0 命名和 PNG16 格式。参考输入是独立录制的前缀，不包含目标片段的未来帧。相机或焦距诊断参数改变，需要匹配的新参考。指定参考后若校验失败，直接拒绝，不退回片内预热。未指定参考，仍执行原有路径。

批量运行器增加 `--scene-references <directory>`，每个片段要求 `<directory>/<sequence>/REFERENCE.json`；缺失记录 `SCENE_REFERENCE_NOT_PROVIDED`，保留在全部 30/40 片段中，不默默混入另一套输入条件。逐帧账本新增实际 `binding`，兼容核对器优先使用该绑定，也支持旧账本。

验证使用解析渲染的合成场景：空场录制在共同时间 0 s，动作录制在 100 s，目标片段 0.1 s 已开始下降。外部参考路径从首帧取得 76 个目标点，40/40 帧有目标，0.7 s 形成候选；片内预热路径缺直立参照，无候选。重复参考包 SHA 相同，6 帧因果前缀逐值一致。错误顺序、时钟不确定度重叠、同一录制、错相机/目标/步长、损坏栅格、NaN、地面不达原标准及批量缺参考均有拒绝检查。它们是软件反例，不是人体效果样本。

全部真实 UR Fall 默认路径再跑 70 段、11936 帧，所有旧字段逐值相同、所有目标缓存 SHA 相同；新增字段仅为实际绑定。原有 28/30 参考窗命中、1/40 日常触发保持。现有 CSV 没有共同绝对时钟或空场资格，因此没有为 fall-10/fall-22 构造声称合法的真实参考，不能把合成成功改写为 30/30。

本轮 ML123、核心705、capture69、标定2 项 `-B -W error` 通过；IFW192S 386 帧完整回放保持原链输出。外部参考样本的40帧、2510个点在本地 Python3.8.10/NumPy1.17.4 与当前环境状态/事件一致，最大数值差1.42e-14；不是 ARM 原生或性能验证。

证据位于 `docs/evidence/2026-10-23_fall_scene_reference/`，含源前件、合成 CLI 端到端、默认全量逐帧对照、拒绝与校验、旧版兼容结果。独立 IFW192S 事件真值、长时日常数据、物理标定和原生板端仍缺，整体目标尚未完成。后续按实际事前录制/冻结工件接入真实数据，不用假设背景补足成绩。
