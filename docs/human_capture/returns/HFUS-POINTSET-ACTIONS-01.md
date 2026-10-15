# HFUS-POINTSET-ACTIONS-01 回传 · 2026-10-14

用户指定原pointset页、已有S1模型与中央人物，授权自动研究/定位/骨架/倒地姿态与总控制台集成，无用户审核前置。Codex唯一writer，技能ponytail/scientific-toolkit-skill；原core/GT/模型/录制/旧output不改。HEAD/全树22566文件基线见本轮证据。

验收唯一v1：docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r1/ACCEPTANCE_V1.md。新actions.py/config_actions.yaml/action_output，原页server/app/index适配两数据集；console_gui/html新入口、新ConsolePointset.spec/EXE/ZIP、桌面快捷方式。

| ID | 自验状态 | 证据 |
|---|---|---|
| A01 | PASS，22558保持/8授权变化，0缺失/错误，HEAD未变 | BASELINE_BEFORE/FINAL_PRESERVATION |
| A02 | PASS | 代表帧研究与FINAL_REPORT场景区分 |
| A03 | PASS（软件，不是身份精度） | 1934+32帧与全源行校验 |
| A04 | PASS | 1934目标关联/空场0，因果单测 |
| A05 | PASS支持契约；解剖标定UNKNOWN | 所有有效节点当前点均值；79歧义帧 |
| A06 | PASS软件；真实跌倒NOT_RUN | 两受控躺下候选，初始躺地/gap测试 |
| A07 | PASS | BROWSER_ACTIONS_V2与旧output保护 |
| A08 | PASS | FROZEN_STARTUP退出0、RELEASE_MANIFEST、SHORTCUT_UPDATE |
| A09 | PASS | 浏览器/console7/JS12/pointset8 |
| A10 | PASS记录；独审/物理NOT_RUN | FINAL_REPORT |

SUBMITTED，自验完成，未ACCEPTED。人体/家具完整精度、关节准确率及真实失衡跌倒未证明。旧控制台运行窗口未终止，桌面快捷方式新启动才加载新EXE；ZIP是依赖当前工作区的本机备份。无训练/采集/部署/Git写。


## 2026-10-14 R2 · Codex当前点集诊断与局部实验回传

- 当前唯一验收：evidence/2026-10-14_hfus_pointset_actions_r2/ACCEPTANCE_V2.md；SHA见ACCEPTANCE_FINAL.json。
- 状态SUBMITTED，非ACCEPTED。实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md与scientific-toolkit-skill/SKILL.md；单writer，无代理/模型训练。
- 起始master / c21c443b0befe559e08283edb0efc2af02dcc6b8，24627文件全树SHA、既存dirty保留；范围与提交源码SHA见FINAL_PRESERVATION/SOURCE_SHA_FINAL。无Git写。
- 根因：最大簇可能只保留主体；贴地删除与端部碎裂独立于PCA轴缺测。082623/f192未选219点簇AI_INFERRED疑似端部，非GT；主簇内部污染及误删身份UNKNOWN。
- 实现：原r01页五层/源点点击/基线与五种单因素实验；新research/experiment/verify模块、新冻结研究配置；core与历史输出只读。全1934+32帧重现与6方案11796帧当前源成员/节点均值独立核验PASS。
- 实验：point12新增434、point20新增4863且新增2歧义；component20新增5917，f192局部214成员/8节点，但新增3旧解3；low20新增4921含58近地近背景点。拒绝局部恢复晋级，轴实验79→38缺测、无成员变化，仍缺方向身份精度，实验保留。记录每个新增依据、所有失败与新困难。
- R201–R208逐ID自验见ACCEPTANCE_FINAL；局部恢复/方向精度/身份污染不冒称PASS。pointset11、console Python7/JS12、真实Edge九会话/全部79歧义+新困难/三视角/缺测/播放暂停/事件/导出/非法输入/iframePASS。gap页面fixture为SYNTHETIC，因果重置单测PASS。
- 实际Console_Pointset.exe --check-startup ok=true，动态加载同一r01；默认保持R1，所以EXE/快捷方式/旧版本保留，无打包替换。页面选择baseline即算法回滚；旧UI三件套保留快照。
- 设备/物理/独审NOT_RUN；人体完整率、家具污染率、解剖/方向精度UNKNOWN。confirmed恒false，不采集部署HR-09训练提交推送。
- 未闭合：38轴歧义、局部恢复新119/140/232困难、f192身份未证明、靠近目标背景删除是否身体未知。下一步从这些源绑定窗口研究稳定背景接触排除与当前可见端部，不扩大ROI、不补造点。
- 实际命令、返回码、源码与输出SHA、浏览器图片、首尾保全及失败证据均在R2报告/当前索引；本机自验非独立复审。
