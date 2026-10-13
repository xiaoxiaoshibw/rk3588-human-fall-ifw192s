'use strict';
// Independent static geometry proposal branch. Frozen constants; no GT input.
const S=require('./core/schema');
function addStatic(eng){const original=eng._fusion_a_chain;eng._fusion_a_chain=function(fc,lv,diag){const out=original.call(this,fc,lv,diag),start=performance.now(),seed=[],cells=new Map();for(let i=0;i<lv.length/4;i++){const x=lv[i*4],y=lv[i*4+1],z=lv[i*4+2];if(![x,y,z].every(Number.isFinite)||z<1||z>2.2||x*x+y*y>64)continue;const key=Math.floor(x/.2)+','+Math.floor(y/.2);if(!cells.has(key))cells.set(key,[]);cells.get(key).push(i);}
 const visited=new Set(),groups=[];for(const key of cells.keys()){if(visited.has(key))continue;const pending=[key],ids=[];visited.add(key);while(pending.length){const k=pending.pop(),[x,y]=k.split(',').map(Number);ids.push(...cells.get(k));for(const n of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]]){const kk=n.join(',');if(cells.has(kk)&&!visited.has(kk)){visited.add(kk);pending.push(kk);}}}groups.push(ids);}
 let added=0;for(const ids of groups){if(ids.length<16)continue;let min=[Infinity,Infinity],max=[-Infinity,-Infinity],x=0,y=0;for(const i of ids){x+=lv[i*4];y+=lv[i*4+1];for(let d=0;d<2;d++){min[d]=Math.min(min[d],lv[i*4+d]);max[d]=Math.max(max[d],lv[i*4+d]);}}x/=ids.length;y/=ids.length;
 if(Math.hypot(max[0]-min[0],max[1]-min[1])>1.4)continue;
 if(out.cands.some(c=>Math.hypot(c.centroid.x-x,c.centroid.y-y)<.35))continue;
 const raw=[];for(let i=0;i<lv.length/4;i++){const dx=lv[i*4]-x,dy=lv[i*4+1]-y,z=lv[i*4+2];if(dx*dx+dy*dy<=.45*.45&&z>.1&&z<2.3)raw.push(i);}if(raw.length<16)continue;
 const sub={n:raw.length,x:new Float32Array(raw.length),y:new Float32Array(raw.length),z:new Float32Array(raw.length)},inten=new Float32Array(raw.length);raw.forEach((i,j)=>{sub.x[j]=lv[i*4];sub.y[j]=lv[i*4+1];sub.z[j]=lv[i*4+2];inten[j]=lv[i*4+3];});const zlo=Math.min(...sub.z),zhi=Math.max(...sub.z);if(zhi-zlo<.5)continue;
 const prob=this.rf.predict_person(this.rf.extract(sub,inten)),z=sub.z.reduce((a,b)=>a+b,0)/raw.length;
 const f={cx:x,cy:y,cz:z,n:raw.length,z_min:zlo,z_max:zhi,joint:prob>=.55?'CONFIRMED_HUMAN':'NON_HUMAN',label:prob>=.55?'HUMAN':'NON_HUMAN',confidence:prob,reasons:[]};
 const c=S.make_candidate({candidate_id:'static_'+fc.frame_index+'_'+added,point_indices:Uint32Array.from(raw),point_count:raw.length,centroid:{x,y,z},scores:{rf51:{prob,threshold:.55,model_sha:this.rf_model_sha}},foreground_source:'static_geometry',gen_reason:'raw_upper_body_seed',geo_features:f});c._pipe_f=f;c.rf51_prob=prob;c.static_path=true;out.cands.push(c);
 const positions=new Map(out.final_ids.map((id,j)=>[id,j])),values=Array.from(out.fg_final);for(const id of raw){if(positions.has(id))continue;positions.set(id,out.final_ids.length);out.final_ids.push(id);out.sources.push('static_geometry');values.push(...lv.subarray(id*4,id*4+4));}out.fg_final=Float32Array.from(values);added++;
 }
 diag.layers.push({layer:'static_geometry',in_points:lv.length/4,out_points:out.final_ids.length,in_candidates:groups.length,out_candidates:added,elapsed_ms:performance.now()-start});return out;};return eng;}
module.exports={addStatic};
