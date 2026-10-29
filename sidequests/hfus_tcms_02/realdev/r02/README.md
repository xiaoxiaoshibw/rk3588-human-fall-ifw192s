# S01 测量复核与候选配平坐标诊断

本目录为 HFUS-TCMS-02-REALDEV-02-S01 的隔离源码。RESEARCH：复核测量定义；ENGINEERING：完整历史 R/t 的来源、坐标和回放。运行依赖本机已有 Python 3.12、NumPy、psutil；旧契约回归另用已有 SciPy。PC离线工具，不部署板端。

唯一源为 `D:/Code/ldiar/data/sessions/cap_20261017_113516`。只解每28B行前12B XYZ，尾16B opaque。所有源行保留；`source_row`是帧内行，`global_row=offset+source_row`，`byte_offset=28*global_row`。无效/零点不旋转、不平移，不参与显示，但可按行反查。

证据根为 `D:/Code/ldiar/docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s01_r1/`。所有输出排他创建，不能对已存在标签重跑覆盖。原数据、旧 r01、生产源码、配置、模型、GT不写。`bootstrap.py`已经完成，仅初始化一次，不能重复执行。

本轮最终完整输出为 `full_final/`；早期 `full/`、`probe/`保留。最终运行前源码SHA在 `full_final/CODE_AT_START.json`。`full/`未在运行前记录代码SHA，不能补填成已记录；最终run已新增该冻结记录。两次完整运行结果等价性另见作者检查/清单。

候选变换完整复用 `data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json` 的R/t，按真实SHA绑定；不重估、不混入nominal_R。列向量 `p_local=R@p_raw+t`，行数组 `p_raw@R.T+t`。只允许 `CANDIDATE_PLANE_PREVIEW / OFFLINE_REVIEW`；没有本段地面身份/空间时间几何/物理资格，不输出物理身高，不近地硬删。

处理的是冻结结果的数值变换：全部点行、M0中心和全支持CSR、匹配点、8角OBB、候选成员与中心、历史轨迹/预测中心。真实冻结资产没有速度/协方差字段，纯数学适配器用合成例检验速度只旋转、协方差RΣRᵀ。M0噪声仅有xyz标准差，其派生协方差明确标为对角近似代理，不能冒充原始完整协方差。

从仓库根启动新只读服务（现有 `SERVICE_FINAL.json` 记录本次交付服务地址；下例另建用户进程记录）：

```powershell
python -B -W error sidequests/hfus_tcms_02/realdev/r02/server.py --run full_final --service-record SERVICE_USER.json --port 0
```

打开终端打印的 `http://127.0.0.1:<port>/?fi=430`。服务器只绑定loopback、GET只读；数据/版本漂移拒绝启动，变换更新必须新run，不复用旧身份。保留原M0建立结束192、首显示193；页面全段变换仅OFFLINE_REVIEW，不能回填在线有效资格。

页面操作：

1. 两面板始终同帧。检查案例依次为0、192、193、270、271、385、430、431、432、439、520、750、760、770、779。
2. 橙色为候选框/旧平面，青色为冻结M0，紫色为抽样支持，绿色/粉色为历史实测/预测轨迹。地图、当前点、框、轨迹来自后端已变换数值；相机选择只改投影。
3. 点击当前点，或填`source_row`点“反查源点”，查看56个hex字符的原28B、RAW/local XYZ、源SHA、帧号和变换版本。无效行也能查询。
4. 输入`surface_id`点“反查M0支持”能回查原始支持源行；API `start/count`分页（最多100行）。全量7,181,833支持点已计算，页面最多显示600支持点、3000表面和9000当前行，仅为显示限额。

```powershell
python -B -W error -m unittest discover -s sidequests/hfus_tcms_02/realdev/r02 -p test_coordinates.py -v
node sidequests/hfus_tcms_02/realdev/r02/browser_contract.test.js
```

历史平面在自己的候选系z=0只证明数学一致；新段全场/旧选择带残差照实显示，二者都不是经审核的真实地面验证。人体/尾段失败原样保留，本轮不重分割、不重新聚类关联、不调阈值、不新求地面。
