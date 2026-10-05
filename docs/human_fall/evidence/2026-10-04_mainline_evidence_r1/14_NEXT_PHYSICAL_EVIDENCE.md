# 来源链之后的主线关卡（不自动启动新采集）

原bag→canonical bin→既有NPZ的新证据在本目录，旧文件/标志不追改。来源链的独立复核通过后，继续研究真实地面资格应优先解决下列缺口；不再盲调sampling/candidate cap或把新软件PASS当成physical PASS。

| 所需事实 | 必须如何绑定 | 当前边界 |
|---|---|---|
| 录制时SDK extrinsic与坐标输出 | 2026-10-02录制窗口、驱动run/启动日志、实际config SHA与参数联合证据；写清source/target frame与变换方向 | 当前config/保留六零SDK日志无联合绑定；unknown |
| source系的世界up方向 | 独立安装测量/坐标定义，给出from/to、主动或被动旋转、单位及不确定性；世界up在source由相应逆变换表达 | 用户确认雷达向下看；角度未知，PCA/model normal不是测量 |
| 点云坐标原点距地面高度 | 原点定义/与光学窗口偏移、现场测量和误差界，绑定同一次安装与录制 | 约1.1m是光学窗口高度，不能填成已验原点高度；批准height输入不擅改 |
| 四固定区域的地面身份 | 独立现场/源帧身份与原row索引；确认是否台阶/家具/反射/地面，不按FIT残差过滤holdout制造PASS | FIT/v1/v2/v3形状与残差是几何观察，身份未核验 |
| GL04真正DPR-only验证 | 同一个实际browser document、固定CSS rect/camera/frame/coordinate，两mode验证真实window DPR与backing缓冲跟随，不JS伪造 | 当前IAB只支持viewport(w,h)；V04/C12/M03尚未完成 |

现时测量若无安装未变/录制时关联证据，只能支持当前安装，不反推10月2日旧录制。需要新的受控记录时另以明确设备/采集范围执行；本轮只读取既有文件。

timestamp附加限制：原PointCloud2有float64，canonical28B提取format1把它降为float32。最大数值误差已实测0.007811；不保证微秒精度，也不当作clock/sync证据。现有fall流程的frame header secs/nsecs仍精确保留；未来若使用逐点时间，应从已恢复原bag保留原精度，并为新输入format独立定版，不静默改原28B资产。
