"""Same whole-tree SHA check; normalize only the stored append text to actual LF.
Original failed checker/output are retained. No input/evidence file is repaired.
"""
from pathlib import Path

OUT = Path(__file__).parent
code = (OUT / '06_integrity.py').read_text(encoding='utf-8')
code = code.replace("append = (OUT / '05_return_append.md').read_bytes()", "append = (OUT / '05_return_append.md').read_text(encoding='utf-8').encode('utf-8') + (OUT / '07_return_final_note.md').read_text(encoding='utf-8').encode('utf-8')")
code = code.replace("'09_integrity.json'", "'09_integrity_r2.json'").replace("'09_integrity.md'", "'09_integrity_r2.md'")
code = code.replace('详见09_integrity.json', '详见09_integrity_r2.json')
code = code.replace('stdout/stderr/真实exit见06_integrity同前缀日志。', 'stdout/stderr/真实exit见06_integrity_r2同前缀日志。初次06_integrity因CRLF/LF校验错误exit1已保留，受保护文件没有漂移。')
exec(compile(code, str(OUT / '06_integrity.py') + ':r2', 'exec'))
