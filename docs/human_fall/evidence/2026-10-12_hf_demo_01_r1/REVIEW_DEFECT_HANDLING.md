# 独审缺陷处置
- P2-1：新增 manifest_v2.json 补实际导入 scripts/sensor_health.py、core/__init__.py 和 UI v2 SHA；原清单保留。审核给出的 core/sensor_health.py 不存在，首次补清单脚本因此失败，已生成 UI v2 三文件但未生成清单。核对 sys.modules 实际路径后补清单；不据审核猜测文件路径。原规则与写入前基线比对记入 FINAL_SHA.json。
- P2-2：审核者读取的是自身仍在运行的 jsonl，是中间状态；最终以 OPENCODE_01_STATUS.json 实际退出/导出/模型/REVIEW_COMPLETE 为准。
- P3-1/2：新增 app_v2.js/index_v2.html，规则文案从 manifest_v2.settings 读取，补站姿基线条件；时间轴上限和总时长由 rows 派生。原 UI 不覆盖。
- P3-3：README 解释独占输出和新实验用新目录；不采纳删除历史产物重建建议，用户禁止覆盖历史。
- P3-4：v2 标签“合成观测”，README 指定 localhost HTTP 启动。
- SHA 负例：BAD_SHA_BROWSER.json 实际记录 mismatch/无法加载/playEnabled false；不宣称审核者亲验。
- 回归命令：python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_hf06_fall_state.py；20项，exit0，REGRESSION.log / REGRESSION_EXIT.json。
- lie_fast 与 fall 同几何输入，用于展示无法辨别意图，不是独立真实误报样本。
- 独审对 v1 完成；v2 为主控处置建议并另做浏览器验证，不宣称独审者复审 v2。
