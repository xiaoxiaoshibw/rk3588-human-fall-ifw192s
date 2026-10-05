# GL03 R3 执行服务阻塞 / 2026-10-02

当前软件仍REWORK，指定实现服务BLOCKED。不是R3提交/验收PASS。R3已准备具体任务和原失败检查，生产代码仍为R2版本。

## 已完成与仍失败

R2原九方法通过，正常ground/source门控、303实现者回归及既有GL02行为保留；R1独立300/follow2/UI18+18和GL02 12+2曾实际通过。R3待修reference四方法原样4失败（R2/71_reference_before）：from_frame、known to_frame、no-ground node资格、full reload新ID旧reference矩阵。对应G03/G04/G05，不能用测试总数放行。

O01独立BFS复算确认六组连接数量/成员正确，但原报告错将source-Z提示解释为唯一可能地面，并混旧逐面剥离支持率/RMS。本轮独立纠正见04_o01_independent_audit.md；所有六个平面保持身份未知、真实单帧根因BLOCKED。新诊断实现与回传纠正文仍待指定写入者完成。

## CLI环境核验和安全恢复尝试

原OpenCode1.18.34启动/会话列表出现`no such column: project_id`，旧session读取报Session not found；`summarize`接口Unexpected server error。未手工迁移、删除或重写原用户数据库，未改auth.json。只读sqlite schema查看和凭据类型/指纹比较不输出密钥。

按[OpenCode官方数据库路径实现](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/database/database.ts)支持的OPENCODE_DB，在单个进程环境指定C:/Users/30680/.cache/codex-gl03-opencode-v1/gl03-v1.db，未改全局配置。隔离会话可创建，但同模型无工具probe最终HTTP403：`An active OpenCode Go subscription is required to use Go models`。原Go key与当前credential记录指纹相同，没有发现可替换的新Go key；不能归因为误用旧key。probe/exit/error完整保留在03_*，未重试付费服务或擅自换模型/购买订阅。未复制或显示凭据。

旧会话ses_f050597efffecPzMkhE6Bqww4f暂不可读；隔离probe会话ses_f048219c1ffecbyg3karSb69LP不是开发提交。保留CLI原日志与所有源码，不把服务错误记算法失败。

## 恢复锚点

指定Go模型的服务/账号权限可用后，在隔离DB的新工单会话用AI_PROMPT_GL03_OPENCODE_R3.md与当前SHA恢复；不再硬续不兼容旧DB。只读校验79条R3基线结束时全部未变（05_blocked_source_verification.txt），HEAD=49eb7581；中断期间外部git/dist变化保留。当前无活动实现写入者。Codex没有改生产代码，没有部署/采集/联网板端或启动GL04。

软件结论：G01/G02及已审部分保留；G03/G04/G05 reference未闭合、O01报告待纠正；GL03未总体PASS。D01 NOT_RUN，实际物理/分割仍BLOCKED。下一次继续先复核源码/运行状态，不重复已通过部分，不降低失败断言。
