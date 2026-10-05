# Codex GL04 R7 独立复审 / 2026-10-03

**代码修复条目无FAIL；GL04尚未软件收口：V04实际DPR-only变化仍NOT_RUN。** V10结构性BLOCKED、D01设备NOT_RUN另列。原R5/R6阻断全部闭合，不派R8，不并入正式页，不启动GL05/部署/采集。

## 提交、范围与执行

指定OpenCode `opencode-go/deepseek-v4.1-flash`/default DB，唯一production writer；Codex独立编排/复审。01 probe9.172秒PROBE_OK/exit0；原session `ses_f01ba3f48ffepSrGKkcHrb3onk`官方summarize26.641秒，导出summary=true/finish=stop/原provider-model。03同session R7续接05:40:08–05:50:04+08:00，真实exit0、SUBMITTED后停写。实际skill工具加载ponytail已核（05_ponytail_verified.json）；当前无活动writer。

| preview文件 | 现场/提交after SHA256 |
|---|---|
| human_fall.js | ef09c0540394841e48edf5a0bfb40c59f58c26d396906ed0fd6db421f70c9cb3 |
| human_fall_lib.js | 3f633cf6ec71a237258a3c837c5f9774edbd656bcfefc2d43d5e26ebaa87b38e |
| human_fall_lib.test.js | 42bb309311c42943f8c3ab61c19286bea76ca073257d84ff795ac4495ca4b9a1 |
| index.html（未改） | 6e687d95d77144e04fa67fc473e3f8437dcca1e36f8717d72466d338f78cd62f |

1778文件tracked/untracked范围基线00_resume_before_manifest.json；codex_review_01/94_scope_verify.json核无意外范围变更、原54重构SHA与R6完全相同。原44/48经前轮同样校验，语义未降低。正式Q/E/帮助、core/config/driver/其它webui/旧R1–R6证据原样；HEAD master/cbd0be1未变。Windows src/CMakeLists仍原不可hash软链接，未替换。末尾99_final_verify再次核提交SHA与冻结范围。

## 独立检查和根因闭合

codex_review_01复制原Codex90/92/95/97/harness，只调整嵌套深度，原断言不动：41/2/3/20 PASS；55lib PASS，五命令exit0（93_codex_exits.json）。这些为Codex新独立输出，不引用实现者自验冒名。98_codex_provenance另10项全部PASS/exit0：两条真正来源FAIL保持原预期；bbox-only negative保留actual_points raw中心、legacy缺字段保留；五条过严hide探索预期按R6契约裁决改为非测量/非physical，新文件保留旧98失败历史。

R7最小根因：sourcePositionQualified仅检查来源，与含bbox负旗的physical门分开；hfRenderState位置与hasMeasuredPos/hfPred共用。unavailable/predicted/其它显式non-actual不再显示当前sourceXYZ/“实测”，actual_points/null/缺字段保留。未改选择/frame/physical/灰预测诊断/几何路径。真实生产preview入口+localhost mock复现：browser30正常3m/实测/upright；31 unavailable、32矛盾predicted均位置 '--'/无有效观测/physical unknown；33 bbox_observed=false且actual_points仍3m/实测、physical unknown。原browser15 FAIL闭合。

## V01–V10/D01

| ID | 结果 | 证据与边界 |
|---|---|---|
| V01 | PASS | 独立90显式R/t/实际ground AABB/冲突拒/缺外参回退；R6六图与本轮两mode真实camera消费，数学字段不变 |
| V02 | PASS | 独立90/97/55支持预算/源索引/单位/有限性，grid仍独立非已核验地面 |
| V03 | PASS | 单位/版本与mode标签、完整schema绑定、source mm/source选择及support mm拒，旧断言保持 |
| V04 | NOT_RUN | 纯8角/DPR及真实camera近远/behind/退化/resize已验；同页面可控实际DPR-only变化未成功，不能标全PASS |
| V05 | PASS | 独立90/97 token全部既定子字段、旧列表/拖选共享guard、原ID/current正例；clip下拖框无伪命中 |
| V06 | PASS | 95/97及R6browser14 ground未知source raw与physical分门；绑定/schema/verifier/单位/静默/断连恢复通过 |
| V07 | PASS | 98+真实31/32来源明确non-actual时当前位置/实测为空；预测只诊断、0/多/other目标不背书、两mode非locked旧几何拒 |
| V08 | PASS | R6新fixture/generator不变，六图同frame/R/t与metadata/FPS/queue明确、无外参入口禁用；本轮mock仍当前frame与flags false |
| V09 | PASS | 原54 SHA完全保留、55lib通过；bbox-only否定不清合法raw中心，legacy/预测/选择/历史/ACK原义保留；正式/core不改复用既有回归 |
| V10 | BLOCKED | 生产build_snapshot仍缺显式R/t/support，冻结core/topic；synthetic只证消费能力 |
| D01 | NOT_RUN | 未授权真实设备/人体/板端性能；无板端网络/部署/采集 |

## C01–C15

| 行 | 结果 | 依据 |
|---|---|---|
| C01 | PASS | legacy首选/当前raw保留，92/97/98及55 |
| C02 | PASS | 既有到达顺序入口未改；位置/标签同消费当前来源门 |
| C03 | PASS | 同内容reload/camera变化保留原ID，90/既有实跑 |
| C04 | PASS | cal交错未知/当前恢复，90 |
| C05 | PASS | nullable binding/同ID内容/全既定token字段，90/97 |
| C06 | PASS | schema/frame/epoch/verifier守门，90/97 |
| C07 | PASS | 无/空/other/重复详情未知，不借ready基线背书，90/97 |
| C08 | PASS | source来源否定与bbox物理否定分门，真实31–33+98；灰诊断保留非测量/非physical原义 |
| C09 | PASS | R6真实pending/ready/静默/断连/当前终态重连/历史保留；入口原样及90 GPU失效 |
| C10 | PASS | valid/unknown/none/verifier物理资格与raw分门，95/97与R6browser14；恢复正例 |
| C11 | PASS | 旧token拒/当前原ID、list/drag共同提交guard，90/97/55 |
| C12 | NOT_RUN | 真实clip/退化已补，DPR-only切换仍未跑成功 |
| C13 | PASS | 点预算/索引/支持非米及3D有限，90/97/55 |
| C14 | PASS | source/transform/support单位及当前/旧选择守门，97/55 |
| C15 | PASS | R6完整fixture与offset=t[2]、performance字段证据不变；真实当前读数与来源诚实 |

M01/M02/M04/M05/M06/M07/M08/M09/M10/M11 PASS；M03 NOT_RUN，仅DPR-only子项未闭合。M05为localhost状态输入，不执行真实baseline采集。

## 浏览器方法、局限与剩余

R6/browser_01六图/相机交互/失效恢复及夹具正负证据对未改入口继续有效；本轮生产入口30–33验证实际修复。全部为localhost synthetic/offline，真实WebGL/Three.js，不是VM截图。

M11补验使用本轮证据目录camera_control_page.html：从未改index复制，仅改资源URL为绝对生产JS路径并追加**证据用UI相机按钮**；HF两个生产JS仍按现场SHA加载，生产文件不注入/不改。实际camera近/远平面、behind、near==far退化通过按钮触发。两mode reset overlay非空；near-crossing保守隐藏、全部near/far/behind/singular overlay alpha均0；八次全clip/退化拖框每次新增“未命中”，无伪选择/红屏，console空。12截图、clip_results.json/clip_drag_results.json与空console存browser_01。近交叉保守不画框符合原lib预期，不要求凭缺失角造巨大矩形；数学/其它camera回归均过。测试相机reset、页关闭、visibility恢复。

实际DPR在R6不同页面/布局测到1和1.2，但不能代替DPR-only运行转换。R7同页visibility尝试前后均1，CSS/画布尺寸不变（real_dpr_visibility_attempt.json）；Ctrl+plus此前也未产生可控变化。当前可用viewport接口只调宽高，未伪造devicePixelRatio、未以VM修改属性冒充真实DPR。按用户硬口径保留V04/C12/M03 NOT_RUN，软件未收口、正式页不并入。

当前无代码FAIL，不派R8、不换模型/DB/认证/配置。状态文件更新为等待真实DPR浏览器复核；V10生产集成与D01物理分层待办，不启动GL05。正式页merge边界只在获审后生效，目前不触发确认/合并/部署。未跑326/7/12+2、未commit/push/reset/checkout/clean，用户Q/E/帮助/HR/重组和旧证据保留。
