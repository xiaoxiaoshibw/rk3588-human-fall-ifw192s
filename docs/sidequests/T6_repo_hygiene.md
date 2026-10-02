# T6 仓库卫生（只读勘察 + 提案）

## 一、事实

### 1.1 .gitignore 现状
- 根目录 `.gitignore`：**不存在**（根目录确认无此文件）。
- `src/human_follow_calibration/.gitignore`：仅 1 行 `__pycache__/`。
- `webui/` 下无 .gitignore；另外两个 .gitignore 在 `文档/10-1/github/{hdl_people_tracking,Lidar-Based-Fall-Detection}/`，属外部克隆仓库自带，与本仓库无关。
- 唯一生效的全局忽略来自 `.git/info/exclude` 第 7 行：`/captures/`（本地私有配置，不随仓库分发）。

### 1.2 体量表（du -sh）
| 路径 | 大小 |
|---|---|
| 文档/ | 125M |
| docs/ | 38M |
| docs/human_fall/evidence | 37M（docs/ 的 97% 都在证据目录） |
| src/human_fall_detection | 1.5M |
| webui | 888K |
| src/human_follow_calibration | 47K |
| returns/ | 0（空目录） |
| captures/ | 不存在 |

### 1.3 >5MB 单文件清单（共 6 个，全部在 文档/）
| 文件 | 大小 |
|---|---|
| 文档/10-1/数据集调研/2402.17171_LiveHPS数据集.pdf | 38M |
| 文档/10-1/数据集调研/2509.12197_LiDAR人体姿态估计综述.pdf | 21M |
| 文档/10-1/papers/2205.05918_多模态跌倒检测.pdf | 8.8M |
| 文档/10-1/数据集调研/2211.10598_LidarGait基准.pdf | 6.7M |
| 文档/10-1/github/hdl_people_tracking/data/boost_kidono.model | 6.2M |
| 文档/10-1/github/Lidar-Based-Fall-Detection/.../Trial0.ipynb | 5.1M |

### 1.4 git check-ignore 实测（均无根 .gitignore 前提）
| 路径 | 结果 |
|---|---|
| captures/ | 忽略（.git/info/exclude:7） |
| 文档/ | **不忽略** |
| 文档/**/*.pdf、**/*.pdf | **不忽略** |
| **/__pycache__ | 仅 src/human_follow_calibration 下生效，src/human_fall_detection 下 4 个 __pycache__（共 ~593K）**不忽略** |
| docs/.../01_cli_events.jsonl | **不忽略**，git add docs/ 会全收 |
| webui/node_modules | 目录不存在，不会被忽略 |
| 另发现 src/human_fall_detection 下 4 个 __pycache__ 目录当前都是未跟踪可入库状态。 |

### 1.5 文档/ 内容（17 个 PDF，124 文件，125M）
- 文档/AISC-3830用户手册.pdf（1.4M，供应商手册）
- 文档/跌倒检测文献/（6.1M）：PointNet++ 正文 3.9M、ST-GCN 1.6M、补充材料 604K 等
- 文档/10-1/数据集调研/（72M，4 个大 PDF）
- 文档/10-1/papers/（22M）
- 文档/10-1/github/（25M，两个外部仓库克隆，含 6.2M 模型权重与 5.1M notebook）
- 其余：问题.md + assets、manifest.json、README.md
- captures/ 不存在，无 PCAP 风险实测项。

### 1.6 其他注意
- `rk.txt` 含 `ssh wel@192.168.3.125`（内网地址，敏感度低但属运维信息）。
- docs/human_fall/evidence/ 下最大 jsonl 1.8M（opencode_events），单批 5.3M 封顶；证据是纯文本事件日志。

## 二、提案

### 2.a 最小 .gitignore 增补规则（每条一行 + 理由）
```
__pycache__/        # 全仓库 Python 缓存，约 593K，无版本价值，避免误 add
*.pdf               # 一刀切：全部 PDF 都不入库（17 个 = 上 MB 级字节），文献/手册走外部存档
文档/10-1/github/   # 两个外部仓库克隆（25M，含模型权重），应以其原仓 fork/链接替代
/captures/          # 与现有 info/exclude 对齐并随仓库分发（bag/PCAP 不入库是既定约束）
```
判断依据逐类评：
- 人体点云采集数据：当前仓库内无原始采集文件（captates 不存在、只有 captures 忽略占位）；`__pycache__`+`/captures/`+`*.pdf` 已把现实风险全覆盖，不需要再假设性加规则（YAGNI）。
- 证据 jsonl：**建议入库**。单文件 ≤1.8M、单批 ≤5.3M、全部 37M，作为 HF/GL 链的审计证据价值高于体积成本；纯文本、无敏感数据。不加忽略规则。
- 供应商 PDF / 文献 PDF：二进制不入库是既定约束；38M+21M 单文件必要之外且无 diff 价值。
- 文档/ 其余（问题.md、README、manifest、assets 截图 84K）：可入库，是项目文档而非二进制。

### 2.b commit 分批提案表（docs/ "全收 vs 挑收"）
| 批次 | 内容 | 单项风险 |
|---|---|---|
| B1 | src/human_fall_detection/（剔除 __pycache__）、src/human_follow_calibration/ | 低，纯源码+测试+配置，1.5M |
| B2 | docs/human_fall/ 全部（含 37M evidence jsonl）| 中：一次入库 37M 历史；但证据是项目链的一部分，挑收会破坏审计可得性。判断：**全收**。理由：37M 对 modern git 无压力，且 CLAUDE.md 明确 docs/ 是权威文档树、证据是验收材料。 |
| B3 | AGENTS.md、CLAUDE.md、open_webui.bat、rk.txt、webui/（全部 888K，无 node_modules） | 低；rk.txt 含内网 IP，入库前用户自行裁定，可降至 B4 |
| B4 | 文档/ 内小件：问题.md、问题.assets、跌倒检测文献/{README,manifest}.json、10-1/README.md+notes+manifest | 低；PDF 与 github/ 全不入库 |
| B5（不建议） | returns/ 空目录 | git 不跟踪空目录，无需处理 |

### 2.c src/CMakeLists.txt 软链长期归档选项（只列不执行）
| 选项 | 取舍 |
|---|---|
| git update-index --assume-unchanged src/CMakeLists.txt | 本地吞掉常态 M 提示；本地配置不随仓库走，新 clone 后又出现 |
| 在板端（Linux）以 `git checkout` 恢复软链后提交 | 根治：index 记录为 symlink 类型；需板端操作，Windows 无法验证 |
| 入库时用 `git config core.symlinks=false` 同步设置 | 仅缓解显示；clone 到 Linux 仍需正确软链 |
| 保持现状 | Windows 上永远显示 M，易在 `git add -A` 时被误提交为普通文件（把软链变成含路径文本的常规文件）——**最坏选项** |

完成：T6
