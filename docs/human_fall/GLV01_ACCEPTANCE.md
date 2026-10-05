# GL-V01 算法验证工作台 / 唯一验收 v2

2026-10-05 R2：用户指出四个自动框不是平地，并明确“算法能够自己找，我自己画过”。Codex唯一writer。取消把平面数值通过等同地面身份的R1完成判断；自动算法必须从三维点云找地面，人工四ROI只作独立对照。v1原表保存在本轮evidence/GLV01_ACCEPTANCE.md.before，历史证据与失败不追改。

| ID | 当前要求与可观察预期 | 结果/证据 |
|---|---|---|
| V01 | 总控保留原入口，算法验证采用修复版；桌面快捷方式可达 | PASS 作者自验；12包源码逐字节/13链接 |
| V02 | 原要求仅三会话；本轮自动结果只验203349/203135/202456 | FAIL 列表范围：共享树另外加入223757第四会话，已保留该外部差异，未将原“仅3”静默记PASS；三个本轮源的API检查通过 |
| V03 | 202456原人工配平与输入字节保持，原四区仅作为参考 | PASS 作者自验；原job27f870...保持；自动函数不读参考；网页白虚线/独立平面对照 |
| V04 | 两新会话＋202456独立自动寻找，不复制R/t；三法/逐区/3留帧门不降；只合格方法导出 | PASS 作者自验；3自动job均三法PASS且一致；04/09；所有旧FAIL保留 |
| V05 | source/config/report/manifest绑定；旧未经地面识别的数值ROI不自动消费；失效/切换/失败清旧框 | PASS 作者自验；旧候选诊断保留、衍生下载拒绝、replay入口身份及source门；05b/06c/07b与浏览器 |
| V06 | 原meta/bin/旧结果不覆盖；全帧原行/非XYZ保持，measurement与tz独立，physical/extrinsics/runtime=false | PASS 作者自验；14/旧文件129项；09九套全记录重放 |
| G01 | 先发现低处近水平面，检查局部法向、完整厚度、连续面积，再取四安全块；不是按俯视密度选四格 | PASS 作者自验；floor_detector纯函数/密集桌面及人体混入反例 |
| G02 | 空间均衡候选发现仅FIT帧；不读取手画ROI，不残差裁掉最终域行 | PASS 作者自验；04候选uses_manual_reference=false/FIT数88/99/110；冻结域whole-XY/full-height |
| G03 | 页面显示实际算法输出框、XZ/YZ全高度与当前帧全量统计；自动失败不留旧框 | PASS 作者自验；showReport同步regions、自动开始清空框；新侧视/原参考虚线 |
| G04 | 自动结果与202456人工四ROI独立对照，不用该对照倒调检测结果 | PASS 作者自验；1.586310° / 0.005015m，后置对照；04/页面 |
| S01 | ponytail/科学技能、dirty/untracked基线、写前设计/回归/提交停写、如实记录scope与旧失败 | PASS 作者步骤；外部独审NOT_RUN；04意外只读检查第4源的scope遗漏已记录06，不冒称本轮第4成功 |
| D01 | 设备/未曝光物理真值/部署/捕获/在线接管 | NOT_RUN；全部仅本地离线，不标ACCEPTED |

状态：R2 SUBMITTED / STOPPED。[回传](returns/GL-V01.md)。地面自动识别及三个指定录制的数值验证已作者自验；整体未ACCEPTED，列表范围V02仍有外部差异，外部独审未运行，不能等同物理标定/全场泛化。

Luka 收口补充（不回填以上判断）：发现分发的旧镜像 dist/Console.exe 与 dist/hr02_offline/Console.exe 仍停在 R1 SHA，desktop zip 同样旧，已在停止驻留旧进程后统一同步为 R2 C8F34A5E…（详见 evidence/2026-10-05_gl_v01_r2/18_console_sync.json、21_closeout_luka.md）。
