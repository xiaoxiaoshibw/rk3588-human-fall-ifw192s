# 计划制定三轮分析实录

日期：2026-10-14；作者Codex。用户授权制定计划并交OpenCode审核，未执行算法开发。

## 第1轮：交接证据与现状复核

读取用户指定两个聊天最新结论，随后读取ldiar AGENTS、HF WORKFLOW、HC README、M3′ FINAL_REPORT、R3 FINAL_REPORT及既有HF-CLOSE/DATA/BG报告。确认M3′无新VALID、R3只恢复当前FG，默认仍R1。审计A01与C01存在KS1归因冲突，回到background_ab.js核验：代码显式ground_keep_below_m=-.25，不能将已禁裁剪实验的低位失败归因生产0.10m规则。结论是先逐点定位上游删除，不能继续仅做骨架或碎片数量优化。

## 第2轮：实际实现路径与实验设计

读取pointset的core/actions/research_actions、config/config_actions与RUN_MANIFEST，JS human_pipe_lib函数/调用链、r04 background_ab/score_background_ab。确认Python使用3D背景距离和−0.25m域，JS采用体素参考/在线占据且有独立清理阶段；两链不能共用删除归因。现有_layers与sources.npz可复用，但INVALID/RANGE/HEIGHT等还需细分。逐点source_index须区分帧内/全局/byte offset，重复XYZ不能按坐标推断身份。

发现RUN_MANIFEST依赖D:/Code/radar/Plan/evidence/indoor-empty/20261014-low-pose-r01；当前background.npz存在（仅存在性检查，算法实施前仍须完整SHA/注册绑定核验）。在计划中新增跨仓依赖核验和局部阻断规则。主产品复用原8944页面；JS只作来源已绑定的部分标签对照，避免另开产品。

## 第3轮：反证、效果门与收口

核查三类风险：背景新增可能吸家具、已开发数据的重复使用不能成为泛化证据、无VALID的跨会话背景只能隔离诊断。计划拆分实际first_terminal_reason与重叠/反事实原因；冻结诊断条件、保留验证重用事实；完整人体/家具/解剖精度仍UNKNOWN。

候选门具体要求原32空场0目标、原动作无新目标缺失、已有绑定局部人体保留不退化和已知家具混入不增，UNKNOWN单列；缺标签不能视作零污染。允许无收益时交付诊断模式和失败裁决，但不晋级候选。提出计划v1并由OpenCode独立核查，不把作者自查当外部审核。

## 本轮工具状态

已读取ponytail技能，路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。OpenCode可用，opencode models确认opencode-go/deepseek-v4.1-flash存在，使用仓库约定模型、plan agent、pure模式；权限仅read/glob/grep/list允许，其余deny。首调用因--file可变长参数吞入末尾prompt而失败exit1，原日志保留；将prompt置于选项之前后重新启动，未改原失败输出。

算法实验/浏览器/设备/生产均NOT_RUN，本轮没有修改算法、GT、录制或默认版本。
