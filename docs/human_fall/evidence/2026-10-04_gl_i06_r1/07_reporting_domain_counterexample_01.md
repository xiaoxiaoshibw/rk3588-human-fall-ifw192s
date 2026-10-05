# A03/A05预算域反例与新编号修订

源码核查发现：复用GL-I05有界storage的best_support只描述已存见证。candidate_budget=0时仍已执行TLS并获得非空W，但其stored best为None；若晚到最大支持见证恰未存，也不能把该域当全W锚点。原GL-I05研究源码不改。本单refinement_01/02保留历史，01未执行（reason表达式优先级写前审查修订为02）；02为首次数值研究，不作为最终完整W发布入口。

refinement_03保持完全相同TLS/成员/seed及资源行为，只把完整per-event W的ALL/NEAR/BEST_ONLY/最高ties/best_support单独用既有向量oracle发布，并用独立标量oracle核对。旧bounded storage metric明确嵌套stored_subset_diagnostics；有storage gap仍unresolved，即便完整诊断账本能计算关系也不伪闭合。full metric索引引用variant.W，不引用report.witnesses（后者为有界storage）。新02发布台账从不可变01数值记录派生，追加实际full-domain决策耗时，不重算或替换历史记录；另运行03实际入口和预算反例。

不改变NEAR/.8/10°/.05m，也不借J删见证。此为本单完整W要求的根因修订；不改变既有获审工单契约。
