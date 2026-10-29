# 最终展示形态与当前离线实现

用户指定的最终展示形态固定为：左侧可旋转的实测点云与目标绿框、右侧相机、下方高度曲线/状态色条/时间轴，以及随当前疑似状态变化的报警条。实现入口为 `pc_apps/range_fall/replay_compare.py`，模板为 `replay_template.html`。它消费已保存结果，不运行地面/模型拟合、背景统计、跟踪或规则更新。

## 两种输入

```powershell
# 保留指定126帧样例效果，仅重绘已保存的显示数据
python -B -W error pc_apps/range_fall/replay_compare.py --session data/sessions/cap_20261023_221125 --saved-view docs/evidence/2026-10-23_single_person_fall_compare --out docs/evidence/<new_saved_view>

# 用已审计因果W2和相同来源的规则账本生成同款页面
python -B -W error pc_apps/range_fall/replay_compare.py --session data/sessions/cap_20261018_110029 --replay-run docs/evidence/2026-10-23_range_sync_integration/verified/replay_386 --audit-run docs/evidence/2026-10-23_range_sync_integration/complete/audit_386 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --out docs/evidence/<new_causal_view>
```

输出新目录，不能覆盖现有产物、源会话、data/captures 或输入目录。`--no-preview` 可用于没有Pillow的本地兼容环境，HTML、账本与算法无此依赖。`--title` 只改变页面标题，文本会转义。

保存样例模式核对源会话/标定/地面绑定、显示数据与逐帧账本，以及已有 `CHECKS.json.artifacts` 的冻结SHA。没有冻结清单时明确记 `UNVERIFIED_NO_FROZEN_MANIFEST`。旧126帧样例没有完整实测来源行，只记录 `UNAVAILABLE_IN_LEGACY_DISPLAY`，不能冒认W2来源审计。其背景仍是整段p98、非因果；旧地面已拟合，本轮不重新拟合。

因果模式要求 `range_experiment` 的SOFTWARE_AUDITED报告、内容摘要、输入W2三文件、完整源码清单、规则/来源账本、原始会话与地面/provenance匹配。逐帧再核对raw SHA、offset、时间、推理摘要、规则目标行和稳定实测标志。只解码当前原始XYZ用于显示；显示抽样不进入算法，框使用全部目标行。无地面时保留RAW参考网格，高度UNKNOWN。

## 已处理的显示问题

- 无实测目标时绿点/绿框/测量为空，状态为未知；预测和歧义不能显示成“无跌倒”。高度未知不画成零米，曲线在目标、代次、时钟或观测断档处断开。
- 横轴按源时间；时钟回退显式切为帧序。播放器按源时间截止点调度，扣除绘制耗时，末帧停止；不能据此宣称算法实时达标。
- 报警按连续实测区间分别着色，状态条不跨断档延续旧状态。顶栏报告首次嫌疑与累计实测帧数，不把分离区间写成一整段报警。
- 相机按已有bag墙钟与主机接收时间取近邻，不参与算法。0.20s仅为画面新鲜度预算，超时、加载中或失败时隐藏旧图；延迟回调不能盖过新帧，同图跨雷达帧更新当前时间差。物理同步UNKNOWN，无外参、不投影点云。
- 常驻模式、非因果或显式前缀、GT/物理同步UNKNOWN与confirmed关闭标识。显示坐标中的传感器原点按已有地面变换放置。

## 本轮验证与入口

证据 `docs/evidence/2026-10-24_range_replay_view/complete/`：

- [126帧同款效果页](evidence/2026-10-24_range_replay_view/complete/saved126/index.html)，不重跑原非因果算法，112帧绿框、23个疑似帧保持；原始页与历史证据保留。
- [386帧因果W2页](evidence/2026-10-24_range_replay_view/complete/causal386/index.html)、[780帧因果W2页](evidence/2026-10-24_range_replay_view/complete/causal780/index.html)。这两段没有配套相机，界面如实显示缺失；不拿另一会话图片补齐。
- 15项新增Python、14项JS、45项range合同、9项既有显示helper与7项旧页面测试通过。Python使用`-B -W error`。旧生成器的真实会话重建会调用拟合，本轮未执行；新增入口完成真实126/386/780及120帧前缀导出。
- 本地Python3.8.10/NumPy1.17.4运行15项新增测试、126帧保存样例与386帧审计结果导出；不是ARM或板端测试。
- 首轮旧预览极慢（126帧导出102.269s），数值检查发现7条屏幕坐标含NaN但深度有限的网格线。保留日志、部分输出及中断记录；新预览只把有限、近面前方且坐标有界的线交给光栅器。新PNG是同源数据绘制预览，不是浏览器截图。

原G1/G2失败保持，f360语义UNRESOLVED。人体/身份/真实跌倒/浴室效果、物理同步和新链板端性能UNKNOWN。这里交付的是可复用离线展示入口，未部署或改生产默认；后续沿同一测量/状态契约推进运行时与性能，不以展示效果代替GT或预算通过。

2026-10-24 已在同一模板接入[显式逐帧运行时与源节奏回放](RANGE_RUNTIME.md)：`pc_apps/range_fall/runtime_replay.py`持续发布当前帧的W1/W2、既有特征与规则输出，PC本地服务只绑定127.0.0.1。服务/页面各缓存最多240帧；暂停/历史选择独立于后台算法，源帧缺口断开曲线和报警。原导出入口继续用于保存样例/已审计账本，新入口不把126帧非因果样例当因果运行时验证。
