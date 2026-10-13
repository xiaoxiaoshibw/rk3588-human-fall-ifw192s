# 保护检查发现的范围外并发漂移

见不可覆盖的 `ASSET_CHECK_01.json`。首次全树检查发现：

- 旧 `sidequests/human_fusion_lab_next/next/review/` 的 build_review_package.py、review_export.py、review_loader.py、既有review_out/review_package.jsonl变化；同目录新增测试/输出/pycache。
- 旧 `docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/` 新增文档与 `returns/HFUS-D02-REVIEW.md`，不属于本轮授权writer证据目录。
- 旧 `sidequests/human_fusion_lab/results/chrome_q01b.log` 变化。

主控此前已明确把旧next/review纳入保护且不给任何子代理写入权限；A/C独占其他目录，B明确确认上述全部非其执行/写入。本轮B只依赖冻结A接口和lab GT codec/leveling/data_loader，不调用旧next/review runner。保留所有外部内容，不恢复、不删除、不把外部文件收编为本轮成果。无法据现有证据确认范围外writer身份，故不宣称其内容已审或符合本轮所有权。

本轮全树一致性保持 **BLOCKED**；本轮使用的源码、真实capture、GT、模型等应分别按INPUT_LOCK/各运行manifest验证。日志增长不改变算法源码，但也不是整树冻结PASS。最终再查实际漂移，不回填本次失败。
