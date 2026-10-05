# HR-02 sid 载入故障诊断

用户 2026-10-04 报告会话面板显示「回放器未注册 sid 载入接口」。这是 PC 回放器修复，不启动 HF/GL 工单或设备任务。

基线：master / 73447d12ec1255643f6531e2d9e2287fb1481059。范围内含 staged/unstaged 用户改动及未跟踪 annotator.html，状态与全部相关文件 SHA 见 00/01。Codex 唯一写入者；使用 C:/Users/30680/.codex/skills/ponytail/SKILL.md。

根因：replay.js 的用户差异删除 HR-05 标注层时也删除末尾 IIFE 闭合 `})();`。node --check 实报 Unexpected end of input / exit 1。JavaScript 全文件解析失败，line 224 的既有 window.__load_session_sid 赋值未执行；panel.js 本身正常，所以能显示会话及上述下游报错。

最小修复：仅补回闭合，不恢复已删除标注层，不改接口或 panel/server；原有选目录及 sid 载入共享 load()。

验收 v1：

| ID | 预期与检查 |
|---|---|
| S1 | replay.js 全文件可解析，回归检查能暴露原缺陷 |
| S2 | 页面启动显示场景；侧栏本地 sid 点击成功显示首帧、帧数和 seq |
| S3 | 既有 human_replay_lib.test.js 回归通过 |
| S4 | 只补闭合与解析回归，不恢复用户已删除标注代码；panel/index/server 不变 |
| S5 | 回放只读，所用原始 meta/bin 前后 SHA 与 mtime 不变 |

受影响入口：侧栏点击本地会话、侧栏手动选（均调用 __load_session_sid）、工具栏目录选择（直接调用 load）。全文件解析修复覆盖三者；无需改变 sid、数据协议或会话版本。浏览器仅做本地回放，不触发同步/录制/删除。
