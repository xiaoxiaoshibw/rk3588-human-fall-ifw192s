# 本地室内 LiDAR 原型第一阶段

LOCAL-INDOOR-LIDAR-01，独立于公开数据实验/HFUS E0/E1/生产。仅九段用户明确批准输入；不训练，不使用旧分类器，不改原数据和原页面。

双击 `start_demo.bat`，或在仓库根执行：

```powershell
python -B -W error sidequests/local_indoor_lidar_phase1/server.py
```

终端打印准确 `LOCAL_INDOOR_URL=http://127.0.0.1:<空闲端口>/`，复制到浏览器。绑定127.0.0.1，端口自动分配，不杀其他服务。当前会话原URL为 http://127.0.0.1:63383/ ，重启后以打印值为准。

页面三栏：原始完整房间（只剔除不可渲染的非有限坐标）、人工审核/AI几何建议（明确待核验）、原R1真实候选。有限源行顺序每ceil(N/20000)取1，可切全点；候选成员始终全点。三栏同一名义配平/注册坐标；“原始”指处理前点集，不指传感器原坐标显示。原XYZ可从成员JSON查询，原始28B不复制保存。黄色是原R1单目标，其他颜色是未选簇，均非人体概率。

交互：切sid/frame、播放暂停、左拖旋转/右拖平移/滚轮缩放、显隐、归位、候选聚焦、固定待审队列及几何簇数疑点跳转。选择候选后查看成员链接与包围范围；跳帧/失效清空旧结果和审核草稿。UI接口不会自动产生人工记录。具名用户可提交候选级记录；聊天中的明确人工确认也可在绑定准确帧后作为 HUMAN_CHAT_CONFIRMATION 追加，不扩成点级GT。

复算使用下方独立验证器，新结果JSON必须不存在，绝不覆盖baseline。原prepare里的 `code` 是数值开跑时整包快照，其中旧UI仅历史；数值`prototype.py`与旧依赖必须保持SHA。后续viewer由独立 `DELIVERY_V4.json`绑定，不能因UI修改重签数值结果。`prototype.py prepare/replay`仅为保留的首算执行入口，不作为当前公开重跑命令；其旧整包SHA门会拒绝之后更新的UI。

审核字段中 `null` 明确表示 UNKNOWN，`false` 才是否认；聊天确认与表单记录共用此规则，不省略字段。固定REVIEW_QUEUE.json的real_human_reviews=0是创建时快照，保留不覆盖；实时/api/catalog把它改名creation_snapshot_reviews，并从真实记录派生real_human_reviews（帧数）与human_candidate_assertions（候选记录数），不能将静态快照当作当前审核数。页面/本地JS静态服务逐次核对SHA，API请求同时核对运行源码签名；运行中改文件会失败，不能继续显示旧结果。

```powershell
python -B -W error sidequests/local_indoor_lidar_phase1/verify.py <新的验证结果.json>
python -B -W error -m unittest discover -s sidequests/local_indoor_lidar_phase1 -p test_prototype.py
node sidequests/local_indoor_lidar_phase1/state.test.js
```

verify独立重算全2024帧并与已存终止原因/成员逐行比较，检查所有候选SHA与bbox、旧E0 R1逐帧选点兼容。软件fixture不会进入真实效果分母。原背景源cap131958已缺失，旧artifact可重放但原拟合/校准无法重验；新cap221808仅沿原91FIT/91CAL/90HOLDOUT边界。本轮完整原R1只用旧冻结背景，不重拟合测试数据。

唯一验收、00_DIAG、逐帧结果、复算、截图、审查与报告在 `docs/human_capture/evidence/2026-10-15_local_indoor_lidar_phase1_r1/`。人工0/可信组0时不报告人体召回、碎片率、混合率、独立识别效果或训练资格PASS。
