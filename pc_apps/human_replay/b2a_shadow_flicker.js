/* b2a_shadow_flicker.js — Track 闪烁/id 漂移定量归因 (B2a 步骤 3).
 *
 * 读 b2a_shadow_probe 的 raw/*.tracks.jsonl + *.clusters.jsonl, 对每会话:
 *   A. track 生卒表: 每条 track 的 born/die 帧、位置、命中帧数、assoc_prob 均值
 *   B. id 漂移对: track A 死后 W 帧内, 新 track B 在距 A 最后位置 <1.0m 出生 → (A,B) 漂移对
 *   C. 闪现统计: confirmed_now=true 的连续段 ("shown episode") 长度分布,
 *      ≤2 帧的段记一次"闪烁" — 即用户截图里"柜子弹一下红框就消失"的量化
 *   D. 柜位间歇成簇剖面: 该会话 rank>=1 簇的质心位置出现时序 (presence run 长度 + 缺口长度)
 *
 * 归因判别 (对应裁定步骤 3: 区分检测簇间歇丢失 vs Track 关联失败):
 *   - 若 D 显示柜位簇"存在期短、缺口长" → 检测侧间歇成簇是主因
 *   - 若某帧柜位簇存在且 prob≥thr 但 同帧无 track assoc (tracks 表 assoc_prob=null) → 关联失败
 *
 * 跑法: node b2a_shadow_flicker.js <raw_dir> <out_json>
 */
"use strict";
var fs = require("fs");
var path = require("path");

var NAMES = {
    cap_20261009_122637: "男生近距离", cap_20261009_122616: "男生中距离",
    cap_20261009_122700: "男生远距离", cap_20261009_121647: "女生近距离",
    cap_20261009_121622: "女生中距离", cap_20261009_121723: "女生远距离",
};
var THR_KEYS = ["0.55", "0.65", "0.8"];
var REBORN_WINDOW = 30;       /* A 死后 30 帧内 B 在 1m 内出生 → 漂移对 */
var GATE_M = 1.0;

function frames_of(obj, key) { return obj.per_thr[key]; }

function analyze_session(dir, sid) {
    var clusters = fs.readFileSync(path.join(dir, sid + ".clusters.jsonl"), "utf8")
        .split("\n").filter(Boolean).map(JSON.parse);
    var tracks = fs.readFileSync(path.join(dir, sid + ".tracks.jsonl"), "utf8")
        .split("\n").filter(Boolean).map(JSON.parse);
    var out = { sid: sid, name: NAMES[sid] || "", n_frames: tracks.length };

    THR_KEYS.forEach(function (tk) {
        /* ---- A. track 生卒表 ---- */
        var tab = {};   /* id -> {born, die, first_pos, last_pos, hits, shown, prob_sum, prob_n, ages} */
        tracks.forEach(function (t) {
            var pt = frames_of(t, tk);
            if (!pt) return;
            pt.tracks.forEach(function (tr) {
                var e = tab[tr.id];
                if (!e) {
                    e = tab[tr.id] = { id: tr.id, born: t.frame, die: t.frame,
                        first_pos: [tr.cx, tr.cy], last_pos: [tr.cx, tr.cy],
                        hits: 0, shown: 0, prob_sum: 0, prob_n: 0, max_age: 0 };
                }
                e.die = t.frame;
                e.last_pos = [tr.cx, tr.cy];
                e.max_age = Math.max(e.max_age, tr.age);
                if (tr.assoc_prob !== null) {
                    e.hits++;
                    e.prob_sum += tr.assoc_prob; e.prob_n++;
                    if (tr.confirmed_now) e.shown++;
                }
            });
        });
        var list = Object.keys(tab).map(function (k) {
            var e = tab[k];
            e.mean_prob = e.prob_n ? +(e.prob_sum / e.prob_n).toFixed(3) : null;
            /* die 帧修正: 若最后出现于末帧, 记 alive_at_end */
            e.alive_at_end = (e.die === tracks.length - 1) ||
                (tracks.length - 1 - e.die) <= 15;   /* TTL 内都算"可能还活着" */
            delete e.prob_sum; delete e.prob_n;
            return e;
        }).sort(function (a, b) { return a.born - b.born; });

        /* ---- B. id 漂移对 ---- */
        var drifts = [];
        for (var i = 0; i < list.length; i++) {
            var a = list[i];
            if (a.alive_at_end) continue;
            for (var j = 0; j < list.length; j++) {
                var b = list[j];
                if (b.born <= a.die || b.born > a.die + REBORN_WINDOW) continue;
                var d = Math.hypot(a.last_pos[0] - b.first_pos[0], a.last_pos[1] - b.first_pos[1]);
                if (d < GATE_M) drifts.push({ from: a.id, to: b.id, gap_frames: b.born - a.die, dist: +d.toFixed(2) });
            }
        }

        /* ---- C. shown episode 闪烁 ---- */
        var episodes = [];   /* {id, start, len} */
        var cur = null;
        tracks.forEach(function (t) {
            var pt = frames_of(t, tk);
            if (!pt) return;
            var shown_ids = {};
            pt.tracks.forEach(function (tr) { if (tr.confirmed_now) shown_ids[tr.id] = true; });
            /* 多 track 并行: 每 id 独立 episode 状态 — 简化为按 id 维护 */
            if (!cur) cur = {};
            var ids = new Set(Object.keys(cur).concat(Object.keys(shown_ids)));
            ids.forEach(function (id) {
                if (shown_ids[id]) {
                    if (!cur[id]) cur[id] = { start: t.frame, len: 0 };
                    cur[id].len++;
                } else if (cur[id]) {
                    episodes.push({ id: +id, start: cur[id].start, len: cur[id].len });
                    delete cur[id];
                }
            });
        });
        Object.keys(cur || {}).forEach(function (id) {
            episodes.push({ id: +id, start: cur[id].start, len: cur[id].len });
        });
        var flashes = episodes.filter(function (e) { return e.len <= 2; });

        out["thr_" + tk] = {
            tracks: list, drift_pairs: drifts,
            episodes_total: episodes.length,
            flash_episodes: flashes.length,
            flash_detail: flashes.slice(0, 10),
        };
    });

    /* ---- D. 柜位间歇成簇 (与阈值无关, 测检测侧) ----
     * 取该会话 rank>=1 簇的 (cx,cy) 众数位置作柜位锚点; 逐帧判 0.5m 内有无簇 */
    var rankN = clusters.filter(function (c) { return c.rank >= 1; });
    if (rankN.length >= 5) {
        var mx = 0, my = 0;
        rankN.forEach(function (c) { mx += c.cx; my += c.cy; });
        mx /= rankN.length; my /= rankN.length;
        var presence = [];
        for (var fi = 0; fi < tracks.length; fi++) presence.push(false);
        clusters.forEach(function (c) {
            if (c.rank < 0) return;
            if (Math.hypot(c.cx - mx, c.cy - my) < 0.5) presence[c.frame] = true;
        });
        /* run/gap 长度 */
        var runs = [], gaps = [], i = 0;
        while (i < presence.length) {
            var v = presence[i], j = i;
            while (j < presence.length && presence[j] === v) j++;
            (v ? runs : gaps).push(j - i);
            i = j;
        }
        var probs = rankN.map(function (c) { return c.person_prob; }).sort(function (a, b) { return a - b; });
        out.cabinet_profile = {
            anchor: [+mx.toFixed(2), +my.toFixed(2)],
            present_frames: rankN.length, total_frames: tracks.length,
            presence_rate: +(rankN.length / tracks.length).toFixed(3),
            run_len_median: runs.length ? runs.sort(function (a, b) { return a - b; })[Math.floor(runs.length / 2)] : 0,
            gap_len_max: gaps.length ? Math.max.apply(null, gaps) : 0,
            n_episodes: runs.length,
            prob_p10: probs[Math.floor(probs.length * 0.1)],
            prob_p50: probs[Math.floor(probs.length * 0.5)],
            below_055: rankN.filter(function (c) { return c.person_prob < 0.55; }).length,
        };
    } else {
        out.cabinet_profile = { note: "rank>=1 簇 <5 帧, 无复发柜位", rankN: rankN.length };
    }
    return out;
}

var raw = process.argv[2], out_json = process.argv[3];
var sids = fs.readdirSync(raw).filter(function (f) { return f.endsWith(".tracks.jsonl"); })
    .map(function (f) { return f.replace(".tracks.jsonl", ""); }).sort();
var report = sids.map(function (s) { return analyze_session(raw, s); });
fs.writeFileSync(out_json, JSON.stringify(report, null, 1));

/* 控制台摘要 */
report.forEach(function (r) {
    console.log("\n=== " + r.sid + " (" + r.name + ") frames=" + r.n_frames + " ===");
    var t = r["thr_0.55"];
    console.log("  0.55: tracks=" + t.tracks.length + " 漂移对=" + t.drift_pairs.length +
        " shown段=" + t.episodes_total + " 闪烁(<=2帧)=" + t.flash_episodes);
    t.tracks.forEach(function (e) {
        console.log("    #" + e.id + " born=" + e.born + " die=" + e.die +
            " hits=" + e.hits + " shown=" + e.shown + " max_age=" + e.max_age +
            " mean_p=" + e.mean_prob + (e.alive_at_end ? " [存活至末]" : " [已死]") +
            " pos=(" + e.first_pos[0].toFixed(2) + "," + e.first_pos[1].toFixed(2) + ")");
    });
    t.drift_pairs.forEach(function (d) {
        console.log("    漂移: #" + d.from + " -> #" + d.to + " gap=" + d.gap_frames + "f dist=" + d.dist + "m");
    });
    var c = r.cabinet_profile;
    if (c.anchor) {
        console.log("  柜位(" + c.anchor + "): 成簇 " + c.present_frames + "/" + c.total_frames +
            " (" + (c.presence_rate * 100).toFixed(0) + "%)  episodes=" + c.n_episodes +
            " run中位=" + c.run_len_median + "f gap最长=" + c.gap_len_max + "f" +
            "  prob p10/p50=" + c.prob_p10 + "/" + c.prob_p50 + "  <0.55的帧=" + c.below_055);
    } else {
        console.log("  柜位: " + c.note + " (rankN=" + c.rankN + ")");
    }
});
console.log("\nwrote " + out_json);
