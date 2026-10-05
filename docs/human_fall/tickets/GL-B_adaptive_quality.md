# GL-B：Estimator Quality与confidence / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN；等待A软件验收及后续启动。唯一表在本文件。来源：[最终计划](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约§4](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。

## 目标与范围

新增quality模块：共同全点及逐区RMS/P95/MAD/support、point_count、tangent coverage、eigen谱退化、normal合理性与geo score。规则与全部soft/hard参数集中于版本化新profile；不只看RMS，不调用时间controller，不把confidence当真实概率。先声明/冻结soft_good、hard reject、权重与区域支持策略的完整合法候选profile，然后检查；不写生产YAML。

前置：A统一schema/domain。输出QualityReport/score_components/hard_gate_results/reject_reasons；B输出单估计器geo quality，不提前给FINAL资格。

## 前置诊断矩阵

clean/noisy/plane+人/箱/平行台面、多ROI缺失；相同RMS但点数/覆盖/线状退化不同；norm/offset/malformed；region权重/支持分母；bad startup/config reload；caller mutation × 后续估计/消费者。所有quality入口使用同domain snapshot。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-B-01 | 全共同域及逐区未裁尾残差与独立标量oracle≤1e−12m；RANSAC内支持另列；不能用inlier RMS替换full | full/region residual oracle | NOT_RUN |
| AGL-B-02 | min_points/min支持区/coverage与λ2/λ3退化hard gate；共线、窄带、少量/单格集中低RMS也必须invalid | analytic line/strip/two-dimensional GT | NOT_RUN |
| AGL-B-03 | score∈[0,1]，非法输入score0；7几何分项+上游normal/区域门；hard fail不能由平均score救回；参数soft/hard关系严格 | score monotonicity/boundary/negative inputs | NOT_RUN |
| AGL-B-04 | 四ROI整体好但某必需区域FAIL仍降级/拒；墙/箱顶/竞争平面不以多点/低RMS签ground truth；P02已知留一区失败原样记录 | existing P02 fixture + mixed-geometry cases | NOT_RUN |
| AGL-B-05 | score_kind/分项/计数/cover basis/参数SHA可追溯；缺basis或无版本不默认世界XY；caller/reload无旧score泄漏 | schema/basis/epoch consumer matrix | NOT_RUN |
| AGL-B-S01 | 最小module/stdlib+NumPy/Python3.8；diag→自验/回归/SHA/停写→指定独审；旧规则/生产不改 | scope and return/independent review | NOT_RUN |

## 交付

quality module、完整候选profile规范（未启用）、集中几何/score检查，`evidence/<date>_agl_b_rN/`、`returns/GL-B.md`逐ID；真实accuracy/ROC缺证据明确NOT_RUN/BLOCKED。不为旧数据过门提高max_p95。不自动进入C。
