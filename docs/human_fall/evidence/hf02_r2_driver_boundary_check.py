"""HF-02 R2 supplementary check: compile the submitted helper verbatim per ROS
variant and exercise carry / NaN / Inf / negative / both second limits.

This complements review_hf02_driver_codex.py (unchanged); it compiles the same
actual helper with -DROS_FOUND=1, -DROS_FOUND=2 and with ROS_FOUND undefined
(the standalone default used by the Codex script). Synthetic, no ROS runtime.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / "src/inno_lidar_ros/src/source/publish_manager.cpp").read_text()
match = re.search(r"    static void deviceStampToRos\(.*?\n    }", source, re.S)
assert match, "submitted helper not found"
helper = match.group(0)
assert "#if ROS_FOUND==1" in helper, "per-ROS range branch missing from helper"

program = "#include <cmath>\n#include <cstdint>\n#include <iostream>\n#include <limits>\n"
program += helper + r'''
static int failures = 0;

static void expect(double input, uint32_t want_sec, uint32_t want_nsec, const char* label)
{
    uint32_t sec = 123u, nsec = 456u;
    deviceStampToRos(input, sec, nsec);
    if (sec != want_sec || nsec != want_nsec)
    {
        std::cout << "FAIL " << label << ": input=" << input << " got=" << sec << "/" << nsec
                  << " want=" << want_sec << "/" << want_nsec << '\n';
        ++failures;
    }
    else
    {
        std::cout << "ok   " << label << " -> " << sec << "/" << nsec << '\n';
    }
}

int main() {
    const double inf = std::numeric_limits<double>::infinity();
    const double nan = std::numeric_limits<double>::quiet_NaN();
    expect(409.9999999996, 410u, 0u, "carry at 1e9 rounding boundary");
    expect(409.9999999994, 409u, 999999999u, "no carry just below boundary");
    expect(12.5, 12u, 500000000u, "plain fraction");
    expect(0.0, 0u, 0u, "zero");
    expect(nan, 0u, 0u, "NaN invalid");
    expect(inf, 0u, 0u, "+Inf invalid");
    expect(-inf, 0u, 0u, "-Inf invalid");
    expect(-1.0, 0u, 0u, "negative invalid");
#if ROS_FOUND==1
    expect(4294967295.5, 4294967295u, 500000000u, "ROS1 last second fraction kept");
    expect(4294967296.0, 0u, 0u, "ROS1 first out-of-range second rejected");
    expect(1e300, 0u, 0u, "ROS1 huge value rejected before cast");
#else
    expect(2147483647.5, 2147483647u, 500000000u, "ROS2 int32-max second fraction kept");
    expect(2147483648.0, 0u, 0u, "ROS2 first out-of-range second rejected");
    expect(3000000000.0, 0u, 0u, "ROS2 3e9 rejected (would be negative int32)");
    expect(1e300, 0u, 0u, "ROS2 huge value rejected before cast");
#endif
    if (failures) { std::cout << "BOUNDARY_FAILURES=" << failures << '\n'; return 1; }
    std::cout << "BOUNDARY_OK\n";
    return 0;
}
'''
compiler = os.environ.get("CXX", r"D:\APPS\mingw64\bin\g++.exe")
env = os.environ.copy()
env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
variants = (("ROS1", ["-DROS_FOUND=1"]), ("ROS2", ["-DROS_FOUND=2"]),
            ("undefined", []))
overall = 0
with tempfile.TemporaryDirectory(prefix="hf02_r2_stamp_") as directory:
    cpp = Path(directory) / "stamp.cpp"
    cpp.write_text(program)
    for name, extra in variants:
        exe = Path(directory) / ("stamp_" + name + ".exe")
        build = subprocess.run([compiler, "-std=c++14", "-Wall", "-Wextra"] + extra
                               + [str(cpp), "-o", str(exe)],
                               env=env, capture_output=True, text=True)
        print("== variant {} : HELPER_BUILD_EXIT={}".format(name, build.returncode))
        print(build.stdout, build.stderr, sep="", end="")
        if build.returncode:
            overall = build.returncode or 1
            continue
        check = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
        print(check.stdout, check.stderr, sep="", end="")
        print("== variant {} : HELPER_CHECK_EXIT={}".format(name, check.returncode))
        if check.returncode:
            overall = check.returncode or 1
print("DRIVER_BOUNDARY_EXIT=" + str(overall))
raise SystemExit(overall)
