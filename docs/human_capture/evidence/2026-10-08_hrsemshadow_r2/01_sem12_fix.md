# SEM-12 证据绑定修复

原缺陷定位见 00_audit.md。仅新增 R2 工具，不改原 finish.py 或 R1 页面。今后的人工审阅入口为本目录 review.html，校验命令为：

```
node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/review_binding.js <人工sidecar路径>
```

## 实际修复

| 文件/函数 | 修改原因与行为 |
|---|---|
| review_binding.js: authority / PINS | 源码固定 R1 binding、clusters、votes、template、bundle 的 SHA 及实际路径；先重哈希再读取。候选 sidecar 不能选择权威文件或更新清单。拒绝修改基准的 AUTHORITY_SHA_MISMATCH / AUTHORITY_BINDING_MISMATCH |
| review_binding.js: source / content | 读取指定 sid 的原始 meta/bin，核固定 SHA 与 TLS/report/manifest；按 offset_points+row、28B 从真实源读取所有成员，重算 raw_member_sha256 与变换 XYZ，核权威 xyz_sha256 |
| review_binding.js: receipt / validate | 绑定 id/sid/mode/ordinal/seq/ci、固定逻辑源路径、完整 rows、row摘要、原始28B内容摘要、XYZ摘要、review_id、vote_member_id、票帧摘要；票帧确有对应 ci。检查必需字段、重复ID、枚举、PERSON person_id；不是只看记录内部是否一致 |
| build_review.js: main | 权威摘要检查后复用原34案例；从raw生成receipt；验证实际嵌入points与权威row/XYZ。页面payload摘要固定在脚本常量，不能由payload自己给出可信SHA |
| review_template.html: indexfile / loadraw | 整个外部索引固定digest，逐行身份/唯一性/rows摘要；源SHA、seq、row范围、实际重建XYZ及票据核对；通过后才展示和保存，失败清空可审状态，异步陈旧请求不生效 |
| review_template.html: choose / save / savepoint / export | 保存实际校验后的receipt；切帧清空拾取row和更新身份状态栏；点标签仅限已绑定删除线索。新增binding_version=2，保留schema=1与原标签纪律；部分审阅合法，不冒充全覆盖 |
| sem12.test.js / independent_receipts.py | 明确正负预期；独立Python无校验器导入，从原始字节和固定变换核34案例实际显示内容与票据 |

原 member_sha256 仅是 row 列表摘要；新增 raw_member_sha256 绑定每个成员的全部28字节，xyz_sha256绑定实际显示坐标。完整来源路径和源整文件摘要也必须一致。人工可以合法只审部分记录，但每个被审成员的完整row集合必须齐全，删除成员/重复ID均拒绝；GT覆盖仍需另行统计。

## 七类负例与正例

实测 sem12_verified.run.json / sem12_verified_results.json（最终版本）。四个正例：两个不同真实成员的合法记录、合法删除点、嵌入页导出、全索引+raw载入页导出。17个明确拒绝，七类全部覆盖：

| 必需挑战 | 实测错误 |
|---|---|
| 替换成员，保留旧SHA | MEMBER_ROWS_MISMATCH；真实页面 INDEX_SHA_MISMATCH，随后 DISPLAY_NOT_VERIFIED |
| 交换两个成员SHA | RECORD_BINDING_MISMATCH，定位member_sha256 |
| 只改名称/显示身份 | MEMBER_UNBOUND / DISPLAY_ID_MISMATCH |
| 改内容不更新权威 | AUTHORITY_SHA_MISMATCH: points.bin；变造内容receipt为RECORD_BINDING_MISMATCH |
| 审阅成员与票成员不同 | VOTE_BINDING_MISMATCH，定位vote_member_id或vote_frame_sha256 |
| 删除必要成员/重复ID/缺必需字段 | MEMBER_ROWS_MISMATCH / DUPLICATE_ID |
| 内部相互一致的伪造记录 | 与权威rows不一致为MEMBER_ROWS_MISMATCH；自改authority为AUTHORITY_BINDING_MISMATCH |

另测源路径重定向、PERSON缺person_id、失败后旧显示不能保存。所有负例都断言具体错误，不以“任何异常”算通过。实际浏览器重复证实篡改拒绝、清空后禁止保存、权威4311成员索引载入、114205 f0两个完整簇1029+2412=3441点、投影、row拾取、UNKNOWN合成导出；browser_export_validation exit0。下载夹具 reviewer 为 SYNTHETIC BROWSER TEST ONLY，真实人工标签数0。

独立证据：receipts_final（exit0、stderr为空）逐字节/坐标核对34案例、100簇、2358删除点、183340成员坐标；full_recompute重建全部12019508候选成员坐标；edge重建52228线索。原两次R2页面草稿保留，不计最终版。首个独立receipt脚本exit0但有ResourceWarning，未作为干净通过证据；关闭文件后最终日志无警告。首个final自测因独占输出已存在exit1，保留；改为显式新结果文件后实际成功。

**SEM-12：PASS（工具和证据绑定）。** 真实点身份、标签真值、完整GT依然BLOCKED；校验器不证明人工确实观察过屏幕。工具源码/交付页属于外部受保护信任根，交付manifest记录SHA；如果攻击者同时更换工具源码和所有外部可信摘要，普通本地校验器不能提供硬件签名级证明，必须在可信副本上复核。旧R1入口保留为历史，不应再用于新GT验收。
