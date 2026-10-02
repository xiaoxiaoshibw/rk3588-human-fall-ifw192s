# GL03 R1 Codex独立复审 / 2026-10-02

结论：**软件REWORK（G03源frame资格）/ O01方法需纠正；完整现场大框成因与真实分割BLOCKED，设备NOT_RUN。** R1数学/主要状态修复已闭合，不能据300回归把整单判PASS。

独立证据70–76：8方法、GL02 12+2、fall300、follow2、两个UI各18均exit0。G02点索引/非交换median/原数据不变、G04坐标预测/框、G05选择缓存/stale/monitor以及G07optional兼容通过。R1先由Codex检查点51集中反馈四根因，实现者补28回归后闭合；原始测试夹具/debug失败保留。原50零点atol断言已纠为1e-9，不作为生产bug。

G03从“新derived字段绑定”沿消费链继续检查，77新增源frame方法：pure source-only/full两子例及节点case均失败，9方法合计3 fail。不同source frame的点仍用innolidar平面给height_m/ground_relative_available/ground_valid，节点valid+locked并输出位置；GDID空只关闭新框，没关闭上游旧高度/请求资格。这是v1已列actual frame/node/旧guard同根因漏覆盖，补查责任记录在此，不称新要求。修复应共享frame-consistency gate，process/request/status均失效且正常源恢复；保留raw frame/seq/stamp/epoch，不能因错误frame抛异常杀worker。

O01原60/61消融为`abs(z-median_z)<=max(.05,3*MAD)`，MAD=.4913，厚度阈值1.4739m，删78.7%。它诚实写z-band/未确认，但不是任务所需的倾斜疑似平面支持消融；“删除该带后components仍1”不能证明ground不桥接。R2需引用现存GL00候选n/d、0.05m残差支持假设，在同输入/配置/投影下比较成员/连接，仍不得确认现场地面/身份。原失败方法保留。

原R1回传实写root returns/GL-03.md，与权威docs/human_fall/returns路径不符。Codex已核源/目标在工作区、目标不存在，Move-Item内容SHA相同迁入canonical；见79。原CLI路径事实保留，后续唯一canonical回传，不丢内容。

直接同session/model派R2（AI_PROMPT_GL03_OPENCODE_R2.md），无需用户转交。未部署/采集/联网或启动GL04；代码单写入者，Codex只写审查证据/纠正文档路径。
