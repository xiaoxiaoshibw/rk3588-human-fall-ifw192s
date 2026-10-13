# P2：秒超时后同内部ID再入的原始事件标签漏标

只读cause_review发现：冻结hook的created_or_reentered只检查frame TTL；expired_ids只看最终bank key消失。同ID因timestamp差>180s、frame差<=30而过期后被本帧独立FG重新建立时，两字段可能都是空。这是事件标签缺陷，不是H4推理/bank本身的超时实现缺陷。

最小反例：before bank1(timestamp0,frame0)，当前timestamp181/frame1，原链先过期，再以相同PIPE ID1独立FG重建(timestamp181,frame1)。原raw label未记重入；正确expired_prior=[1]、same_id_reentered=[1]。源码在全跑期间冻结，未覆盖或重写它。

补证由新analyze_bank_events.py从保存的bank_before、bank_after和真实cfg/帧/时间派生：超帧TTL或超秒TTL任一个就过期，当前同ID新frame更新即重新建立。输出BANK_EVENT_CASES_*保留derived_expired_prior_ids/derived_same_id_reentered及原raw label；不把原标签当无过期证明。全会话受影响计数须以实际派生账为准，不能假设零。

H4仍只改合法刷新x/y；不修改原180s/30帧门，不改评分快照。最终独审须核查此限制和派生补证，不称原运行标签已修复。
