# D05 离线返工交付（R02/R03/R04）

唯一writer Codex；ponytail实际路径 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。冻结生产、模型、GT、captures与旧证据只读。当前验收表 `docs/human_capture/evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_V1.md`，历史两轮各保留原表。不是D06/D07，不部署、不采集。

从仓库根目录运行：

```powershell
python -B -W error sidequests/human_fusion_lab_next/d05/r04/demo_server.py --port 8914
```

打开 http://127.0.0.1:8914/ ，默认当前R04（与R02 split全帧等价）。可切A06/R02 split/R03失败分类对照。三个窗使用同会话、帧、时间戳和投影；画面加载时清除旧帧。全场检查家具，人工PERSON区域选项仅用于显示，不进入推理。未审核区域UNKNOWN，S9无绑定资格；raw/effective分数和coasting最后观测明确区分。服务器逐文件SHA校验，浏览器逐响应SHA校验。

可审查代码：hook_split.js=已实跑R02单因素密集核心分离；hook_unknown_fast.js=仅等价短路；run.js/trace.js记录全过程；verify_parity.py完整成员与判决对拍；perf_bank.js纯算法串行计时与retention前后账；demo_server.py/demo.html只读查看保存顺序推理，seek不续票。证据与退出状态在R02/R03/R04各新目录，原失败账均保留。

重新跑实验必须提供新的空输出目录，runner拒绝覆盖。verify_parity.py与默认证据写入脚本仅供审查，已经存在的输出会拒绝覆盖。未提供任意写生产入口。实际结果与限制以FINAL_REPORT/追加return为准，不宣布ACCEPTED。
