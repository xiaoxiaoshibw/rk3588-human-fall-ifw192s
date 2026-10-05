# P02 R3 分区/逐帧地面建模 · 00 基线（写前冻结）

2026-10-04。范围：只写本目录新文件 + `P02_ACCEPTANCE.md` 追加 R3 条目 + `returns/P02.md` 末尾追加（R3 报告完成后）。不修改任何生产代码、runtime、driver、webui、annotator.html、采集配置或既有证据；不设备/采集/部署/网络/commit/push/reset。

## ponytail 声明

实际读取 `C:\Users\30680\.claude\skills\ponytail\SKILL.md`（sha256 见 scripts 下方记录路径声明；本机绝对路径）。阶梯：复用 R2 冻结 NPZ 与 R2 已审纯函数（AST 只载函数定义，不运行其 main）→ 一个分析脚本 `p02_r3_analysis.py` + 一个 HTML 报告，不新依赖、不改 ROI/门。

## 起始 HEAD

`3fc1338fc306444959433a41bdeaeefd705f58ec`（2026-10-05 写前 `git rev-parse HEAD`）。HEAD 与 R2 基线 afaa37d 之间的 3fc1338 为用户自有新提交（跌倒页文案），不在本单范围。

## 范围内用户差异（写前 `git status -s`）

- 跟踪修改：`.gitignore / AGENTS.md / CLAUDE.md / docs/human_fall/{CLI_RECOVERY,DISPATCH,GL03_ACCEPTANCE,GROUND_LEVELING_PLAN,README,REVIEW_LOG,WORKFLOW}.md / returns/GL-03.md / tickets/* / docs/sidequests/REVIEW.md / pc_apps/* / src/CMakeLists.txt / src/human_capture/scripts/capture_server.py / webui/*` —— 全部用户既有差异，本单只读不动。
- 未跟踪：`docs/human_fall/P02_ACCEPTANCE.md`、`docs/human_fall/returns/P02.md`、`docs/human_fall/evidence/2026-10-04_p02_four_roi_r1/` —— R2 产物即本单只读输入；本单新增 `evidence/2026-10-04_p02_r3_region_frame/`。

## 输入/保护文件 SHA（写前实算）

| 文件 | SHA-256 |
|---|---|
| （输入）R2 `02_FROZEN_POINTS.npz` | d5f29b8609525a677e1f4e25c26d134a47f0bf572c6808834ff36c5c2e436012 |
| （输入）R2 `00_BASELINE.json` | 5842e584916794d3ec37e28a2cfda0c106ec865ebc8308eeb65229ff7534e1d0 |
| （输入）R2 `fit_four_regions.py` | 5b0777ffb50b354df869593348e849831413a01edc453613caa7956051f9097c |
| （输入）R2-r2 `p02_same_domain_estimators.py` | 8efa98c7d29585029cb298ddb29c60612890419d9fa17939ad3f1da7a0011402 |
| （保护）`pc_apps/human_replay/annotator.html` | 58af6bdd3ee9a1fda371a1bba9108d798109ed8e32d2242c627c8f3bfb57f902 |
| （保护/R3 追加）`docs/human_fall/P02_ACCEPTANCE.md` 前态 | 0d69eba634879aefbb3a857d6127cf6c422c6f491c013f574f70f27696813388 |
| （保护/R3 追加）`docs/human_fall/returns/P02.md` 前态 | 71676c5bbe3022311b8a80acb83bfd73b8c1e6529881444e70791913f78cce8a |

## 数据源完整性再核（写前实测）

- R2 `00_BASELINE.json` 声明的 annotator.html / R2-r2 源码 / 01_SELECTION.json SHA 全部 OK。
- 两 session `meta.json`/`points.bin` SHA 与 R2 `02_SELECTION.json` 声明一致（cap_20261004_202456 A=91 帧、cap_20261004_203349 C=102 帧）。
- 冻结 NPZ：392196 点，A=184956/C=207240，四区计数 #1=151861、#2=90803、#3=101948、#4=47584，与 R2 一致；distinct（session,frame,region）单元 772 = 193×4。

## 复用约定

- TLS/SVD/RANSAC 三个纯函数经 AST 从 `2026-10-04_p02_ground_r2/p02_same_domain_estimators.py` 载入（只载 `plane_from_*` 定义，不执行其 main/断言）。
- `sign_up` 用其自身定义（n_z≥0 向上）；R3 额外用 R2 名义显示系 z 轴做方向参考。
- TLS 参数协方差按一阶 delta 方法（Gaussian 误差的 Cramér–Rao 协方差）从 SVD 直接可得，见脚本注释；只作不确定度参照，不作物理精度。
