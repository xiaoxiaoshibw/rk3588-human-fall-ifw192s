import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
workflow = ROOT / "docs/human_fall/WORKFLOW.md"
review = ROOT / "docs/human_fall/REVIEW_LOG.md"
expected = {
    workflow: "8DFE6D07A672971F00A77152930F85140453A366C88808CBB7EE03F8D7D16D0A",
    review: "1790EF8499384398691F45B3214E26ECCFC1CFF94EFB9773CDB184FDEE2F53EF",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read(path):
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8-sig")


workflow_entry = '''## 2026-10-14 HF-CONSOLE-02 r04真人倒地回放控制台入口

用户明确要求修复小demo并集成总控制台。保留pointset/r01“骨架与倒地检测”，新增real_fall/r04“真人倒地回放”。当前[唯一验收v1](evidence/2026-10-14_hf_console_02_r1/ACCEPTANCE_V1.md)、[报告](evidence/2026-10-14_hf_console_02_r1/FINAL_REPORT.md)、[回传](returns/HF-CONSOLE-02.md)。控制台源码支持两套动态端口；桌面快捷方式目标Console_Pointset.exe按ConsolePointset.spec重建，通用Console.exe也重建，ZIP含两者。源码/两个冻结EXE/headless Edge/ZIP自验C02-01–06 PASS。r04单事件仍verified:false；TOP_REGION显示P95恶化、END_B有效帧减少，身份/关节GT与泛化BLOCKED。C02-07独立复审NOT_RUN、设备/物理NOT_RUN，不报ACCEPTED。无采集、部署、训练/模型切换、生产修改或Git写；实际ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。完整源码/EXE/ZIP SHA见本轮FINAL_SHA.json。

'''
review_entry = '''## 2026-10-14 HF-CONSOLE-02 作者提交（非独立复审）

[唯一验收v1](evidence/2026-10-14_hf_console_02_r1/ACCEPTANCE_V1.md)/[报告](evidence/2026-10-14_hf_console_02_r1/FINAL_REPORT.md)/[回传](returns/HF-CONSOLE-02.md)。控制台保留pointset/r01入口并新增真实r04回放；源码与Console.exe、桌面快捷方式目标Console_Pointset.exe、ZIP均已构建和自验。C02-01–06 PASS：动态服务、headless Edge两卡片/iframe、f72告警图像、冻结启动、双EXE和ZIP逐字节绑定。r04 f72仍verified:false；TOP_REGION平滑回退、END_B槽可用下降及目标点删除风险保留。独立复审NOT_RUN，人体/家具/关节GT与泛化BLOCKED，设备/物理NOT_RUN；SUBMITTED，未ACCEPTED。未改源录制/GT/模型/生产、未部署/采集/提交推送。详证据目录FINAL_SHA与浏览器/启动/打包记录。

'''

contents = {workflow: workflow_entry + read(workflow), review: review_entry + read(review)}
for path, expected_sha in expected.items():
    if sha(path) != expected_sha:
        raise RuntimeError("shared workflow changed since backup: %s" % path)
temps = {}
for path, content in contents.items():
    temp = path.with_name(path.name + ".hf-console-02.tmp")
    if temp.exists():
        raise FileExistsError(str(temp))
    temp.write_bytes(content.encode("utf-8").replace(b"\n", b"\r\n"))
    temps[path] = temp
for path, temp in temps.items():
    os.replace(str(temp), str(path))
print("updated WORKFLOW and REVIEW_LOG with HF-CONSOLE-02 record")
