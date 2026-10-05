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
    for (const timer of [...h.timers.values()]) { assert.strictEqual(timer.ms, 6000); timer.cb(); }
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
    console.log("PASS O1/O2/O3: local-first, offline click, timeout, recovery, selection, stale refresh");
})().catch(e => { console.error(e); process.exitCode = 1; });
