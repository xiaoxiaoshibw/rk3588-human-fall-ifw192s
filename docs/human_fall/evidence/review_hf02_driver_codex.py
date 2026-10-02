"""Compile the submitted stamp helper verbatim, without building a ROS workspace."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / "src/inno_lidar_ros/src/source/publish_manager.cpp").read_text()
match = re.search(r"    static void deviceStampToRos\(.*?\n    }", source, re.S)
assert match, "submitted helper not found"
program = "#include <cmath>\n#include <cstdint>\n#include <iostream>\n#include <limits>\n"
program += match.group(0) + r'''
int main() {
    uint32_t sec, nsec;
    deviceStampToRos(409.9999999996, sec, nsec);
    if (sec != 410 || nsec != 0) return 2;
    deviceStampToRos(std::numeric_limits<double>::quiet_NaN(), sec, nsec);
    if (sec != 0 || nsec != 0) return 3;
    deviceStampToRos(3000000000.0, sec, nsec);
    // builtin_interfaces/Time.sec is int32 in ROS2.
    int32_t ros2_sec = sec;
    std::cout << "helper_sec=" << sec << " ROS2_int32_sec=" << ros2_sec << '\n';
    if (ros2_sec < 0) {
        std::cout << "FAIL: nonnegative out-of-range ROS2 input became a negative stamp\n";
        return 1;
    }
    return 0;
}
'''
compiler = os.environ.get("CXX", r"D:\APPS\mingw64\bin\g++.exe")
env = os.environ.copy()
env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
with tempfile.TemporaryDirectory(prefix="codex_hf02_stamp_") as directory:
    cpp = Path(directory) / "stamp.cpp"
    exe = Path(directory) / "stamp.exe"
    cpp.write_text(program)
    build = subprocess.run([compiler, "-std=c++14", "-Wall", "-Wextra", str(cpp),
                            "-o", str(exe)], env=env, capture_output=True, text=True)
    print(build.stdout, build.stderr, sep="", end="")
    print("HELPER_BUILD_EXIT=" + str(build.returncode))
    if build.returncode:
        raise SystemExit(build.returncode)
    check = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
    print(check.stdout, check.stderr, sep="", end="")
    print("HELPER_CHECK_EXIT=" + str(check.returncode))
    raise SystemExit(check.returncode)
