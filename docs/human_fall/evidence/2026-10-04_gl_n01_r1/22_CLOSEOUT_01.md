# GL-N01 R1 收口 / SUBMITTED / STOPPED

按用户约26°下俯、1.1m当前安装参数，固定名义离线配平已真正运行于89帧点云，并输出同帧前后图。指定Go Flash/defaultDB独审N01–N06/S01/Q01–Q06 PASS，无FAIL/无需返工；P01独立物理BLOCKED，D01 NOT_RUN。真实浏览器file协议测试NOT_RUN/BLOCKED；静态图可视与原HTML逻辑已验证，不冒称mock为浏览器。

计划当前[主线v3](../../GROUND_LEVELING_NEXT_STAGE_PLAN_V3.md)；唯一[GLN01 v1](../../GLN01_ACCEPTANCE.md)。阶段A完成，后续B独立地面复核/C微调与变安装适应/D接入与设备分开。此前E01/E02/GL02/03/I05/I06保留复用，不重做来源链或K2/K3/IRLS。旧计划before全文归档，当前指针覆盖其旧入口。

## 实际产物

- leveled_01/nominal_model.json：R_y(+26°)、t=(0,0,+1.1)，from innolidar→ground_nominal；content model ID、单位、X前/Y左/Z上假设及roll/yaw=0明确。先旋转再沿旋正后的竖直Z平移。
- leveled_01/nominal_leveled.npz：全部3699085有效点+原pooled source_rows；原4372400点中673315零return单列、非finite0。89帧header/输入输出行范围/statistics齐全；未改原NPZ/meta/bin或回填来源标志。
- leveled_01/frame_stats.json / input_manifest.json：逐帧计数/场景全点Z分位及输入来源绑定；场景全点统计不是地板误差。
- leveled_01/view.html：同帧source/nominal XZ/YZ、可更换帧/pitch/height，导出固定版本与控件预览区分；每帧均匀抽2000源行，只影响显示。
- 07_before_after_frame05_01.png：实际查看四面板，原斜带在26°后近水平，低位点带仍在z=0以下。图中范围裁剪只是展示，不删NPZ点；没有给这条带自动签地板身份，也没有把高度改成拟合约1.33。

全有效点独立标量oracle最大差3.55e-15m；独审同值，源原点映射(0,0,1.1)、inverse误差2.2e-16m。445fall/2follow回归通过，新增7集中tests通过；独审另做52严格输入负例、4实际CLI拒绝零落盘、源行/样本/全部帧/模型身份/消费者资格检查。Python3.8 AST通过，不称板端运行。

## 实际独审与冻结

一次fresh probe17，14.109秒exit0/PROBE_OK，session ses_ef9ec1fccffe1HTv8iWCU36sdm；实际独审18，432.843秒exit0/finish stop，session ses_ef9eb256bffeoe5S6fzhbsEqxd。20两导出确认provider=opencode-go/model=deepseek-v4.1-flash/defaultDB。技能全文作为16prompt附入，未触发上单外部目录拒绝，不改变auth/model/DB/权限。19为实际最终原文，21记录全部工具输入、write/edit/patch调用0、40manifest漂移0。三源码自提交后停写。

保护4010文件仅允许的两计划入口文档变动，旧数学/calibration/config/driver/UI/数据/evidence及catkin表示保持。作者source_01/02快照保留，提交前只补inverse严格类型与HTML转义。代码SHA绑定14工单manifest；输入产物内无代码SHA，这是独审明确的非阻断观察，不能伪称产物独自包含它。

## 逐ID结果

| ID | 结果 |
|---|---|
| N01 | PASS |
| N02 | PASS |
| N03 | PASS |
| N04 | PASS |
| N05 | PASS（离线产物/静态图/软件逻辑）；实际浏览器NOT_RUN/BLOCKED |
| N06 | PASS |
| S01 | PASS |
| P01 | BLOCKED |
| D01 | NOT_RUN |
| Q01 | PASS |
| Q02 | PASS |
| Q03 | PASS |
| Q04 | PASS |
| Q05 | PASS |
| Q06 | PASS |

参数变更能够生成新model ID/新目录，不需要改代码；nominal能数值变换，但不能进入冻结runtime的verified/valid门。基于实际地面的自动修正是后续阶段C，不以“参数可改”冒称未知安装已自动识别。用户参数足够做本单，P01不再作为基础名义变换前置阻塞。

本单状态SUBMITTED、无writer，无设备/新采集/网络/部署/生产接入。当前最小后续是核低位点带的地面源行和偏移，复用E02与已有indices/拟合/质量检查；不自动以残差筛验证点、放宽竞争门或改旧批准输入。
