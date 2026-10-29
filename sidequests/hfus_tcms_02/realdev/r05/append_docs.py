"""S4: append the S3-review/r2/S4 record to WORKFLOW (top) and REVIEW_LOG (end), binary + LF only."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s4core as C

WORKFLOW = C.ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = C.ROOT / 'docs/human_fall/REVIEW_LOG.md'

WF_ENTRY = """## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S03 澶嶅鏀跺熬 + HFUS-TCMS-02-REALDEV-02-S04 灏炬/杩戝湴璇婃柇锛圫UBMITTED锛?
鐢ㄦ埛瑕佹眰鈥滆嚜宸卞彂缁?opencode 澶嶅鐒跺悗鎸佺画寮€鍙戔€濄€係3 鍏堥€?`opencode-go/deepseek-v4.1-flash`锛坧lan 鍙锛宔xit 0锛?82.9 s锛夛細**鏃犱换浣曟敼鍙?G05/G06/G07/G10/G11/G12 鍒ゅ畾鎴栨暟鍊?鍥犳灉缁撹鐨勭己闄?*锛屾彁鍑?2 椤逛綆涓ラ噸搴﹁瘉鎹己闄凤紙D1 娴忚鍣ㄧ増鏈湭鍐呭祵銆丏2 n/d 涓?C3D_03 宸?1 ULP锛変笌 2 椤规枃妗?nit锛圖3 `appchain/run.py` 涓嶅瓨鍦ㄣ€丏4 `EVALUATION.json` 璺緞锛夈€係3 r2 鍙敹灏捐繖 4 椤广€佷笉閲嶈窇搴旂敤閾撅細娴忚鍣ㄧ増鏈敼鐢?CDP `/json/version` 鍐呭祵銆丼2 鍘熷 n/d 瀛樺叆 provenance锛埼?2.22e-16锛屽悓涓€骞抽潰锛夈€佷袱浠藉嫎璇紱r1 灏佸瓨浠堕€愬瓧鑺傛湭鍔ㄣ€?
闅忓悗鏂板伐鍗?S4锛堝敮涓€[H01鈥揌08楠屾敹v1](evidence/2026-10-17_hfus_tcms_02_s04_r1/ACCEPTANCE_V1.md)銆乕鍗忚v1](evidence/2026-10-17_hfus_tcms_02_s04_r1/PROTOCOL_V1.json)銆乕鎶ュ憡](evidence/2026-10-17_hfus_tcms_02_s04_r1/REPORT.md)銆乕鍥炰紶](returns/HFUS-TCMS-02-REALDEV-02-S04.md)锛夊湪 S3 宸查獙璇佸潗鏍囦笂鍋氳瘖鏂細鎺ヨЕ甯?杩戝湴鍙仛鏍囩涓庤鏁帮紙涓嶅垹琛屻€佷笉鏀瑰尮閰嶃€佷笉鍋氱墿鐞嗛珮搴︼級锛?*灏炬闆跺€欓€夋牴鍥犳槸 M0 鑳屾櫙鍚告敹**鈥斺€?45鈥?79 鍏?12 甯ч浂鍊欓€夛紝contact 甯︾害 9.83k 琛屼腑 99.8% 琚垽鑳屾櫙锛屽墿浣欑瀛?8鈥?5 琛屽叏涓?鈮? 鐐瑰皬缁勮 `UNSUPPORTED` 鎷掔粷锛涘弽璇佸悓甯у叧鎺?M0锛圓锛夋瘡甯ч兘鏈?4鈥?0 涓€欓€夈€俧430鈥?49 鍏?30 甯ф棤闆跺€欓€夈€侀€愬抚鍒嗚В閰嶅钩锛堜絾鏈」鏃犺韩浠?杞ㄨ抗锛孲1 鐨?f439 LOST 鏃笉鑳藉鐜颁篃涓嶈兘鍚﹀畾锛夈€傚垎瑙ｆ亽绛夊紡鍦ㄥ叏閮?587 涓舰鎴愬垎缁勫抚涓婃垚绔嬶紝193 涓?MAP_BUILDING 甯ф寜 r01 璇箟涓嶉€傜敤骞跺崟鍒楀璁°€傜湡瀹?Edge 5 甯ч€氳繃鍒嗗甫/鍒嗚В/灏炬鍘熷洜/56 hex 鍗曠偣/鐩告満涓嶅彉銆?
鐘舵€?SUBMITTED锛堥潪 ACCEPTED锛夛細S4 涓嶆敼 S3 鐨?GEOMETRY_VALIDATED_LOCAL锛屾棤 GT 鈫?浜轰綋鏁堟灉 UNKNOWN锛涘熬娈佃创鍦板墠鏅繚鐣欎笌韬唤绉嶅瓙浠嶆湭瀹炵幇锛堥渶棰勬敞鍐屾柊鍙樹綋涓庣敤鎴?AI 瑙嗚鎺堟潈锛夛紱鍦伴潰韬唤/鐗╃悊楂樺害/鐙珛 D/璁惧 BLOCKED/NOT_RUN锛汼5 涓庨鏋堕噷绋嬬鏈淳鍙戙€俤ata 鍙銆佹棫璇佹嵁鍙銆佹棤 Git 鍐欍€備互涓嬪師鏂囧畬鏁翠繚鐣欍€?"""

RV_ENTRY = """
## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S03 澶嶅 + S04 灏炬璇婃柇锛堜綔鑰呰嚜楠?SUBMITTED锛?
- S3 鐙珛 AI 鍙澶嶅锛坄opencode-go/deepseek-v4.1-flash`锛宲lan锛宔xit 0锛?82.9 s锛夛細鏃犳敼鍒ょ己闄凤紱D1鈥揇4 瑙?`docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_review_r1/REVIEW_SUMMARY.json`銆?*涓嶆槸** Codex 姝ｅ紡楠屾敹銆?- S3 r2锛坄2026-10-17_hfus_tcms_02_s03_r2/`锛屽皝瀛?`c82ea013鈥?4e`锛夛細D1 娴忚鍣ㄧ増鏈唴宓屻€丏2 S2 鍘熷 n/d provenance锛埼?2.22e-16锛夈€丏3/D4 鍕樿锛況1 灏佸瓨 `601a7a24鈥?27b` 鏈姩銆?- S4锛坄2026-10-17_hfus_tcms_02_s04_r1/`锛孒01鈥揌08 鑷獙 PASS锛夛細**灏炬闆跺€欓€?= M0 鑳屾櫙鍚告敹**锛?2 甯ч浂鍊欓€夈€乧ontact 甯?99.8% 鍒よ儗鏅€佺瀛?8鈥?5 琛屼负 鈮? 鐐瑰皬缁勶級锛汚锛堟棤 M0锛夊悓甯?4鈥?0 鍊欓€夊弽璇侊紱f430鈥?49 鏃犻浂鍊欓€夈€傛帴瑙﹀甫浠呮爣绛捐鏁帮紱鍒嗚В鎭掔瓑寮?587/587 甯ф垚绔嬨€?93 涓?MAP_BUILDING 甯т笉閫傜敤銆?- 淇濈暀澶辫触锛歚FAILED_RUN_V1/`锛坆g 涓?members 閲嶅鐩稿噺锛夈€乣RUN_FAIL1/`锛團rozenMap 璺緞锛夈€乣RUN_FAIL2/`锛圡0 鎸囩汗锛夈€?- 澶嶅閲嶇偣锛氭帴瑙﹀甫鏄惁瓒婄晫鎴愨€滃垹鐐?鐗╃悊楂樺害鈥濓紱鍒嗚В鎭掔瓑寮忔槸鍚﹁浜嬪悗鏀归棬锛涙棤韬唤鏄惁琚璇绘垚杞ㄨ抗缁撹銆?- 涓嬩竴姝ワ細S5 涓庘€滀汉浣?楠ㄦ灦鎸佺画鏍囧畾鈥濋噷绋嬬鍙﹁娲惧彂锛涗笉鑷 ACCEPTED銆?"""


def sha(b):
    return hashlib.sha256(b).hexdigest()


if __name__ == '__main__':
    wf, rv = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    if b'\r' in wf or b'\r' in rv:
        raise SystemExit('not LF-only; refusing')
    entry = WF_ENTRY.encode('utf8')
    if b'HFUS-TCMS-02-REALDEV-02-S04' in wf[:600]:
        raise SystemExit('WORKFLOW already has the S4 entry at the top')
    with WORKFLOW.open('wb') as f:
        f.write(entry + wf)
    with REVIEW.open('wb') as f:
        f.write(rv + RV_ENTRY.encode('utf8'))
    wf2, rv2 = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    checks = dict(workflow_original_bytes_preserved=wf2[len(entry):] == wf,
                  review_original_bytes_preserved=rv2[:len(rv)] == rv,
                  crlf_after=dict(workflow=wf2.count(b'\r\n'), review=rv2.count(b'\r\n')),
                  sha_before=dict(workflow=sha(wf), review=sha(rv)),
                  sha_after=dict(workflow=sha(wf2), review=sha(rv2)))
    C.write(C.OUT / 'DOCUMENT_APPEND.json', dict(item=C.ITEM, method='binary splice, UTF-8, LF only', checks=checks,
                                                 PASS=bool(checks['workflow_original_bytes_preserved']
                                                           and checks['review_original_bytes_preserved']
                                                           and not any(checks['crlf_after'].values()))))
    print('appended', len(wf2), len(rv2), 'PASS', not any(checks['crlf_after'].values()))
