"use strict";
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function harness() {
    function element() {
        const classes = new Set();
        return {style: {}, dataset: {}, children: [], listeners: {}, textContent: "",
            classList: {add: x => classes.add(x), remove: x => classes.delete(x),
                contains: x => classes.has(x), toggle: x => classes.has(x) ? classes.delete(x) : classes.add(x)},
            addEventListener(type, cb) { this.listeners[type] = cb; },
            appendChild(child) { this.children.push(child); },
            set innerHTML(value) { this.children = []; this.html = value; },
            querySelectorAll() { return this.children; }};
    }
    const els = {}, pending = [], timers = new Map(), loaded = [];
    let timerId = 0;
    const context = {document: {getElementById: id => els[id] || (els[id] = element()),
            createElement: element}, window: {__load_session_sid: sid => { loaded.push(sid); return Promise.resolve(); }},
        AbortController, setTimeout: (cb, ms) => { const id = ++timerId; timers.set(id, {cb, ms}); return id; },
        clearTimeout: id => timers.delete(id),
        fetch: (path, options) => new Promise((resolve, reject) => {
            pending.push({path, options, resolve: data => resolve({ok: true, json: () => Promise.resolve(data)}), reject});
            options.signal?.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), {name: "AbortError"})));
        })};
    vm.runInNewContext(fs.readFileSync(__dirname + "/panel.js", "utf8"), context);
    return {els, pending, timers, loaded};
}
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const take = (h, path, method) => {
    const p = h.pending.find(q => q.path === path && !q.taken
        && (!method || (q.options && q.options.method === method)));
    assert(p, "pending not found: " + path + (method ? " " + method : ""));
    p.taken = true;
    return p;
};
const local = {sessions: [{sid: "cap_local", local: true, duration_sec: 1, frames: 2}]};

(async function () {
    const h = harness();
    h.els.sessionsBtn.listeners.click();
    assert.strictEqual(h.pending[0].path, "/api/board/status");
    assert.strictEqual(h.pending[1].path, "/api/sessions?scope=local");
    h.pending[1].resolve(local);
    await flush();
    assert.strictEqual(h.els.sessBody.children.length, 1, "show local while remote is pending");
    assert.strictEqual(h.pending[2].path, "/api/sessions");
    h.els.sessBody.children[0].listeners.click();
    await flush();
    assert.deepStrictEqual(h.loaded, ["cap_local"], "offline click reaches replay loader");
    for (const [id, timer] of [...h.timers.entries()]) {
        if (timer.ms === 6000) { timer.cb(); h.timers.delete(id); }
    }
    await flush();
    assert.strictEqual(h.els.sessBody.children.length, 1);
    assert.strictEqual(h.els.panelStatus.textContent, "离线 · 本地会话");
    assert.strictEqual(h.els.recBtn.disabled, true);

    // A later refresh recovers, and an older refresh cannot overwrite its rows.
    h.els.refreshBtn.listeners.click();
    h.pending[3].resolve(local); await flush();
    const stale = h.pending[4];
    h.els.refreshBtn.listeners.click();
    h.pending[5].resolve(local); await flush();
    h.pending[6].resolve({sessions: [...local.sessions, {sid: "cap_remote", local: false}], board_error: null});
    await flush();
    assert.strictEqual(h.els.sessBody.children.length, 2);
    assert(h.els.sessBody.children[0].classList.contains("sel"), "preserve local selection on merge");
    stale.resolve({sessions: [], board_error: null}); await flush();
    assert.strictEqual(h.els.sessBody.children.length, 2, "ignore stale remote response");

    h.els.refreshBtn.listeners.click();
    h.pending[7].resolve(local); await flush();
    h.pending[8].resolve({sessions: [], board_error: "board failed"}); await flush();
    assert.strictEqual(h.els.sessBody.children.length, 1, "board error cannot erase local rows");
    assert.strictEqual(h.els.panelStatus.textContent, "离线 · 本地会话");

    // O4: 远端行点击 = 自动同步，完成后自动载入（板端 transferred 会话同一条路）
    h.els.refreshBtn.listeners.click();
    h.pending[9].resolve(local); await flush();
    h.pending[10].resolve({sessions: [...local.sessions,
        {sid: "cap_remote", local: false, transferred: true}], board_error: null});
    await flush();
    assert.strictEqual(h.els.sessBody.children.length, 2);
    h.els.sessBody.children[1].listeners.click();
    await flush();
    const syncCall = h.pending[11];
    assert.strictEqual(syncCall.path, "/api/sync");
    assert.strictEqual(syncCall.options.method, "POST");
    assert.strictEqual(JSON.parse(syncCall.options.body).sid, "cap_remote");
    // 未下载本地前不许改名
    h.els.renameBtn.listeners.click();
    assert(h.els.syncNote.textContent.includes("先点它自动同步"), "rename blocked before download");
    syncCall.resolve({ok: true, note: "拉取中"});
    await flush();
    const pollTimer = [...h.timers.values()].find(timer => timer.ms === 5000);
    assert(pollTimer, "sync poll timer scheduled");
    pollTimer.cb();
    await flush();
    assert.strictEqual(h.pending[12].path, "/api/sessions");
    assert.strictEqual(h.pending[13].path, "/api/sync_status");
    h.pending[12].resolve({sessions: [...local.sessions, {sid: "cap_remote", local: true}],
        board_error: null});
    h.pending[13].resolve({running: false, sid: null, last_sid: "cap_remote",
        last_result: "ok", last_error: null});
    await flush();
    assert(h.loaded.includes("cap_remote"), "sync completion auto-loads the session");
    h.pending[14].resolve({sessions: [...local.sessions, {sid: "cap_remote", local: true}]});
    await flush();
    h.pending[15].resolve({sessions: [...local.sessions, {sid: "cap_remote", local: true}],
        board_error: null});
    await flush();

    // O5: 改名 → POST /api/rename（trim）→ 列表显示 name
    h.els.renameBtn.listeners.click();
    assert(h.els.renameRow.classList.contains("open"), "rename row opens for local selection");
    h.els.renameInput.value = " 客厅-下蹲 ";
    h.els.renameOk.listeners.click();
    await flush();
    const renameCall = h.pending[16];
    assert.strictEqual(renameCall.path, "/api/rename");
    assert.strictEqual(JSON.parse(renameCall.options.body).name, "客厅-下蹲");
    renameCall.resolve({ok: true, sid: "cap_remote", name: "客厅-下蹲"});
    await flush();
    assert(!h.els.renameRow.classList.contains("open"), "rename row closes on success");
    h.pending[17].resolve({sessions: [...local.sessions,
        {sid: "cap_remote", local: true, name: "客厅-下蹲"}]});
    await flush();
    h.pending[18].resolve({sessions: [...local.sessions,
        {sid: "cap_remote", local: true, name: "客厅-下蹲"}], board_error: null});
    await flush();
    assert(h.els.sessBody.children[1].html.includes("客厅-下蹲"), "list shows renamed label");

    // R1: 板端卡 transferring → 失败说明 + 「退回重试」→ 自动重拉
    const h2 = harness();
    h2.els.sessionsBtn.listeners.click();
    take(h2, "/api/board/status").resolve({ros: "up", disk_free_mb: 100, sessions_total: 0});
    take(h2, "/api/sessions?scope=local").resolve({sessions: []});
    await flush();
    take(h2, "/api/sessions").resolve({sessions: [
        {sid: "cap_stuck", local: false, download_requested: true, state: "transferring"}],
        board_error: null});
    await flush();
    assert(h2.els.sessBody.children[0].html.includes("下载中"), "stuck row shows 下载中");
    h2.els.sessBody.children[0].listeners.click();
    await flush();
    take(h2, "/api/sync", "POST").resolve({ok: true, note: "拉取中"});
    await flush();
    [...h2.timers.values()].find(t => t.ms === 5000).cb();
    await flush();
    take(h2, "/api/sessions").resolve({sessions: []});
    take(h2, "/api/sync_status").resolve({running: false, sid: null, last_sid: "cap_stuck",
        last_result: "failed", last_error: "板端卡在传输中：点「退回重试」…",
        recoverable: true, recover_sid: "cap_stuck"});
    await flush();
    assert(h2.els.recoverRow.classList.contains("open"), "recover row opens on stuck failure");
    assert(h2.els.syncNote.textContent.includes("退回重试"), "failure note points to retry");
    h2.els.recoverBtn.listeners.click();
    await flush();
    take(h2, "/api/recover", "POST").resolve({ok: true, sid: "cap_stuck"});
    await flush();
    const retry = take(h2, "/api/sync", "POST");
    assert.strictEqual(JSON.parse(retry.options.body).sid, "cap_stuck");
    assert(!h2.els.recoverRow.classList.contains("open"), "recover row closes when retry starts");

    // R2: 录制中显示会话号 + 已录时长（每秒走表；停止/重开清空）
    const h3 = harness();
    h3.els.sessionsBtn.listeners.click();
    take(h3, "/api/board/status").resolve({ros: "up", disk_free_mb: 100, sessions_total: 0,
        current: "cap_rec", current_created_iso: new Date(Date.now() - 65000).toISOString()});
    take(h3, "/api/sessions?scope=local").resolve({sessions: []});
    await flush();
    assert.strictEqual(h3.els.recBtn.textContent, "■ 停止录制");
    assert(h3.els.recSid.textContent.startsWith("cap_rec · 已录 01:0"),
        "elapsed shown: " + h3.els.recSid.textContent);
    [...h3.timers.values()].find(t => t.ms === 1000).cb();   // 1s 走表一次
    await flush();
    assert(h3.els.recSid.textContent.startsWith("cap_rec · 已录 01:0"),
        "still ticking: " + h3.els.recSid.textContent);
    h3.els.sessionsBtn.listeners.click();   // 关闭：停表
    h3.els.sessionsBtn.listeners.click();   // 重开：重新拉板端（此时已停录）
    take(h3, "/api/board/status").resolve({ros: "up", disk_free_mb: 100, sessions_total: 0});
    take(h3, "/api/sessions?scope=local").resolve({sessions: []});
    await flush();
    assert.strictEqual(h3.els.recSid.textContent, "", "cleared after recording ends");
    assert.strictEqual(h3.els.recBtn.textContent, "● 开始录制");

    console.log("PASS O1/O5: local-first, offline click, timeout, recovery, selection, stale refresh, "
        + "remote auto-sync+load, rename; R1 stuck-recover-retry; R2 recording elapsed");
})().catch(e => { console.error(e); process.exitCode = 1; });
