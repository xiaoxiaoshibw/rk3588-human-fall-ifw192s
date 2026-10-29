# HFUS-MARKOV-EXPERIMENT-01

独立离线侧链，Codex唯一代码writer；复用E0 G0背景/聚类/关联/成员、原RF提取器和Three.js渲染依赖。未改生产/模型/数据/GT，无训练或板端操作。技能：ponytail `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，scientific-toolkit-skill及matplotlib；论文子代理paper-lookup，复核子代理只读。

本地入口：http://127.0.0.1:8947/ 。从仓库根执行：

```powershell
python -B -W error sidequests/human_fusion_lab_next/temporal_markov_r01/server.py --port 8947
```

也可双击 start_demo.bat，终端保持运行。选择会话，播放/暂停、上一/下一帧或拖时间轴；重置从当前帧开始重算，起点之前显示未计算。启停HMM/HSMM控制显示；参数改变会重算实验结果，恢复按钮回到冻结结果。灰点为完整原始帧经原E0变换后的显示抽样，青点为候选，不是全量点数。分歧导航不是已确认误检/漏检。人工复核以真实审核人追加到本轮证据human_reviews，不写冻结GT、不自动解除训练门。

实际复现命令见证据 COMMANDS.md。首次完整提取消耗磁盘读取；核心推理只需stdlib+NumPy，PC特征图另用Matplotlib，RF严格复用原Node模块。运行输出目录必须全新，防止覆盖证据。当前结果run_r3明确复用run_r2特征字节，重新推理；r1失败、r2旧输出保留。

数据通路：原meta/points SHA → E0 INDEX绑定corrected坐标/selected成员/identity → 当前RF批推理与几何 → 各轨迹独立滤波/MC/HMM/HSMM → 固定AB账本 → 同帧Demo/特征图。无需ROS/设备/网络。
