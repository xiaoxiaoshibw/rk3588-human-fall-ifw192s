# 标定距离图的2D形状旁路

首轮实现计划阶段1—3：固定基线、描述同帧真实目标、检查连续观测与开销。`core/range_shape.py`只返回描述子；`tools/range_shape_shadow.py`运行独立离线对照。生产节点、W1/W2、关联和跌倒状态机均未修改。

## 数据流与适用范围

当前帧 → 原有RangeRuntime（W1/W2 + 原规则）→ 同帧目标source_rows → ShapeObserver。

`shape_features(frame, rows, labels=None)`也可接收3D候选的真实来源行，并不要求候选由2D分割生成。但本轮CLI评估的是W1/W2旁路，不能称为报告B0或生产3D链已经完成融合。背景、地面、候选和轨迹均沿用各自绑定；没有新拟合或训练。

## 描述子

| 字段 | 定义与边界 |
| --- | --- |
| pixel_count / bbox_rc / row_span / col_span | 当前目标实际命中的唯一栅格数量、含端点包围范围及跨度；不是原始点序reshape |
| fill_ratio / aspect_col_row | 像素占包围矩形比例、列跨度/行跨度；只是栅格形状，不是人体完整度 |
| azimuth_span_deg / elevation_span_deg | 选中栅格的标定角最大值减最小值；单像素中心角跨度为0，未估计像素足迹 |
| range_squared_sum_px_m2 | Σr²，补偿像素数量随距离变化的代理量；未乘标定固体角，不是物理面积，不能直接跨标定比较 |
| boundary_edges / touches_grid_boundary | 当前目标是否接触方向表四边；不等价于真实人体被截断，也不含8m处理窗边界 |
| adjacent_invalid_fraction | 目标像素中，存在至少一个表内四邻域无有效回波的比例；表外单独计边界，不推断遮挡原因 |
| fragments / largest_fragment_fraction | 当前目标在既有深度组件标签中的像素分布；标签缺省时unknown，不另建独立物体计数 |

不填孔、不裁边、不扩张、不把未选点加入目标。`completeness`、`occlusion`和人体语义均为UNKNOWN。输入必须是唯一、非空、可一一映射到本帧有效测量的来源行；被最近回波规则拒绝的重复点不能重新进入。

## 时序契约

ShapeObserver仅接受稳定、实测且来源行与当前选中轨完全相同的目标。预测、竞争、缺测不输出形状，并清空历史。身份键包含来源绑定、grid SHA、generation和track ID；换身份、重复/回退时间、超过0.3秒间隔、源帧不连续均重置。历史窗口最多1.2秒/128帧，触及容量后显式重开连续段。

输出连续样本数、实际覆盖时长、像素数及Σr²的相邻观测比、像素数相对窗口首观测比。首观测无历史比值，不补零、不补预测、不跨断档累计。上述窗口和容量是软件选择，未被验证为最优识别参数。暂不输出站/跪/躺分类，不改变原有下降或低位累计门。

## 运行

从仓库根目录运行，输出必须为新目录，且不能位于原始数据目录中：

```powershell
# 因果386帧；使用原有同源绑定地面，缺失或不匹配即拒绝
python -B -W error tools/range_shape_shadow.py --session data/sessions/cap_20261018_110029 --empty-prefix-frames 50 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --out docs/evidence/<new_386_run>

# 因果780帧；无同源地面，不借用386地面
python -B -W error tools/range_shape_shadow.py --session data/sessions/cap_20261017_113516 --empty-prefix-frames 50 --out docs/evidence/<new_780_run>

# 126帧无因果空场条件；显式整段p98，仅探索形状，禁止冒称在线验证
python -B -W error tools/range_shape_shadow.py --session data/sessions/cap_20261023_221125 --exploratory-p98 --rounds 1 --out docs/evidence/<new_126_exploration>

python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_range_shape.py
python -B -W error -m unittest discover -s tools -p test_range_shape_shadow.py
```

默认依次运行一轮关闭旁路的基线及三轮开启旁路的回放，逐帧比较完整跟踪/规则/状态摘要、重复运行描述子，并检查旁路前后的记录和解码数组未变。只写描述子、来源行摘要及计时，不复制点云或相机。`--limit 120 --rounds 1`用于独立前缀对照。p98探索始终使用完整会话建背景，不能用于因果前缀证明。

CONFIG绑定实际解释器/NumPy、全部core源码、入口、标定、输入和地面provenance，运行结束重查。旁路开销包含构造继承组件标签；基线JSON、数组未变检查、读写盘及哈希不计入该阶段。`event_plus_shadow_ms`为逐帧实际阶段耗时相加后取分位，不能将两个P95直接相加，也不是发布循环或设备端到端耗时。没有新增整链性能通过声明。

SUMMARY中`inference_sha256`是逐帧推理摘要十六进制字符串拼接后的SHA，不是历史工具对完整纯推理JSON拼接的摘要，不能直接与历史`c8ad205a…`比较。本轮逐帧对照使用完整跟踪/规则/状态的`baseline_sha256`及来源行摘要。

## 2026-10-24 实测

采用独立串行的`serial386`、`serial780`，各一轮关闭旁路基线和三轮开启旁路；早期与全树扫描/测试重叠的运行保留但不用于最终计时。

| 项目 | 386帧 | 780帧 |
| --- | --- | --- |
| 可计算形状的帧 | 269 | 355 |
| 目标触及方向表边界的帧 | 15 | 23 |
| 目标包含多个既有组件的帧 | 2 | 20 |
| 三轮对原跟踪/规则/状态的逐帧差异 | 0 / 0 / 0 | 0 / 0 / 0 |
| 三轮旁路P95，非预热全部帧 | 2.677 / 2.625 / 2.641 ms | 2.945 / 2.836 / 2.890 ms |
| 三轮旁路P95，仅有实测目标帧 | 2.712 / 2.677 / 2.674 ms | 3.258 / 3.109 / 3.301 ms |
| 原事件链加旁路逐帧总和P95 | 30.557 / 28.911 / 29.556 ms | 35.691 / 36.188 / 35.426 ms |

旁路描述子三轮一致，两段独立120帧前缀与全段前缀一致。真实386源序列跳过f104后，f105时序历史重开为1个样本，历史比值为null；没有跨缺帧累计。46份原有core源码SHA保持不变。

126帧p98探索有112帧可计算形状，但没有一帧目标触及方向表边界；入画早期f2/f3/f4/f6分别仅52/44/49/103像素，邻接无回波比例44.2%/45.5%/49.0%/35.9%。因此未触边不能证明完整，邻接无回波也不能直接解释为遮挡。f30与f68的像素数5330/755、列行比0.444/1.359，中位距离1.283/2.357m，Σr²代理9266.85/4159.03 px·m²；这些是同源可观测差异，没有转换成人体姿态或跌倒真值。

核心全量771项在新增第10项测试前通过；最终2D定向10项、独立入口3项、原运行时13项均通过，Python均`-B -W error`。新增4份Python文件通过3.8语法解析；缺少实际3.8环境，未运行3.8/NumPy1.17.4或ARM测试。原有核心套件的合成地面拟合测试单列，不代表本轮对真实会话做拟合。

## 本轮边界与下一步

结果见`docs/evidence/2026-10-24_range_shape_shadow/`和项目进度。现有历史逐帧JSONL曾被数据清理删除，本轮重新生成同版本关闭旁路对照，不把缺失历史账本标为已复核。Python3.8运行目录当前缺失，只能报告本轮实际执行环境及3.8语法解析情况。

辅助信号能算出，不等于能判断人体完整、遮挡或真实跌倒。下一阶段先分析边界接触/面积变化与观测缺口的关系，只有能解释收益及回退后才单因素接入规则；不能用报警变少证明效果变好。原G1/G2失败、f360语义未解决、真实跌倒和板端性能UNKNOWN继续保留。
