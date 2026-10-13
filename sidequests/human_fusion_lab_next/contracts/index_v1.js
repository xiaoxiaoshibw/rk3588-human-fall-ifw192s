'use strict';
const crypto=require('crypto');
const L=require('../../human_fusion_lab/core/leveling');
const VERSION='hfus-index-v1';
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
function mapFrame(sensor_xyzi, coordinate){
 if(!(sensor_xyzi instanceof Float32Array)||sensor_xyzi.length%4)throw Error('expected sensor xyzi Float32');
 const n=sensor_xyzi.length/4, raw_to_compact=new Int32Array(n).fill(-1), ids=[];
 for(let r=0;r<n;r++){const x=sensor_xyzi[r*4],y=sensor_xyzi[r*4+1],z=sensor_xyzi[r*4+2];if(Number.isFinite(x)&&Number.isFinite(y)&&Number.isFinite(z)&&(x!==0||y!==0||z!==0)){raw_to_compact[r]=ids.length;ids.push(r);}}
 const compact_to_raw=Uint32Array.from(ids), leveled_xyzi=L.level_frame(sensor_xyzi,coordinate.R,coordinate.T,coordinate.already_leveled),compact_leveled_xyzi=new Float32Array(ids.length*4);
 // Invalid raw rows stay invalid after translation; no coordinate based identity lookup.
 for(let r=0;r<n;r++)if(raw_to_compact[r]<0)for(let d=0;d<3;d++)leveled_xyzi[r*4+d]=NaN;
 ids.forEach((r,c)=>compact_leveled_xyzi.set(leveled_xyzi.subarray(r*4,r*4+4),c*4));
 return {version:VERSION,raw_to_compact,compact_to_raw,leveled_to_raw:Uint32Array.from({length:n},(_,i)=>i),raw_to_leveled:Uint32Array.from({length:n},(_,i)=>i),leveled_xyzi,compact_leveled_xyzi};
}
function decodeRaw28(buffer,coordinate){
 if(!Buffer.isBuffer(buffer)||buffer.length%28)throw Error('raw28 length');
 const sensor_xyzi=new Float32Array(buffer.length/28*4);
 for(let r=0;r<buffer.length/28;r++)for(let d=0;d<4;d++)sensor_xyzi[r*4+d]=buffer.readFloatLE(r*28+d*4);
 return {...mapFrame(sensor_xyzi,coordinate),sensor_xyzi,raw28_sha256:sha(buffer)};
}
function compactIdsToRaw(ids,map){return Array.from(ids,i=>{if(!Number.isSafeInteger(i)||i<0||i>=map.compact_to_raw.length)throw Error('compact index out of range');return map.compact_to_raw[i];});}
function pointsetSha(ids){const b=Buffer.alloc(ids.length*4);Array.from(ids).forEach((v,i)=>{if(!Number.isSafeInteger(v)||v<0||v>0xffffffff)throw Error('invalid raw row');b.writeUInt32LE(v,i*4);});return sha(b);}
module.exports={VERSION,mapFrame,decodeRaw28,compactIdsToRaw,pointsetSha,sha};
