# SEM-05～08、10 逐项重验

现行唯一表 v1未修改；正式95%总帧门与人工全帧身份/批准连续映射要求保持。固定源与job：R1 pass3/binding.json（独立固定SHA 2f0f3aaaf6b6c62aedcf5b02de30539da13cc0afce324d7dc4fba44ccdb26416）；旧负例negative4/binding.json和固定金标来源。全帧使用原始meta/bin、冻结TLS/诊断矩阵与原pipeline，不挑解、不调阈值。

命令和各源码/输入摘要、exit/输出在 full_recompute.run.json、data_r2.run.json、negatives.run.json、edge.run.json、WD02_contract.json；详细原始输出recompute.json/data_audit.json/negative_recompute.json/edge_source_audit.json。全部上述必要验证exit0，算法判定独立于执行成功。

| ID | 实测结果 | 真实依赖/阻断 | R2状态 |
|---|---|---|---|
| SEM-05 | 114205 REF_SHADOW，244帧/519簇，13 HUMAN帧，上界5.33% | 原meta人工标注0、无全帧批准身份映射；上界已不足95%，不能声称只等GT就可过；gate WARN未运行正式V2 | BLOCKED |
| SEM-06 | 114254 REF_SHADOW，271帧/819簇，269 HUMAN帧=99.26%结构代理 | 非ROI成员、家具混入/连续身份未人工确认；gate WARN；代理不升准确率 | BLOCKED |
| SEM-07 | 114340离线V2，281帧/815簇，281 HUMAN帧结构代理 | 185参考删除点+5 cleanup点+全部边缘身份UNKNOWN；91.92%区域指标不等于人体保留；缺全帧GT | BLOCKED |
| SEM-08 | 114422离线V2，195帧/576簇，1 HUMAN帧，上界0.51%；HEAD0/ARM45/LEGS1/TORSO195 | 原meta人工标注0、全帧身份缺失；目标上界已不足95%，不补头/不裁ROI凑票 | BLOCKED |
| SEM-10 | 旧可用448分支帧/2210簇/458区域结果与R1一致；旧空场54帧283簇0 HUMAN | WD01 P4/WS12区域HUMAN身份待GT；箱子64次UNKNOWN、low_bar64次空输入NOT_RUN有效负例、格栅NOT_RUN；WD02契约待裁定/0处理帧 | BLOCKED |

SEM-05～08源meta的human_annotations均为空（全管线recompute与原summary一致）；本轮生成的browser_synthetic_export只是UNKNOWN自动化夹具，不计真实GT。R2新receipt校验能够可信绑定审阅对象，但并未新增人工标签、批准连续身份或对抗采集资产。

依赖关系：SEM-05～08→可信审阅工具（SEM-12已修复）+人工成员/全帧GT；SEM-10→WD01实例/混合身份GT+有效非空箱子/格栅/横条覆盖+WD02裁定后同固定输入测试。SEM-12解除的是工具依赖，其他依赖尚未解决，因此没有BLOCKED自动转PASS。

只重放已有获授权输入。WD02保持未处理，未采集补数据。R1旧WD01全簇只读索引/交集可定位，但R2页面仍仅覆盖五段新会话；旧负例还需要单独可信审阅入口与人工闭合，这是证据依赖缺口，未在本单扩大成新管线。
