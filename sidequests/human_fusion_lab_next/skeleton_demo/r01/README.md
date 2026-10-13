# 真实点云粗骨架预览

在仓库根目录运行 `python -B -W error sidequests/human_fusion_lab_next/skeleton_demo/r01/server.py`，打开 http://127.0.0.1:8925/ 。绑定本机，无板端连接。双击同目录 start_demo.bat 也可启动。

默认显示近距真实点云第220帧；拖动旋转、滚轮缩放，支持九会话切换、检测候选切换、播放暂停、逐帧和时间轴。点击节点表可高亮支撑点。家具对照可能仍有算法错误确认，显示的是候选几何，不将其改写为真人标签。

从R06 control已保存的完整候选成员读取原28B点记录，复用已有参考坐标、旧通用normalize/observe和3D控件。GT不进入节点估计或默认候选选择；没有生成reviewer、PERSON或可见性标签，未修改原SKO资格门。源码和输入在启动/请求时与已有SHA记录核对，响应另作SHA核验。ledger索引和hash流式读取，不全量加载GB账本。

五个高度区域中心（顶部、上身、胸部、骨盆区域、下部）以及可明确分离的下部A/B；不是精确解剖关节。顶部始终头/手待确认，手臂/肘/腕未估计。直立适用条件之外、无支撑或混簇范围冲突显示未知。没有时序滤波、未来帧或上一帧补节点；本页未接跌倒规则。

软件检查：`python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/skeleton_demo/r01 -p test_server.py`。

验收与真实效果限定见 docs/human_capture/evidence/2026-10-12_hr_skeleton_demo_01_r1/ACCEPTANCE_V1.md。唯一writer Codex；实际pony­tail技能路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。
