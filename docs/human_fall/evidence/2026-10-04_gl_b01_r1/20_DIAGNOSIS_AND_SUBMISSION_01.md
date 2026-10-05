# GL-B01 R1 观察诊断 / SUBMITTED（作者自验，待指定独审）

阶段B软件实现已完成，三新代码路径停止写入。唯一GLB01_ACCEPTANCE v1，Codex唯一writer；ponytail实际C:/Users/30680/.codex/skills/ponytail/SKILL.md。26°/1.1m原N01模型不改，无RANSAC/candidate/IRLS/设备/采集/部署/生产接入。PCA仅固定旧ROI全部场景点的几何观察，不用于补up/安装高度或筛validation。

## 已得到实际结果

四个不同源帧组（FIT ordinal5，validation6/7/8）对应2959场景行，全部高度保留：FIT近1084、中752、远436、侧687；完整CSV每行带pooled/source row、ordinal/seq/group/sourceXYZ/nominalXYZ。13独立标量/成员/XY footprint对拍全行0失败；12实际查看区域图，19原HTML脚本离线mock DOM角色标签/finite绘制通过。没有重新尝试被浏览器拒绝的file协议，也不冒称browser实测。

| 域 | 点数 | nominal场景Z中位数(m) | 说明 |
|---|---:|---:|---|
| 新FIT近，frame5 | 1084 | -0.266873 | XY footprint全部高度，不是已核地面误差 |
| 新VAL中，frame6 | 752 | -0.259127 | 同上 |
| 新VAL远，frame7 | 436 | -0.236127 | 同上 |
| 新VAL侧，frame8 | 687 | -0.159036 | 含上下两层，均保留 |
| 旧固定FIT ROI | 1214 | -0.229656 | 全点PCA残余倾斜0.316781°；nominal plane offset+0.239822m，源plane offset为观察量不是尺量 |

旧v1/v2/v3全ROI PCA相对nominal Z倾角分别2.0017/57.4858/7.4646°；各自模型/全点域独立，不把这些角当地板倾角，也不把全场景RMS当真实误差。它说明旧验证集需要重新核地面成员；偏移、区域混杂、单平面前提等分开解释。

## 用户人工场景身份子项已完成

用户本轮对12图明确回答“是对应现场木地板，紫色侧区对应工作台”。17_user_scene_confirmation_01绑定figure SHA、plan/model/source身份、region/group/ordinal/seq，18为索引。低位连续点带木地板、侧区上层工作台语义=user_confirmed。不能再写“地面完全未知”。

确认范围是图中物理带语义，不是穷举每一行的标签、边界/过渡噪声或独立尺量精度。review_02输出在答复前生成，保留immutable pending历史；17/18是当前确认补证，不覆写CSV中的unreviewed_scene_member。不会把候选区内所有高度或高位工作台点全标ground。最终逐source行地面集合尚未签造，selection_candidate=null；P01独立精度/SDK/具体集合复核仍BLOCKED。

## 逐ID作者自验

| ID | 自验结果 | 证据 |
|---|---|---|
| R01 | PASS | nominal-run NPZ/meta/bin/XYZ/model/window + legacy source绑定，parse快照及首尾SHA；99帧外部资料明确不采用 |
| R02 | PASS | strict plan/noZ/XY全高度、四互异帧、frozenselector/gate；全源行独立对拍 |
| R03 | PASS | 2959行CSV完整索引/坐标，全高度/显示采样分开，17场景确认范围清楚 |
| R04 | PASS | 全scene Z/hist/cells和legacy PCA分别标域；clean/slope/offset/mixed/line/empty合成；真实观察不回填height |
| R05 | PASS（软件） | pending真例；14实际CLI synthetic完整人工确认分支复用E02.check_selection、仍physical/candidate=false；实际用户语义17已计入但不造逐行集合 |
| R06 | PASS | plan ID/caller/新model/同path异内容/已有out/保护路径；16两版本语义输出byte相等，15真实out exit2；人工消费时从source/model/plan重新计算权威场景行，caller不能扩大footprint |
| S01 | PASS（作者阶段，独审待完成） | 写前00/01，三新源码版本txt；08集中8/09fall453/05follow2 exit0；11 AST3.8；21scope/22manifest/return后停写 |
| P01 | BLOCKED | 已有用户木地板/工作台语义确认；具体源集合/独立误差/SDK旧run未核，分层不抹掉确认 |
| D01 | NOT_RUN | 不运行设备/采集/部署/生产/IRLS，PCA不输出标定 |
| Q01 | PASS | schema/kind/finite/unit/frame/source/window/empty稳定pending |
| Q02 | PASS | caller plan/observation改、身份/新版本/输出保护；不cache |
| Q03 | PASS | frame alias/跨组/重复/越界/zero/Inf与全高度保留 |
| Q04 | PASS | synthetic clean/倾斜/offset/混杂/line/empty + 各域独立标注 |
| Q05 | PASS | partial human/坏person/缺landmark/residual_method/出footprint拒；fresh source recomputation；17不冒充逐行ready |
| Q06 | NOT_RUN（待指定独审） | 自验/manifest/return关闭后fresh≤1min probe，指定Go Flash/defaultDB只读独审 |

命令/真实exit见03–10/15_meta+原logs；无失败记录被覆写。source_01→02补小cell数值界与角色标签/已知倾斜测试，03是02完整快照；source_04补人工确认消费者从源重算，防caller修改观察报告绕过footprint；新增反例保留。最终当前产物review_02，review_01历史不改。新图17确认与原数据/模型/本轮scope绑定。

软件下一步可接已确认场景身份的行级选择复核，之后用原质量门评估固定变换误差；PCA观察量不直接改参数、旧验证点不按本轮fit残差洗掉。关闭作者日志，源码停写后交指定只读独审。
