# GL-I01 离线capture数值输入适配验收 v1

建立2026-10-03。依据用户引用上一聊天计划后“开始开发/继续”，执行[计划C](evidence/2026-10-03_next_stage_plan_r1/PLAN_REVIEW.md)的本地软件准备。GL-P01软件已独审；本单不启动GL05设备、不采集/板端联网/部署/自动生成真实标定。唯一表为本文件；单OpenCode Go Flash/default DB writer，Codex独审。

范围：严格只读现有28B capture export，准备带可追溯manifest的数值NPZ，并在constrained数值入口校验实际源帧组成员；保持旧points/legacy语义与constrained --bag拒绝。使用stdlib+NumPy、Python3.8，不导入replay服务或采集器，不改ground数学/配置/driver/网页。

| ID | 要求/负例与可观察预期 | 检查入口/层级 | 结果 |
|---|---|---|---|
| I01 | 仅human_capture_session/schema1、原始bag2session/0.1.0、明确28B little-endian布局；meta/bin hash与精确长度、total/count/offset完整连续；缺失/截断/尾字节/重叠/空洞/unknown schema或clip/drop!=0拒绝 | pure adapter合成格式反例+现有真实export数值输入 | **PASS**（R1，2026-10-03 Claude Code） |
| I02 | 全部源帧按原顺序/原行保留，不预滤零点或重编号；points Nx3与export XYZ精确一致；ranges可把任意pooled index恢复为frame ordinal/seq+capture内行索引，后续finite/zero过滤仍用原行索引 | zero/boundary/dense source mapping | **PASS**（R1） |
| I03 | frame与units=m必须显式声明、与meta声明一致；不暗转mm。使用整数header stamp_sec/nanosec，保留seq/time_domain/可选bag_time各自来源，不从f32点timestamp恢复ns或跨时钟混算 | manifest/provenance边界，bool/float/非法stamp拒绝 | **PASS**（R1） |
| I04 | manifest固定实际完整源帧range及确定性frame_group，原meta/bin/points内容hash绑定；加载时核源文件与布局/成员，不许改group别名使同源帧成为独立组、重命名来源绕过绑定 | adapted NPZ→CLI verified loader；tamper/源缺失明确拒绝 | **PASS**（R1） |
| I05 | 拟合区与>=3独立验证区由外部显式提供；fit与各validation不能交叉点/源帧。bounds先受声明frame group约束，不以平面残差预滤；不能用任意group字符串放行。缺选择/组名/先验不自动选地面 | constrained入口opt-in membership gate→现有fitter/validator，不改数学 | **PASS**（R1） |
| I06 | adapted manifest/points/hash/row count/group/frame/stamp或CLI frame冲突拒绝；未知/损坏NPZ含manifest不得退回legacy忽略；失败不写calibration/diagnostics；source文件不修改 | CLI成功/拒绝及副作用检查 | **PASS**（R1） |
| I07 | provenance明确metadata_declared、point_index_domain=capture_export_row、original_bag_point_index unknown、原bag hash只declared未实核；所有物理verified=false。真实export数值≠真实标定/单位或安装verified，synthetic检查明确标签 | wire manifest及真实本地export结果，不拟合真实artifact | **PASS**（R1） |
| I08 | 一个不可覆盖NPZ（points+标量Unicode input_manifest JSON，allow_pickle=False），完整准备后exclusive原子写；已有目标/失败无覆盖；legacy普通NPY/NPZ points及HF/GL frozen行为保留，Python3.8/std+np | new CLI/Python+target guard/兼容回归/范围SHA | **PASS**（R1） |
| B01 | 原bag点索引/逐帧frame与单位独立来源/layout证据未齐备，第一版不冒充原bag row index | source/physical层：capture schema未持久化width/height/original_count且frame硬编码 | **BLOCKED**（维持） |
| D01 | 地面身份/拟合ROI+三空间验证区/up_axis与源轴/可见高度/现场判据、设备/性能/部署 | 未取得现场协议/未设备操作 | **NOT_RUN**（维持） |

软件I01–I08通过不解除B01/D01，也不自动生成实际ground cal。约1.1m是光学窗口离地、安装向下角未知，不能作已核原点高度/先验。现有cap_20261002_163621可用于完整真实export解析与索引验证；不得为本单录新数据。

## 完整操作与消费者矩阵

诊断阶段必须逐行列实际函数/赋值顺序/校验/保存、过滤和消费映射，并停止。Codex核源码未改和矩阵完整后，单独实施派工。无本单已获审软件前置不得从诊断自行开工。

| 行 | 输入/操作×消费者 | ID | 可观察预期 | 结果 |
|---|---|---|---|---|
| M01 | valid完整多帧export→NPZ→constrained loader | I01/02/03/04/07 | 按原行/帧，整数stamp与声明frame/units、实际hash清晰 | **PASS**（R1） |
| M02 | zero XYZ/帧边界首尾/不同count/空帧 | I01/02 | 零点保留；空帧政策明示不伪点，range不重编号 | **PASS**（R1） |
| M03 | meta/bin截断/尾数据/overlap/gap/total矛盾 | I01/06 | 创建/加载前拒绝，无输出副作用 | **PASS**（R1） |
| M04 | unknown格式/version/layout/endian/clip/drop | I01/07 | 明确拒绝，无悄悄猜格式/提物理资格 | **PASS**（R1） |
| M05 | bool/float/string count/seq/stamp、非法ns/frame/units | I01/03/06 | strict type及time/frame声明检查 | **PASS**（R1） |
| M06 | 修改source/meta/bin/points/manifest/members/group后reload | I04/06 | 逐级hash+canonical member binding拒绝，不降为legacy | **PASS**（R1） |
| M07 | ordinary legacy NPY/NPZ无manifest→现入口 | I08 | 原义/默认/已有返回保持，不要求capture source | **PASS**（R1） |
| M08 | fit/validation点交叉或同源帧不同group名 | I04/05/06 | 绑定实际帧，不能通过标签绕过，输出不写 | **PASS**（R1） |
| M09 | bounds across pooled frames + group限制 | I02/05 | 先限制实际group成员；索引仍pooled原行、不残差预筛 | **PASS**（R1） |
| M10 | missing ROI/group/priors/<3 validation区域 | I05/06/07 | 现有invalid或明确拒绝，不自动拟合真实地面 | **PASS**（R1） |
| M11 | output exists/失败/重复写/竞争出现目标 | I06/08 | exclusive原子写，不覆盖旧/半截正式产物 | **PASS**（R1） |
| M12 | adapted CLI成功+失败→artifact input provenance | I04/05/06/07/08 | 带实际map/hash，legacy语义不变；所有physical仍false | **PASS**（R1） |
| M13 | 真实163621 export全89帧4372400行→适配/加载 | I01/02/03/04/07 | 无源修改、不拟合；点数/hash/range/零点与时间域诚实 | **PASS**（R1） |

建议单个NPZ内部manifest包含canonical source meta/bin路径/hash、bag hash声明与未核标记、完整ordered frame ranges、稳定group、points规范字节hash、frame/units显式声明与unknown verification。路径不可达时明确拒绝，不从hash字符串推断已读取源；首版是本地有源输入的严格路线。避免旁路manifest：包含input_manifest的NPZ在CLI加载必须强制校验，无此key的旧points保持旧行为。
