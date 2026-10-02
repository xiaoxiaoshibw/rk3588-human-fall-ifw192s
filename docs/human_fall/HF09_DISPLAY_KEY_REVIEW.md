# R3最后显示映射守卫与恢复

当前R3已部署20261001T031804Z、node24770；CLI在deployment后API连接中断(exit1)，不是用户取消。先检查板上当前工作，不重新覆盖实现/重做30min。

根端独立node docs/human_fall/evidence/review_hf09_display_keys.js失败：objectKeys无条件同时返回source S与display D。selected display topic声明不一致、或visualization.source与parent.source不一致时仍可走S/D误匹配，未满足R3严格映射要求。

请给visualization增加明确source_topic（实际订阅的原始云话题）；objectKeys(obj, selectedTopic) 在有mapping时：选择source_topic仅S、选择visualization.topic仅D且source header一致、其他topic返回[]；不一致source返回[]。无mapping时可保留legacy/synthetic S。前端所有调用传实际POINTS_TOPIC。支持?points=/innolidar_points真实全流诊断，不破坏旧协议；有效测试明确topic错配/source错配/负age。

修后根端独立脚本PASS，同树完整回归/实际wire序号映射probe/root已有独立边界全保留；manifest/self排除与精确PID新增也给真实stdout证据。追加HF09第3轮回传/部署说明与证据后退出，Codex最后浏览器复测。source topic与所选display topic都只读，不改原算法/driver/标签/confirmed。
