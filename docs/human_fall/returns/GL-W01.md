
## 2026-10-05 GL-W01 R1 / Codex / SUBMITTED

# GL-W01 R1 / 作者自验收口 / 2026-10-05

状态SUBMITTED；源码writer已停写，不标整单ACCEPTED。指定Go Flash/defaultDB独审一次无工具probe55.477s超时，真实exit1，stdout/stderr无session/推理事件；独审服务BLOCKED。不得把作者检查或CLI未返回称指定独审PASS。

唯一验收GLW01_ACCEPTANCE.md v1。Codex唯一writer，ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。03 fall回归458/exit0；原回放Node45/exit0（工具输出）；23四个集中检查/exit0，20真实HTTP端口冲突与无stderr窗口版/exit0。15项源SHA和Python3.8 AST在22；不是板端运行验证。

| ID | 结果 | 检查/证据 |
|---|---|---|
| W01 | PASS（作者自验） | 09真实浏览器加载91帧、确认/按钮/三方法/前后对照，输入变化即时失效；20本地服务新端口与windowed stderr，静态卡片/回放链接审查 |
| W02 | PASS（作者自验） | 23 config严格owned、ROI重叠/源指纹；domain.npz存fit全source/rows/region/frame及独立holdout rows；无Z/残差门，UI确认依据 |
| W03 | PASS（作者自验） | 23合成26/-1/1.3真值与线退化；真实178850点同域、独立frame30/60/90；原raw RANSAC861/20261001/5cm、不精修 |
| W04 | PASS（作者自验） | 23三方法全valid但LS与RANSAC角冲突不给推荐反例；09公开full/region/holdout和pairwise，不以相关LS二票压鲁棒方法 |
| W05 | PASS（作者自验） | 14全4470632行，opaque字节/无效行/frame表/原SHA；独立RxRy forward/inverse max约4.81e-7m；真实浏览器下载ZIP全SHA与CRC一致（工具输出） |
| W06 | PASS（作者自验） | 23 source sameID异内容/坏meta/schema/NaN/bool/单位/路径/输出overwrite/409并发/failed不能下载/输出SHA篡改拒绝；UI generation + load lock + late result丢弃 |
| S01 | BLOCKED（指定独审）；其他流程PASS（作者） | 00诊断/01全含untracked基线、11复核、22停写；06 probe阻塞，不切模型/DB/认证。源码之外外部P02 append保留 |
| P01 | PASS（资格区分）；物理精度BLOCKED | report/meta/transform physical/extrinsics/runtime=false，参考1.14独立于d；已曝光录制留帧不是未见物理真值 |
| D01 | NOT_RUN | 无设备/部署/采集/driver/板端网络/控制命令 |

真实软件验证录制A=cap_20261004_202456，fit88frames/178850points，3留出帧。TLS/SVD pitch26.6234附近/roll-1.396附近/tz1.321854m，full RMS1.894cm/P953.797cm/support98.5%；RANSAC pitch26.221/roll-1.391/tz1.318828m，full RMS2.148cm/P953.849cm/support99.2%。三方法四区+三留帧通过、2°/.03m一致性通过，仅离线显示推荐TLS。

完整结果captures/leveled/8b3bbb66b48e4ff5a83c12e589919420；旧ecdf结果另保留，不覆盖。每方法points.bin/meta.json/transform.json/quality.json/dataset.zip；root report/domain/manifest。source annotations独立保存，衍生human_annotations清空，不混用源框。未修改src生产、webui、原captures、旧evidence。新增AGL-A～I状态保持NOT_RUN。

保护检查11中P02_ACCEPTANCE.md与returns/P02.md在本轮被外部追加R3研究，非本单写入，保留不回滚。其分区/PPCF方案未集成此静态工作台。原用户所有dirty/untracked与软链接保留，HEAD未改变。

限制：static batch模型；对新场景先确认新的四区，不能承诺自动识别任意物理地面；200万fit点超限拒绝不暗中抽稀；服务重启后结果URL不恢复但磁盘ZIP/目录保留；没有AGL时间controller/online pipeline。物理datum/误差/全场外推仍未闭合。指定独审待服务可用后另明确恢复，不自动无限probe。

### 提交源文件SHA

| 路径 | SHA256 |
|---|---|
| pc_apps/human_replay/leveling.py | 05b234ea7438483175599be9d0b78f6f8e7bbbb553aacff9948cbdb95e101072 |
| pc_apps/human_replay/leveling_quality.py | 4cbafd0c1ab64f7efabf1a3740b26983154105c847a151bdbb6a09be2f33c04e |
| pc_apps/human_replay/leveling_test.py | 994a7057dc8472b6931557a86684a84c17f60f3bc342a430c0576d43138778e3 |
| pc_apps/human_replay/leveling_estimators/ransac.py | 6d7d3a02e455798bbb3be7b91c7530827f9f684715de16409ff4351b7f5da4d6 |
| pc_apps/human_replay/leveling_estimators/svd.py | 421aa1793fd94fea6742d1744a05b1678f1c4f54f647d2d8596e3578b7a74077 |
| pc_apps/human_replay/leveling_estimators/tls.py | e71caec7a338b892588fcbc03b8c3b8a86f383f94c3ebe938cbd08f99cf3c07c |
| pc_apps/human_replay/leveling_estimators/__init__.py | 55871ef7fc76288be02c3572dc8c222052d8196dfa65ed2d5a851cbefb4b886b |
| pc_apps/human_replay/leveling.js | e53ebcde4ed922a53840a872d299d9b6329d4225f09ea828a66145df044a9687 |
| pc_apps/human_replay/leveling.html | a0afb65e2176402c942d4ed9c3760d5e71ae08c16fbb0c8041e424eb2d95cea9 |
| pc_apps/human_replay/human_replay_lib.py | 021a64f51784ff800af3b6b70aa4c920acc202a188f2367626b7051d9755bbcf |
| pc_apps/human_replay/index.html | 7ca5e7bf52ec26b6a562221e7f8438131499b486bb187fc5370518dfd549b7a1 |
| pc_apps/console/Console.spec | ad9c6a80011139e4dd3b193e0f3156caa5ec03d21e90c47c9c18068a1c953f58 |
| pc_apps/console/console.html | dbcccfb8eb4970c7ff5bda5fd8024d3a9029c11155a7e5706f9d3543069d1d7f |
| pc_apps/console/console_gui.py | c434751b7cb9784228132f044fe9bf9093e1b338a42794c1052f733bec4674ed |
| pc_apps/console/console_test.py | e97b7b583c51135b7683f637148db1daab39336303f9f3fe7c58f78cffac7dca |

验收表v1 SHA256=8c6693bf4d34a6e0b23bcc20dd959a5cde700474d63f303d6afbe93aa92a0f09；起始/当前master HEAD=3fc1338fc306444959433a41bdeaeefd705f58ec。实际指定模型推理未取得：probe命令指定opencode-go/deepseek-v4.1-flash/defaultDB，真实超时exit1。实现者Codex模型遵循当前聊天设置，不编造model/session ID。


## 2026-10-05 最终打包版运行附记

21最终包装exit0；25最终CArchive 24文件+console.html逐字节一致、GUI port_query编译入口正确；EXE64701381bytes，SHA在25。前几次启动测试父命令结束/用户继续后进程与服务不再存活，没有取得包装源码异常trace，不将旧404/无listener称最终包故障。保持测试宿主等待后，父16448/子7800实际本地服务8901，31源meta/bin真实SHA，32提交的十五源码SHA在当时一致。

实际Console.exe页面完整执行91帧/178850fit点/holdouts30,60,90三方法，全部valid/consensus GOOD，生成27f870c6c7be43f4b9dc50121a5fc03f。33是真实打包版浏览器截图，34绑定最终EXE/提交算法版本/产物SHA，所有算法code_hashes匹配22提交。窗口版启动、NumPy估计、zip/export全链作者自验PASS；指定独审S01仍BLOCKED（06服务probe），不是独审/物理标定。

最终34复核时共享源leveling.py已由外部P03工作新增leveling_lib.detect_ground_domain/auto schema及auto选区入口；本单源码writer在22后已停写，没有回滚或合并外部改动，不将P03标本单PASS。提交包保持25固定版本，运行的27f产物严格匹配22，不含新P03分支。源码树中的后续auto变体需要它自己的验收，不能用本包结论外推。

交付程序pc_apps/console/dist/gl_w01/Console.exe，卡片“离线配平”；本单保留旧dist/Console.exe等发布包未覆盖。用户从固定新版进入本次功能。完整结果captures/leveled/27f870c6c7be43f4b9dc50121a5fc03f；所有原录制不变。
