====================================================
 LiDAR 总控制台 (LiDAR Console)  20261005
====================================================

【运行】
  解压后双击 Console.exe 即可，无需安装 Python 或任何库。
  首次启动 Windows 可能弹 "SmartScreen 已保护你的电脑"
  -> 点 "更多信息" -> "仍要运行"。

【它能做什么】
  打开后是一个总控制台首页，四个入口：
    - 数据标注     本地 ROI 标注页 (annotator)
    - 会话回放     本地点云会话回放器 (replay)
    - 板端 WebUI   连接 RK3588 板 (需板在线)
    - 离线配平     四区评估 (TLS / SVD / RANSAC)

  标注/回放/配平服务 (127.0.0.1:8901) 随控制台一起启动，
  关闭控制台窗口即自动停止，无需另开命令行。

【系统要求】
  Windows 10 1803+ / Windows 11
  依赖系统自带 WebView2 运行时（Win11 和多数 Win10 已内置）。
  注：应用内如提示需要用 Edge/IE 打开，说明缺 WebView2，
      到微软官网装 "Evergreen WebView2 Runtime" 即可。

【数据目录】
  captures\remote\  — 回放/标注读取的会话数据放这里
                      (cap_xxx 文件夹，含 meta.json + points.bin)
                      可从板端同步，或手动拷入。

【源码】
  源码\ 目录（可选，与 Console.exe 同版）：
  console_gui.py（主程序）、console.html（界面）、Console.spec（打包配置）、
  自测脚本与打包脚本。仅供二次开发参考，运行 Console.exe 不需要。
