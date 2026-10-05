# R2 地面身份纠错 / 写前设计

用户明确指出自动四框不是平地。R1错误把残差筛选/几何门PASS当成地面身份。P03 1m候选按地内点计数取格，却交下游全部高度，XY内混入桌面/人体；R1 25cm FIT残差挑格也只有数值选择，不能替代场景身份。Codex负责该判断和完成状态错误，撤回两新会话“已配平”语义，不再追调网格到PASS。

Codex唯一writer，继续已读 C:/Users/30680/.codex/skills/ponytail/SKILL.md。基线master/3fc1338fc306444959433a41bdeaeefd705f58ec，dirty/untracked/原source/原capture/所有旧结果见01–03；旧证据、原report/meta/bin不改。

修复：validation新增源/config绑定的人工地面审查记录；202456原job27f870...仅保留用户既有参考身份。其他旧候选均UNCONFIRMED，不自动预览/下载衍生数据，报告仍保留数值PASS/FAIL。工作台完整名义高度XZ/YZ投影与四区全高度统计供人工核查；明确四区人工确认后才运行新job并留下独立不可覆盖审查记录。自动配平入口暂阻断这3sid；回放leveled_latest和旧leveling下载同样拦截未确认候选，避免只改UI漏消费者。数学、检测候选/阈值/原数据不改。

| 操作 × 状态 | 修复/预期 | v2 ID |
|---|---|---|
| startup/reload × R1数值通过但地面未确认 | UNCONFIRMED，撤回完成/自动变换/衍生下载；诊断报告可读 | G01/G04 |
| 同sid同内容/newID/原地源变化 | 资格绑定source/config/job；源漂移仍拒绝；新sid清旧确认 | G03/G04 |
| 旧auto/无review/伪造review/config变化 × POST | 启动writer前拒绝，不写输出/审查记录 | G03/G04 |
| 真正人工请求 × ready/failed | 区域与先验/basis/source快照审查，只有相同job/config/source可恢复；数值FAIL照样不导出 | G03 |
| 手动选区/参数/basis变化 × 页面 | 清确认，侧视与全高度统计按当前帧更新；不裁Z/残差 | G02/G03 |
| 202456旧job与新auto候选 × 所有consumer | 只原用户参考job保留，不把同sid所有候选升级 | G05 |
| validation/leveling source/run/latest/artifact/replay caller | 同一qualification门，旧服务重启后生效 | G04 |

v2不加数值门，增加用户明确要求的地面身份门；R1完成状态被纠正，旧数值结果不篡改。新两会话真实地面身份尚需用户场景指认，G07 BLOCKED；不是设备物理标定，D01 NOT_RUN。
