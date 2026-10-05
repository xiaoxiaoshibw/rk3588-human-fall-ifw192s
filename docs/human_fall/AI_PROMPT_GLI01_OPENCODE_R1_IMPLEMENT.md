# GL-I01 R1 阶段二：写前设计获审后实施

Codex已核07修订设计及08源码零变/09_DESIGN_APPROVED，现明确放行实施；不是阶段一自行开工。唯一GLI01_ACCEPTANCE v1要求不变。只读最新07_diag_revision及09批准新增细节，06裁决优先，00初版冲突为历史。用已有summary和targeted rg/lines，不全读history/source/tests。实际ponytail仓库内本轮副本/full，回传声明真实路径。

允许生产：新core/capture_input.py、新scripts/prepare_capture_input.py、scripts/calibrate_sensors.py的manifest识别及adapted route；新集中tests/test_gli01_capture_input.py；docs/human_fall/GLI01_INPUT_CONTRACT.md、本轮证据、末尾追加returns/GL-I01.md。冻结ground/math/runtime/calibration/config/driver/所有webui/采集器/原captures/旧证据，不commit/push/reset/checkout/clean、不board/network/capture/deploy/GL05/model/DB/global config。

核心：固定每完整源帧一个canonical content-based group，显式--frame/--units=m，不自定义groups；NPZ精确points+Unicode scalar input_manifest；实际source XYZ raw<f4bytes==NPZpoints==manifest digest，actual meta/bin/frames/group重核，no source拒，含marker损坏无fallback。所有入口detect，adapted非constrained拒。bounds group-first+pooled原行，显式indices越组拒，缺选择/先验/少于3validation拒。capture_export_row且原bag未知/baghash仅declared/physical false；整数headerstamp，不从f32点时间恢复ns。

全校验包括extraction.dropped_frames strict-int0；多连续空帧/首尾空帧/endpoints映射。temp全写+flush/fsync+os.link exclusive，unsupported拒不直接copyfallback。adapted只一个cal输出、拒diagnostics；invalid fit/export/derived/reference_axis/构造失败在任何写前return2。旧legacy普通points与diagnostics行为不改。

按I01–I08/M01–M13自验，集中有效检查与原GL01相关回归、scope/SHA。可对现有真实163621只读运行prepare+reload，保存本轮evidence/prepared/ NPZ和摘要（source4372400/89/zero673315/hash/headerstamp/time_domain），严禁拟合真实cal/选ROI/写生产config。实际成功cal CLI只用显式synthetic fixture并标签清晰；原数据零修改。失败历史保留，日志到文件只反馈摘要，不灌大型arrays/全suite输出。

提交只SUBMITTED/BLOCKED，逐I/B/D/M结果与实际命令/exit/源SHA/source数据hash/model/session/skill及限制，停止代码/tests写入交Codex独审，不自行启动设备/下一单。上下文如近120k先停交Codex同模型压缩，不无限重读。
