# GL-I01 实施前设计门通过 / 2026-10-03

Codex完整读07_diag_revision.md，两个只读审查助手分别核对原子/manifest/source三方绑定和索引/声明/分组；初版8处根因缺口已闭合。08_scope_gate实际证明src/config/webui无变化，新增adapter/CLI/test仍不存在，关键calibrate/ground/calibration/采集器源码SHA一致。**写前设计门PASS，现单独放行阶段二**，只按07修订及06裁决，不按00初版冲突设计实施。

既有要求再明确：extraction.dropped_frames必须strict-int 0，拒bool/float/string非零；frame.dropped_points与total_dropped_points亦然。多个连续空帧、首尾空帧、共享row端点必须正确（row在半开range，不能归到零宽frame；searchsorted如使用需端点策略及检查）。source meta/bin hash与XYZ来自同一读取内容快照，避免hash后再次读取成为不同数据；完整points应Nx3 raw<f4且字节与实际source重建匹配。所有manifest入口强制detect；所有adapted输入/fit/export构造校验在唯一写入前，invalid不生成artifact，diagnostics新路线明确拒、legacy原义不变。

I01–I08/M01–M13运行仍NOT_RUN，须提交后独审，不将设计PASS当代码PASS。B01/D01及GL04DPR/正式/GL05/设备/部署/采集/网络边界不变。单OpenCode指定Go Flash/default DB writer，先新probe，同session实施；源码与tests按白名单。需要超过白名单即停写说明调用链，不私自扩大。
