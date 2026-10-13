# HF-DEMO-01 / R1 / 唯一验收 v1
2026-10-12，用户明确要求优先完成简化跌倒识别 Demo。独立离线演示，不混用 HFUS-D05/D06/D07；D05-R06 尚未收口，保留。
写入前 BASELINE_BEFORE.json：15824 文件，tracked/untracked/ignored，错误/扫描中变化为空；非原子扫描，不宣称全树冻结。主控唯一 writer。
代码范围 sidequests/human_fusion_lab_next/fall_demo/r01；文档范围本证据、HF-DEMO-01 回传、WORKFLOW 当前入口与 REVIEW_LOG。原算法只读复用。

| ID | 预登记标准 |
|---|---|
| FD01 | 隔离可启动，无生产/原模型/原始数据修改；来源与 SHA 可查 |
| FD02 | 合成跌倒经原 FeatureExtractor + FallStateMachine 计算：下降、疑似、确认告警、恢复；每事件仅一次 |
| FD03 | 合成行走、缓慢坐下、初始低姿态、遮挡无确认告警；遮挡显示 UNKNOWN；明确快速主动躺下无法区分 |
| FD04 | 播放/暂停、单步、时间轴、场景切换、重置、告警跳转和本地确认；seek 回放已计算逐帧结果，不积累重复事件 |
| FD05 | 真浏览器操作、截图、控制台检查；输入数据 SHA 校验失败时停止展示 |
| FD06 | 指定 OpenCode 只读独审和缺陷记录 |
| FD07 | 真实跌倒准确率、真实检测跟踪、设备与部署：NOT_RUN，不以模拟代替 |

先生成固定种子合成已知目标点集，计算几何特征并交给现有状态机；不是原始雷达分割/分类链。仅 synthetic fixture 开启 confirmed，生产默认不开启。单位 m/s，18秒、10Hz。成功/失败不改变冻结标准。
