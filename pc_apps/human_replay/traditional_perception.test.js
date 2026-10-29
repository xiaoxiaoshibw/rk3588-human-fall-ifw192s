"use strict";
const assert=require('assert'),T=require('./traditional_perception'),F=require('./fresh_map_lib');
let passed=0;
function test(name,fn){fn();passed++;console.log('PASS',name);}
function person(low,shift=0){
    const a=[];
    for(let ix=0;ix<6;ix++)for(let iy=0;iy<5;iy++)for(let iz=0;iz<12;iz++){
        const x=3+shift+(ix-2.5)*.045,y=1+(iy-2)*.045,z=.2+iz*.14;
        a.push(low?3+shift+(z-.97)*.75:x,y,low?.34+(x-3-shift)*1.1:z,50);
    }
    return new Float32Array(a);
}
function setup(opts,refs=[],trusted=true){
    const bg=new Float32Array([8,8,1,50]);
    const engine=new T.Engine(opts),state=F.create_fresh_state(F.build_reference(refs.concat(Array.from({length:8},()=>bg)),{}),{ev_confirm_frames:3});
    let frame=0,t=0;
    return {engine,state,step(points,dt=.1){const bgn=trusted?Math.max(4000,points.length/4*10):20,all=new Float32Array(points.length+bgn*4);
        all.set(points);for(let i=0;i<bgn;i++)all.set(bg,points.length+i*4);
        t+=dt;F.fresh_update(state,all,t);return engine.tick(all,state,frame++,t);},
        now:()=>t,frame:()=>frame};
}
test('exact one-to-one assignment avoids greedy trap, and explicitly rejects overflow',()=>{
    assert.deepStrictEqual(T.assign([[.4,.5],[.1,Infinity]],1).pairs,[[0,1],[1,0]]);
    assert(T.assign(Array.from({length:9},()=>[.1]),1).overflow);
});
test('metric 3D splits vertically detached objects; source indices partition exactly',()=>{
    const p=new Float32Array([1,1,.2,1,1.02,1,.2,1,1,1,1.5,1,1.02,1,1.5,1]);
    const c=T.cluster(p,[0,1,2,3],{...T.DEFAULTS,min_points:1});
    assert.strictEqual(c.length,2);assert.deepStrictEqual(c.flatMap(x=>x.indices).sort(),[0,1,2,3]);
});
test('standing identity is confirmed, then low posture continues without creating another ID',()=>{
    const s=setup();let r;for(let i=0;i<15;i++)r=s.step(person(false));
    assert.strictEqual(r.tracks.filter(a=>a.confirmed).length,1);const id=r.tracks[0].id;
    for(let i=0;i<30;i++)r=s.step(person(true));
    assert.strictEqual(r.tracks[0].id,id);assert(r.claims.length>200);assert.strictEqual(r.tracks[0].posture,'FALL_CANDIDATE');
    assert.strictEqual(r.events.filter(e=>e.type==='FALL_CANDIDATE').length,1);
    assert(r.events.every(e=>e.confirmed===false));
    for(let i=0;i<15;i++)r=s.step(person(false));
    assert.strictEqual(r.tracks[0].id,id);assert.strictEqual(r.tracks[0].posture,'STANDING');
    assert(r.events.some(e=>e.type==='RECOVERED'));
});
test('initial lying object cannot create a human identity or a fall event',()=>{
    const s=setup();let r;for(let i=0;i<40;i++)r=s.step(person(true));
    assert.strictEqual(r.tracks.length,0);assert.strictEqual(r.events.length,0);
});
test('slow controlled descent is lying, not a fast fall candidate',()=>{
    const s=setup();let r;for(let i=0;i<15;i++)s.step(person(false));
    const a=person(false),b=person(true);
    for(let i=1;i<=80;i++)r=s.step(Float32Array.from(a,(v,k)=>v+(b[k]-v)*i/80));
    for(let i=0;i<30;i++)r=s.step(b);
    assert(r.claims.length>200);assert.strictEqual(r.tracks[0].posture,'LYING');
    assert(!r.events.some(e=>e.type==='FALL_CANDIDATE'));
    for(let i=0;i<15;i++)r=s.step(a);
    assert(r.events.some(e=>e.type==='POSTURE_RETURNED'));
    assert(!r.events.some(e=>e.type==='RECOVERED'));
});
test('short occlusion retains ID; >2s gap does not retain posture evidence',()=>{
    const s=setup();let r;for(let i=0;i<15;i++)r=s.step(person(false));const id=r.tracks[0].id;
    s.step(new Float32Array(),.3);r=s.step(person(false),.1);assert.strictEqual(r.tracks[0].id,id);
    r=s.step(person(true),3);assert.strictEqual(r.claims.length,0);assert.strictEqual(r.events.length,0);
});
test('duplicate frame is idempotent, reverse time rejected, reset clears identity/events',()=>{
    const s=setup();let r;for(let i=0;i<12;i++)r=s.step(person(false));
    const hits=r.tracks[0].hits;
    assert.strictEqual(s.engine.tick(person(false),s.state,s.frame()-1,s.now()),r);
    assert.strictEqual(r.tracks[0].hits,hits);
    assert.throws(()=>s.engine.tick(person(false),s.state,s.frame(),s.now()-1));
    s.engine.reset();assert.strictEqual(s.engine.tracks.length,0);assert.strictEqual(s.engine.events.length,0);
});
test('squat/table height without prior identity never passes birth gate',()=>{
    const s=setup();let r;const p=person(false);for(let i=2;i<p.length;i+=4)p[i]*=.6;
    for(let i=0;i<30;i++)r=s.step(p);assert.strictEqual(r.claims.length,0);
    assert(r.observations.some(o=>o.reasons.includes('low_top')));
});
function join(...a){return Float32Array.from(a.flatMap(p=>Array.from(p)));}
test('many rejected noise clusters do not turn off a genuine standing identity',()=>{
    const s=setup();let r;const p=join(person(false),...Array.from({length:10},(_,i)=>person(true,(i+1)*2)));
    for(let i=0;i<16;i++)r=s.step(p);
    assert(r.observations.length>8);assert(!r.overflow);assert.strictEqual(r.eligible_observations,1);
    assert(r.claims.length>200);assert.strictEqual(r.tracks.filter(a=>a.confirmed).length,1);
});
test('eligible overload freezes births but sustains a unique existing identity',()=>{
    const s=setup();let r;for(let i=0;i<16;i++)r=s.step(person(false));const id=r.tracks[0].id;
    const p=join(...Array.from({length:10},(_,i)=>person(false,i*2)));
    for(let i=0;i<8;i++)r=s.step(p);
    assert(r.overflow);assert(r.eligible_observations>8);assert.strictEqual(r.tracks.length,1);
    assert.strictEqual(r.tracks[0].id,id);assert(r.claims.length>200);
});
test('a split into equally near observations remains unknown with an explicit reason',()=>{
    const s=setup();let r;for(let i=0;i<16;i++)r=s.step(person(false));
    const p=join(person(false,-.4),person(false,.4));
    for(let i=0;i<4;i++)r=s.step(p);
    assert.strictEqual(r.claims.length,0);assert(r.branches.some(b=>b.reason==='ambiguous_track'));
});
test('two identities cannot both claim a merged equidistant observation',()=>{
    const s=setup();let r;for(let i=0;i<16;i++)r=s.step(join(person(false),person(false,.9)));
    assert.strictEqual(r.tracks.filter(a=>a.confirmed).length,2);
    for(let i=0;i<4;i++)r=s.step(person(false,.45));
    assert.strictEqual(r.claims.length,0);assert(r.branches.some(b=>b.reason==='ambiguous_observation'));
});
test('far or expired low objects cannot inherit a standing identity',()=>{
    for(const [shift,dt] of [[1.5,.1],[0,1.2]]){
        const s=setup();let r;for(let i=0;i<16;i++)s.step(person(false));
        for(let i=0;i<8;i++)r=s.step(person(true,shift),i===0?dt:.1);
        assert.strictEqual(r.claims.length,0);assert.strictEqual(r.events.length,0);
    }
});
test('a reference-supported low object is not evidence for identity continuation',()=>{
    const low=person(true);for(let i=1;i<low.length;i+=4)low[i]+=.45;
    const s=setup({},Array.from({length:8},()=>low));let r;
    for(let i=0;i<16;i++)r=s.step(person(false));assert(r.tracks.some(a=>a.confirmed));
    for(let i=0;i<8;i++)r=s.step(low);
    assert.strictEqual(r.claims.length,0);assert.strictEqual(r.events.length,0);
});
test('a brief squat followed by standing cannot seed a later slow descent event',()=>{
    const s=setup();let r;const a=person(false),b=person(true);
    for(let i=0;i<16;i++)s.step(a);for(let i=0;i<4;i++)s.step(b);for(let i=0;i<8;i++)s.step(a);
    for(let i=1;i<=40;i++)r=s.step(Float32Array.from(a,(v,k)=>v+(b[k]-v)*i/40));
    for(let i=0;i<20;i++)r=s.step(b);
    assert(!r.events.some(e=>e.type==='FALL_CANDIDATE'));
});
test('poor reference: static human-shaped object stays unverified, moving person can be admitted',()=>{
    const s=setup({},[],false);let r;for(let i=0;i<30;i++)r=s.step(person(false));
    assert.strictEqual(r.claims.length,0);assert(r.tracks.length>0);assert(!r.tracks[0].confirmed);
    assert(r.branches.some(b=>b.reason==='awaiting_independent_motion'));
    for(let i=1;i<=12;i++)r=s.step(person(false,i*.01));
    assert(r.claims.length>200);assert(r.tracks[0].confirmed);assert(!r.overflow);
});
test('one impossible vertical jump cannot claim the floor or create a recovery event',()=>{
    const s=setup();let r;for(let i=0;i<16;i++)s.step(person(false));
    const floor=person(true);for(let i=2;i<floor.length;i+=4)floor[i]-=.12;
    // Existing fresh evidence must already be confirmed, as for a persistent floor artifact.
    for(let i=0;i<3;i++)F.fresh_update(s.state,floor,s.now());
    r=s.step(floor);
    assert.strictEqual(r.claims.length,0);
    assert(r.observations.some(o=>o.association_rejections.some(x=>x.reason==='vertical_discontinuity')));
    for(let i=0;i<8;i++)r=s.step(person(false));assert.strictEqual(r.events.length,0);
});
test('equal timestamps cannot accelerate seconds-based identity confirmation',()=>{
    const s=setup();let r;for(let i=0;i<30;i++)r=s.step(person(false),0);
    assert(r.tracks.every(a=>!a.confirmed));assert.strictEqual(r.events.length,0);
    for(let i=0;i<6;i++)r=s.step(person(false),.1);
    assert(r.tracks.some(a=>a.confirmed));
});
test('nearby broad low furniture cannot inherit an identity despite descent and novelty',()=>{
    const a=[];for(let x=0;x<15;x++)for(let y=0;y<15;y++)for(let z=0;z<3;z++)a.push(3+(x-7)*.075,1+(y-7)*.075,.2+z*.16,50);
    for(const width of [.45,1]){
        const s=setup({low_minor_width_m:width});let r;for(let i=0;i<16;i++)s.step(person(false));
        for(let i=0;i<8;i++)r=s.step(new Float32Array(a));
        assert(r.observations.some(o=>o.f.ok&&o.f.height_m>=.2&&o.f.radius_m<.75&&o.evidence_n>=60));
        if(width===.45){assert.strictEqual(r.claims.length,0);assert.strictEqual(r.events.length,0);}
        else assert(r.claims.length>60,'the identical scene must be admitted without the transverse width limit');
    }
});
function rising(height){
    const a=[];
    for(let x=0;x<10;x++)for(let y=0;y<10;y++)for(let z=0;z<24;z++)
        a.push(3+(x-4.5)*.04,1+(y-4.5)*.035,.1+z*height/23,50);
    return new Float32Array(a);
}
test('low-to-standing window has separate causal claims and confirmed offline backfill',()=>{
    const s=setup(),rows=[];
    for(let i=0;i<8;i++)rows.push(s.step(rising(.7)));
    assert(rows.some(r=>r.tracks.some(a=>a.provisional_birth)));assert(rows.every(r=>r.claims.length===0));
    for(let i=0;i<4;i++)rows.push(s.step(rising(1.4)));
    const promoted=rows.find(r=>r.backfill.length);assert(promoted);assert(promoted.claims.length>800);
    const birth=rows.find(r=>r.tracks.length).frame;
    assert.strictEqual(promoted.backfill[0].frame,birth);
    assert(promoted.backfill.length>0);
    assert(rows.filter(r=>r.frame<promoted.frame).every(r=>r.claims.length===0));
    assert.strictEqual(new Set(promoted.backfill.map(b=>b.track_id)).size,1);
});
test('narrow stationary stool never confirms even with trusted reference',()=>{
    const s=setup({cluster:'xy'});let r;
    const stool=Float32Array.from(Array.from({length:70},(_,i)=>[3+(i%7-3)*.055,1,.12+(i%2)*.57,50]).flat());
    for(let i=0;i<30;i++)r=s.step(stool);
    assert(r.observations.some(o=>o.f.ok&&o.f.n===70),'stool must reach admission as an actual cluster');
    assert.strictEqual(r.claims.length,0);assert(!r.tracks.some(a=>a.confirmed));
    // A dense stationary low structure must also stay provisional, even when n passes.
    for(let i=0;i<30;i++)r=s.step(rising(.7));
    assert(r.tracks.some(a=>a.provisional_birth));assert(!r.tracks.some(a=>a.confirmed));
});
test('111738-style centroid jitter is not direct motion; the feature can be disabled',()=>{
    for(const mode of [0,2,3]){
        const s=setup({xy_motion_mode:mode},[],false);let r;
        for(let i=0;i<40;i++)r=s.step(person(false,(i%2)*.09));
        assert(r.tracks.length);assert(!r.tracks.some(a=>a.confirmed));assert.strictEqual(r.claims.length,0);
    }
});
test('zero-XY standing rise confirms by shape alone under poor reference',()=>{
    const s=setup({xy_motion_mode:0},[],false);let r;
    for(let i=0;i<8;i++)r=s.step(rising(.7));
    for(let i=0;i<4;i++)r=s.step(rising(1.4));
    const a=r.tracks.find(a=>a.confirmed);assert(a&&a.shape_motion);assert(!a.reference_trusted);
    assert(a.motion_m<1e-5);assert(r.claims.length>800);
});
test('multiwindow motion works with irregular timestamps over a full half-second',()=>{
    const s=setup({xy_motion_mode:3},[],false);let r;
    for(let i=0;i<30;i++)r=s.step(person(false,i*.012),.11);
    assert(r.tracks.some(a=>a.confirmed));assert(r.claims.length>200);
});
test('a structural provisional birth can rise into a sparse strict standing observation',()=>{
    const s=setup({xy_motion_mode:0},[],false);let r;
    for(let i=0;i<8;i++)r=s.step(rising(.7));
    assert(r.tracks.some(a=>a.provisional_birth));
    for(let i=0;i<5;i++)r=s.step(person(false));
    assert(r.observations.some(o=>o.birth&&!o.structure));
    assert(r.tracks.some(a=>a.confirmed&&a.shape_motion));assert(r.claims.length>200);
});
test('a long-lived provisional structure does not prevent a nearby standing entrant from confirming',()=>{
    const s=setup({xy_motion_mode:0},[],false);let r;
    for(let i=0;i<28;i++)r=s.step(rising(.7));
    assert(!r.tracks.some(a=>a.confirmed));
    for(let i=0;i<5;i++)r=s.step(person(false,.35));
    assert(r.observations.some(o=>o.birth&&!o.structure));
    assert.strictEqual(r.tracks.filter(a=>a.confirmed).length,1);assert(r.claims.length>200);
});
test('provisional overload explicitly freezes births while sustaining an existing confirmed identity',()=>{
    const crowded=join(person(false),...Array.from({length:9},(_,i)=>{
        const p=rising(.7);for(let k=0;k<p.length;k+=4)p[k]+=(i+1)*2;return p;
    }));
    const empty=setup({},[],false);let r;
    for(let i=0;i<4;i++)r=empty.step(crowded);
    assert(r.overflow&&r.eligible_observations>8);assert.strictEqual(r.tracks.length,0);
    assert.strictEqual(r.claims.length,0,'over-budget births remain explicitly unknown');
    const live=setup();for(let i=0;i<15;i++)r=live.step(person(false));const id=r.tracks[0].id;
    for(let i=0;i<4;i++)r=live.step(crowded);
    assert(r.overflow&&r.eligible_observations>8);assert.strictEqual(r.tracks.length,1);
    assert.strictEqual(r.tracks[0].id,id);assert(r.claims.length>200);
});
console.log(passed+' tests passed');
