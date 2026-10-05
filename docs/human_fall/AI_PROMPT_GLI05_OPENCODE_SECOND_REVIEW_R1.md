# GL-I05 R1 OpenCode独立二审提示

本模板仅在主开发AI完成可审提交、停写并提供具体run_root/11_submission_manifest.json后派发；当前是准备状态，无实施/无probe/无二审结果。

指定OpenCode CLI `opencode-go/deepseek-v4.1-flash` / default DB。使用native skill(name=ponytail)，记录工具实际返回的路径；**不读取、扫描或哈希外部Codex技能目录，不比较技能文件字节**。不改model/DB/auth/权限/全局配置。不允许生产或研究原型返工写入；新二审scripts/outputs仅run_root/opencode_second_review_01/，每次失败/修订使用新编号脚本和输出，禁止覆盖自己或作者的旧证据。集中报告全部问题后，由编排者明确交接才能成为下一轮单writer。

读取WORKFLOW当前角色覆盖、GLI05_TASK.md研究契约、唯一GLI05_ACCEPTANCE.md v1、主开发本轮00_diag/计划修订/实验/manifest/回传，实际新研究代码及冻结依赖。不注入所有历轮。先核提交范围与SHA，审查结束再核；原始CLI真实session/model/defaultDB/exit由编排器日志/导出补齐，不猜session或称接口“interactive”。

按所有C/E/S/B/D条目及Q01–Q10集中独立审查，即使发现FAIL也完成其它安全独立检查。复跑作者tests只是部分证据，必须另外做手算/对抗fixture和同序列oracle检查：

- ALL、NEAR、BEST_ONLY的区分，NEAR池内全两两关系而非只best；最高支持tie、.8阈值两侧、middle-best/0-6-12°链不能漏判。weak distinct正例只能dominant而非all唯一；预算缺口不能在later strong best到达后消失。
- 新原型证明方法对0/4/8°全相似首锚/顺序的影响；近优true-distinct、close/late/tie、排序/代表更新/存储裁剪不误闭合；oracle限同已见序列，不把未见假设排除。
- raw/refine/拒绝/证明合并/未处理计数与每事件映射；candidate/refine/trace/iteration/证明/cache预算边界，所有closed对独立oracle正确；清洁/低噪与weak-dominant正例能闭合，不永远拒。
- cache若实现，验证source/fit全量/sample映射/up/height/settings/code上下文与精确成员依赖；相同mask与不同mask、伪造哈希碰撞、caller改数据/报告、跨run/settings变化、cache满回退或预算不足。不能用trace回读作无限候选工作缓存。cache不采用时核否定证据和未缓存正确实现，不要求为了验收新增缓存。
- 同source/selector/seed/settings/序列与冻结baseline/GL-I04比较；实际fit状态、研究oracle、posthoc holdout不混；分阶段公平计时、重复测量/资源峰值可核查，不新增无依据速度门或要求真实candidate必须过。
- 四固定box×全部source frames、空/alias/跨组、source索引与全统计，显示预算和frame切换；参考plane/WHAT_IF/source轴/未知extrinsic标签；局部产物不能被当calibration或GL04DPR证明。
- 时间绑定证据表与检索边界；没有记录保持B01/B02 BLOCKED，不把历史六零/frame/PCA/光学窗口高度升级为录制配置或物理身份。不按FIT残差改validation。
- 全树含untracked/SHA、原GL-I04及生产代码/配置/data/UI/HR/旧证据保持，外部共享树差异如实归因，Python3.8 AST/stdlib+NumPy，本机不代替目标板；manifest日志哈希正确，真实文件与原始输出存在。

实际报告00_review.md：SECOND_REVIEW_SUBMITTED/STOPPED，包含逐ID及Q PASS/FAIL/NOT_RUN/BLOCKED，要求来源/触发/实际/预期/根因/最小返工、独立命令exit和实际日志路径、首尾SHA/原生技能/会话身份（可由编排器补齐）、研究采用建议。不要复制作者结论当独立证据，不自行修改验收表/状态/ACCEPTED，不接入原型或启动设备操作。
