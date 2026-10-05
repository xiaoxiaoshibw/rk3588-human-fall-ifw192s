# GL-I01 写前诊断审查及裁决 / 2026-10-03

阶段一03 CLI exit0/READY_FOR_DESIGN_REVIEW，05实际scope gate证实src/config/webui零变化；只读助手核5个源码SHA一致，新源码/tests不存在。流程两阶段门已真正执行。初版00_diag为写前事实，保留不覆盖；**初版设计REWORK_DESIGN，尚不准源码实施**。以下为I01–I08同一v1下普通工程裁决，不新增物理要求，无需用户再确认。

1. **显式声明入口**：prepare只支持--source-dir（固定meta.json+points.bin）、--frame required、--units required且只接受m、--output。无默认innolidar/m，无任意--meta/--bin/--groups扩展。meta.frame非空且与声明一致；未来若meta.units有明确记录也须一致，unknown类型拒绝。始终metadata_declared/physical false，不将单位缺原记录变成verified。
2. **确定性实际帧身份**：一个bundle只有一份完整source。固定每帧一个group，无caller分区/alias配置；group ID由path-independent source meta/bin内容身份+frame ordinal/seq/stamp的确定性公式生成，记录成员为该完整frame range。loader从实际源重建并核该公式及完整ordered members；改group名/成员不可自报通过。其独立仅表示源帧集合不交，不表示统计/物理独立。
3. **实际source重建三方相等**：loader读实际meta/bin，重建canonical source XYZ f4字节/frames/group；NPZ points必须精确Nx3/little-endian f4、无object/额外列或静默转换，实际source XYZ digest == NPZ原points字节digest == manifest期望digest；source meta/bin SHA、layout、声明/unknown flags、frames/group逐层核。只核自洽的3个声明hash不够，不能称hash防伪。缺源拒绝。
4. **所有入口识别manifest**：在shared input加载/主入口识别含key。adapted只允许constrained；非constrained在任何写入前明确return2，不能忽略marker走legacy。损坏含marker NPZ绝不fallback；无key的普通points仍旧行为，不能给adapted lineage资格。
5. **保留selector类型、group-first**：共享selection helper接受原region selector+group。bounds先限制实际成员，再做坐标bounds，映回pooled原行；组外坐标也命中不属于错误。显式pooled indices必须都在声明group，越组才拒绝。fit与validation用同helper，禁止将region先在全pool变成indices而丢类型。缺fit selector/group/priors或少于3显式validation拒绝，不自动选。既有ground函数仍校点/帧隔离，不改数学。
6. **adapted单输出与顺序**：首版adapted拒绝--diagnostics（写前明确错误）；完整诊断仍可在artifact.constrained_ground读取，旧普通points diagnostics原义不变。所有source/selection/fit/export/derived/reference_axis/完整artifact验证在首次写前结束；adapted invalid fit与缺导出条件return2且无artifact。成功只发一个immutable calibration JSON；不声称两个路径事务原子。
7. **原子exclusive**：新NPZ只采用同目录完整temp+flush/fsync+os.link exclusive publish，无此能力明确拒绝，不降级直接O_EXCL拷贝暴露半截目标。adapted calibration也仅在支持atomic exclusive link时复用现save_exclusive_json（旧legacy fallback不改），预校完整JSON后单输出。构造/输入/算法拒绝在写前；目标竞争已有文件保留。temp清理只动自身临时文件。

初版M09“跨pool bounds既通过又拒绝”和M11 O_EXCL fallback不保留到实施。初版run_constrained只探测manifest、prepare漏声明/自定义groups无canonical、old invalid先写diag的事实均已核。请写新07_diag_revision.md，将上述裁决逐M01–M13映射到实际新函数/旧入口顺序及测试，停在READY_FOR_DESIGN_REVIEW。Codex核修订设计和源码零变后才另发实施提示。

B01/D01不变；原数据、ground/math/runtime/config/driver/webui、GL04DPR/正式合并门全部保持。严格软件适配不推出原bag行索引、单位/安装/地面/性能验证。
