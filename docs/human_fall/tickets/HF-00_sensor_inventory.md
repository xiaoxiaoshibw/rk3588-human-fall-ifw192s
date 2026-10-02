# HF-00 传感器与环境盘点
执行：Luna（文档/批量盘点）；OpenCode 真机只读探查、Codex 独立复核。依赖：无。状态：ACCEPTED（盘点交付范围）；剩余单位/同步转 HF-02，安装/地面转 HF-03。用户确认无相机，首版消费一个点云流和辅助 IMU。

先读 ../DISPATCH.md、../hardware_inventory.md 和已有 evidence 日志，再读取 ponytail SKILL.md。当前已验证 SSH wel@192.168.3.125 与 slam-localization 容器；优先补未验证项，避免重复整套盘点。禁止写算法、改驱动、升级依赖或猜测凭据。

本单已关闭盘点范围，下面是历史盘点任务；原相机项目已按用户说明撤出。不要为了旧清单重做相机搜索或等待 CameraInfo，下一单见 HF-01。

## 工作
1. 复核 LUNA_AUDIT.md 的文件与行号；列表区分已有代码、用户描述、已验证运行和未知。
2. 真机收集 uname/架构、ROS 版本、Python/OpenCV/NumPy/厂商 SDK 版本、CPU/内存及可用加速器。核对手册与实物。
3. 用 rostopic list/info/type/hz、有限采样 header 和 rosparam/TF 获取点云、IMU、左右图像、CameraInfo/厂商深度的话题与频率。图像编码、分辨率、左右同步/基线与坐标轴单独记录。采样命令须有限时长，保存原始日志。
4. 验证 IMU 原始单位、姿态有效性与源时间语义：向厂商说明或采样证据查证，标 unknown 的字段不要填猜值。
5. 建立采集元数据模板和场景表；探测脚本不得默认写硬件参数。

## 交付
docs/human_fall/LUNA_AUDIT.md；docs/human_fall/hardware_inventory.md；原始日志本地路径；returns/HF-00.md。真机未运行时静态部分可回传，整单仍未验收。

## 验收
每个硬件结论有来源/日志；未知项明确归属后续工单，不用频率/数值量级代替同步或单位证据。盘点的 ACCEPTED 不表示同步、标定或算法已通过；内部双目光学形态未知不阻止使用已验证的单个点云接口。
