# GL-V01 实现前诊断与操作矩阵

Codex唯一writer；已读 C:/Users/30680/.codex/skills/ponytail/SKILL.md（本聊天前一轮已读，继续使用），WORKFLOW v2、GL-W01/P03现行实现。基线master/3fc1338fc306444959433a41bdeaeefd705f58ec，01含dirty/untracked，02源码SHA，03原meta/bin，04既有配平全文件快照。

既有leveling.html列所有本地会话，leveling.js载入后清结果且不恢复存盘report；leveling.artifact_path依赖进程_jobs，重启旧结果下载不可用。202456三份现有report均TLS推荐/三法有效，最新27f870c6c7be43f4b9dc50121a5fc03f。本次不重算/覆盖它。另两个尚无report。console APPS四项，需第五项继续添加。

最小设计：新增validation.py（固定3sid、存盘报告读取/绑定/下载；调用现有leveling.start/source，不复制算法）和validation.html（复用leveling.js，显示3行概览）；leveling.js按页面模式选择API并恢复已有结果；原离线配平保持。human_replay_lib新路由仅本地；console追加卡片。leveling.py/estimators/quality不写。

| 操作/输入 × 状态 | 入口与赋值顺序/保留或失效 | 验收/检查 |
|---|---|---|
| startup与重启 × 完整历史/无结果 | validation.sessions扫描固定3sid；latest先校验绑定再提供report/transform/download | V02/V03/V05 HTTP |
| 同内容reload/同sid连续切换 × loading/ready | JS generation先递增清空→load源→latest→token检查→显示；旧返回无副作用 | V03/V05 JS/browser |
| 同sid异内容/源原地变化 × saved/running | current source SHA与report/manifest绑定不一致拒绝，既有run_job运行末校验保留 | V05负例 |
| 新sid × source/report/参数 | 清旧report/preview/ROI依据；只该sid返回可展示 | V05/browser |
| 非成员sid/错job归属/非法schema × 各API | 先membership，再existing request/source函数；拒绝无任务无写入 | V02/V05 HTTP |
| 损坏report/manifest/transform/缺文件/不支持schema × saved | 不恢复半成品；报告/核心meta-transform哈希验证；下载逐文件SHA验证 | V05负例 |
| caller修改请求 × running | existing validate_request拥有source/config副本；工作台直接复用，不另造job writer | V05复用leveling_test |
| 三法FAIL/冲突/成功 × ready | 拒绝也提供诊断报告；仅valid方法导出；不重用别会话变换 | V04/V06实际数据 |
| 202456既有 vs另两新job | 原report与源只读；每新job UUID新目录；新SHA快照区分 | V03/V06 |

固定3sid是新工作台范围，不限制原回放/离线配平。二维source域保留full height/no residual trim/3独立留帧；auto候选与手动对照分开记录，不暗中降门或把拟合高度当测量值。D01/真物理不适用本地交付，NOT_RUN。
