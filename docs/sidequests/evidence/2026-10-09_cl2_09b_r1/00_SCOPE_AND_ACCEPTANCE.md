# CL2-09B 唯一验收表 v1

2026-10-09，用户在明确“CL2-09B离线修复、不部署”的选项后回复“好的继续”。Codex唯一writer；ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。

新candidate源码副本及patch只在本目录，不接运行中的生产模块、不改冻结v1/v2源、原始会话、旧evidence、TLS求解或门控。此表仅CL2-09B；CLUSTER01 v1历史验收及09A不改。回传追加CLUSTER-01；若无法写原return则报告真实阻断，不重造历史。

| ID | 验收要求 |
|---|---|
| B01 | 冻结source/input/历史SHA；main全文件含untracked/ignored仅作上下文，执行用冻结副本 |
| B02 | 5格反例修复；候选必须同时满足原间距≥0.5m、独立4、条件数≥0.1；不降低任何A/B门 |
| B03 | 原selector所有成功结果逐字保留；无可行四区仍拒绝，稳定排序/并列策略可复验 |
| B04 | ≤24和>24失败路径检查；失败后完全搜索可行四区，记录最坏O(n4)离线成本与实测规模，不假称板端时延PASS |
| B05 | 直接入口及v2/v3调用者回归；v1成功verbatim、身份/purity不变；Python3.8语法兼容、-W error |
| B06 | 121647原ROI/TLS/门控不变、原选择成功不会换区；其有效TLS仍BLOCKED；不生成替代放行数据 |
| B07 | OpenCode指定模型真实只读独审；保存version/help/模型、有效权限、argv/stdout/stderr/exit及实际session身份 |
| B08 | 证据manifest及起止SHA复核；append-only return；原日志/失败全部保留，不自行ACCEPTED |
| E01 | 接入运行中的生产、发布Console、部署：BLOCKED（未授权） |
| D01 | 设备、物理、采集、B2/B3：NOT_RUN（未执行） |

## 实现前集中诊断与覆盖

根因：v2在≤24枚举中先最大化min_sep，再检查唯一获胜组合的条件数；>24也只查一次贪心组合。共线最大间距失败并不证明不存在合格四区。调用者floor_sheet.detect_floor_regions_v2及floor_roi.detect_floor_regions_v3；后者自己的15cm `_select_four`已有feasible-before-rank，保持不改。

修复策略：先计算旧选择及完整旧结果，若通过原样返回；仅旧失败时按稳定组合序完整枚举，同时查原间距/独立/条件门，在可行集最大化min_sep。无可行项返回旧失败诊断。完全共线集合可用叉积恒为0快速证实不可行。旧成功贪心>24不重新排名，避免无故换ROI。最坏失败搜索O(n4)只作为离线候选，本轮不接生产。

| 操作/状态 | 覆盖 | 保留/失效规则 |
|---|---|---|
| startup/重复同内容/输入顺序变化 | 五格+随机完整oracle、重复及反序测试 | 确定排序，不修改caller列表 |
| 无四区/距离不够/所有共线/条件不足 | 合成negative，含>24全共线 | 保持拒绝，不通过放宽门控 |
| 旧成功/等间距并列/边界阈值 | 新旧完整dict比较，原间距0.5边界 | 旧成功逐字返回 |
| >24旧贪心失败但局部存在可行项 | 构造候选集+完整oracle | 失败兜底不能只换一个seed |
| 身份层失败/dirty ROI/15cm fallback | 原floor_detector/sheet/roi suites | 不修改A层、purity、15cm实现 |
| 同ID异内容/新IDreload/损坏父记录/生命周期 | 不改loader/version/产物加载；仅候选纯函数，相关项NOT_RUN | candidate manifest使用源码SHA新variant标识，不替换旧report或冒称同版本 |
| 外来frame/非法解码/校准变化 | 现有源校验不修改，09A固定输入复核 | 仅处理clean cells，不改decoder/坐标/TLS |

本轮产物是可审查离线修复候选，不是生产接入许可。若性能或独审产生新FAIL，留存失败并在范围内修复；设备/物理不能由合成测试替代。
