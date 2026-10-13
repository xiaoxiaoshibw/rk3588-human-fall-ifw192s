# HFUS-D05-R04 唯一验收 v1（2026-10-12，实验前冻结）

用户当前明确授权的持续离线返工；不是D05a/D05b，不启D06/D07。唯一writer为Codex。ponytail实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。新源码仅 `sidequests/human_fusion_lab_next/d05/r04/`，新证据仅本目录。基线15338文件覆盖tracked/untracked/ignored，无读取错误/检测到漂移；非原子扫描且R03分析输出当时仍运行，不声称全树冻结。边界与R02/R03同样，冻结资产只读、无Git写/部署/采集/生产/驱动/网络/ML。

## H3 单因素：A06 等价短路优化

源码已证实邻居计数 nb 是非负整数，minLocal=1 时 `(nb===0||nb>=1)` 恒成立，局部邻域计数对A06结果没有约束力。只在这个条件下跳过邻居网格构建与邻居遍历；参考支持计数达到minRef即可停止，因为消费者只判 `<minRef`。保留r=.6、link=.3、minRef=1、minLocal=1、z>.1、reason/state/stats、R02 split与全部跟踪/模型参数。minLocal>1回退原完整密度计数，不引入新语义。不纳入R03失败分类gate。

H3预期语义完全等价且降低纯算法p95；九会话任一帧实际成员/背景mask/组件/候选/分数/确认/跟踪/指标差异就是FAIL。性能原门p95<50ms不降低；如果仍不达标如实FAIL。算法效果冻结为R02split部分收益，不称新真人收益，不改变家具与GT资格BLOCKED。

| ID | 冻结要求 |
|---|---|
| R04-01 | 起止branch/HEAD/status和tracked/untracked/ignored SHA、变化/错误/运行中文件单列 |
| R04-02 | 等价逻辑源码检查、稀疏/稠密/边界minLocal反例对拍，原统计语义保持，GT-free |
| R04-03 | 九会话完整实跑、加载源码/config/model/input/GT SHA/退出码；逐帧mask/组件/候选/跟踪/strict/legacy相对R02split精确一致，保持冻结D04对照 |
| R04-04 | 无评测竞争串行纯算法计时、统一前5帧预热、p95<50ms，读取/instrument/render另列，Windows不冒充板端 |
| R04-05 | 最終可操作3窗Demo包含R04以及R03失败对照；九会话/播放暂停/步进/拖动/重置/同帧时间戳/UNKNOWN/原始分数与原因/SHA校验/真实浏览器证据 |
| R04-06 | 指定OpenCode opencode-go/deepseek-v4.1-flash只读最终独审；真实exit/模型/完整指令与缺陷处理 |
| R04-07 | 源码SHA、逐帧账/逐场景/成功失败索引/人工最小包/追加return；工程、算法、GT、生产独立裁定，不ACCEPTED |

继续依据：R02远行和走停走真实收益，H2家具减少但近距184→179证伪无回退假设，应停止扩大此分类规则。H3只处理已证实无作用的计算，不隐瞒家具自维持/远行剩余32FN/转身BG损失/遮挡混簇/不充分GT。
