# GL-S01 evidence r1 · 范围与基线

- 日期：2026-10-05；用户授权开单（见 [GL-S01 工单](../../tickets/GL-S01_floor_sheet_v2.md)、[GLS01 v1](../../GLS01_ACCEPTANCE.md)）。
- 本目录为 GL-S01 实施证据：变更前后 SHA、golden 真实数据验证、全量回归日志、回传。
- 修改范围（`pc_apps/human_replay/`）：新建 `floor_sheet.py`、`floor_sheet_test.py`；修改 `leveling.py`（auto 入口 + code_files）、`validation.py`（接受 v2 kind）。未改 `floor_detector.py`（SHA 保持 `72CE790F...`，与探针基线一致）、网页/console/captures/旧证据。
- 基线 HEAD：`8676bb479d4ae35cf22075cfe70225cf2220572a`（工作树保持原有 dirty/untracked）。

## 变更前后 SHA256

| 文件 | 变更前 | 变更后 |
|---|---|---|
| `floor_sheet.py` | 不存在 | `92D2ED105AC98FAAD68C2AD182DBC8A160DDBB08D4EE57AEA424CF3591CF6793` |
| `floor_sheet_test.py` | 不存在 | `0C6E311E652BBD833024237BB297F1823DEECFCBA79165D7FDFDFC40BB92A452` |
| `leveling.py` | `4B3FAAFB2EFD688B3FF3AC00F247AEDBFB676573754C25AD3CBF6E4BF942EBDC`（探针期） | `E01D5266B373EF89EACC214912B82E412EB06608B752243DE45C45769FAF264A` |
| `validation.py` | 未记录（untracked；最近归档旧版 `evidence/2026-10-05_gl_v01_r2/validation.py.before` = `7C84B9BA...`） | `FF7A51478D2AC64BB7352CBC68CE30163662E7FDA2D65267EFAE000AAC2063D8` |
| `floor_detector.py` | `72CE790F656FAF60A5122BCE550073412945A1A4C18D9B6195BA29928CE9B06A` | 同前（未修改） |

- ponytail：按全局规则加载 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（skill 工具，full）。用途：新增单文件模块 + 单测试文件；v1 冻结复用；无新依赖；无未请求抽象。
