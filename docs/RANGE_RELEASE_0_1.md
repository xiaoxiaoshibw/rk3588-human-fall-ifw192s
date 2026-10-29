# Range Replay 0.1.0

首个 PC 显式离线源码发行版：当前点云逐帧经过 W1、W2、特征与规则，驱动可旋转点云、实测绿框、同源相机近邻、高度曲线、状态和报警页面。算法只消费当前及过去帧；confirmed 关闭。生产默认与设备服务不受此入口影响。

## 启动

需要已有 Python 3.8+ 与 NumPy。实际验证环境为 Windows Python 3.12.10/NumPy 1.26.4 和 Python 3.8.10/NumPy 1.17.4。发行包不含解释器、原始会话或模型，不自动联网安装依赖。

解压到任意目录，打开终端：

```powershell
python -B -W error run.py --check
python -B -W error run.py --session D:/Code/ldiar/data/sessions/cap_20261018_110029 --empty-prefix-frames 50 --paced --serve 8940 --open-browser --out D:/Code/ldiar/docs/evidence/my_new_replay
```

`start.cmd` 可接受完全相同的参数。`--session` 必须指向既有 `meta.json` 和 `points.bin`；`--empty-prefix-frames` 是明确的空场声明，不能把任意起始片段宣称为空场。输出必须是新的、位于输入和数据目录以外的目录。示例使用已声明50帧空场的386会话；更换会话须有它自己的空场声明。

可选 `--ground <既有绑定地面JSON>` 会校验会话、坐标、源字节和原始 provenance。地面文件与其 provenance 必须仍可读取；发行包不附赠或跨会话复用地面。省略地面时高度和规则证据 UNKNOWN。

页面仅监听 `127.0.0.1`。Ctrl+C 结束服务；正常处理结束后仍可浏览。`replay.html` 可双击复看最后最多240帧及相应近邻图片，完整逐帧账本另存。再次运行需指定新的输出目录。`--exit-after-replay` 用于自动化退出。

全帧确定性核对使用相同命令去掉 `--paced --serve 8940 --open-browser`；`--limit 120` 使用因果前缀。`--speed` 只控制本地回放节奏。源时钟、回放排队帧龄和设备端到端延迟分列，设备延迟 UNKNOWN。

## 页面与结果

绿点、点数、框和特征来自全部当前目标测量，抽样只影响绘制。预测、失锁、歧义与无效地面清空对应测量；跨目标、代次和观测断档不连接高度或报警区间。相机近邻只作预览，过期或加载失败隐藏；物理同步 UNKNOWN。

动态页面和服务各缓存最多240帧。暂停及历史跳帧保留选中帧，恢复跟随才跳到最新。跳帧只渲染，不重算算法。队列容量1，覆盖帧均保存处置原因；实际消费序列单独重放核对。

输出 `CONFIG.json`、`frames.jsonl`、`RULE_BASELINE.jsonl`、`SOURCE_ROWS.jsonl`、`ARRIVALS.jsonl`、`CONSUMED.json`、`timings.jsonl`、`display.jsonl` 与 `SUMMARY.json`。异常运行保留 `ERROR.log`/`FAILURE.json` 和已到达帧处置，不作为完整运行。正常运行以无 FAILURE 且 SUMMARY 存在为完成；逐帧差异及原性能门槛见 SUMMARY。文件与输入 SHA 被记录并在结束时重查。

`MANIFEST.json` 提供每份发行文件的 SHA256，启动前自动核对；它用于完整性检查，不是签名或发行者身份认证。ZIP 的 SHA256 单独随发行产物提供。源码树入口为 `pc_apps/range_fall/release.py`；打包入口为 `pc_apps/range_fall/make_release.py`。

## 已知限制

原 G1b 5.448% FAIL、f360 UNRESOLVED；原 G1c PC P95<10ms 和 G2 含跟踪 P95<15ms 尚未通过，PC20ms/板端30ms仅候选预算。首次背景初始化可能导致队列覆盖，必须读 ARRIVALS，不承诺零丢帧。780会话无有效同源地面，高度 UNKNOWN。

Python3.8/NumPy1.17 与3.12/1.26 的780帧 f716 有既有拒绝组合的刚体诊断漂移；两边均以 no_supported_fragment 拒绝，当前测量、目标行、特征和规则等价。完整数值一致性仍记 FAIL，不抹去诊断或放宽容差。

这是可运行、可审计的 PC 离线开发发行版。真实人体、身份、跌倒、浴室与物理同步效果均 UNKNOWN，不能据此晋级生产。设备部署、ARM性能、1h/24h现场运行及独立GT评测属于后续外部依赖；本发行不执行采集、拟合或部署。详细三轮性能及逐帧结果见仓库 `docs/RANGE_RUNTIME.md` 与发行证据目录。
