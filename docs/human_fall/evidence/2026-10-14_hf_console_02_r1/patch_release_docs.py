import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
files = {
    "README.txt": ROOT / "pc_apps/console/README.txt",
    "make_release.py": ROOT / "pc_apps/console/make_release.py",
    "ConsolePointset.spec": ROOT / "pc_apps/console/ConsolePointset.spec",
}
expected = {
    "README.txt": "A0515AFE74F82504E44E5017600576C3A5FE4227D6A7E972BE9C033F73372B4D",
    "make_release.py": "AA91B7727FBF7B1C4A41446EEE2A093F6A42E7F2E178A6FDB12CE6C5906169CF",
    "ConsolePointset.spec": "AFACBA1CC45AF8846954D662C151B330CDA76E7F3EE7093F2386FA9A06C7CAB7",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read(path):
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


readme = read(files["README.txt"])
start = readme.index("  打开后是一个总控制台首页，五个入口：")
end = readme.index("\n【系统要求】", start)
readme = readme[:start] + '''  打开后是总控制台首页，包含十个入口：
    - 会话回放       本地点云会话回放器
    - 板端 WebUI     连接 RK3588 板（需板在线）
    - USB 摄像头     板端 MJPEG 预览
    - 算法验证       四区评估（TLS / SVD / RANSAC）
    - 人体识别       纯几何 · pin ROI 辅助判别人/家具（不跑模型）
    - 人检锁定       B2a RandomForest 51维人/非人 · 实时跟踪
    - GT 标注        人工点云标注工作台
    - 骨架与倒地检测 pointset/r01 八段动作 · 粗部位与姿态候选
    - 真人倒地回放   r04 真实录制 · 点支撑粗部位 / 原型告警
    - USB＋雷达联合录制  数据直接保存到本机

  真人回放使用094333受控倒地会话及131958空场参考。13个显示槽是当前点支撑的粗部位，不是已验证的解剖关节；7.46秒告警是未验证原型事件，confirmed保持关闭。'''+readme[end:]
readme = readme.replace(
    "  回放/配平/人体识别/人检锁定服务随控制台一起启动（本机默认 8901，",
    "  会话回放、pointset/r01、真人r04和联合录制服务随控制台一起启动（回放默认 8901，",
    1,
)
readme = readme.replace(
    "【源码】\n  源码\\ 目录（可选，与 Console.exe 同版）：",
    "【构建与源码】\n  桌面“总控制台.lnk”使用 Console_Pointset.exe，构建命令为：\n"
    "    python -m PyInstaller --noconfirm ConsolePointset.spec\n"
    "  通用入口 Console.exe 使用 Console.spec；make_release.py 将两个可执行文件一起打入 ZIP。\n"
    "  源码\\ 目录（可选，与构建版本同版）：",
    1,
)
readme = readme.replace(
    "console_gui.py（主程序）、console.html（界面）、Console.spec（打包配置）、",
    "console_gui.py（主程序）、console.html（界面）、Console.spec / ConsolePointset.spec（打包配置）、",
    1,
)

release = read(files["make_release.py"])
release = release.replace(
    "在本目录运行：\n    python -m PyInstaller --noconfirm Console.spec\n    python -B make_release.py",
    "在本目录运行（桌面快捷方式目标）：\n    python -m PyInstaller --noconfirm ConsolePointset.spec\n"
    "通用 Console.exe 可另用 Console.spec 构建。\n    python -B make_release.py",
    1,
)
release = release.replace(
    '    "LiDAR_Console/源码/Console.spec": "Console.spec",',
    '    "LiDAR_Console/源码/Console.spec": "Console.spec",\n'
    '    "LiDAR_Console/源码/ConsolePointset.spec": "ConsolePointset.spec",',
    1,
)

spec = read(files["ConsolePointset.spec"])
spec = spec.replace(
    "# 从 pc_apps/console/ 目录跑: python -m PyInstaller --noconfirm Console.spec",
    "# 从 pc_apps/console/ 目录跑: python -m PyInstaller --noconfirm ConsolePointset.spec",
    1,
)
updates = {"README.txt": readme, "make_release.py": release, "ConsolePointset.spec": spec}
for name, path in files.items():
    if sha(path) != expected[name]:
        raise RuntimeError("source changed since pre-edit snapshot: %s" % name)

temps = {}
for name, data in updates.items():
    path = files[name]
    temp = path.with_name(path.name + ".hf-console-02.tmp")
    if temp.exists():
        raise FileExistsError(str(temp))
    temp.write_bytes(data.encode("utf-8").replace(b"\n", b"\r\n"))
    temps[path] = temp
for path, temp in temps.items():
    os.replace(str(temp), str(path))
print("updated README, release manifest, and pointset build spec")
