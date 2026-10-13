# HFUS-D05 R05 实跑审核事实（尚非FINAL）

H4只改单次合法bank更新坐标为当前独立FG证明候选centroid，其余R04算法/配置/原模型不变。control/anchor各9会话合计2605帧，两个真实Node进程21200/10936均exit0，18个新ledger共5210行。CONTROL_PARITY实际exit0、2605帧全部点/候选/分类/确认/跟踪/strict/legacy精确一致R04。baseline15463文件master HEAD026e06303f60ed1bbe4ddc4d037836db68da6d27，errors/drift/missing为空，不声称全树原子冻结。

原“retained直接刷新银行”假设已被源码及实际事件账证伪：原链已排除MERGED/RETAINED刷新。家具57刷新帧全部有独立cleanup高分输入，FG误接受周期再入加有限恢复是真实问题。新的PA内部多候选同轨迹可使证明候选中心偏离PIPE EMA；far f4偏移.50468m，证明候选人工覆盖.9633/纯度.9738，同ID命中3候选。pre-fusion provenance和每个恢复点全部合格覆盖anchor保存在实际新ledger，不混同最终A/B标签。

analysis_v2正式审计exit0：42收益帧/24回退帧、全1530 PERSON对象诊断行、2605逐帧对照，D04冻结终端/candidates逐帧匹配不改旧账。CAUSAL_WINDOWS保存near210–227/far0–10及65–75两方连续窗口。

| 场景 | control strict observed TP/FN | anchor | control→anchor legacy confirmed TP/FP/FN |
|---|---|---|---|
| furniture175227 | 0/0 | 0/0 | 0/348/0→0/348/0 |
| near175429 | 184/74 | 185/73 | 255/541/3→255/549/3 |
| far175553 | 67/32 | 84/15 | 97/188/2→97/116/2 |
| walk175804 | 10/1 | 10/1 | 10/21/1→10/21/1 |
| turn175943 | 4/2 | 4/2 | 4/6/2→4/6/2 |
| occl180235 | 10/61 | 10/61 | 64/94/7→66/93/5 |
| 5m180337 | 7/5 | 7/5 | 11/10/1→11/9/1 |
| still180557 | 51/2 | 51/2 | 51/115/2→51/115/2 |
| S9 | INVALID_BINDING | INVALID_BINDING | 不报告正式精度 |

**H4注册收益门FAIL**：near总TP+1仍不能抵消f220–224五个保护帧全部TP→FN。其BG/cleanup人体点相同，原bank EMA恢复583/511/440/368/328人体点；当前FG证明在f217–219仅覆盖14.3/12.6/9.8%人体、center与EMA偏移.237/.197/.170m，盲目重定中心削弱后序真实恢复。far原center偏移>.4m则有收益。不是传感器极限。家具human重叠1/5、propagated351/1515两方相同，未解决纯FG高分误接受。独立负例/连续身份/退出/S9仍BLOCKED。

纯性能：FULL_COMPARISON_V2→REPLAY_CONTRACTS→PERFORMANCE真实串行，均实际exit0；first5预热，tick内无trace/owner/读盘/渲染/序列化。control8/9场超原50ms、anchor6/9超门，Windows不冒充板端。旧R04<50记录保留，但不能替代本轮失败。没有证据将时差归咎传感器、热降频或CPU外部竞争；具体软件/运行原因待独立性能探针，不盲重跑删失败。

| 场景 | control p95 ms | anchor p95 ms |
|---|---:|---:|
| furniture | 54.850 | 52.499 |
| near | 70.775 | 54.648 |
| far | 72.178 | 59.063 |
| walk | 50.358 | 48.981 |
| turn | 54.792 | 50.438 |
| occl | 50.128 | 49.735 |
| 5m | 67.244 | 77.288 |
| still | 48.941 | 46.603 |
| S9探索 | 64.734 | 61.748 |

软件重复/倒放/gap/reset/跨会话两方真实契约PASS，真实身份/退出不以零重复ID或有限coast代替资格。原始事件同ID超秒TTL再入漏标P2由BANK_EVENT_CASES_v2同时按秒/帧TTL派生，raw不覆盖。两次分析失败保持log/exit/partial账：v1银行审计枚举大小写、analysis_v1 UNKNOWN NULL访问；v2双方同口径完整重算，原评分不改。

Demo v1实际显示调用[]及融合分数被标raw的缺陷保留原源、DOM、截图；新demo_v2/8917显示真实model_calls、PA内部概率、fusion_p，union_model_p=NOT_RECONSTRUCTED；实际恢复/相对control点集增删、bank坐标、confirmed观测/有限coast与GT来源分离。真正浏览器九会话/控制与截图正在新固定tab3句柄验证，不能把v1或跨tab错误导出当当前PASS。

当前已实证远行f5：control纯度.5335/覆盖.9762→anchor纯度.8205/覆盖.9854，严格FN→TP；相对control移除4718 final点，仅6有人体参照支撑，新增702点其中65有人体参照支撑。净BG14点中无human支持，不说成“恢复14个真人点”。此帧有收益，不抵消near回退。

本轮停止扩大“每次都锚定当前FG中心”。下一假设需另登记：当旧EMA中心仍在当前证明中心的既有0.4m恢复圆内，保留它；仅超出原恢复半径时考虑修正。这使用原配置半径/当前点云与允许历史，不用GT或未来帧，尚未运行，不冒充成果。先完整Demo/指定独审/追加return，再进入新离线返工轮次，不启动HFUS-D06/D07。

writer主控；实际ponytail C:/Users/30680/.codex/skills/ponytail/SKILL.md；源码/模型实际加载SHA各SUMMARY，R05工具源码TOOLING_SOURCES_V2。工程材料部分待真浏览器/独审/结束SHA，算法FAIL、GT/生产BLOCKED，部署/采集/驱动网络/板端/物理NOT_RUN，未ACCEPTED。
