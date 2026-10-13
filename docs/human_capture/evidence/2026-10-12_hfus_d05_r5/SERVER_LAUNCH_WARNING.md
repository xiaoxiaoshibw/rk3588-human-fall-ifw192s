# Demo启动器告警与实物核验边界

Python一次性Popen启动器退出0并输出PID21796，随后-Python -W error在Popen析构时提示“subprocess is still running”。这是未等待持久服务的启动器ResourceWarning，不能称启动检查clean。未停止/重新覆盖服务或日志；实际运行与可用性须以DEMO_SERVER.log、PID/listener及真实浏览器SHA/同帧操作核验，不能只用poll=null或文件存在证明。

后续持久服务启动采用PowerShell Start-Process -WindowStyle Hidden或保持所属执行会话，避免该启动器写法。此告警不涉及算法实跑、输入、GT或模型修改，所有实际评测子进程另有等待和真实退出状态。
