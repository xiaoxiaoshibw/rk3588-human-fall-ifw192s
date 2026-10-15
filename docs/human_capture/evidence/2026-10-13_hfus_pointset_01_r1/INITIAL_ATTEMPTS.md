# 初始尝试记录

基线脚本首次以正确仓库根目录启动后被作者误以为根目录太宽而中断；随后错误改成parents[3]导致尝试写sidequests/docs不存在目录，FileNotFoundError。已恢复脚本文件parents[4]（对文件路径，而run.py用HERE目录parents[3]），重新完整扫描19751项且最终全量复核无漂移。错误尝试只读，未在外部目录生成证据或修改数据。

正式跑9段前，先对近距走动2帧做smoke，之后以相同参数全9段2605帧重跑。初始RF对象分类训练遍历含S1全帧；发布前统一改为S1 FIT-only并重新训练RF/重算全部候选分数/模型统计，原背景和几何推理不变。旧模型权重未改。最终验收只采用model_comparison.json中S1_train_rule=fi % 3 == 0结果。
