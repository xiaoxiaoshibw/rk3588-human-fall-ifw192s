

### R40收尾补记（只追加）

06_integrity首轮exit1：393个protected文件无漂移；失败仅因校验器把以Windows文本方式保存的append.md之CRLF，与实际以二进制追加的LF相比较。原return前缀和实际追加内容正确，没有回传破坏。旧失败stdout/stderr/run/json/md保留；r2按真实追加字节复核，09_integrity_r2.md/json为当前完整性结果。

集中报告现以07_research_and_minimal_plan_r2.md为最终；研究结论、GT/production状态不变，仅补完整性校验修订及真实首轮exit1记录。观察到范围外README变化及cap_20261007_154920/下载部署证据新增，均保留，未由本轮脚本写入，不推测操作者。REWORK_REQUIRED不变。
