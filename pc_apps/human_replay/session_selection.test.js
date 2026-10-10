"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const picker = require("./session_selection.js");
const old = "cap_20261002_223757", latest = "cap_20261009_181716";
const rows = [{sid:old,frames:2,local:true},{sid:latest,frames:3,local:true}];
let tests=0;
function test(name, fn) { fn(); console.log("PASS "+name); tests++; }
test("S01 default latest with reversed/shuffled input", () => {
    for (const list of [rows,rows.slice().reverse()]) assert.equal(picker.choose(list,null).sid,latest);
});
test("S02 valid explicit old sid respected", () => assert.equal(picker.choose(rows,old).sid,old));
test("S03 unavailable/invalid/empty explicit sid visible safe fallback", () => {
    for(const sid of ["cap_20261010_235959","../x","", "<img onerror=x>"]) {
        const p=picker.choose(rows,sid); assert.equal(p.sid,latest); assert.match(p.message,/回退/);
    }
});
test("S04 incomplete/remote/error/empty rows excluded", () => {
    const list=rows.concat([{sid:"cap_20261010_000000",frames:0},
        {sid:"cap_20261010_010000",frames:1,local:false},
        {sid:"cap_20261010_020000",frames:1,error:"bad meta"}]);
    assert.equal(picker.choose(list,null).sid,latest);
});
test("S05 empty list finishes with clear notice", () => {
    const p=picker.choose([],null); assert.equal(p.sid,""); assert.match(p.message,/没有本地完整/);
});
test("S06 deterministic sorting and dedup independent of alias/created_iso", () => {
    const list=rows.concat([{...rows[1],name:"aaa",created_iso:"1900"}]);
    assert.deepEqual(picker.choose(list,null).list.map(s=>s.sid),[latest,old]);
});
test("S12 legal local clip suffix respected and unsafe suffix rejected", () => {
    const sid="cap_20261002_165321_clip_1989287-1989294";
    assert.equal(picker.choose(rows.concat([{sid,frames:2,local:true}]),sid).sid,sid);
    for(const bad of [sid+"/file",sid+"..",sid+" ",sid+"_".repeat(100)]) {
        assert.equal(picker.choose(rows,bad).sid,latest);
        assert.match(picker.choose(rows,bad).message,/回退/);
    }
});

async function integration(query, response, failLoad=false, failHTTP=false) {
    let listener; const loads=[];
    const select={disabled:false,innerHTML:"",value:"",options:[],addEventListener(t,fn){listener=fn;},appendChild(o){this.options.push(o);}};
    const notice={textContent:""};
    const ctx={URLSearchParams,Set,Promise,location:{search:query},document:{createElement(){return {}; }},
        fetch:async()=>({ok:!failHTTP,status:503,json:async()=>response})};
    vm.createContext(ctx); vm.runInContext(fs.readFileSync("session_selection.js","utf8"),ctx);
    await ctx.SESSION_SELECTION.start({select,notice,url:"/api/sessions?scope=local",load:sid=>{loads.push(sid);if(failLoad)throw Error("bin HTTP 404");}});
    return {select,notice,loads,listener};
}
(async()=>{
    for (const [query,sid] of [["",latest],["?sid="+old,old],["?sid=../x",latest]]) {
        const got=await integration(query,{sessions:rows});
        assert.deepEqual(got.loads,[sid]); assert.equal(got.select.value,sid);
        if(query.includes("../")) assert.match(got.notice.textContent,/回退/);
    }
    console.log("PASS S07 async startup default / explicit / fallback");tests++;
    const empty=await integration("",{sessions:[]});assert.equal(empty.select.disabled,true);assert.deepEqual(empty.loads,[]);
    const failed=await integration("",{sessions:rows},false,true);assert.match(failed.notice.textContent,/发现失败/);assert.deepEqual(failed.loads,[]);
    const malformed=await integration("",{});assert.match(malformed.notice.textContent,/格式错误/);
    console.log("PASS S08 empty / HTTP error / malformed terminate");tests++;
    const race=await integration("",{sessions:rows},true);assert.match(race.notice.textContent,/载入失败/);
    console.log("PASS S09 stale files at load fail visibly, no silent replacement");tests++;
    for(const page of ["human_detect.html","human_track.html"]) {
        const html=fs.readFileSync(page,"utf8");assert.match(html,/id="sessionNotice"/);assert.match(html,/session_selection.js/);
        assert.doesNotMatch(html,/\?sid=cap_/);
    }
    assert.match(fs.readFileSync("human_track.html","utf8"),/url: "\/api\/sessions\?scope=local"/);
    assert.match(fs.readFileSync("human_detect.js","utf8"),/url: "\/api\/leveling\/sessions"/);
    assert.doesNotMatch(fs.readFileSync("human_detect.js","utf8"),/els\.session\.addEventListener\("change"/);
    assert.doesNotMatch(fs.readFileSync("human_track.html","utf8"),/sessSel\.addEventListener\("change"/);
    console.log("PASS S10 both page integrations and query-free entrypoints");tests++;
    const manual=await integration("",{sessions:rows});
    manual.select.value=old;await manual.listener();
    assert.deepEqual(manual.loads,[latest,old]);
    console.log("PASS S11 manual switch loads exactly once; no legacy duplicate listener");tests++;
    console.log(tests+" tests passed");
})().catch(e=>{console.error(e);process.exitCode=1;});
