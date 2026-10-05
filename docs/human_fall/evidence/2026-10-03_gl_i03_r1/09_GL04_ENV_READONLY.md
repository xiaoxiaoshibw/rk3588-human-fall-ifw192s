# GL04真实DPR环境只读调查 / 2026-10-03

Codex只读助手gl04_dpr_feasibility已读WORKFLOW/v1验收/R7独审与computer-use skill/guidance/confirmations；通过cua.getState及browser capabilities/viewport/visibility文档查询，没有UI操作/创建tab/写文件/启动服务。

当前apps=[]；仅Browser id2 Codex In-app Browser/iab与id1 Codex MCP Apps/mcpapps，两者tabs=[]。原生app控制禁用，浏览器可用viewport接口只有width/height，visibility接口get/set，无真实zoom/DPR/deviceScaleFactor/显示屏操作。不能以viewport resize/VM假DPR/旧跨导航观测闭合条目。

GL04 V04/C12/M03真实DPR-only仍NOT_RUN，正式不合并。解除需可控真实浏览器DPR变化，保持同tab/CSS布局/相机/帧绑定/状态并核两画布CSS/bitmap及两mode。R7旧证据before/after均DPR1不能替代。未改网页、系统设置、设备/网络/配置或状态。
