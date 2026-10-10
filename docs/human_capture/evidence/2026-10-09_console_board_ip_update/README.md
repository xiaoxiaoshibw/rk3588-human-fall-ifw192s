# 2026-10-09 Console.exe 板端地址更新（192.168.3.125 → 192.168.31.58）

用户直派：板子迁移到新网络并固定为 `192.168.31.58` 后，控制台 exe 内两处板端地址同步更新。
只换 IP 常量，端口不变（:8090 板端 WebUI / :8766 捕获控制面）；其余用户工作树改动未触碰。

## 改动文件（SHA256）

| 文件 | 改动 | 旧 SHA256 | 新 SHA256 |
|---|---|---|---|
| pc_apps/console/console.html | 「板端 WebUI」卡片 desc/url → `192.168.31.58:8090` | 9458C6B7182E6B14EABA4B0A743CDFC033307793EAE948A26E45265736259269 | 042719DA3D656B629A94F495708D83E38535C2B4F8AB06E8C16AC9C0DBC4C203 |
| pc_apps/console/console_html.test.js | 3 处断言 URL 同步 | 8E4F776C0B9C45C26BF1E7FD575F96E2176D450DD3B720A9AF943D2AEA18A6D3 | F4E742EECE8ED318EC6F15FDEE31D2C9603369AFAD283B3FF8022A952FAC6B55 |
| pc_apps/human_replay/config.py | 内嵌副本 `BOARD_URL` → `192.168.31.58:8766` | BD2576B77F9DDD2C98F77B50FC67DBD44D21CE390032F9C6F0313544205C7B3D | 3892DE7FB0641D02FB7A5563A3E57551E9FC98C1798E816964CF66364B2E2088 |

## 测试（原始日志同目录）

| 套件 | 结果 | 日志 |
|---|---|---|
| console node（console_html.test.js） | 10 passed, 0 failed | 01_console_node.log |
| console python（console_test.py） | Ran 4 tests, OK | 02_console_python.log |
| human_replay python（`*_test.py`，共 46 项） | 45 OK；**1 ERROR 为环境预存**：`leveling_auto_test::test_real_sessions_detect_four_regions` 缺本机数据 `captures/remote/cap_20261004_202456`（该测试文件未改、本次改动不涉 leveling/数据路径；本地 `captures/remote/` 现状确无此目录） | 03_human_replay_python.log |
| node 回放各套（human_replay_lib / panel / human_detect_lib / human_pipe_lib / registration） | 全过（45 passed / O1–O5 PASS / 11 passed / 38 passed / T37 全 PASS） | 04_node_replay.log |

## 重建与内嵌副本核验

- 旧 exe 备份：`dist/Console_backup_20261009_0948.exe`
- `python -m PyInstaller --noconfirm Console.spec` → exit 0；`dist/Console.exe` 64,590,767 B（2026-10-09 09:50:14），SHA256 `B9A0FCE00840E0DE86EA04EC39F546B551AC749776C15888CD8EC3DCCF8C672C` → 05_pyinstaller.log
- `python -B make_release.py` → exit 0；`dist/LiDAR_Console.zip` 64,633,665 B，SHA256 `76B67D4400AF3A1F254A5016E837BC5B357654D8C3F90A42BCB12DCC67577D1C` → 06_make_release.log
- 离线探针 `probe_embedded.py`（用 PyInstaller `CArchiveReader` 直接抽取 exe 内嵌副本，不启动 GUI）：
  - 旧 exe（备份）：`console.html` / `human_replay/config.py` 均 `old_ip=True, new_ip=False` → VERDICT FAIL（探针具备判别力，非空过）→ 04b_embedded_probe_before.txt
  - 新 exe：两处均 `new_ip=True, old_ip=False` → VERDICT PASS → 07_embedded_probe_after.txt
- zip 复检：14 entries；`LiDAR_Console/源码/console.html` 含新 IP 不含旧 IP；包内 Console.exe 64,590,767 B → 08_zip_check.txt

## ponytail

使用路径：`C:\Users\30680\.config\opencode\skills\ponytail`（本会话 skill 加载）。
最小改动 = 两处地址常量 + 3 处断言同步；未重构、未新增抽象、未动运行逻辑。

## 边界

- 未启动 GUI、未连板；板端地址固定（板端 netplan 静态 + 路由器 DHCP 绑定）为今日另一项直派工作，本目录只记录 exe 侧。
- `dist/LiDAR_Console/` 历史解压目录与更早的 exe 备份未动。
