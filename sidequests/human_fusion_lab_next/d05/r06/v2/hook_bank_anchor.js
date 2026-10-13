'use strict';
// ponytail: 只有原坐标超出既有恢复半径才改合法银行坐标；全部资格、票、寿命与两个tracker保持原样。
const S=require('../../../../human_fusion_lab/core/schema');
const copy=x=>JSON.parse(JSON.stringify(x));
function proof(cands,id,threshold) {
    return cands.filter(c=>c.track_id===Number(id)&&c.foreground_source===S.CAND_SRC.FG&&c.rf51_prob>=threshold)
        .sort((a,b)=>b.rf51_prob-a.rf51_prob||(a.candidate_id<b.candidate_id?-1:a.candidate_id>b.candidate_id?1:0))[0]||null;
}
function applyBankAnchor(engine,anchored,diagnostics=true) {
    const tick=engine._tick_fusion,pa=engine._fusion_a_chain,pb=engine._fusion_b_chain;
    let before={},pipeBefore=[],aOut=null;
    engine._tick_fusion=function(fc,...args) {
        if(diagnostics){before=copy(this.retention.tracks);pipeBefore=this.pipe_ctx.tracker.tracks.map(t=>({id:t.id,x:t.x,y:t.y,active:t.active,human_confirmed:t.human_confirmed,votes:(t.votes||[]).slice()}));}
        return tick.call(this,fc,...args);
    };
    engine._fusion_a_chain=function(...args){aOut=pa.apply(this,args);return aOut;};
    engine._fusion_b_chain=function(fc,...args) {
        const updates=[],bank=this.retention.tracks;
        for(const [id,item] of Object.entries(bank)) {
            if(item.frame_index!==fc.frame_index)continue;
            const c=proof(aOut.cands,id,this.cfg.rf51_threshold);
            if(!c)throw Error('bank refreshed without independent FG proof');
            const original={x:item.x,y:item.y};
            const displacement=Math.hypot(original.x-c.centroid.x,original.y-c.centroid.y);
            const changed=anchored&&displacement>this.cfg.retention.hot_cell_radius_m;
            if(changed){item.x=c.centroid.x;item.y=c.centroid.y;}
            if(diagnostics)updates.push({internal_track_id:Number(id),proof_candidate:c.candidate_id,
                original_pipe_anchor:original,proof_centroid:{x:c.centroid.x,y:c.centroid.y},
                displacement_m:displacement,anchor_changed:changed,
                current_anchor:{x:item.x,y:item.y},confirmations:item.confirmations,
                reason:changed?'PROOF_CENTER_OUTSIDE_ORIGINAL_RESTORE_RADIUS':'ORIGINAL_PIPE_EMA'});
        }
        if(diagnostics) {
            const clean=new Set(aOut.final_ids.filter((r,i)=>aOut.sources[i]===S.CAND_SRC.FG));
            const candidates=aOut.cands.map(c=>({id:c.candidate_id,internal_track_id:c.track_id,
                raw_indices:Array.from(c.point_indices),foreground_source:c.foreground_source,
                independent_fg_points:Array.from(c.point_indices).filter(i=>clean.has(i)).length,
                retained_points:Array.from(c.point_indices).filter(i=>!clean.has(i)).length,
                prob:c.rf51_prob,centroid:{x:c.centroid.x,y:c.centroid.y},
                classifier_decision:c.classifier_decision_auc,pipe_confirmed:!!c._pipe_f.track_confirmed}));
            const owners=aOut.final_ids.filter(i=>!clean.has(i)).map(i=>({raw_index:i,
                anchors:Object.entries(before).filter(([,a])=>a.confirmations>=this.cfg.retention.window_confirm
                    &&fc.timestamp-a.timestamp<=this.cfg.retention.timeout_s
                    &&fc.frame_index-a.frame_index<=this.cfg.retention.max_lost_for_retain
                    &&(args[0][i*4]-a.x)**2+(args[0][i*4+1]-a.y)**2<=this.cfg.retention.hot_cell_radius_m**2)
                    .map(([id])=>Number(id))}));
            // args[0] is the actual current leveled frame, not GT or a future observation.
            if(owners.some(o=>!o.anchors.length))throw Error('retained point has no live bank owner');
            this._bank_events={bank_before:before,bank_after:copy(bank),pipe_before:pipeBefore,
                pipe_after:this.pipe_ctx.tracker.tracks.map(t=>({id:t.id,x:t.x,y:t.y,active:t.active,human_confirmed:t.human_confirmed,votes:(t.votes||[]).slice()})),
                pre_fusion_candidates:candidates,updates,retained_owners:owners,
                expired_ids:Object.keys(before).filter(id=>!bank[id]),
                created_or_reentered:updates.filter(u=>!before[u.internal_track_id]
                    ||fc.frame_index-before[u.internal_track_id].frame_index>this.cfg.retention.max_lost_for_retain).map(u=>u.internal_track_id),
                scope:'pre-fusion PA provenance; B-only terminal FG is not bank proof; same-frame multi-assignment preserves original tracker behavior'};
        }
        return pb.call(this,fc,...args);
    };
    return {kind:'bank_anchor_only_outside_original_restore_radius',enabled:anchored,diagnostics,
        proof:'unchanged original FG + confirmed bank eligibility',tie_break:'probability descending, candidate ID',
        changed_fields:anchored?['bank.x','bank.y']:[],no_gt_or_future:true};
}
module.exports={applyBankAnchor,proof};
