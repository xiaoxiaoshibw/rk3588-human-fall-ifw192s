# GL-00 首轮派工补充 / 2026-10-01

用户已成组授权GL-00～05串行执行，Codex直接派发/读取/复审/返工；每关独立PASS前不得发依赖单。执行模型必须opencode-go/deepseek-v4.1-flash。首轮探针session ses_f0970b477ffe1NwpuOZoMmVIES实际返回MODEL_PROBE_OK，进程0；这是探针会话，不是本单开发会话。

先读本单、DISPATCH、GROUND_LEVELING_PLAN、GROUND_LEVELING_METHOD_REVIEW和最新用户授权边界，及AGENTS、CLAUDE、工作流、回传模板、所有冻结契约、部署/运行/审查和HF03/09/11最新回传。读取C:/Users/30680/.codex/skills/ponytail/SKILL.md并记录真实路径。

本单只读数据分析和方案；仅允许本单证据、回传、GL方案/契约草案文档及必要独立分析脚本。不改生产源码、任何生效参数、网页、冻结配置/契约；不安装库、不commit/push，不部署，不启动/重启任何雷达或服务。不要跨GL-01，不自行PASS。

Codex基线已在本目录00_*和01_*记录：master/c96489e40037aca810b23b98d71ba34632d18bd0，含未跟踪源码/资源/文档哈希；用户driver改动与catkin软链接保留。CLI当前1.18.34，模型列表有指定模型。发现一个既有交互OpenCode进程，但无本单run写入；不接续其他人的会话。

当前本地captures目录不存在，rg仅找到历史synthetic_plane.npz，不把它当device。ssh BatchMode已确认wel@192.168.3.125可达，主机welcomtech，slam-localization Up 2 days；可以只读核对容器/bag/磁盘/现有话题。涉及inno_lidar_msg须source正确devel。凭据不读、不输出、不保存。

用户截图已在聊天解释为左工位/椅子、中间地面、右台子、红框机器人；不得上传原始图/人体点云到云，不把截图像素当XYZ，网格不是地面。历史bag与当前布局/安装对应未知，必须单列，不猜确认。新采集暂未获本次具体授权（Codex正异步询问最多5s/50帧/100MB），只读已有数据；采集依赖项先BLOCKED，不能私自采集。

完成不依赖真实数据的参数计划、RANSAC预算估算、最小兼容契约草案。数值提案需区分旧基线、设计约定、待实测门槛；不能以计划数值冒充冻结物理验收阈值。若真实数据可访问，可离线只读统计/诊断写新隔离文件，记录hash/source frame/时期与竞争平面；不在活动工作区改参数来跑。

GL-00数据结论只有在真实地面ROI/独立验证区/安装先验能对应样本时才完整；缺项写BLOCKED，其余写已完成，不整体造PASS。所有测试/CLI/SSH内外退出码和实际结果落盘，不预填数字。

回传追加docs/human_fall/returns/GL-00.md；本轮证据用本目录，保留Codex启动记录。记录本单真实session/model，不把probe ID冒充工单ID。最后只列出回传路径、改动、证据与未完成项并结束，让Codex读取复审；不要让用户搬运文件。
