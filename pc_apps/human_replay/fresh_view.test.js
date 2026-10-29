"use strict";
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('fresh_view.js', 'utf8');
function fixture(search, failure) {
    const elements = {};
    ['highlightSwitch','freshHud','detectBtn','lutSel','freshControls','perceptionDetails','perceptionMode','freshReference'].forEach(id => elements[id] = {
        value:'',options:[{value:'cap_20261014_221808'},{value:'cap_20261015_111738'}],appendChild(o){this.options.push(o);},
        style:{}, hidden:id === 'freshHud', addEventListener(type, fn) { this[type] = fn; }
    });
    const calls = { frames:0, resets:0, seeks:[], refs:0, fetches:[], gen:0 };
    const old = {};
    let release;
    const reference = new Promise((resolve,reject) => release = () => failure ? reject(Error('missing reference')) : resolve(2));
    const c = { URL, URLSearchParams, Promise,
        location:{search,href:'http://127.0.0.1:8901/'+search,assign(url){calls.url=url;}},
        document:{getElementById:id=>elements[id],createElement:()=>({})},
        HUMAN_DETECT_OVERLAY:old,
        FRESH_SET_REF:files=>{calls.refs++;return reference;},
        FRESH_OVERLAY:{set_mode(mode){calls.mode=mode;},on_frame(){calls.frames++;},reset(){calls.resets++;},
            notify_session(){return ++calls.gen;},set_transform(r,t){calls.transform=[r,t];}},
        human_replay_lib:{DEFAULT_LEVEL_TRANSFORM:{R:[1,0,0,0,1,0,0,0,1],t:[0,0,0]}},
        fetch(url){calls.fetches.push(url);throw Error('unexpected fetch');},
        replay_internal:{S:{meta:{session_id:'cap_new'},geo:{},tracker_last_idx:55},set_idx:i=>calls.seeks.push(i)}
    };
    c.window=c;vm.createContext(c);vm.runInContext(source,c);
    return {c, elements, calls, old, release};
}
(async () => {
    let f=fixture('?sid=cap_old'); await f.c.FRESH_VIEW_READY;
    assert.strictEqual(f.c.HUMAN_DETECT_OVERLAY,f.old);
    assert.strictEqual(f.calls.refs,0);assert.strictEqual(f.elements.highlightSwitch.checked,false);
    f.elements.highlightSwitch.checked=true;f.elements.highlightSwitch.change();
    let u=new URL(f.calls.url);assert.strictEqual(u.searchParams.get('sid'),'cap_new');
    assert.strictEqual(u.searchParams.get('highlight'),'1');

    f=fixture('?highlight=1&sid=cap_old&freeze=60');
    assert(f.elements.detectBtn.hidden && f.elements.detectBtn.disabled);
    assert(f.elements.lutSel.disabled);
    f.c.HUMAN_DETECT_OVERLAY.on_frame({});assert.strictEqual(f.calls.frames,0);
    f.release();assert.strictEqual(await f.c.FRESH_VIEW_READY,true);
    assert.strictEqual(f.calls.mode,'xy');assert(!f.elements.freshControls.hidden);
    f.c.HUMAN_DETECT_OVERLAY.on_frame({});assert.strictEqual(f.calls.frames,1);
    assert.strictEqual(f.calls.seeks[0],0);assert.strictEqual(f.c.replay_internal.S.tracker_last_idx,-1);
    assert.strictEqual(f.c.HUMAN_DETECT_OVERLAY.notify_session(),1);
    assert.strictEqual(f.c.HUMAN_DETECT_OVERLAY.notify_session(),2);
    f.elements.highlightSwitch.checked=false;f.elements.highlightSwitch.change();
    u=new URL(f.calls.url);assert.strictEqual(u.searchParams.get('highlight'),'0');
    assert.strictEqual(u.searchParams.get('sid'),'cap_new');assert(!u.searchParams.has('freeze'));

    f=fixture('?highlight=1',true);f.release();assert.strictEqual(await f.c.FRESH_VIEW_READY,false);
    f.c.HUMAN_DETECT_OVERLAY.on_frame({});assert.strictEqual(f.calls.frames,0);
    assert(f.elements.freshHud.textContent.includes('未启用'));assert(f.elements.freshHud.style.color);
    f=fixture('?highlight=1&ref=../../bad');assert.strictEqual(await f.c.FRESH_VIEW_READY,false);
    assert.strictEqual(f.calls.refs,0);
    f=fixture('?highlight=1&perception=xy&ref=cap_other');f.release();await f.c.FRESH_VIEW_READY;
    assert.strictEqual(f.calls.mode,'xy');assert.strictEqual(f.elements.freshReference.value,'cap_other');
    f.elements.perceptionMode.value='legacy';f.elements.perceptionMode.change();
    u=new URL(f.calls.url);assert.strictEqual(u.searchParams.get('perception'),'legacy');assert.strictEqual(u.searchParams.get('ref'),'cap_other');
    f=fixture('?highlight=1&perception=typo');assert.strictEqual(await f.c.FRESH_VIEW_READY,false);
    assert.strictEqual(f.elements.perceptionMode.value,'xy');assert.strictEqual(f.calls.refs,0);
    f=fixture('?highlight=1');f.release();await f.c.FRESH_VIEW_READY;
    f.c.replay_internal.S.load_source='manual';f.elements.highlightSwitch.checked=false;f.elements.highlightSwitch.change();
    assert(!f.calls.url);assert(f.elements.highlightSwitch.checked);assert(f.elements.freshHud.textContent.includes('本地目录'));

    const html=fs.readFileSync('index.html','utf8');
    assert(html.indexOf('src="fresh_overlay.js"')<html.indexOf('src="detect_overlay.js"'));
    assert(html.indexOf('src="detect_overlay.js"')<html.indexOf('src="fresh_view.js"'));
    assert(html.indexOf('src="fresh_view.js"')<html.indexOf('src="replay.js"'));
    assert(html.includes('Promise.resolve(window.FRESH_VIEW_READY)'));
    console.log('PASS: default/off/on, preserve session, restart history, detector exclusion, pending/error/invalid reference, generation and script order');

    // Same reference must move with a new session calibration, never reuse old-frame background.
    const c={Float32Array,Set,Map,performance,console,
        human_pipe_lib:require('./human_pipe_lib.js'),fresh_map_lib:require('./fresh_map_lib.js')};
    vm.createContext(c);vm.runInContext(fs.readFileSync('fresh_overlay.js','utf8'),c);
    const O=c.FRESH_OVERLAY,I=c.FRESH_INTERNAL,identity=[1,0,0,0,1,0,0,0,1];
    O.set_transform(identity,[0,0,0]);
    const meta={session_id:'ref',point_stride_bytes:28,total_points:1,frames:[{offset_points:0,count_points:1,bag_time_sec:0}]};
    const raw=new Float32Array([1,1,.5,10,0,0,0]);
    const files=[{name:'meta.json',text:()=>Promise.resolve(JSON.stringify(meta))},
        {name:'points.bin',arrayBuffer:()=>Promise.resolve(raw.buffer)}];
    await c.FRESH_SET_REF(files);
    function frame(x) {
        const color=new Float32Array(3);O.attach_color(color);O.set_leveled_in_s(true);
        O.on_frame({meta:{...meta,leveling:{}},idx:0,buf_f32:new Float32Array([x,1,.5,10,0,0,0]),geo:{attributes:{color:{}}}});
    }
    frame(1);assert(I.state().ref.has(c.human_pipe_lib.key_bg(1,1,.5)));
    O.set_transform(identity,[2,0,0]);assert.strictEqual(I.state(),null);
    frame(3);assert(I.state().ref.has(c.human_pipe_lib.key_bg(3,1,.5)));
    assert(!I.state().ref.has(c.human_pipe_lib.key_bg(1,1,.5)));
    assert.throws(()=>O.set_transform([NaN],[0,0,0]));
    await assert.rejects(()=>c.FRESH_SET_REF([{name:'meta.json',text:()=>Promise.resolve(JSON.stringify({...meta,leveling:{}}))},files[1]]));
    await assert.rejects(()=>c.FRESH_SET_REF([files[0],{name:'points.bin',arrayBuffer:()=>Promise.resolve(new ArrayBuffer(4))}]));
    console.log('PASS: calibration rebuild and state reset; malformed/preleveled reference rejected');
})().catch(e=>{console.error(e);process.exitCode=1;});
