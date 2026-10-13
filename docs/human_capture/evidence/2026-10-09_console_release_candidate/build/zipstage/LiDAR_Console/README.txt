====================================================
 LiDAR 总控制台 (LiDAR Console)  20261009 B1
====================================================

【运行】
  解压后双击 Console.exe 即可，无需安装 Python 或任何库。
  首次启动 Windows 可能弹 "SmartScreen 已保护你的电脑"
  -> 点 "更多信息" -> "仍要运行"。

【它能做什么】
  打开后是一个总控制台首页，五个入口：
    - 会话回放     本地点云会话回放器 (replay)
    - 板端 WebUI   连接 RK3588 板 (需板在线)
    - 离线配平     四区评估 (TLS / SVD / RANSAC)
    - 算法验证     四个会话配平结果与算法对照
    - 人体识别     纯几何 · pin ROI 辅助判别人/家具 (不跑模型)
                   (默认载入 cap_20261002_223757,
                    需要先对同一会话跑过一次「离线配平」)
    - 人检锁定     B2a RandomForest 51维人/非人 · rf_person_v1 · 实时跟踪
                   会话回放中聚类出候选后, rf_person.js 提 51 维几何特征
                   并跑 rf_person_v1.json 推断 P(person), 实时画红框 + track_id

  回放/配平/人体识别/人检锁定服务 (127.0.0.1:8901) 随控制台一起启动，
  关闭控制台窗口即自动停止，无需另开命令行。

【系统要求】
  Windows 10 1803+ / Windows 11
  依赖系统自带 WebView2 运行时（Win11 和多数 Win10 已内置）。
  注：应用内如提示需要用 Edge/IE 打开，说明缺 WebView2，
      到微软官网装 "Evergreen WebView2 Runtime" 即可。

【数据目录】
  captures\remote\  — 回放读取的会话数据放这里
                      (cap_xxx 文件夹，含 meta.json + points.bin)
                      可从板端同步，或手动拷入。

【B1 说明】
  人检锁定是诊断/演示性质的第一代实现：
    - 用背景差分 (空场模板) + 5cm 网格连通找人物,
      跟踪 1.5s 断档内保持 track_id
    - 当前只覆盖站立人物 (HR-09 第一批 12 段全部站立);
      姿态 (walk/sit/lying/fall) 和 RF 分类是 B2 的事
    - 空场模板是 2026-10-09 大房间; 换房间 (如浴室) 需重新录模板
      并重新生成 bg_envelope.json (见 源码/human_ml/dump_bg_envelope.py)

【源码】
  源码\ 目录（可选，与 Console.exe 同版）：
  console_gui.py（主程序）、console.html（界面）、Console.spec（打包配置）、
  自测脚本与打包脚本。仅供二次开发参考，运行 Console.exe 不需要。
