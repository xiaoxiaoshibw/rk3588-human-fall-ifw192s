# GL-A R1 返工（R2）集中诊断：canonical_plane offset 未同步归一

日期：2026-10-05。来源：独审 FAIL（`../2026-10-05_agl_a_r1/31_OPENCODE_VERDICT_01.md`）；契约 §1「归一化时 normal 和 offset 同除 norm」；验收 AGL-A-02「n/d 同步 normalize/flip」。

## 根因（一行）

`core/adaptive_ground/contracts.py` 的 `canonical_plane` 只做 `vector = vector / norm`，**offset 原值保留** → 非单位法向输入时返回的平面被放大 ‖n‖ 倍：
`(0,0,2)·p − 2.64 = 0`（z=1.32）被返回为 n=(0,0,1)、d=−2.64（z=2.64）。

## 受影响入口 / 消费者 / 测试缺口

- 入口：`canonical_plane`（`assemble_estimate` 公有装配路径经此）。
- 消费者：三个适配器当前只传单位法向（eigh / SVD / cross÷‖cross‖），产物未受损；受损面是该公有入口对非单位输入会生成"残差按错误平面计算且无报错"的记录。
- 测试缺口：A-02 原用例只用单位法向（÷1.0 不可见）；无缩放输入反例。与作者 `00_diag.md` §0「n/d 同除归一」自相矛盾，属实现遗漏。

## 最小修复位置

`canonical_plane` 在 `vector = vector / norm` 之后、符号对齐（alignment/flip）之前增加：

```python
value = value / norm
```

同类入口一次查完：`angles_from_normal` 只归一向量、无 offset 配对；`validate_plane_estimate` 为只读校验（要求单位法向 ≤1e-9）；全包无第二处 n/d 归一入口。

## 保留行为

- 单位法向输入：`norm==1` 时 `value/norm` 与原值在浮点意义下 ≤1 ulp 差异；全部既有断言（places≤12、容差门）之外的变化需以 R2 回归与样例 manifest 字节对照为准。
- 符号翻转仍同时作用于归一后的 n 与 d。
- 非法输入（零范数 / 非有限 / bool / string）拒绝行为不变。

## 检查计划

1. 先加回归用例（修复前运行，必须 FAIL）：缩放 n 直接入口两例（含翻转）+ `assemble_estimate` 全链（offset=1.32、RMS≈0）。
2. 修复后：GL-A 专项 + 全量回归 + 冻结哈希/HEAD 核对。
3. 留存：修复前复现（01_repro_before_fix.txt）、修复前回归 FAIL 日志（10_regression_before_fix.txt）、修复后日志、样例 manifest 字节对照。
