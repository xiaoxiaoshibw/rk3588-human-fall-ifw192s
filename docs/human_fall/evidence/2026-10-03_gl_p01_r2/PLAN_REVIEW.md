# GL-P01 R2 集中设计前置

R1仅同族容器交集失败，根因与责任见R1/CODEX_REVIEW；v1条目不变，完整M01-M12及新增list/tuple R/t×pure/Node/ROS/JS检查；不发孤立失败方法补丁。R1其它独立证据对SHA未变部分复用。先diag再source；同模型/default DB/同session，派前新<=1分钟probe，不第二writer。R1约86k上下文，续接如近120k按实际API压缩，不全量重读。只producer及集中tests；支持与physics边界不变。
