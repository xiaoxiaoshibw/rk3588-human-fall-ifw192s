# 当前交付 Demo v2

从 D:/Code/ldiar 运行 `python -B -W error sidequests/human_fusion_lab_next/d05/r04/demo_v2/demo_server.py --port 8915`，打开 http://127.0.0.1:8915/ 。默认R04，含A06/R02 split/R03失败对照。三窗同帧和SHA；切换会话时先核验SHA，帧控制暂时禁用，完成后开放，避免跳转被初始化覆盖。初次会话要验证多份大ledger，等待显示SHA_VERIFIED；seek读取保存推理，不改变跟踪。人工PERSON视域只影响显示。V1源码/结果/失败截图保留，当前用此v2。当前算法仍有混簇/家具/遮挡等失败，资格与生产BLOCKED，不ACCEPTED。
