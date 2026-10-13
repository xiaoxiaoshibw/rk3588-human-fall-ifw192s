'use strict';
const VERSION='hfus-strict-v1';
const ACCEPTED=new Set(['HUMAN_CANDIDATE','CONFIRMED_HUMAN']);
function members(o){const a=Array.from(o.raw_indices||o.indices||o.point_indices||[]);if(new Set(a).size!==a.length||a.some(i=>!Number.isSafeInteger(i)||i<0))throw Error('invalid/duplicate raw member');return a;}
function overlap(c,g){const C=members(c),G=new Set(members(g)),n=C.filter(i=>G.has(i)).length;return {intersection:n,coverage:G.size?n/G.size:0,purity:C.length?n/C.length:0};}
function assignment(gt,pred,valid){
 let best={pairs:[],cost:Infinity};
 function visit(i,used,pairs,cost){if(i===gt.length){if(pairs.length>best.pairs.length||pairs.length===best.pairs.length&&cost<best.cost)best={pairs:pairs.slice(),cost};return;}visit(i+1,used,pairs,cost);for(let j=0;j<pred.length;j++){const q=valid(gt[i],pred[j]);if(!used.has(j)&&q!==null){used.add(j);pairs.push([i,j]);visit(i+1,used,pairs,cost+q);pairs.pop();used.delete(j);}}}
 // ponytail: exact search for this protocol's <=2 humans; replace only if object scale grows.
 visit(0,new Set(),[],0);return best.pairs;
}
function count(gt,pred,exhaustive,negative=[]){
 const pairs=assignment(gt,pred,(g,c)=>{const o=overlap(c,g);return o.coverage>=.5&&o.purity>=.8?1-o.coverage:null;}),used=new Set(pairs.map(p=>p[1]));
 const unmatched=pred.map((c,j)=>({c,j})).filter(o=>!used.has(o.j)),known=unmatched.filter(o=>exhaustive||negative.some(g=>overlap(o.c,g).purity>=.8));
 return {tp:pairs.length,fn:gt.length-pairs.length,fp:known.length,unmatched_unknown:unmatched.length-known.length,pairs,fn_ids:gt.filter((_,i)=>!pairs.some(p=>p[0]===i)).map(g=>g.id),fp_ids:known.map(o=>o.c.id||o.c.candidate_id),unknown_ids:unmatched.filter(o=>!known.includes(o)).map(o=>o.c.id||o.c.candidate_id)};
}
function evaluateFrame({gt=null,candidates=[],raw_components=[],tracks=[],qualification='UNKNOWN',exhaustive=false}){
 const persons=(gt||[]).filter(g=>g.class_name==='PERSON'),neg=(gt||[]).filter(g=>g.class_name==='FURNITURE'&&g.source==='human'),accepted=candidates.filter(c=>c.accepted===true||ACCEPTED.has(c.decision||c.classifier_decision));
 const observed=[],coast=[];
 for(const t of tracks.filter(t=>t.human_confirmed)){const supports=accepted.filter(c=>c.track_id===t.id&&(c.track_segment===undefined||t.track_segment===undefined||c.track_segment===t.track_segment)&&members(c).length>0);if(t.lost===0&&supports.length){const ids=[...new Set(supports.flatMap(members))];observed.push({id:t.id,raw_indices:ids});}else coast.push(t.id);}
 if(gt===null||qualification==='UNKNOWN'||qualification==='INVALID_BINDING')return {version:VERSION,status:qualification,proposal:null,accepted:null,observed_confirmed:null,coast_ids:coast,gt_persons:0};
 return {version:VERSION,status:qualification,gt_persons:persons.length,proposal:count(persons,raw_components.filter(c=>c.hard_gate_pass!==false),exhaustive,neg),accepted:count(persons,accepted,exhaustive,neg),observed_confirmed:count(persons,observed,exhaustive,neg),coast_ids:coast};
}
module.exports={VERSION,members,overlap,assignment,count,evaluateFrame};
