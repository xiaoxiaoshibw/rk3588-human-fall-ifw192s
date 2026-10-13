"use strict";
/* gt_workbench_ops.test.js — GT 工作台操作层（改名/别名/拉取/录制）的纯 fetch 行为测试。
 * 复用 panel.test.js 的 vm 沙箱 harness：fake fetch + pending queue + flush。
 */
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function harness() {
    function element() {
        return {style: {}, dataset: {}, children: [], listeners: {}, textContent: "", title: "", disabled: false,
            addEventListener(type, cb) { this.listeners[type] = cb; },
            click() { if (this.listeners.click) this.listeners.click({ target: this }); },
            focus() {},
            setAttribute() {},
            getAttribute() { return null; }};
    }
    const els = {}, pending = [], timeouts = [];
    const context = {
        document: {getElementById: id => els[id] || (els[id] = element())},
        window: {},
        console,
        setTimeout: (cb, ms) => { timeouts.push({cb, ms}); return timeouts.length; },
        clearTimeout: () => {},
        fetch: (path, options) => new Promise((resolve) => {
            pending.push({path, options, resolve: (code, data) =>
                resolve({ok: code < 400, status: code, json: () => Promise.resolve(data)})});
        }),
        prompt: () => "unused",
    };
    // 预建档：mkctx / 测试都用 h.els.x，不走 document.getElementById —— lazy hack
    ["noteEl", "renameInput", "renameOk", "pullBtn", "recBtn", "frozenListEl"]
        .forEach(id => { context.document.getElementById(id); });
    vm.runInNewContext(fs.readFileSync(__dirname + "/gt_workbench_ops.js", "utf8"), context);
    return {els, pending, timeouts, GT_OPS: context.GT_OPS};
}
const flush = async () => { for (let i = 0; i < 80; i++) await Promise.resolve(); };
const lastPending = (h, pathFrag, method) => {
    for (let i = h.pending.length - 1; i >= 0; i--) {
        const p = h.pending[i];
        if (p.taken) continue;
        // 完全相等 or 以 pathFrag 结尾（防 /api/gt/pull 吃掉 /api/gt/pull_status）
        if (p.path !== pathFrag && !p.path.endsWith(pathFrag)) continue;
        if (method && (!p.options || p.options.method !== method)) continue;
        p.taken = true;
        return p;
    }
    return null;
};

// mkinfo() → fresh S.session_info-like dict；mkctx → 绑定到 h.els 上 id 用 kebab-case。
function mkinfo() {
    return {sid: "cap_20261011_120000", display_name: "S1", draft_alias: null, version_aliases: {}};
}
function mkctx(h, ids, extra) {
    // fake 元素：harness 已经在访问 document.getElementById 时建好档；
    // GT_OPS.bind 只访问 ctx.els（不读 document），所以由这里把 fake 元素显式塞进 ctx.els。
    const els = {noteEl: h.els.noteEl};
    for (const id of ids) els[id] = h.els[id];
    const ctx = Object.assign({
        els,
        get_session_info: () => ctx._info,
        reload_session: () => {},
        after_pull_ok: () => { ctx._info._pulled = true; },
    }, extra || {});
    ctx._info = mkinfo();
    return ctx;
}

(async function () {
    // ---------- 1) rename_session OK ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["renameInput", "renameOk"]);
        const seen = [];
        ctx.reload_session = sid => seen.push(sid);
        h.GT_OPS.bind(ctx);
        h.els.renameInput.value = "新名";
        h.els.renameOk.click();
        const p = lastPending(h, "/api/rename", "POST");
        assert(p, "rename POST 应发出");
        assert.deepStrictEqual(JSON.parse(p.options.body),
            {sid: "cap_20261011_120000", name: "新名"});
        p.resolve(200, {ok: true});
        await flush();
        assert.strictEqual(h.els.noteEl.textContent, "已改名: 新名");
        assert.deepStrictEqual(seen, ["cap_20261011_120000"]);
    }

    // ---------- 2) rename_session board-mode 403 降级文案 ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["renameInput", "renameOk"]);
        h.GT_OPS.bind(ctx);
        h.els.renameInput.value = "x";
        h.els.renameOk.click();
        const p = lastPending(h, "/api/rename", "POST");
        p.resolve(403, {ok: false, board_mode: true, error: "板端模式下 本地会话改名 被禁用"});
        await flush();
        assert.strictEqual(h.els.noteEl.textContent, "板端模式下会话不可改名（只允许标注）");
        assert.strictEqual(h.els.noteEl.style.color, "#f88");
    }

    // ---------- 3) set_alias draft ----------
    {
        const h = harness();
        const ctx = mkctx(h, []);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.set_alias("cap_x", "draft", null, "测试 draft 名");
        const p = lastPending(h, "/api/gt/alias", "POST");
        assert(p);
        assert.deepStrictEqual(JSON.parse(p.options.body),
            {sid: "cap_x", scope: "draft", name: "测试 draft 名"});
        p.resolve(200, {ok: true, name: "测试 draft 名"});
        await pr;
        assert.strictEqual(h.els.noteEl.textContent, "别名已存");
    }

    // ---------- 4) set_alias version ----------
    {
        const h = harness();
        const ctx = mkctx(h, []);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.set_alias("cap_x", "version", "V2", "交叉段");
        const p = lastPending(h, "/api/gt/alias", "POST");
        assert.deepStrictEqual(JSON.parse(p.options.body),
            {sid: "cap_x", scope: "version", name: "交叉段", version: "V2"});
        p.resolve(200, {ok: true, version: "V2", name: "交叉段"});
        await pr;
    }

    // ---------- 5) pull_from_board: poll → ok ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["pullBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.pull_from_board();
        const p1 = lastPending(h, "/api/gt/pull", "POST");
        assert(p1);
        p1.resolve(200, {ok: true});
        await flush();
        const p2 = lastPending(h, "/api/gt/pull_status");
        assert(p2, "轮询应发出");
        p2.resolve(200, {running: false, last_result: "ok",
                         detail: {pulled: [["cap_x/draft.json", "abc"]], skipped: [], conflicts: []}});
        for (const t of h.timeouts.splice(0)) t.cb();
        await pr;
        assert(ctx._info._pulled, "after_pull_ok 应被触发");
        assert.strictEqual(h.els.noteEl.textContent.startsWith("同步完成"), true);
    }

    // ---------- 6) pull_from_board: failed → error note ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["pullBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.pull_from_board();
        const p1 = lastPending(h, "/api/gt/pull", "POST");
        p1.resolve(200, {ok: true});
        await flush();
        const p2 = lastPending(h, "/api/gt/pull_status");
        p2.resolve(200, {running: false, last_result: "failed", last_error: "GT_V* 冲突"});
        await pr;
        assert.strictEqual(h.els.noteEl.style.color, "#f88");
        assert.strictEqual(h.els.noteEl.textContent.includes("GT_V* 冲突"), true);
    }

    // ---------- 7) toggle_record start ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["recBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.toggle_record();
        const p1 = lastPending(h, "/api/board/status");
        assert(p1);
        p1.resolve(200, {ros: "up", current: null});
        await flush();
        const p2 = lastPending(h, "/api/board/record/start", "POST");
        assert(p2, "未录制应走 start");
        p2.resolve(200, {ok: true});
        await flush();
        const p3 = lastPending(h, "/api/board/status");
        assert(p3);
        p3.resolve(200, {ros: "up", current: "cap_20261011_130000",
                         current_created_iso: "2026-10-11T00:00:00Z"});
        await pr;
        assert.strictEqual(h.els.recBtn.textContent, "■ 停止录制");
    }

    // ---------- 8) toggle_record stop ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["recBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.toggle_record();
        const p1 = lastPending(h, "/api/board/status");
        p1.resolve(200, {current: "cap_x", current_created_iso: null});
        await flush();
        const p2 = lastPending(h, "/api/board/record/stop", "POST");
        assert(p2);
        p2.resolve(200, {ok: true});
        await pr;
        assert.strictEqual(h.els.recBtn.textContent, "● 开始录制");
    }

    // ---------- 9) toggle_record board-mode 403 文案 ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["recBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.toggle_record().catch(() => {});
        const p1 = lastPending(h, "/api/board/status");
        p1.resolve(200, {current: null});
        await flush();
        const p2 = lastPending(h, "/api/board/record/start", "POST");
        p2.resolve(403, {ok: false, board_mode: true, error: "板端模式下 触发板端录制 被禁用"});
        await pr;
        assert.strictEqual(h.els.noteEl.textContent.includes("webui/human_capture"), true);
        assert.strictEqual(h.els.noteEl.style.color, "#f88");
    }

    // ---------- 10) refresh_board_status board down → 禁按钮 ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["recBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.refresh_board_status().catch(() => {});
        const p = lastPending(h, "/api/board/status");
        p.resolve(502, {ok: false, error: "连接板失败"});
        await pr;
        assert.strictEqual(h.els.recBtn.disabled, true);
        assert.strictEqual(h.els.noteEl.textContent.startsWith("板端离线"), true);
    }

    // ---------- 11) frozen_list event 委托（别名 ✎） ----------
    {
        const h = harness();
        const info = mkinfo();
        info.version_aliases = {V1: "老名"};
        let called = null;
        h.GT_OPS.bind({
            els: {noteEl: h.els.noteEl, frozenListEl: h.els.frozenListEl},
            get_session_info: () => info,
            reload_session: () => {},
            set_alias_on_version: v => { called = v; },
        });
        h.els.frozenListEl.listeners.click({target: {getAttribute: () => "V1"}});
        assert.strictEqual(called, "V1");
    }

    // ---------- 12) M3: poll 失败应 reject 而不是挂起 ----------
    {
        const h = harness();
        const ctx = mkctx(h, ["pullBtn"]);
        const ops = h.GT_OPS.bind(ctx);
        const pr = ops.pull_from_board();
        const p1 = lastPending(h, "/api/gt/pull", "POST");
        p1.resolve(200, {ok: true});
        await flush();
        // 第一次轮询 = 仍在跑 → 触发 setTimeout；我们 sweep timeout 让下一次轮询发出
        const p2 = lastPending(h, "/api/gt/pull_status");
        p2.resolve(200, {running: true, last_result: null, detail: null});
        /* 先 flush 等 promise chain 推进 → 500ms timeout 入 h.timeouts，再 sweep */
        await flush(); await flush();
        assert(h.timeouts.length >= 1, "running 分支应入 500ms timeout");
        for (const t of h.timeouts.splice(0)) t.cb();
        await flush(); await flush();
        const p3 = lastPending(h, "/api/gt/pull_status");
        assert(p3, "第二次轮询应发出（M3 fix 前会 hang，fix 后应可见）");
        const gone = {error: "连接已断"};
        p3.resolve(502, gone);
        // FIX-REVIEW-M3: 老 bug 是 hang promise。修后 pr 应 reject。
        let rejected = false, resolved = false;
        await pr.then(() => { resolved = true; }, () => { rejected = true; });
        assert(rejected && !resolved, "成功 500 应 reject,不 hang");
        assert(h.els.noteEl.textContent.length > 0, "note 应该有错误说明");
    }

    console.log("gt_workbench_ops.test.js: 12/12 PASS");
})().catch(e => { console.error(e); process.exit(1); });
