'use strict';
// Exercise the actual QML command functions with a controlled timer and bridge.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(__dirname + '/native/Main.qml', 'utf8');
const names = ['send', 'cancelSeekPreview', 'queueSeekPreview', 'flushSeekPreview'];
const functions = names.map(name => {
    const found = source.match(new RegExp('    function ' + name + '\\([^]*?\\n    }'));
    assert.ok(found, name);
    return found[0];
}).join('\n');
const sent = [];
const context = {
    pendingSeekIndex: -1, pendingSeekContext: '', seekContext: 'session-A',
    snap: {mode: 'replay'},
    viewer: {command: command => sent.push(JSON.parse(JSON.stringify(command)))},
    seekPreviewTimer: {running: false, start() { this.running = true; }, stop() { this.running = false; }}
};
context.root = context;
vm.createContext(context); vm.runInContext(functions, context);
for (let i = 0; i < 500; ++i) context.queueSeekPreview(i);
assert.equal(sent.length, 0);
context.flushSeekPreview();
assert.deepEqual(sent, [{op: 'seek', index: 499}]);
context.flushSeekPreview(); assert.equal(sent.length, 1);
context.queueSeekPreview(200); context.send({op: 'step', delta: 1}); context.flushSeekPreview();
assert.deepEqual(sent.at(-1), {op: 'step', delta: 1}); assert.equal(sent.length, 2);
context.queueSeekPreview(300); context.seekContext = 'session-B'; context.flushSeekPreview();
assert.equal(sent.length, 2);
context.queueSeekPreview(400); context.snap.mode = 'live'; context.flushSeekPreview();
context.queueSeekPreview(450); assert.equal(context.pendingSeekIndex, -1);
assert.equal(sent.length, 2);
context.snap.mode = 'replay';
context.queueSeekPreview(123.7); context.flushSeekPreview();
assert.deepEqual(sent.at(-1), {op: 'seek', index: 124});
console.log(JSON.stringify({status: 'PASS', burstInput: 500, burstCommands: 1,
    cases: ['latest_position', 'release_flush_once', 'ordered_command_cancel', 'session_change', 'live_mode', 'rounding']}));
