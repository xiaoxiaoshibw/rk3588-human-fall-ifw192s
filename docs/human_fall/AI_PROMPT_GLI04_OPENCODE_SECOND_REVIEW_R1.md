# GL-I04 R1 OpenCode独立二审提示

目标角色：opencode-go/deepseek-v4.1-flash / default DB独立二审，native skill(name=ponytail)。本模板用于Codex完成GL-I04、停写并提供本轮run_root与11_submission_manifest.json后；现在尚无实施/派工，不预填PASS。

生产源码/config/tests/批准draft全部只读，本次不并行返工；发现缺陷集中报告，Codex明确交接后才另发单writer返工。不要换model/DB/auth/权限/全局配置，不设备/网络/采集/部署/GL05。新二审脚本/证据只放run_root/opencode_second_review_01/，旧证据不覆盖。

读WORKFLOW最新分工、GLI04_TASK.md、唯一GLI04_ACCEPTANCE.md v1、实际新生产文件及研究prototype、run_root/00_diag.md与11_submission_manifest.json。不注入全部历轮。先核实际SHA与声明一致、范围/提交停写，再按L01–L06/R01–R06/S01与Q矩阵全表独立复现；缺实施产物不能猜测或标通过。

重点独立检查：

- source/frames/member/单位/输入与独占输出；diagnostic产物不能冒充calibration；所有旧数据/draft/原core/config/GL-I03/UI保持。
- 旋转的条件假设/from-to/逆变换、approved vs WHAT_IF、录制extrinsic缺口；不能把模型法向或旧零值当physical事实。
- 四box×每frame全点与empty记录、pooled/frame内索引、边界/alias/跨组、显示抽样与统计分离；固定空间分箱不按残差筛validation；手算RMS/P95/support与UTF-8/JSON非finite。
- frozen actual fit vs replay计数 vs事后holdout，早退阶段不能伪称后续验证；真实89帧报告能重算、不pool fit/生成candidate。
- baseline parity、同seed/序列的oracle；prototype所有已见合格假设有事件，非传递相似链/代表漂移/排序/close及late competitor不误接受；候选/精炼/trace预算不足必须unresolved。
- 正例可解析闭合，不能永远unresolved；多seed/噪声/输入置换、成本与失败诚实。无改进本身不是FAIL，安全断言失败必须FAIL。

即使遇到FAIL，也跑完剩余独立安全检查；每失败给已有ID/来源/触发/实际/预期/共享根因/最小返工，不借二审增加无来源物理门或硬性能目标。B01/B02未补证仍BLOCKED，D01/D02NOT_RUN；软件完成不依赖它们，亦不证明真实标定通过。

新报告00_review.md含真实session/model/defaultDB/实际技能路径、逐ID PASS/FAIL/NOT_RUN/BLOCKED、命令exit/源码位置/输入SHA/范围、首尾被审SHA、全部缺陷和研究采用建议。只SECOND_REVIEW_SUBMITTED/STOPPED，不自行改验收表/状态/ACCEPTED或接入原型。Codex核原始输出/模型/退出状态/SHA后收口。
