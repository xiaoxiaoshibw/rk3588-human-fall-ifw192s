# HF07安装调试定位（Codex直接续接提示）

继续原session ses_f0c1d2e43ffeMDoXiXAHqpVYqQ，不重盘点。Codex看到重复devel import失败，已仅停本次CLI worker28532补准确定位，源代码/已建隔离ws保留。

catkin devel的core/__init__.py是relay shim；执行原源码init时__file__仍指向devel/lib/python3/dist-packages/core，而不是src/human_fall_detection/core。当前bootstrap仅用__file__导致加不到source scripts，最初缺sensor_health，后续多层except ImportError掩盖成features/timebase/baseline找不到。不要复制/修改冻结sensor_health/解码器。

源/devel用core.__path__里的真实source core目录，优先加入其../scripts；installed目录从dist-packages/core向上3层得到install/lib，再接human_fall_detection（当前代码又加lib导致install/lib/lib/human_fall_detection，错误）。确认导入sensor_health.__file__：devel应为实际source脚本，install为install/lib/human_fall_detection/sensor_health.py。冻结helper _load_xyz_from_cloud已支持邻接install/lib/human_follow_calibration以及source/src/human_follow_calibration/scripts；准确脚本路径即可复用，不要破坏冻结实现。

修好后实测source/devel/install各从/tmp、不同cwd运行，打印core.__path__/sensor_health.__file__/解码器加载结果，缺哪里只修打包。可用标准catkin setup.py模块/目录安装，别在调用者手工PYTHONPATH糊通过。

SSH所有脚本用Python subprocess input=utf8 bytes或.encode，去CRLF；Get-Content管道会加CR，不再用引号嵌套heredoc导致假的PY NameError。失败日志保留。继续HF07节点验证→HF11 actual页面/预览，普通错误自行解决。

浏览器已只读核对原实时页面：49k点、9.4Hz/IMU225Hz正常；原UI把rad/s、m/s²和异常255称已知，当前物理语义未核验，新页面保留原数值但标原始单位待核验、255含义未知，不据此停雷达或假故障。临时测试标签已关闭。Cua浏览器DOM约33秒，独立浏览器调用需60秒超时，后续Codex验新预览URL。
