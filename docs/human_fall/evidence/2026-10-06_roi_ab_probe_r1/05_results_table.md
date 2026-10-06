# ROI A/B 对照表（4 golden）

SHADOW 在三会话全部把 ROI 换成了**不同格子**（`changed=true`）；223757 作为 control 仍走 v3。

## cap_20261004_202456（v1）

| 指标 | CURRENT | SHADOW | Δ |
|---|---|---|---|
| ROI 中心 x 范围 | [1.375, 2.375] | [1.625, 2.625] | 内移 |
| min_pairwise_sep_m | 0.75 | 0.50 | −0.25 |
| condition | 0.750 | 0.721 | −0.029 |
| max local RMS (m) | 0.0140 | 0.0103 | −0.0037 ✅ |
| mean local RMS | 0.0104 | 0.0080 | −0.0024 ✅ |
| min_frame_count | 40 | 39 | −1 |
| λ2/λ3 | 0.813 | 0.817 | +0.004 ✅ |
| TLS full RMS | 0.01391 | 0.01061 | −0.0033 ✅ |
| RANSAC full RMS | 0.01482 | 0.01104 | −0.0038 ✅ |
| max pairwise normal disagree (°) | 0.618 | 0.417 | −0.201 ✅ |
| holdout worst RMS | 0.01670 | 0.01320 | −0.0035 ✅ |
| valid estimator count | 3 | 3 | 0 |
| recommended | tls | tls | 同 |

## cap_20261004_203135（v1）

| 指标 | CURRENT | SHADOW | Δ |
|---|---|---|---|
| min_pairwise_sep_m | 0.50 | 0.50 | 0 |
| condition | 0.435 | 0.548 | **+0.113** ✅ |
| max local RMS | 0.0148 | 0.0148 | 0 |
| mean local RMS | 0.0108 | 0.0093 | −0.0016 ✅ |
| min_frame_count | 39 | 55 | +16 ✅ |
| λ2/λ3 | 0.272 | 0.220 | **−0.052** ⚠️ |
| TLS full RMS | 0.01437 | 0.01391 | −0.0005 ✅ |
| max pairwise normal disagree (°) | 0.697 | 0.392 | **−0.305** ✅ |
| holdout worst RMS | 0.01709 | 0.01747 | +0.0004 ⚠️ |
| valid estimator count | 3 | 3 | 0 |
| recommended | tls | tls | 同 |

## cap_20261004_203349（v1）

| 指标 | CURRENT | SHADOW | Δ |
|---|---|---|---|
| min_pairwise_sep_m | 0.75 | 0.50 | −0.25 |
| condition | 0.750 | 0.721 | −0.029 |
| max local RMS | 0.0139 | 0.0104 | −0.0035 ✅ |
| mean local RMS | 0.0103 | 0.0080 | −0.0023 ✅ |
| λ2/λ3 | 0.811 | 0.817 | +0.006 ✅ |
| TLS full RMS | 0.01383 | 0.01063 | −0.0032 ✅ |
| RANSAC full RMS | 0.01490 | 0.01076 | −0.0041 ✅ |
| max pairwise normal disagree (°) | 0.331 | 0.239 | −0.091 ✅ |
| holdout worst RMS | 0.01674 | 0.01249 | −0.0043 ✅ |
| valid estimator count | 3 | 3 | 0 |
| recommended | tls | tls | 同 |

## cap_20261002_223757（v3 control）

- v1：❌ `floor_regions_invalid`（只有 6 个 25cm 净格，无≥8 格连通组件）
- v2：❌ `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep=0.354`
- v3：✅ `lowest_floor_sheet_v3_fine_roi`，4 区 sep=0.541m, cond=0.179, recommended=tls, 3 valid

生产语义**未被改变**（v3 仍接管）。
