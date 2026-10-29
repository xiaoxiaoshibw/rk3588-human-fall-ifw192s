import { describe, expect, it } from 'vitest';
import { makeRangeAdapter } from '../src/algorithm/rangeResult.ts';
import type { RangeResult } from '../src/algorithm/rangeResult.ts';
import { AlgorithmHost } from '../src/algorithm/host.ts';
import { emptyDoc } from '../src/domain/types.ts';
import { mkPerson, UndoHistory } from '../src/annotation/ops.ts';

const packet: RangeResult = {
  manifest: { sessionId:'s', coordinateFrame:'sensor-IFW192S-raw', units:'m', confirmedEnabled:false,
    contentSha256:'a'.repeat(64),sourceFrameCount:4,algorithm:{id:'range-rules',version:'1.0.0',configSha256:'b'.repeat(64)} },
  frame: {frameIndex:1,stampSec:1.1,state:'suspected',reasons:[],trackId:'T1',generation:0,measured:true,
    sourceRows:[0,1],heightMedianM:.3,box:{x:1,y:2,w:1,h:.5,zMin:.1,zMax:.6}},
  intervals:[{startFrame:1,endFrame:2,label:'suspected_fall'}],
};
function context() {
  const doc=emptyDoc('s',4);doc.persons=[mkPerson('P1')];
  return { sessionId:'s',frameIndex:1,generation:1,doc,
    frame:{sessionId:'s',frameIndex:1,stampSec:1.1,count:2,x:new Float32Array(2),y:new Float32Array(2),z:new Float32Array(2),intensity:null,generation:1} };
}
describe('source-bound range adapter',()=>{
  it('keeps sustained low posture an action and never relabels it as a fall',async()=>{
    const out=await makeRangeAdapter({...packet,intervals:[{startFrame:1,endFrame:2,label:'sustained_low_posture'}]}).run(context());
    expect(out[1]).toMatchObject({kind:'interval',kindOf:'action',label:'sustained_low_posture'});
    expect(out[1]!.reason).toContain('不是跌倒事件');
  });
  it('produces separate measured-box and suspected-interval suggestions with frozen config',async()=>{
    const a=makeRangeAdapter(packet);const out=await a.run(context());
    expect(a.paramsHash).toBe('b'.repeat(64));expect(out.map(s=>s.kind)).toEqual(['box','interval']);
    expect(out[1]).toMatchObject({label:'suspected_fall',startFrame:1,endFrame:2});
  });
  it('rejects a different source timestamp or frame and out-of-bounds rows',async()=>{
    const a=makeRangeAdapter(packet);const ctx=context();ctx.frame.stampSec=2;
    await expect(a.run(ctx)).rejects.toThrow(/源帧/);
    await expect(makeRangeAdapter({...packet,frame:{...packet.frame,sourceRows:[0,3]}}).run(context())).rejects.toThrow(/越界/);
  });
  it('does not invent a measured box during missing observations',async()=>{
    const out=await makeRangeAdapter({...packet,frame:{...packet.frame,measured:false,sourceRows:[],box:null},intervals:[]}).run(context());
    expect(out).toEqual([]);
  });
  it('adopts an interval with provenance in one undoable operation; disabled adoption is refused',async()=>{
    let enabled=true;
    const host=new AlgorithmHost(makeRangeAdapter(packet),{enabled:()=>enabled,currentGeneration:()=>1,commitOp:()=>{}});
    const ctx=context();const suggestions=await host.run(ctx);
    const doc={...ctx.doc,suggestions};const s=suggestions[1]!;
    const adopted=host.adopt(doc,s.suggestionId,'P1')!;
    const history=new UndoHistory();
    const next=history.commit(doc,{t:'composite',label:'adopt',ops:adopted.ops}).doc;
    expect(next.intervals[0]!.origin).toMatchObject({kind:'adopted',algorithm:'range-rules@1.0.0'});
    expect(history.undo(next)).toEqual(doc);
    enabled=false;expect(host.adopt(doc,s.suggestionId,'P1')).toBeNull();expect(host.reject(doc,s.suggestionId)).toBeNull();
  });
  it('disabling a running algorithm discards its result',async()=>{
    let enabled=true;let release!:()=>void;
    const a=makeRangeAdapter(packet);const run=a.run;
    a.run=async ctx=>{await new Promise<void>(r=>{release=r});return run(ctx)};
    const host=new AlgorithmHost(a,{enabled:()=>enabled,currentGeneration:()=>1,commitOp:()=>{}});
    const pending=host.run(context());enabled=false;release();expect(await pending).toEqual([]);
  });
});
