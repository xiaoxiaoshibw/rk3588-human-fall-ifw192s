# HC-JOINT-LOCAL-01 R2 相机超时修复

用户报告两次失败，Codex唯一writer，2026-10-13，SUBMITTED未ACCEPTED；独审NOT_RUN。
唯一表ACCEPTANCE_V1.md。技能实际读取C:/Users/30680/.codex/skills/ponytail/SKILL.md。

## 定位

cap_20261013_202750_joint_155297：相机30帧，最后relative_sec=1.297；停止4.312秒，相差3.015秒。雷达22帧，最后4.219秒。
cap_20261013_203208_joint_48da34：相机54帧，最后2.203秒；停止5.219秒，相差3.016秒。雷达30帧，最后5.016秒。
相机停止进帧后3秒恰好匹配原urllib读取超时；不是雷达尚未连接或硬盘满。旧错误仅timed out，无法告知来源。

只读ssh检查既有cam-mjpeg systemd和/home/wel/cam_mjpeg_server.py：每个客户端队列maxsize=4；队列满则从广播列表移除，HTTP handler仍q.get(timeout=20)循环。故慢客户端可能被踢而连接继续静默，单纯增加读取超时不能恢复该连接。本次无journal读取权限，未拿到两时刻踢客户端的日志；把该机制记为与现象吻合的解释，不冒称逐事件已证。

## 修改

joint_capture.py把网络读与本机写文件分开：初连失败立即报错；已收过帧后HTTP timeout/断开重建连接，停止请求可取消。连续约12秒无新帧则停止两路。3秒单次读取超时保留用于恢复触发，不改为无限等候。
每次恢复尝试与恢复成功写camera_events.jsonl；记录camera_reconnects。存在重连则终态completed_with_gaps，界面明确视频断段。error_source区分camera/radar/recorder，保留原错。
本机写错误仍立即失败，不会被当作摄像头网络错误重试。收尾先原子写meta.json/joint.json，之后才发布终态；修复原终态发布早于落盘的竞态。
未改板端服务、配置、驱动、算法、模型、GT或历史数据。只读ssh与既有流接收为本次板上动作。

## 验证

| ID | 状态 | 证据 |
|---|---|---|
| JT01 | PASS | 两段原始索引和joint.json；FAILURES.json |
| JT02 | PASS（SYNTHETIC） | 模拟读超时后恢复，雷达持续、最终completed_with_gaps |
| JT03 | PASS（SYNTHETIC） | 永久静默有界失败并命名camera；本机写失败保留partial |
| JT04 | PASS（源码/合成） | camera_events.jsonl和状态；真实30秒未重连，不作为真实重连测试 |
| JT05 | PASS（软件/真实短时） | TESTS.json：9＋7＋12；LIVE_CHECK.json与截图 |
| JT06 | PASS（打包启动） | 最终EXE/ZIP和FROZEN_STARTUP.json、RELEASE_CHECK.json |

首次本轮全量运行命中旧收尾竞态，TESTS_FIRST_FINALIZATION_RACE.json保留；修复发布顺序并join等待线程结束后测试全过。
Edge实际总控制台iframe自动录30.016秒：相机899帧、雷达139帧、432,748,459字节，state=completed，error=null，浏览器pageerror=0。另有手动停止段53/8帧、1.766秒。现有回放列表读取和28B点文件尺寸检查通过。
真实30秒测试验证不再在原4～5秒窗超时，但本次未触发相机重连；恢复分支仅有可控合成证据。最终仅追加终态发布顺序修复，该逻辑由合成测试覆盖。

## 未闭合限制

真实30秒雷达源seq已收区间缺号126，设备跨度27.367337秒、接收跨度29.797秒。网络/桥接吞吐与精确同步仍未通过；不能把本次完成状态当作源帧无缺失或逐帧相机GT。只保留已收到的完整原消息，不伪造缺失帧。
有重连时视频断段；持续失联仍会失败。旧两段会话保留FAILED，不回填为成功。
独审、长时可靠性、真实断流恢复、空间/时间标定、人体/跌倒评分NOT_RUN或NOT_EVALUATED。不提交推送。
