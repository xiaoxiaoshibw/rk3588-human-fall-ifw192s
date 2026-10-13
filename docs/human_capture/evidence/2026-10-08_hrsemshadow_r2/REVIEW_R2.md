# HR-SEM-SHADOW-R2 最终复审

**状态：SUBMITTED / BLOCKED；离线交付 BLOCKED，未 ACCEPTED。生产接入仍未授权。**

SEM-12工具绑定缺陷已最小修复并有可追溯正负实测，恢复PASS。WD02源/产物字节完整，历史生成代码等式的正式规范归属待裁定，保持BLOCKED。SEM-05～08与SEM-10经必要重放仍BLOCKED；其中05/08结构上界已明显不足95%，补GT不能自动恢复目标。

## 逐ID判定

| ID | R2状态 | 可追溯证据 |
|---|---|---|
| SEM-01 | PASS | 00_baseline.json、data_r2、full_recompute、最终integrity.json；固定源/变换/代码SHA未漂移 |
| SEM-02 | PASS | full_recompute中30自检/24ROI对账；negatives的12冻结空场样本；数学/阈值不改 |
| SEM-03 | PASS | data_r2 / full_recompute：1276原始帧、1561分支、4311簇；全成员/小簇/无簇守恒 |
| SEM-04 | PASS | data_audit.json、recompute.json：三值、低支撑UNKNOWN、无效row与拓扑风险披露 |
| SEM-05 | BLOCKED | 03_blocked_revalidation.md；244帧13HUMAN代理、GT未闭合 |
| SEM-06 | BLOCKED | 同上；271帧269HUMAN代理、家具/连续身份GT缺失 |
| SEM-07 | BLOCKED | 同上；281帧代理、185+5/所有边缘身份UNKNOWN |
| SEM-08 | BLOCKED | 同上；195帧1HUMAN代理，HEAD0，GT未闭合 |
| SEM-09 | PASS | 全285帧两口径0 HUMAN，WORKSPACE1582簇/UNKNOWN485公开 |
| SEM-10 | BLOCKED | negative_recompute/WD02_contract及03报告；GT、有效覆盖与WD02裁定缺口 |
| SEM-11 | PASS | 全票重放+独立实际帧窗约束；43碰撞/88过期确认保留，真人身份仍BLOCKED |
| SEM-12 | PASS | 01_sem12_fix.md、4合法/17拒绝、独立raw receipt审核、实际浏览器记录和截图 |
| SEM-13 | PASS | 逐段代理/GT/票源/分母分别报告；未伪造95%或静态误报率 |
| SEM-14 | PASS | 实际digest两对重哈希、最终SEM12、独立审核与38/45/23回归exit0；失败历史保留 |
| SEM-15 | PASS | integrity.json / 05_integrity.md：旧资产逐文件核对，return旧字节前缀不变 |
| SEM-16 | PASS | 完整return、ponytail路径、逐ID/日志/缺口/停止点；未自封ACCEPTED |
| WD02 | BLOCKED | 02_wd02_review.md；不删除等式、不换基准、不处理WD02 |

以上PASS针对该行的离线要求，不是总体软件、真人识别或生产资格。复审由本聊天单writer以独立raw/NumPy逻辑及明确测试预期完成，没有另派审阅人、不伪称第三方签署；未来外部独立签署未执行。用户要求的“至少独立验证逻辑或人工可核预期”由本轮两类证据支持。

## 范围与完整性

实际新增实现：review_binding.js、build_review.js、review_template.html及必要测试/独立审核；旧R1 finish.py、review_template.html、所有frozen evidence保持原SHA。R2页面是新修复入口，旧R1仅历史。没有修改人体检测/分类/Tracker/背景/Registration、源captures、阈值、生产页面或控制命令；没有commit/push/deploy/publish/capture/ML/重签/安装/启生产旗标。详见changes.json、delivery_manifest.json、05_integrity.md。return仅末尾追加。

## 残余问题与停止点

1. WD02契约歧义：需要确认是历史生成源码相等，还是冻结产物消费+当前代码兼容检查。裁定前继续阻断，建议两案见02报告。
2. 正例全帧成员身份与连续person_id、边缘点真值未闭合；05/08还有已证实结构目标上界不足。必须补GT后按原门复验，算法版本优化另行授权。
3. 旧WD01混合归属与有效对抗覆盖不全，旧负例可信人工入口仍缺；low_bar空输入和格栅缺资产不可当通过。只允许未来获授权证据补齐，不自动采集。
4. 原零XYZ背景/拓扑污染、Tracker同帧复用/观测窗问题保留；相关生产补丁不在本单授权。
5. 本地工具源码和交付摘要是信任根，receipt不是防恶意改写工具的硬件签名或人工观察证明；校验不验证标签真值。
6. 全帧外部索引没有零候选帧的行，R2保留原完整载入入口对这种帧的“无索引”拒绝；34嵌入案例仍可看空帧。这是原有可用性缺口，未扩大本单另修。

现在停在R2证据可复审。下一步仅建议：WD02规则裁定、用R2可信入口补人工身份/覆盖、旧负例审阅入口与有效资产补齐、必要时另立冻结分类新版本工单。不能提前推进生产。
