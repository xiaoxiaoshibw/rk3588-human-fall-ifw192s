# 活动区外参考锚点与全部新增三维簇（2026-10-14）

HFUS-SCENE-STATIC-02，SUBMITTED；几何与软件自验通过，未宣布人体身份或物理资格验收。

## 当前成果

同一 pointset/r01 页面、同一 localhost:8954 服务，增加 scene_static 对照：活动区外参考锚点估计小幅位姿变化，继承上一轮双姿态背景过滤。聚类半径、最小点数、候选资格和原 ROI 不变；未训练、切换模型或修改原 core/actions/config。

全视野提取独立当前新增簇，而非只交付中央候选。每簇保留完整源行、采样显示、AABB、PCA方向/轴向尺度、高度分位数、线性/平面性/散布性。各簇同时以不同颜色显示，灰色为冻结观测，亮色框为当前选择；可逐簇回查。只有中央几何候选沿用原点支持的区域节点，其他簇不套人体骨架，身份 UNKNOWN。簇数量不等于人数。

## 输入边界与诊断

本轮开始时 captures/remote 已为空。首次原始诊断因 cap_20261013_083254/meta.json 不存在退出1；失败事实留在 ../2026-10-14_hfus_scene_static_r1/。在命名备份目录未找到原 points.bin，没有复制/下载/重造录制，也不推断缺失原因。

后续显式使用 action_research_retention/baseline_02 保存的完整 raw_xyz、nominal xyz、local_index、global_row 与已冻结帧账本。历史来源SHA与catalog/reproduction一致，逐帧源行/帧边界和坐标变换回算校验；保存当前缓存文件SHA。这里是 CACHED_XYZ_REGRESSION，不是原始录制复跑。intensity/ring/逐点设备时间等原始字节不能重新验证，opaque返回null，页面明确标识缺失。保存帧时间仍来自既有帧账本，未伪造逐点属性。

49个代表帧（探索/复用，非新留出）：初始选锚6558点次位于活动区内，与当前几何目标候选的交集为0，不能据此宣称已有锚点吞人。活动区外对照48/49可补偿、1帧残差恶化拒绝。该限制用于隔离潜在活动干扰，不能证明剩余点全部具有人工确认的家具身份。诊断与代理SHA见 ../2026-10-14_hfus_scene_static_r2/。

当前仍用上一轮空场CAL获得的抖动幅度范围；没有新的活动区外CAL重标定，因为相应原始录制当前缺失。没有用动作帧或32个空场留帧重新设定门限。名义REF_RT/登记变换不是新的物理地面或传感器位姿资格。

## 实跑与验证

Windows / Python3.12；全1,966帧缓存几何运行耗时 748.19 秒（含缓存读取、SHA、产物写入，不是实时性能）。

| 会话 | 几何回归帧 | 中央候选帧 | 本帧独立新增簇范围 |
|---|---:|---:|---:|
| cap_20261013_083254 | 225 | 225 | 3–8 |
| cap_20261013_083218 | 231 | 231 | 3–8 |
| cap_20261013_083120 | 247 | 247 | 3–8 |
| cap_20261013_083044 | 251 | 251 | 4–7 |
| cap_20261013_082906 | 175 | 175 | 3–7 |
| cap_20261013_082829 | 183 | 183 | 3–7 |
| cap_20261013_082717 | 327 | 327 | 3–6 |
| cap_20261013_082623 | 295 | 295 | 3–8 |
| cap_20261013_131958 | 32 | 0 | 0–0 |

- 1934动作帧均有中央几何候选；32空场留帧目标0、独立新增簇0。这是已见数据的缓存回归，不是泛化/人体精度证明。
- 共 9061 个簇观测，不是唯一物体数；每动作帧3–8个候选簇。
- 前景 4,791,433 → 4,786,926，中央候选成员 3,659,895 → 3,660,020；不据此推断家具污染率或人体完整率。
- 活动区内补偿输入0；在当前有效域内已匹配背景被补偿晋升的新增点0。全1966帧fg/background覆盖与互斥、各簇源行互斥、noise/小簇归因、目标成员属于当前新增簇、显示XYZ回算与节点支撑PASS。
- Edge原页九会话/方案切换/冻结观测/全部簇选择/仰卧跳帧/原默认保持PASS。后续截图发现旧全场模式只绘制所选簇、姿态上下文不清；修为所有簇多色同时显示并将姿态限定为中央候选，独立UI回归PASS。截图与BROWSER_CHECK在本目录，先前UI记录在r3保留。
- SYNTHETIC三维XY重叠而Z分离、活动区锚点保护、无未知簇骨架、空输入检查PASS；上一轮抗抖动/双解释检查PASS；node --check app.js PASS。不冒称原录制字节验收PASS。

## 复现与源码

从 D:/Code/ldiar 的 PowerShell：

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -B -W error sidequests/human_fusion_lab_next/pointset/r01/research_scene_static.py --out 新的独占目录 --geometry-ledger sidequests/human_fusion_lab_next/pointset/r01/action_research_retention/baseline_02
python -B -W error sidequests/human_fusion_lab_next/pointset/r01/check_scene_static.py --out 新的检查目录
```

检查器检查当前 action_research_scene_static；新运行目录需另行绑定，禁止覆盖旧输出。SUMMARY/INPUT_PROVENANCE/CALIBRATION/BACKGROUND_CONTEXT与逐帧JSON在该目录；本版源码及SHA在source_snapshot。保留旧scene_change、guarded、R1/R2/R3/retention输出。原GT、模型、生产、录制没有写入；没有采集、部署或Git提交推送。本次只重启本聊天创建的受管理8954会话以加载同页新路由，未停止8944或其他服务。

当前链接：http://127.0.0.1:8954/?dataset=actions&variant=scene_static&fi=0 。页面可切换“全部新增三维簇”，勾选“冻结场景观测”。R1默认未晋级，数据不是已审核人体/家具身份。

实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。

剩余：原18个meta/points文件的原始字节复核受阻；完整人体/家具身份、跨场景泛化、物理配平/位姿与独审未通过。原始文件目录澄清问题已发出，不把无回复当作路径确认。
