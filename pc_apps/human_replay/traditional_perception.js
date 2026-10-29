/* Traditional v2: point membership -> metric clusters -> person admission ->
 * one-to-one association -> posture -> unconfirmed fall events. No DOM/ROS/model.
 * Unlike human_pipe_lib.Tracker/fall_assess (frame-based legacy), lifecycle and
 * posture evidence here use bag-time seconds. These are separate selectable versions. */
(function () {
    "use strict";
    var P = typeof module !== "undefined" && module.exports ? require("./human_pipe_lib.js") : globalThis.human_pipe_lib;
    var F = typeof module !== "undefined" && module.exports ? require("./fresh_map_lib.js") : globalThis.fresh_map_lib;
    var DEFAULTS = Object.freeze({ cluster: "metric3d", cell_m: 0.15, tolerance_m: 0.27,
        min_points: 60, birth_height_m: 1.15, birth_top_m: 1.4, birth_floor_m: 0.35,
        confirm_s: 0.18, lost_s: 1, gate_m: 0.6, min_evidence_ratio: 0.4,
        lying_s: 1, fast_descent_mps: 0.65, descent_drop_m: 0.45, ambiguity_margin_m: 0.08,
        reference_min_support: 0.9, verification_motion_m: 0.04, xy_motion_mode: 2,
        max_vertical_mps: 5, vertical_slack_m: 0.15, low_minor_width_m: 0.45 });
    function sum(points, ids) {
        var a = { n:0,sx:0,sy:0,sz:0,sxx:0,syy:0,szz:0,sxy:0,sxz:0,syz:0,zmin:Infinity,zmax:-Infinity };
        ids.forEach(function (i) {
            var x=points[i*4],y=points[i*4+1],z=points[i*4+2];
            a.n++;a.sx+=x;a.sy+=y;a.sz+=z;a.sxx+=x*x;a.syy+=y*y;a.szz+=z*z;
            a.sxy+=x*y;a.sxz+=x*z;a.syz+=y*z;a.zmin=Math.min(a.zmin,z);a.zmax=Math.max(a.zmax,z);
        });
        return a;
    }
    function cluster(points, indices, cfg) {
        if (cfg.cluster === "xy") {
            var cols = new Map(), packed = new Float32Array(indices.length*4);
            indices.forEach(function (id,k) {
                packed.set(points.subarray(id*4,id*4+4),k*4);
                var key=P.key_vox(points[id*4],points[id*4+1]);
                if(!cols.has(key))cols.set(key,[]);cols.get(key).push(id);
            });
            return P.cluster_voxels(P.voxelize(packed)).filter(function(c){return c.acc.n>=cfg.min_points;}).map(function (c) {
                return { indices:c.keys.reduce(function(a,k){return a.concat(cols.get(k));},[]),acc:c.acc };
            });
        }
        // PCL-style metric flood fill over voxel centroids; no quadratic point pairs.
        var cells=new Map(), size=cfg.cell_m, hops=Math.ceil(cfg.tolerance_m/size);
        indices.forEach(function (id) {
            var x=points[id*4],y=points[id*4+1],z=points[id*4+2];
            var ij=[Math.floor(x/size),Math.floor(y/size),Math.floor(z/size)],key=ij.join(",");
            if(!cells.has(key))cells.set(key,{ij:ij,ids:[],x:0,y:0,z:0});
            var c=cells.get(key);c.ids.push(id);c.x+=x;c.y+=y;c.z+=z;
        });
        cells.forEach(function(c){c.x/=c.ids.length;c.y/=c.ids.length;c.z/=c.ids.length;});
        var left=new Set(cells.keys()),out=[],tol2=cfg.tolerance_m*cfg.tolerance_m;
        left.forEach(function(seed){
            if(!left.has(seed))return;
            var queue=[seed],ids=[];left.delete(seed);
            for(var qi=0;qi<queue.length;qi++){
                var c=cells.get(queue[qi]);Array.prototype.push.apply(ids,c.ids);
                for(var a=-hops;a<=hops;a++)for(var b=-hops;b<=hops;b++)for(var d=-hops;d<=hops;d++){
                    var key=[c.ij[0]+a,c.ij[1]+b,c.ij[2]+d].join(",");
                    if(!left.has(key))continue;var n=cells.get(key);
                    if((c.x-n.x)*(c.x-n.x)+(c.y-n.y)*(c.y-n.y)+(c.z-n.z)*(c.z-n.z)<=tol2){
                        left.delete(key);queue.push(key);
                    }
                }
            }
            if(ids.length>=cfg.min_points)out.push({indices:ids,acc:sum(points,ids)});
        });
        return out;
    }
    /* Exact assignment at <=8 observations/tracks. Larger scenes explicitly return
     * overflow/UNKNOWN instead of truncating people or allocating exponential work. */
    function assign(cost, miss) {
        var n=cost.length,m=n?cost[0].length:0;
        if(n>8||m>8)return {overflow:true,pairs:[]};
        var memo=new Map();
        function solve(i,mask){
            if(i===n)return {cost:0,pairs:[]};var key=i+":"+mask;if(memo.has(key))return memo.get(key);
            var tail=solve(i+1,mask),best={cost:miss+tail.cost,pairs:tail.pairs};
            for(var j=0;j<m;j++)if(!(mask&(1<<j))&&Number.isFinite(cost[i][j])&&cost[i][j]<miss){
                var next=solve(i+1,mask|(1<<j)),value=cost[i][j]+next.cost;
                if(value<best.cost)best={cost:value,pairs:[[i,j]].concat(next.pairs)};
            }
            memo.set(key,best);return best;
        }
        return {overflow:false,pairs:solve(0,0).pairs};
    }
    function Engine(options) {
        this.cfg=Object.assign({},DEFAULTS,options||{});
        if(!["metric3d","xy"].includes(this.cfg.cluster))throw Error("Unknown clustering mode");
        Object.keys(this.cfg).forEach(function(k){
            // 0=off, 1=centroid displacement, 2=net/path, 3=two-window consistency.
            if(k==="xy_motion_mode"){if(![0,1,2,3].includes(this.cfg[k]))throw Error("Invalid motion mode");return;}
            if(k!=="cluster"&&(!Number.isFinite(this.cfg[k])||this.cfg[k]<=0))throw Error("Invalid parameter: "+k);
        },this);
        this.reset();
    }
    Engine.prototype.reset=function(){this.tracks=[];this.next_id=1;this.last_t=null;this.last_frame=-1;this.events=[];this.snapshot=null;};
    function structure(points,o,cfg) {
        var f=o.f;
        if(!f.ok||f.n<800||f.width_m<0.15||f.width_m>0.4||f.radius_m>0.45||
            f.zmin>cfg.birth_floor_m||o.evidence_n<cfg.min_points||o.evidence_n/f.n<cfg.min_evidence_ratio)return false;
        var bins=new Set(o.indices.map(function(i){return Math.floor(points[i*4+2]/0.1);})),run=0;
        return Array.from(bins).sort(function(a,b){return a-b;}).some(function(b,i,a){
            run=i&&b===a[i-1]+1?run+1:1;return run>=6;
        });
    }
    function motion(history,threshold) {
        if(history.length<2)return {centroid:false,direct:false,multiwindow:false,progress:0};
        var first=history[0],last=history[history.length-1],path=0;
        for(var i=1;i<history.length;i++)path+=Math.hypot(history[i].x-history[i-1].x,history[i].y-history[i-1].y);
        var net=Math.hypot(last.x-first.x,last.y-first.y),progress=path?net/path:0;
        var centroid=last.t-first.t>=0.18&&net>=threshold,direct=centroid&&progress>=0.7;
        var mid=history.reduce(function(a,b){return Math.abs(b.t-(first.t+last.t)/2)<Math.abs(a.t-(first.t+last.t)/2)?b:a;},first);
        var ax=mid.x-first.x,ay=mid.y-first.y,bx=last.x-mid.x,by=last.y-mid.y;
        var norms=Math.hypot(ax,ay)*Math.hypot(bx,by);
        return {centroid:centroid,direct:direct,multiwindow:direct&&last.t-first.t>=0.5-1e-6&&norms>0&&(ax*bx+ay*by)/norms>=0.7,progress:progress};
    }
    Engine.prototype._event=function(track,type,t){
        var e={track_id:track.id,type:type,t:t,confirmed:false};
        this.events.push(e);if(this.events.length>1000)this.events.shift();return e;
    };
    Engine.prototype._posture=function(track,f,t){
        var cfg=this.cfg,standing=f.height_m>=0.95&&f.upcos>=0.5;
        var lying=f.zmax<=0.95&&f.height_m<=0.75&&f.upcos<0.5;
        var history=track.history;
        while(history.length&&t-history[0].t>0.7)history.shift();
        var old=history.length?history[0]:null;
        var speed=old&&t-old.t>=0.15?(old.z-f.cz)/(t-old.t):0;
        history.push({t:t,z:f.cz});while(history.length&&t-history[0].t>0.7)history.shift();
        if(standing){
            track.standing_z=Math.max(track.standing_z||0,f.cz);
            track.standing_height=Math.max(track.standing_height||0,f.height_m);
            if(track.stable_lying||track.episode||track.recover_since!==null){
                if(track.recover_since===null)track.recover_since=t;
                track.posture="RECOVERING";
                if(t-track.recover_since>=0.5){this._event(track,track.episode?"RECOVERED":"POSTURE_RETURNED",t);track.posture="STANDING";track.episode=false;track.stable_lying=false;track.recover_since=null;track.fast_at=null;}
            }else {track.posture="STANDING";track.fast_at=null;}
            track.lying_since=null;
        }else{
            track.recover_since=null;
            if((track.standing_z||0)-f.cz>=cfg.descent_drop_m&&speed>=cfg.fast_descent_mps)track.fast_at=t;
            if(lying){
                if(track.lying_since===null)track.lying_since=t;
                if(t-track.lying_since>=cfg.lying_s)track.stable_lying=true;
                track.posture="LYING";
                if(!track.episode&&track.fast_at!==null&&t-track.fast_at<=2.5&&t-track.lying_since>=cfg.lying_s){
                    this._event(track,"FALL_CANDIDATE",t);track.episode=true;
                }
                if(track.episode)track.posture="FALL_CANDIDATE";
            }else{track.posture="LOW";track.lying_since=null;}
        }
    };
    Engine.prototype.tick=function(points,st,frame,t){
        if(!(points instanceof Float32Array)||points.length%4||!Number.isSafeInteger(frame)||frame<0||!Number.isFinite(t))throw Error("Invalid frame context");
        if(this.last_t!==null&&(t<this.last_t||frame<this.last_frame))throw Error("Non-causal input; reset before seeking");
        if(frame===this.last_frame)return this.snapshot;
        if(this.last_t!==null&&t-this.last_t>2)this.tracks=[];
        this.last_t=t;this.last_frame=frame;
        var cfg=this.cfg,indices=[],evidence=new Set(),supported=0,inband=0,self=this;
        this.tracks=this.tracks.filter(function(a){return t-a.last_t<=cfg.lost_s;});
        for(var i=0;i<points.length/4;i++){
            var x=points[i*4],y=points[i*4+1],z=points[i*4+2];
            if(!Number.isFinite(x+y+z)||z<st.o.z_min_m||z>st.o.z_max_m)continue;
            inband++;var v=st.voxels.get(P.key_bg(x,y,z));if(v&&v.ref_sup)supported++;
            var ev=v&&!v.ref_sup&&v.ever_event;if(ev)evidence.add(i);
            var s=F.point_state(st,x,y,z),keep=s==="HOT"||s==="GHOST";
            if(!keep&&ev)keep=this.tracks.some(function(a){return a.confirmed&&Math.hypot(a.x-x,a.y-y)<0.9;});
            if(keep)indices.push(i);
        }
        var observations=cluster(points,indices,cfg).map(function(c){
            var f=P.cluster_features(c),ev=c.indices.reduce(function(n,id){return n+(evidence.has(id)?1:0);},0),reasons=[];
            if(!f.ok)reasons.push("sparse");
            else{
                if(P.classify_human(f).label!=="HUMAN_CANDIDATE")reasons.push("standing_shape");
                if(f.height_m<cfg.birth_height_m)reasons.push("short");
                if(f.zmax<cfg.birth_top_m)reasons.push("low_top");
                if(f.zmin>cfg.birth_floor_m)reasons.push("no_floor_contact");
                if(ev<cfg.min_points||ev/f.n<cfg.min_evidence_ratio)reasons.push("insufficient_novelty");
            }
            var o={f:f,indices:c.indices,evidence_n:ev,birth:reasons.length===0,reasons:reasons,association_rejections:[]};
            o.structure=structure(points,o,cfg);o.provisional=!o.birth&&o.structure;
            return o;
        });
        var costs=this.tracks.map(function(a){return observations.map(function(o){
            var f=o.f;
            function reject(reason){o.association_rejections.push({track_id:a.id,reason:reason,dt:t-a.last_t});return Infinity;}
            if(!f.ok)return reject("invalid_features");
            if(o.evidence_n<cfg.min_points||o.evidence_n/f.n<cfg.min_evidence_ratio)return reject("insufficient_novelty");
            var dt=Math.min(0.5,t-a.last_t),dist=Math.hypot(f.cx-(a.x+a.vx*dt),f.cy-(a.y+a.vy*dt));
            if(Math.abs(f.cz-a.z)>cfg.vertical_slack_m+cfg.max_vertical_mps*(t-a.last_t))return reject("vertical_discontinuity");
            var minor=0.5*(f.cov.xx+f.cov.yy-Math.hypot(f.cov.xx-f.cov.yy,2*f.cov.xy));
            var minorWidth=2*Math.sqrt(Math.max(0,minor));
            // Lying bodies need longitudinal extent; bound transverse width separately.
            var continuation=a.confirmed&&f.zmax<=1.4&&f.height_m>=0.2&&f.radius_m<=0.75&&
                minorWidth<=cfg.low_minor_width_m&&
                a.standing_z-f.cz>=0.25&&a.standing_height-f.height_m>=0.25;
            var upright=a.confirmed&&f.zmin<=cfg.birth_floor_m&&P.classify_human(f).label==="HUMAN_CANDIDATE";
            if(dist>=cfg.gate_m)return reject("outside_xy_gate");
            return o.birth||(!a.confirmed&&o.structure)||upright||continuation?dist:reject("not_admissible_posture");
        });});
        // Noise clusters are diagnostic observations, not association targets.
        var eligible=[];
        observations.forEach(function(o,j){if(o.birth||o.provisional||costs.some(function(row){return Number.isFinite(row[j]);}))eligible.push(j);});
        var assignment=assign(costs.map(function(row){return eligible.map(function(j){return row[j];});}),cfg.gate_m+0.01);
        assignment.overflow=assignment.overflow||eligible.length>8;
        assignment.pairs=assignment.pairs.map(function(pair){return [pair[0],eligible[pair[1]]];});
        if(assignment.overflow){
            // Overload freezes births; unique nearest observations can still sustain confirmed IDs.
            assignment.pairs=[];
            this.tracks.forEach(function(a,i){
                if(!a.confirmed)return;
                var sorted=eligible.filter(function(j){return Number.isFinite(costs[i][j]);}).sort(function(a,b){return costs[i][a]-costs[i][b];});
                if(sorted.length&&(sorted.length<2||costs[i][sorted[1]]-costs[i][sorted[0]]>=cfg.ambiguity_margin_m))
                    assignment.pairs.push([i,sorted[0]]);
            });
            assignment.pairs=assignment.pairs.filter(function(pair){return assignment.pairs.filter(function(p){return p[1]===pair[1];}).length===1;});
        }
        var used=new Set(),matched=new Map(),claims=[],branches=[],backfill=[];
        var rejected=new Map();
        assignment.pairs.forEach(function(pair){
            var ai=pair[0],oi=pair[1],a=self.tracks[ai],o=observations[oi],f=o.f;
            // Near-equal competitors remain unknown instead of silently swapping identities.
            if(costs.some(function(row,k){return k!==ai&&Math.abs(row[oi]-costs[ai][oi])<cfg.ambiguity_margin_m;})){
                rejected.set(a.id,{reason:"ambiguous_observation",obs_index:oi,distance:costs[ai][oi]});return;
            }
            if(costs[ai].some(function(d,j){return j!==oi&&Math.abs(d-costs[ai][oi])<cfg.ambiguity_margin_m;})){
                rejected.set(a.id,{reason:"ambiguous_track",obs_index:oi,distance:costs[ai][oi]});return;
            }
            var dt=t-a.last_t;
            if(dt>0){a.vx=0.5*a.vx+0.5*(f.cx-a.x)/dt;a.vy=0.5*a.vy+0.5*(f.cy-a.y)/dt;}
            a.x=f.cx;a.y=f.cy;a.z=f.cz;a.last_t=t;a.last_frame=frame;a.hits++;
            a.motion_m=Math.max(a.motion_m,Math.hypot(f.cx-a.birth_x,f.cy-a.birth_y));
            a.shape_history=a.shape_history.filter(function(h){return t-h.t<=0.5+1e-6;});
            // Keep the boundary predecessor for mode 3: real 9.68Hz stamps rarely span exactly 0.5s.
            if(cfg.xy_motion_mode===3){while(a.xy_history.length>1&&t-a.xy_history[1].t>=0.5)a.xy_history.shift();}
            else a.xy_history=a.xy_history.filter(function(h){return t-h.t<=0.5+1e-6;});
            // A structure-qualified birth may become sparse while rising; keep the strict standing gate.
            a.shape_motion=a.shape_motion||((o.structure||(a.provisional_birth&&o.birth))&&f.zmax>=1.4&&
                a.shape_history.some(function(h){return f.height_m-h.height>=0.3;}));
            a.shape_history.push({t:t,height:f.height_m});a.xy_history.push({t:t,x:f.cx,y:f.cy});
            a.xy_features=motion(a.xy_history,cfg.verification_motion_m);
            var xy=[false,a.xy_features.centroid,a.xy_features.direct,a.xy_features.multiwindow][cfg.xy_motion_mode];
            var wasConfirmed=a.confirmed;
            // Low-structure births must rise before receiving identity, even with a trusted reference.
            a.confirmed=a.confirmed||(a.hits>=3&&t-a.born_t>=cfg.confirm_s&&
                (!a.provisional_birth||a.shape_motion)&&(a.reference_trusted||xy||a.shape_motion));
            if(!wasConfirmed&&a.confirmed){
                a.confirmed_t=t;a.confirmed_frame=frame;
                // Separate audit stream; online claims never mutate an already-rendered frame.
                if(a.provisional_birth)a.pending.forEach(function(p){backfill.push({frame:p.frame,t:p.t,track_id:a.id,indices:p.indices});});
                a.pending=[];
            }
            a.branch=!a.confirmed&&a.provisional_birth?"provisional_update":o.birth?"standing_update":P.classify_human(f).label==="HUMAN_CANDIDATE"?"upright_continue":"low_continue";
            a.match={obs_index:oi,distance:costs[ai][oi],dt:dt};
            used.add(oi);matched.set(a.id,o);
        });
        if(!assignment.overflow)observations.forEach(function(o,oi){
            if(used.has(oi)||!(o.birth||o.provisional)||self.tracks.some(function(a){return Math.hypot(a.x-o.f.cx,a.y-o.f.cy)<cfg.gate_m;}))return;
            if(self.tracks.length>=8)return;
            var f=o.f,a={id:self.next_id++,x:f.cx,y:f.cy,z:f.cz,vx:0,vy:0,born_t:t,last_t:t,last_frame:frame,
                hits:1,confirmed:false,branch:"standing_birth",posture:"UNKNOWN",history:[],standing_z:f.cz,
                match:{obs_index:oi,distance:0,dt:0},
                standing_height:f.height_m,lying_since:null,recover_since:null,fast_at:null,episode:false,stable_lying:false};
            a.birth_x=f.cx;a.birth_y=f.cy;a.motion_m=0;
            a.provisional_birth=o.provisional;a.born_frame=frame;a.confirmed_t=null;a.confirmed_frame=null;
            a.pending=[];a.shape_history=[{t:t,height:f.height_m}];a.xy_history=[{t:t,x:f.cx,y:f.cy}];
            a.shape_motion=false;a.xy_features=motion(a.xy_history,cfg.verification_motion_m);
            if(o.provisional)a.branch="provisional_birth";
            a.reference_trusted=inband>0&&supported/inband>=cfg.reference_min_support;
            a.reference_support_at_birth=inband?supported/inband:null;
            self.tracks.push(a);matched.set(a.id,o);
        });
        this.tracks.forEach(function(a){
            var o=matched.get(a.id);
            if(!o){branches.push(Object.assign({id:a.id,branch:"missing",age_s:t-a.last_t,
                reason:assignment.overflow?"association_overload":"no_eligible_observation"},rejected.get(a.id)||{}));return;}
            branches.push(Object.assign({id:a.id,branch:a.branch,confirmed:a.confirmed,
                reason:!a.confirmed&&a.provisional_birth&&!a.shape_motion?"awaiting_shape_motion":!a.confirmed&&!a.reference_trusted?"awaiting_independent_motion":"matched",
                motion_m:a.motion_m,reference_trusted:a.reference_trusted},a.match));
            if(!a.confirmed){
                if(a.provisional_birth)a.pending.push({frame:frame,t:t,indices:o.indices.filter(function(id){return evidence.has(id);})});
                return;
            }
            self._posture(a,o.f,t);
            o.indices.forEach(function(id){if(evidence.has(id))claims.push({index:id,track_id:a.id,posture:a.posture});});
        });
        var tracks=this.tracks.map(function(a){return {id:a.id,x:a.x,y:a.y,z:a.z,confirmed:a.confirmed,
            hits:a.hits,last_frame:a.last_frame,last_t:a.last_t,born_t:a.born_t,born_frame:a.born_frame,
            provisional_birth:a.provisional_birth,confirmed_t:a.confirmed_t,confirmed_frame:a.confirmed_frame,
            shape_motion:a.shape_motion,xy_features:a.xy_features,motion_m:a.motion_m,reference_trusted:a.reference_trusted,
            reference_support_at_birth:a.reference_support_at_birth,
            branch:matched.has(a.id)?a.branch:"missing",posture:a.posture};});
        this.snapshot={frame:frame,t:t,tracks:tracks,claims:claims,backfill:backfill,observations:observations,branches:branches,
            events:this.events.slice(),overflow:assignment.overflow,eligible_observations:eligible.length,
            reference_support:inband?supported/inband:null,
            candidate_points:indices.length};
        return this.snapshot;
    };
    var api={Engine:Engine,cluster:cluster,assign:assign,DEFAULTS:DEFAULTS};
    if(typeof module!=="undefined"&&module.exports)module.exports=api;
    if(typeof globalThis!=="undefined")globalThis.traditional_perception=api;
})();
