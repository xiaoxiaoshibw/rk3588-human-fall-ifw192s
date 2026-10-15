# HF-MAINLINE-LEVELING-01 · M3′ 第一轮真实实验

2026-10-14 / Windows 本机离线。SUBMITTED，自验完成，未 ACCEPTED；当前唯一验收为 [v2](ACCEPTANCE_V2.md)。使用 ponytail 与 scientific-toolkit-skill。

**结果：原失败已重现；直接共享选区及公共清洁域返工均未获得合格 leveling，因此没有新的 VALID 配准，也没有人体效果改善或成品晋级。** 本轮交付是可复跑实验与明确失败边界，不是只制定计划。

## 实际实现与范围

新增 `tools/hf_mainline_leveling/run.py`，完整复用原 `leveling.run_job`、`freeze_domain/compare/export_dataset`、`registration.writeJob/load` 与 `reg_gate_v1`；新增 FIT-only 选区诊断 `select_planar.py` 和四项 SYNTHETIC 契约检查。

source=cap_20261013_094333（164帧/8,055,529条28B记录），reference=cap_20261013_131958（97帧/4,765,607条记录）。nominal pitch=26°、roll=0°、高度参考1.14m。所有高度、opaque字段和全局源行保留；没有把新点身份写成人体或地面GT。

真实基线的两套新 UUID 是 d59fd9d11d6f4586b54a549254792477 与 8f449991793c41a8b8bda8b36e451937。原录制复制并核对 SHA 后作为隔离输入，新派生只在本证据目录的 `run_02/workspace/captures/leveled`。原 captures/leveled、latest 自动选择、8944页面、R3源码/结果、生产算法/默认版本均不改。本轮不另起网页或服务。

## 固定实验与失败

| 对照 | 实际运行 | 结果 |
|---|---|---|
| 原各自四区 | 两套 leveling 三估计器、全帧派生、完整配准与真实loader | 原 REJECTED 精确重现；fit_p50=0.02969084m、fit_p90=0.10573128m、holdout_p50=0.02467121m、inlier_ratio=0.4516091 |
| 094333四区同时用于双方 | 冻结四区/FIT/留出/TLS/SVD/RANSAC | 131958跨家族角差2.108359°>2°，offset差0.043213m>0.03m；三方法各自有效，但整体NO_RECOMMENDATION；没有强制采用TLS生成配准 |
| 131958四区同时用于双方 | 同上 | 094333 TLS全域RMS=0.296322m，P95=0.596886m，区域/留出失败；公共XY混入非平面，不是合格公共地面 |
| FIT-only公共清洁域 | 复用原25cm全高度格清洁门，双方clean cells=11/44，交集9格；既有四区跨度/条件门选区 | 只有一套满足跨度的组合；131958区域1 P95=0.053593m>0.05m，三个留出区域1也失败，NO_RECOMMENDATION |
| 公共域FIT平面质量返工 | 遍历9格四区组合，只用FIT；先原≥0.5m分离/条件比≥0.1，再原区域质量门；不读HOLDOUT结果 | 几何可行1套、FIT质量通过0套；没有改门或退回更窄区域以获得通过 |

候选共享XY不是独立证明的同一物理patch。公共域的四区坐标见 `run_03/FROZEN_CONFIG.json`，完整发现门与FIT帧见 `run_03/FIT_DISCOVERY.json`。共有9格并不证明九格共面。第三个对照的几何选择失败之后，补充的选区排序也只计算FIT统计；未根据HOLDOUT或配准残差反向调参。不是只因一项实验失败就停止。

基线的非PASS门项：fit_p50 WARN、fit_p90 REJECT、holdout_p50 WARN、inlier_ratio WARN。实际loader=REJECTED，默认融合关闭，显式flag也无法开启。未产生合格的新共享leveling就不向正式配准writer提交；三组共享候选的配准状态为BLOCKED_LEVELING_QUALITY，**不能声称它们fit_p90未塌缩，也不能声称已经跑出新的REJECTED artifact**。

## 源成员与回归

run_02两段TLS派生的全部12,821,136条记录逐块检查：XYZ精确等于原float64变换后float32转换；非XYZ全部字节相同；invalid/zero XYZ记录原样保留，两个录制分别1,233,506与724,299条；最大量化误差分别9.407e-7m、9.532e-7m。FIT源行与三个holdout行互斥。

run_02和run_03均对125个已列明保护文件执行首尾SHA（含原始两段输入、旧UUID完整产物、旧配准证据、原replay/leveling/registration源）；changed=[]。完整工作树状态及HEAD=c21c443b0befe559e08283edb0efc2af02dcc6b8、master、Python3.12.10/NumPy1.26.4/Node24.14.0见BASELINE。另一会话R3同期修改其权威文档和隔离源码，未纳入本轮变更或功劳。

本轮新增四项契约PASS；原registration测试23项检查PASS；原leveling unittest 4项PASS。Python带`-B -W error`。包括篡改opaque/invalid/XYZ检测、输出拒绝覆盖、选区不alias历史配置、共同域全高度污染拒绝；现有回归覆盖原门边界、fit_holdout_guard、SHA失效和non-VALID融合关闭。现有测试原始输出在实际工具执行记录，数量和完整命令实录在TEST_RUNS；本地新增检查完整日志在TEST_LOCAL.log，不伪造缺失日志。

首跑run_01读取domain.npz字段写成rows而非source_rows，退出1；已修正，失败目录/源码和说明完整保留。run_02完整退出0，run_03完整退出0；0仅表示实验完整运行，不表示几何合格。后续FIT遍历无可行域也退出0，仅表示诊断完成。

## 裁决与主线下一步

1. C01的“2.86°×3m约10cm”算术不成立：3*tan(2.86°)=0.149874m。角差仍是有效观察，不能由此证明10.57cm残差的因果。两次传感器实际位姿不同、区域地面形状和测量偏差均未独立分离。
2. 当前证据只排除了**本轮固定nominal XY共享方案作为立即放行路径**；不排除在独立物理对应/重力轴确认之后改进leveling。更不证明原配准门过严或科学。fit_p90单项PASS也不等于VALID，fit改善可能触发holdout guard。
3. 下一步算法开发优先做**冻结空场参考下的人体候选删点对照**：复用已有R1/R2五层源成员路径，区分KS1高度裁剪、KS2背景判断、后续选簇；在诊断范围保存被删候选的当前源行与删除依据，对低位/静立、家具、空场同时出数。保持UNKNOWN身份，不恢复未知点到生产默认，不等待人工GT才能做离线研究。
4. 094333↔131958配准继续BLOCKED，正式跨会话融合不启用。该阻断不应阻止已有同会话/共同参考假设数据上的隔离背景研究；假设条件必须明示。R3继续其当前FG碎片与粗部位范围，不替代上游删点修复。
5. 人工地面身份/物理对应/重力证据及最终人体身份验收单列，物理/独审/设备NOT_RUN或BLOCKED；M4不能被AI观察冒充完成。未训练、采集、部署、commit/push或confirmed。

## 复跑入口

从 `D:/Code/ldiar` 运行，`--out`必须是不存在的新目录：

```powershell
python -X utf8 -B -W error tools/hf_mainline_leveling/run.py --out <新目录>
python -X utf8 -B -W error tools/hf_mainline_leveling/run.py --shared-clean --out <另一新目录>
python -X utf8 -B -W error tools/hf_mainline_leveling/select_planar.py --discovery <公共清洁域目录>/FIT_DISCOVERY.json --out <新诊断目录>
python -X utf8 -B -W error tools/hf_mainline_leveling/test_run.py
```

工程自验记录见ACCEPTANCE_FINAL；实验运行与质量门分别报告，主线尚未交付通过人体效果验收的成品。
