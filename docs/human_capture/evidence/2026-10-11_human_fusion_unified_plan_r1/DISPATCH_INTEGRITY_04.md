# 最终派审：单行入口与完整指令文件

原生exe第三次无工具probe真实exit0/PROBE_OK、指定model正确；session的user文本保存了首尾一对传输引号（42字符请求保存44字符），严格原字符串相等检查保守报FAIL。这个字段不意味着服务失败。原日志/status不改。

最终实现只允许移除**一对首尾引号**做carrier核验，不trim空白、不补缺失内容。长任务书不再传多行argv：发送单行“read绝对任务书路径并执行全部指令”，要求实际read完成且无截断，任务书文件SHA/原文前后不变。以carrier完整、实际任务书read、指定actual model和实际只读工具共同验收。

这避免推测exe能否保留多行参数；没有更换provider/model/DB/auth或放宽修改权限。最终调用为新无工具probe04+review03；多行任务书仍为OPENCODE_PROMPT_03.md，三轮计划和v2冻结件不变。probe03的保守FAIL和review01/02传输缺失全部保留。
