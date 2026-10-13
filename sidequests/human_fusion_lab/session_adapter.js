/* session_adapter.js — 统一 SESSION 契约适配层（HUMAN-FUSION-UNIFY-R1 / STEP 1）。
 *
 * 将 master `pc_apps/human_replay/session_selection.js` 的 `choose()` 语义移植为
 * fusion_lab 后端纯函数，并按研究语境特化：
 *  - 有效会话 = AUDIT 冻结清单 ∩ 磁盘可读 ∩ 输入 SHA 与冻结值一致；
 *  - 无合法 sid 时选“最新有效会话”（desc 排序，字符串序即时间序，cap_YYYYMMDD_HHMMSS）；
 *  - 显式合法 sid 必须尊重（即便 GT eligible=false，仍可回放翻查，仅降级为 UNKNOWN 提示）；
 *  - 非法 / 不存在 sid → 可见报错 + 兜底到最新有效，绝不静默替换；
 *  - 输入 SHA 不匹配的会话不得成为默认目标（S04“损坏/不完整”在 fusion 语境的特化）。
 *
 * 本层不碰点云（28B 契约归 data_loader），不碰配平/检测/跟踪，只做会话生命周期归一。
 */
"use strict";

/* 与 master 完全一致：cap_YYYYMMDD_HHMMSS 主键，允许受限本地后缀，限长 100。 */
function valid_sid(sid) {
    return typeof sid === "string" && sid.length <= 100 &&
        /^cap_\d{8}_\d{6}(?:_[A-Za-z0-9_-]+)?$/.test(sid);
}

function is_sha_match(rec) {
    if (!rec || !rec.input_sha256 || !rec.declared_session_sha256) return false;
    const a = rec.input_sha256, b = rec.declared_session_sha256;
    return a.meta === b.meta && a.points === b.points;
}

/* choose(rows, explicit_sid) — rows 为 [{sid, frames, local, error, sha_idem}]。
 * 返回 { list, sid, message, default_sid, sha_mismatch_sids }。
 * 与 master 同律：过滤→desc 排序→合法显式优先→否则最新。 */
function choose(rows, explicit_sid) {
    const seen = new Set();
    const list = rows.filter(function (s) {
        if (!valid_sid(s.sid) || s.local === false || s.error || !(s.frames > 0) || seen.has(s.sid)) return false;
        seen.add(s.sid); return true;
    }).sort(function (a, b) { return a.sid < b.sid ? 1 : a.sid > b.sid ? -1 : 0; });

    const explicit = explicit_sid !== null && explicit_sid !== undefined;
    const found = valid_sid(explicit_sid) && list.some(function (s) { return s.sid === explicit_sid; });

    /* 默认目标：最新有效，但 SHA 不匹配者降级为非默认。 */
    const defaultable = list.filter(function (s) { return s.sha_idem !== false; });
    const default_sid = (defaultable[0] && defaultable[0].sid) || (list[0] && list[0].sid) || "";

    let sid, message = "";
    const sha_mismatch_sids = list.filter(function (s) { return s.sha_idem === false; }).map(function (s) { return s.sid; });
    if (found) { sid = explicit_sid; }
    else {
        sid = default_sid;
        if (explicit) message += "指定 sid 不合法或本地不可用：" + (explicit_sid || "（空）") + "。已回退到最新有效会话：" + sid + "。";
    }
    if (!sid) message += "没有有效可用会话（AUDIT 冻结清单 ∩ SHA 守卫为空）。";
    return { list: list, sid: sid, default_sid: default_sid, message: message, sha_mismatch_sids: sha_mismatch_sids };
}

module.exports = { choose: choose, valid_sid: valid_sid, is_sha_match: is_sha_match };
