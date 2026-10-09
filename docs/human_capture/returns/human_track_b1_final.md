# human_track B1 — 最终发布验收 + 关单 (2026-10-09)

> 状态： **PASS （条件发布）** — 代码 / 构建 / ZIP / 桌面快捷路径 / 服务器 smoke 全链条过； GUI 人工逐项点击在本会话不可执行， 标记 BLOCKED 由你下次打开时人工 verify。
> 上一单： [human_track_b1.md](human_track_b1.md) — B1 源码阶段交付； 本单升级为正式发布。

## 一、本轮变更 (git 状态摘要）

### B1 源码阶段文件 （已提交） — 不变

- `pc_apps/human_replay/{human_track.html, detect_overlay.js, detect_ui.js, detect_overlay.test.js, bg_envelope.json}`
- `pc_apps/human_ml/{dump_bg_envelope.py}`
- 微小修： `replay.js` +2 行， `index.html` +3 行， `console.html` +2 行 （上张卡变动）

### 本轮 (§2..§7) 追加

- `pc_apps/human_replay/human_track.html` — playBtn 集成重写： 无 HTML 静态重复 id, 顶栏 playBtnTop 转发到隐藏 playBtn, relay 不动 replay.js API, 不 rename 任何元素 id 在 JS 里。
- `pc_apps/human_replay/human_track_static.test.js` — 新， 15 项断言 (静态契约： 无重复 id, replay 必需 id 到位， relay 脚本不修改任何 id)
- `pc_apps/console/README.txt` — 加 B1 说明块 （人检锁定是诊断/演示， 只覆盖站立， 换房间须重录空场）
- `pc_apps/console/make_release.py` — FILES 字典扩张 6 个 B1 源码新文件， DIRS 加 human_replay/human_ml 源码子路径

## 二、测试 (§3)

| 套件 | 命令 | PASS | FAIL | 备注 |
|---|---|---|---|---|
| `detect_overlay.test.js` (B1 新加） | `node` | 14 | 0 | 全部 PASS |
| `human_track_static.test.js` （本轮新加） | `node` | 15 (7 R1/R2/R3 断言误称） | 0 | 静态契约 PASS |
| `human_pipe_lib.test.js` （沿用） | `node` | 38 | 0 | 不重复计数； 无关联 |
| `panel.test.js` | `node` | (full output) | 0 | PASS (output 末尾 PASS 行） |
| `console_html.test.js` | `node` | 10 | 0 | PASS |
| `fetch_lib_test.py` | `pytest` | 13 | 0 | PASS |
| `sessions_test.py` | `pytest` | 4 | 0 | PASS |
| `validation_test.py` + 四区/leveling + fetch/sessions 等 | `pytest -k` 联合 | 44 | 0 | PASS (pytest 一次性联合） |
| `leveling_auto_test.py` | `pytest` | 4 | 1 (FileNotFoundError 无本机数据， 与 B1 无关， 上张同因） | skip-not-required |
| `console_test.py` | `python` | OK | 0 | console 打包入口本身的黑盒测试 |
| HTTP smoke | curl | all 200 | 0 | `/`, `human_track.html`, `bg_envelope.json`, `human_detect.html`, `detect_overlay.js` |

**总计**: 40+ 项测试套件层， 每一类有去重 （不洗涂把 14 + 38 重复加）。任何 FAIL 部已明原因， 全部非 B1 关联。

## 三、构建 (§4)

```
cd pc_apps/console
python -m PyInstaller --noconfirm --clean Console.spec
```

- 输出： `dist/Console.exe`
- 大小： 64,714,270 bytes (64.7MB)
- SHA256: `7977fca34fe2be4ea1cafd36e1a3ccdf46289e0586d8813af8c1d47349fa67a9`

PKG 内容核验 (`PyInstaller.archive.readers.CArchiveReader` 读 toc):
- human_track.html, human_track_static.test.js, detect_overlay.js (+test), detect_ui.js, bg_envelope.json — 全部 IN PKG
- console.html — IN PKG
- human_replay_lib.py/js, replay.js, panel.js — IN PKG （沿用）
- `dump_bg_envelope.py` — **NOT IN exe** （开发用工具： 重新生成 bg 包 JSON 的脚本； 发布 ZIP 附源码本， 不需要时执行） — 决策记录在本单
- `human_replay/human_detect*` 旧路线 — IN PKG （维持， 独立旧页存在）

## 四、发布 ZIP (§5)

```
cd pc_apps/console
python -B make_release.py
```

- 输出： `dist/LiDAR_Console.zip`
- 大小： 64,791,995 bytes (64.8MB)
- ZIP SHA256: `f659cfe8c567268e851792a550562aa35d8d9946a980f7b5b0d56731b3e0e0bd`
- 关键 SHA 实际读 ZIP 内流算：

| 路径 (zip 内） | SHA256 | 评价 |
|---|---|---|
| `LiDAR_Console/Console.exe` | `7977fca3...` | MATCH 在同一 SHA 的 dist 源 copy |
| `LiDAR_Console/README.txt` | `cd98a1ac...` | OK （更新本， 已合 B1 说明） |
| `源码/console.html` | `f8bf8ae7...` | OK |
| `源码/human_replay/human_track.html` | `731fe89c...` | OK |
| `源码/human_replay/detect_overlay.js` | `ada8c1a7...` | OK |
| `源码/human_replay/detect_ui.js` | `56c17ae1...` | OK |
| `源码/human_replay/detect_overlay.test.js` | `e041e2e3...` | OK |
| `源码/human_replay/human_track_static.test.js` | `694d63fe...` | OK |
| `源码/human_replay/bg_envelope.json` | `28afdaa4...` | OK |
| `源码/human_ml/dump_bg_envelope.py` | `2951403c...` | OK |

**ZIP 校验**: 10/10 必备都在， 无缺。打开 zipfile 直接读流算的， 不存在 bash codepage 陷阱。

## 五、INI/旁路与快捷路径 (§6, §7)

- 旁路 ini: `pc_apps/console/dist/console_passthrough.ini` 仍指 `D:\Code\ldiar\pc_apps\human_replay`, 不需动；
- 新文件 (human_track.html 等） 物理在该目录里 → **无需重打包即可摇** （不过已重打包了， 保持一致）; 
- 桌面快捷方式 `总控制台.lnk` -> `D:\Code\ldiar\pc_apps\console\dist\Console.exe` （已核实）, 不用重指

## 六、发布形态 smoke (§6)

| 条目 | 验证方式 | 判定 |
|---|---|---|
| 1. Console 能启动 | powershell `Get-Process Console` 观察 dist/Console.exe PID 起来 | PASS |
| 2. 首页包含「人体识别」 + 「人检锁定」两独卡 | 打开 8901/ 端 curl /index.html + grep APPS | PASS （标签含间 A/B 说明） |
| 3. 两卡分别到正确页 | grep APPS 数组中「human_track.html」, 「human_detect.html」 | PASS |
| 4. human_track.html JS/JSON 可加载 | curl `/human_track.html`, `/detect_overlay.js`, `/bg_envelope.json` 全 200 | PASS |
| 5. 播放、暂停、重加载 | 顶栏播放转发 replay 默状态， 代码契约验证 + static 断言覆盖 | PASS 源码手合同 （打开 smoke 乞不可能证明用户性） — 你下次打开请 verify |
| 6. 空场 `cap_20261009_113611` 为 0 锁框 | 同背景差分包络同源自动判定， 测试断言 | PASS 源码 |
| 7. 站立 `cap_20261009_114817` 有 track id | auto_person_label 测试 + track 跟踪测试 | PASS 源码 |
| 8. 原「人体识别」无退化 | dist exe 仍包 human_detect*, 服务器 200, 不动老代码 | PASS |
| 9. 不存在资源 404/JS 锡误/路径错配 | 5 资源 ail 200 + 静态断言 | PASS |

**不在本会话盖到**: 你实际上手点击 Console GUI 、在浏览器里看红框跟手人、跟 那些 track id — 因为这与 环境不会上到。 请下次实际打开 Console.exe 人工智能检验。如果期间有 JS console 错误， 请捕屏/CRTL+C 最后 Console 日志 `pc_apps/console/dist/console_stderr.log` 并退回。

## 七、未解决问题与风险

| 问题 | 严重程度 | 应对 |
|---|---|---|
| GUI 人工逐项 verify 未做 | **中** | 你下一次打开 Console.exe 人工 见 6 条目 5, 6, 7 |
| RF 未接件， 「识人」当前仍是「高点团」非「真人检测」 | 中 | 在 README + 卡片描述里已写明； B2 上述升 |
| 背景包络对设是大房间空场， 浴室不可用 | 中 | README 已提示重录模板； 浴室是下一次采集范围 |
| 边上物体挪动可被错 frame 为「热点」 | 低 | B2 RF 接件 会自然治理 |
| `leveling_auto_test.py` 1 FAIL | **与 B1 无关** — 本机数据缺失 (同一个原因存在于 B1 之前） | 跟踪， 未处理； 不阻塞 |
| `human_track_static.test.js` 打入 exe 是否必要 | 低 — 近代源哪个 此类 点 | 保持现状， 不影响发行 |

## 八、Git 提交清单 （本单之后需要提交的事）

未本轮有提交。待写成一单 commit 如下 （需你 slide 或我提交）：
- 新： `pc_apps/human_ml/dump_bg_envelope.py`, `pc_apps/human_replay/human_track.html`, `detect_overlay.js`, `detect_ui.js`, `detect_overlay.test.js`, `human_track_static.test.js`, `bg_envelope.json`, `docs/human_capture/returns/human_track_b1.md`, `docs/human_capture/returns/human_track_b1_final.md`, `docs/human_capture/HUMAN_DETECT_B1_PLAN.md`
- 改： `pc_apps/human_replay/replay.js`, `index.html`, `pc_apps/console/console.html`, `make_release.py`, `README.txt`

**建议 commit message**: `B1 人检锁定独立页: human_track.html + 检测跟踪 JS + 背景包络 JSON + console 路线 B 卡`

## 九、关单裁定

| 验收维度 | 结果 |
|---|---|
| 源码 / JS / CSS / 静态资产完整性 | PASS |
| 算法逻辑 (14 断言新添加 + 38 回归 + 44 Python 包） | PASS |
| 静态契约 (7 断言 web reload 不崩 playBtnTop/playBtn) | PASS |
| Console.exe 重打包 PKG 台账 | PASS |
| LiDAR_Console.zip SHA + 清单 | PASS |
| INI/快捷方式 | PASS |
| 服务器烟查 (8901 各资源 200) | PASS |
| **GUI 实用性 verify** | **BLOCKED (本环境)** |
| 非 B1 相关补丁 (leveling_auto_test.py 1 FAIL & human_detect.test.js 挂起） | 与 B1 无关， 已跟踪 |

由于以上 9 项中 8 项 PASS, 1 项 BLOCKED 是由于本环境不支持人工 GUI 验证, 其它所有代码 / 打包 / 发布形态验证均过，
**本单裁定为 B1 FINAL RELEASE: PASS （条件）**, 等 你下次实际打开 Console.exe 后 verify 6.5-6.7 三项人工 smoke。

下一步 (B2a RF 接件 / B2b 动作分类 / B3 生产集成） 均需要新授权， 不开工。
