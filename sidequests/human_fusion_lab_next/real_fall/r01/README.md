# 真人追踪倒地离线首版

用户新录 cap_20261013_094333：164帧。运行 `python -B -W error server.py` 后打开 http://127.0.0.1:8929/ 。播放、逐帧、时间轴、告警跳转、配平全场/前景、侧面/俯视/旋转可用。

来源：docs/human_fall/evidence/2026-10-13_hf_real_01_r1/。源会话、生产、旧模型与GT只读。自动配平复用 leveling/floor_roi/floor_sheet 与三法质量门；去背景复用已有 pipe reference builder/extract。仅新衍生数据。

背景是前10帧、视觉排除初始人体XY区域的启动参考，不是已确认空场；初始化完成后才开始因果追踪。初始种子(2.2,1.6)m由助手视觉选定，不宣称全自动人体检测。3D体素连通组件+连续最近邻关联；长时间丢失停止关联、要求重新选择，不偷偷换到家具。输出完整目标点源行。

原HF-06特征/状态机保持确认关闭。另标注“原型倒地告警”：同一目标 measured descent 后原状态suspected，P90<=.65m、全Z范围<=.75m连续1.5s才发一次；持续低位不重复，恢复后重新允许事件。这些是未标定开发参数，不能区分主动躺下、坐蹲等困难负例；不是生产confirmed。

当前同一开发会话154/154初始化后帧均有候选关联，约7.460s/帧72一次原型告警；恢复到直立。没有人体GT，关联成功率不等于真实追踪准确率。cap_20261013_093958区域/留帧质量FAIL，不降门接入；094302未本地下载。

检查：`python -B -W error verify.py`；原HF06 unittest 20项；`browser_check.py`是实际headless Edge WebGL界面检查，输出browser_r2（已存在时不可覆盖）。CUA初始化kernel assets失败，独立Chromium备选完成。初次favicon404失败记录与截图保留。

生产/设备/物理/泛化/独审未验收。ponytail读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md。
