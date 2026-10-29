"""Bounded voxel moment surfaces and raw-row ledgers. Aggregation is RESEARCH."""
import copy
import time
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from contracts import digest, save_array, write_new, sha

DEFAULTS = dict(surface_tau_m=.08,noise_m=.012,neighbor_m=.26,association_m=1.25,
                growth_m=.5,max_extent_m=2.4,max_transverse_m=.8,local_change_radius_m=1.2,min_points=3,ttl_s=.7,max_gap_s=2.,seed=17)
LABELS = ['INVALID_XYZ','ZERO_RANGE','UNKNOWN_NO_M0','bg_match','NEW_SURFACE','AMBIGUOUS']
ROW_DTYPE = np.dtype([('label','u1'),('flags','u1'),('surface','<i4'),('candidate','<i4')])


def validity(p):
    finite = np.isfinite(p).all(axis=1)
    return finite, finite & np.any(p != 0,axis=1)


class FrozenMap:
    def __init__(self, output, binding, coordinate, protocol):
        self.output,self.binding,self.coordinate,self.protocol = output,copy.deepcopy(binding),coordinate,copy.deepcopy(protocol)
        self.folder=output/'map'; self.folder.mkdir()
        self.capacity=protocol['map']['max_surfaces']; self.n=0; self.keys={}; self.build=[]
        self.stats=np.zeros((self.capacity,12),dtype='f8')
        self.count=np.zeros(self.capacity,dtype='i8');self.frames=np.zeros(self.capacity,dtype='i4')
        self.first=np.full(self.capacity,-1,dtype='i4');self.last=self.first.copy()
        self.minimum=np.full((self.capacity,3),np.inf);self.maximum=-self.minimum
        self.map_id=None;self.tree=None

    def add(self,f):
        if self.map_id: raise ValueError('Frozen map cannot update')
        if f['source_sha256'] != self.binding or f['coordinate_version'] != self.coordinate: raise ValueError('Map source drift')
        if not 0 <= f['relative_s'] < self.protocol['split']['build'][1]: raise ValueError('Unauthorized map frame')
        p=f['xyz'];_,valid=validity(p); rows=np.flatnonzero(valid)
        # All valid observations, without row sampling; invalid rows have -1.
        cells,inv=np.unique(np.floor(p[rows]/self.protocol['map']['voxel_m']).astype('i8'),axis=0,return_inverse=True)
        ids=[]
        for key in map(tuple,cells.tolist()):
            if key not in self.keys:
                if self.n>=self.capacity: raise MemoryError('Pre-registered map surface budget exceeded')
                self.keys[key]=self.n;self.n+=1
            ids.append(self.keys[key])
        ids=np.asarray(ids,dtype='i4'); sid=ids[inv]
        local_count=np.bincount(inv,minlength=len(cells))
        self.count[ids]+=local_count;self.frames[ids]+=1
        self.first[ids]=np.where(self.first[ids]<0,f['fi'],self.first[ids]);self.last[ids]=f['fi']
        for a in range(3):
            self.stats[ids,a]+=np.bincount(inv,weights=p[rows,a],minlength=len(cells))
            self.stats[ids,a+3]+=np.bincount(inv,weights=p[rows,a]**2,minlength=len(cells))
            np.minimum.at(self.minimum[:,a],sid,p[rows,a]);np.maximum.at(self.maximum[:,a],sid,p[rows,a])
        support=np.full(len(p),-1,dtype='i4');support[rows]=sid
        save_array(self.folder/('support_%04d.npz'%f['fi']),surface=support)
        self.build.append(dict(fi=f['fi'],offset=f['offset'],count=len(p),time_ns=f['time_ns']))

    def freeze(self):
        if self.map_id: raise ValueError('Already frozen')
        n=self.n
        if not n: raise ValueError('No valid mapping observations')
        self.centers=self.stats[:n,:3]/self.count[:n,None]
        self.noise=np.sqrt(np.maximum(0,self.stats[:n,3:6]/self.count[:n,None]-self.centers**2))
        self.minimum=self.minimum[:n].copy();self.maximum=self.maximum[:n].copy()
        self.count=self.count[:n].copy();self.frames=self.frames[:n].copy()
        self.first=self.first[:n].copy();self.last=self.last[:n].copy()
        # Qualification statistics never use temporal validation for calibration.
        self.eligible=(self.count>=20)&(self.frames>=5)
        # Eligibility time span is evaluated only with exact device stamps below.
        support=[];global_rows=[]
        for f in self.build:
            with np.load(self.folder/('support_%04d.npz'%f['fi'])) as z: ids=z['surface']
            keep=ids>=0; support.append(ids[keep]);global_rows.append(np.flatnonzero(keep).astype('i8')+f['offset'])
        support=np.concatenate(support);global_rows=np.concatenate(global_rows)
        order=np.argsort(support,kind='stable')
        self.support_global=global_rows[order]
        self.indptr=np.r_[0,np.cumsum(np.bincount(support,minlength=n))]
        self.stats=None;self.keys=None
        self.tree_ids=np.flatnonzero(self.eligible);self.tree=cKDTree(self.centers[self.tree_ids]) if len(self.tree_ids) else None
        if self.tree is not None:self.tree.data.setflags(write=False)

    def bind_exact_time(self,stamps):
        q=self.protocol['qualification']
        span=(np.asarray(stamps,dtype='i8')[self.last]-np.asarray(stamps,dtype='i8')[self.first])/1e9
        self.eligible=(self.count>=q['min_surface_observations'])&(self.frames>=q['min_surface_distinct_frames'])&(span>=q['min_surface_time_span_s'])
        self.tree_ids=np.flatnonzero(self.eligible);self.tree=cKDTree(self.centers[self.tree_ids]) if len(self.tree_ids) else None
        self.arrays=dict(centers=self.centers,noise=self.noise,minimum=self.minimum,maximum=self.maximum,
                         count=self.count,frame_count=self.frames,first_fi=self.first,last_fi=self.last,
                         eligible=self.eligible,tree_ids=self.tree_ids,support_global=self.support_global,indptr=self.indptr,
                         matching_tree_xyz=self.tree.data if self.tree is not None else np.empty((0,3)))
        save_array(self.folder/'surfaces.npz',**self.arrays)
        self.map_id=self.fingerprint()
        write_new(self.folder/'MAP.json',dict(map_id=self.map_id,coordinate=self.coordinate,source_sha256=self.binding,
                      surfaces=self.n,eligible_surfaces=len(self.tree_ids),build=self.build,protocol=self.protocol,
                      finite_support='Observed voxel AABB + frozen tau; point-centroid proximity, no plane extension'))
        for a in self.arrays.values():a.setflags(write=False)

    def fingerprint(self):
        import hashlib
        h=hashlib.sha256(digest(dict(source=self.binding,coordinate=self.coordinate,protocol=self.protocol,build=self.build)).encode())
        for key,a in sorted(self.arrays.items()):
            h.update(key.encode());h.update(str(a.dtype).encode());h.update(str(a.shape).encode())
            if not a.size:continue
            view=memoryview(np.ascontiguousarray(a)).cast('B')
            for start in range(0,len(view),8*1024*1024):h.update(view[start:start+8*1024*1024])
        return h.hexdigest()

    def match(self,p,valid):
        distance=np.full(len(p),np.inf); surface=np.full(len(p),-1,dtype='i4');bg=np.zeros(len(p),bool)
        if self.tree is not None and valid.any():
            rows=np.flatnonzero(valid);d,ix=self.tree.query(p[rows]);s=self.tree_ids[ix]
            distance[rows]=d;surface[rows]=s
            tau=self.protocol['map'].get('tau',.08)
            bounded=np.all((p[rows]>=self.minimum[s]-tau)&(p[rows]<=self.maximum[s]+tau),axis=1)
            bg[rows]=(d<=tau)&bounded
        return bg,distance,surface


def groups(p,rows,radius,voxel=.13):
    """Occupied voxel components; every raw member maps back, no display sampling."""
    if not len(rows):return []
    keys,inv=np.unique(np.floor(p[rows]/voxel).astype('i8'),axis=0,return_inverse=True)
    n=len(keys);centers=np.zeros((n,3));counts=np.bincount(inv)
    for a in range(3):centers[:,a]=np.bincount(inv,weights=p[rows,a])/counts
    pairs=cKDTree(centers).query_pairs(radius,output_type='ndarray')
    graph=coo_matrix((np.ones(len(pairs),bool),(pairs[:,0],pairs[:,1])),shape=(n,n))
    _,label=connected_components(graph,directed=False)
    raw_label=label[inv];order=np.argsort(raw_label,kind='stable')
    return [rows[q] for q in np.split(order,np.flatnonzero(np.diff(raw_label[order]))+1)]


class Engine:
    def __init__(self,frozen=None,variant='main',code_version='',config=None,run_version='',protocol_sha=''):
        self.map=frozen;self.variant=variant;self.cfg=dict(DEFAULTS if config is None else config)
        self.code_version=code_version;self.run_version=run_version;self.protocol_sha=protocol_sha
        self.track=None;self.last=None;self.usable=True

    def step(self,f,phase='ACTION',qualified=False):
        p=f['xyz'];cfg=self.cfg;reset=None
        binding=copy.deepcopy((f['sid'],f['source_sha256'],f['coordinate_version']))
        if self.last:
            if binding!=self.last['binding']:reset='SOURCE_OR_COORDINATE_CHANGED';self.usable=False
            elif f['time_ns']<=self.last['time']:raise ValueError('Nonmonotonic time')
            elif (f['time_ns']-self.last['time'])/1e9>cfg['max_gap_s']:reset='LONG_DEVICE_TIME_GAP'
        if self.map and f['coordinate_version']!=self.map.coordinate:reset='MAP_COORDINATE_CHANGED';self.usable=False
        if self.map and f['source_sha256']!=self.map.binding:reset='SOURCE_OR_COORDINATE_CHANGED';self.usable=False
        if reset:self.track=None
        self.last=dict(binding=binding,time=f['time_ns'],fi=f['fi'])
        finite,valid=validity(p);bg=np.zeros(len(p),bool);dist=np.full(len(p),np.inf);surfaces=np.full(len(p),-1,dtype='i4')
        active_map=bool(self.map and self.map.map_id and self.usable and self.variant!='no_frozen')
        if active_map:bg,dist,surfaces=self.map.match(p,valid)
        boundary=bool(qualified and active_map)
        seeds=valid & ~bg
        continuation=np.zeros(len(p),bool)
        live=bool(self.track and (f['time_ns']-self.track['last_measured_ns'])/1e9<=cfg['ttl_s'])
        if live and boundary and self.variant!='no_continuation':
            t=self.track
            continuation=valid & np.all((p>=t['min']-cfg['growth_m'])&(p<=t['max']+cfg['growth_m']),axis=1)&(np.linalg.norm(p-t['center'],axis=1)<=cfg['association_m'])&(~bg|(dist>cfg['noise_m']))
        candidates=[];rejected=[];candidate_id=np.full(len(p),-1,dtype='i4')
        bg_tree=cKDTree(p[bg]) if bg.any() else None
        # During building no future finished map is used, candidates diagnostic only.
        for rows in ([] if phase=='MAP_BUILDING' else groups(p,np.flatnonzero(seeds|continuation),cfg['neighbor_m'])):
            initial=rows.copy();q=p[rows]
            if len(rows)<cfg['min_points']:
                rejected.append(dict(count=len(rows),reason='UNSUPPORTED'));continue
            extent=np.ptp(q,axis=0)
            if extent.max()>cfg['max_extent_m'] or (self.variant=='scalable_reference' and np.sort(extent)[-2]>cfg['max_transverse_m']):
                rejected.append(dict(count=len(rows),reason='EXTENT_OR_REFERENCE_TRANSVERSE',min=q.min(0).tolist(),max=q.max(0).tolist()));continue
            grown=np.empty(0,dtype=int)
            if boundary and self.variant!='no_growth':
                possible=np.flatnonzero(valid & ~(seeds|continuation)&(dist>cfg['noise_m']))
                if len(possible):
                    d,_=cKDTree(q).query(p[possible]);grown=possible[(d<=cfg['neighbor_m'])&(np.linalg.norm(p[possible]-q.mean(0),axis=1)<=cfg['growth_m'])]
                    grown=grown[candidate_id[grown]<0]
                    rows=np.union1d(rows,grown);q=p[rows]
            extent=np.ptp(q,axis=0)
            if extent.max()>cfg['max_extent_m'] or (self.variant=='scalable_reference' and np.sort(extent)[-2]>cfg['max_transverse_m']):
                rejected.append(dict(count=len(rows),reason='POST_GROWTH_SCALE',min=q.min(0).tolist(),max=q.max(0).tolist()));continue
            center=q.mean(0);cid=len(candidates);candidate_id[rows]=cid
            contact=False
            if bg_tree is not None:contact=bool((bg_tree.query(q)[0]<=cfg['neighbor_m']).any())
            version=digest(dict(sid=f['sid'],fi=f['fi'],time_ns=f['time_ns'],source=f['source_sha256'],coordinate=f['coordinate_version'],
                               code=self.code_version,run=self.run_version,protocol=self.protocol_sha,qualified=boundary,
                               map_id=self.map.map_id if active_map else None,ground_id=None,
                               rows_sha=__import__('hashlib').sha256(np.asarray(rows,dtype='<i4').tobytes()).hexdigest(),config=cfg,variant=self.variant))
            candidates.append(dict(id=cid,version=version,rows=rows.tolist(),center=center.tolist(),min=q.min(0).tolist(),max=q.max(0).tolist(),
                               count=len(rows),seed_count=int(seeds[rows].sum()),continuation_count=int(continuation[initial].sum()),grown_count=len(grown),
                               quality='mixed/ambiguous' if contact or not boundary or bg[rows].any() else 'UNVERIFIED_CANDIDATE',semantic='UNKNOWN'))
        chosen=None
        if live and self.variant!='no_identity':
            choices=[c for c in candidates if np.linalg.norm(np.asarray(c['center'])-self.track['center'])<=cfg['association_m']]
            if len(choices)==1:chosen=choices[0];self.measure(f,chosen)
        track=self.track_record(f,chosen)
        label=np.full(len(p),4 if active_map else 2,dtype='u1');label[bg]=3;label[~finite]=0;label[finite&~valid]=1
        target=np.zeros(len(p),bool);target[track['rows']]=True;label[bg&(continuation|target)]=5
        rows=np.empty(len(p),dtype=ROW_DTYPE);rows['label']=label;rows['surface']=surfaces;rows['candidate']=candidate_id
        rows['flags']=valid.astype('u1')|(bg.astype('u1')<<1)|(seeds.astype('u1')<<2)|(continuation.astype('u1')<<3)|(target.astype('u1')<<4)
        ground=dict(geometric_valid=False,identity_confirmed=False,physical_verified=False,reason='MISSING_PRIORS_AND_INDEPENDENT_SPATIAL_REGIONS')
        review=self.map.protocol.get('ground_audit') if active_map else None
        if review:
            q=p@np.asarray(review['nominal_R']).T;roi=np.zeros(len(p),bool)
            for a,b,c,d in review['regions_nominal_xy']:roi|=(q[:,0]>=a)&(q[:,0]<=b)&(q[:,1]>=c)&(q[:,1]<=d)
            residual=np.abs(p@np.asarray(review['normal_source'])+review['offset_source_m'])
            compatible=valid&roi&(residual<=review['display_residual_m']);rows['flags']|=compatible.astype('u1')<<5
            ground.update(historical_candidate=review,ground_candidate_rows=int(compatible.sum()),
                          reason='HISTORICAL_TLS_CANDIDATE_ONLY; NO_NEW_INDEPENDENT_SPATIAL_VALIDATION',ground_id=review['ground_id'])
        counts=np.bincount(label,minlength=len(LABELS));assert counts.sum()==len(p)
        hits=np.unique(surfaces[bg])
        local_rows=np.flatnonzero(seeds&(dist<=cfg['local_change_radius_m'])&~np.isin(surfaces,hits)) if active_map else np.array([],dtype=int)
        conflicts=[]
        for s in np.unique(surfaces[local_rows]):
            if s>=0:conflicts.append(dict(surface_id=int(s),current_evidence_rows=local_rows[surfaces[local_rows]==s].tolist(),
                     interpretation='POSSIBLE_LOCAL_CHANGE_NEAR_UNOBSERVED_SURFACE; UNKNOWN_NOT_HUMAN'))
        record=dict(schema='hfus-realdev-frame/1',stage='REAL_DIAGNOSTIC',sid=f['sid'],kind=f['kind'],fi=f['fi'],time_ns=f['time_ns'],relative_s=f['relative_s'],
                    offset=f['offset'],source_sha256=f['source_sha256'],coordinate_version=f['coordinate_version'],variant=self.variant,phase=phase,reset=reset,
                    run_version=self.run_version,protocol_sha=self.protocol_sha,
                    map_id=self.map.map_id if active_map else None,candidate_map_exists=active_map,qualified_M0=boundary,static_boundary_available=boundary,
                    effective_growth=boundary and self.variant!='no_growth',boundary_reason='FINITE_STATIC' if boundary else 'DISABLED_NO_QUALIFIED_STATIC_BOUNDARY',
                    ground=ground,
                    capabilities=dict(strong_free=False,strong_occlusion=False),candidates=candidates,rejected_unknown_objects=rejected,track=track,
                    local_map_conflicts=conflicts,local_map_conflict_rows=local_rows.tolist(),
                    accounting=dict(raw=len(p),valid=int(valid.sum()),invalid=int((~valid).sum()),ledger_rows=len(rows),labels=dict(zip(LABELS,map(int,counts))),
                                    candidate_member_rows=int((candidate_id>=0).sum()),measured_target=track['measured_count']),
                    global_map_status='UNKNOWN_NO_LAYOUT_OR_ANCHOR_AUDIT',development_seen=True,dev_tainted=True,no_physical_ground_conclusion=True)
        self.last['candidates']=copy.deepcopy(candidates)
        return record,rows,hits

    def measure(self,f,c):
        self.track.update(last_measured_ns=f['time_ns'],center=np.asarray(c['center']),min=np.asarray(c['min']),max=np.asarray(c['max']))

    def track_record(self,f,c):
        if not self.track:return dict(state='UNCONFIRMED',rows=[],measured_count=0,center=None,last_measured_ns=None,prediction_age_s=None,track_id=None)
        age=(f['time_ns']-self.track['last_measured_ns'])/1e9
        state='MEASURED' if c else 'PREDICTED' if age<=self.cfg['ttl_s'] else 'LOST'
        provenance=self.track['identity_source']['provenance']
        return dict(state=state,rows=c['rows'] if c else [],measured_count=c['count'] if c else 0,center=self.track['center'].tolist() if state!='LOST' else None,
                    last_measured_ns=self.track['last_measured_ns'],prediction_age_s=age,track_id='ai-reviewed-1' if provenance=='AI_VISUAL_REVIEW' else 'manual-1',
                    identity_source=self.track['identity_source'],human_confirmation=provenance=='HUMAN_CONFIRMATION',
                    quality=c['quality'] if c else 'NO_CURRENT_MEMBERS',
                    identity_claim='AMBIGUOUS_REVIEWED_OBJECT' if c and c['quality']=='mixed/ambiguous' else 'AI_REVIEWED_OBJECT_NOT_GT' if provenance=='AI_VISUAL_REVIEW' else 'REVIEWED_OBJECT')

    def confirm(self,f,r,request,ledger=None):
        if self.variant=='no_identity':raise ValueError('Identity factor disabled')
        for key in ['sid','fi','time_ns','source_sha256','coordinate_version']:
            if request.get(key)!=f[key]:raise ValueError('Wrong confirmation source/time/coordinate')
        if (not self.last or self.last['fi']!=f['fi'] or self.last['time']!=f['time_ns'] or
            self.last['binding']!=(f['sid'],f['source_sha256'],f['coordinate_version']) or
            any(r.get(k)!=f[k] for k in ['sid','fi','time_ns','source_sha256','coordinate_version'])):raise ValueError('Expired confirmation')
        if request.get('run_version')!=self.run_version or request.get('protocol_sha')!=self.protocol_sha:raise ValueError('Wrong run/protocol confirmation')
        provenance=request.get('provenance')
        ai_review=(provenance=='AI_VISUAL_REVIEW' and request.get('human_confirmation') is False and
                   request.get('user_delegation_evidence') and request.get('visual_review_evidence') and request.get('evidence_verified') is True)
        if provenance!='HUMAN_CONFIRMATION' and not ai_review and not (f['kind']=='SYNTHETIC' and provenance=='SYNTHETIC_SIMULATED_CONFIRMATION'):raise ValueError('Actual human or explicitly user-delegated AI review required')
        if not isinstance(request.get('reviewer'),str) or not request['reviewer'].strip() or self.track:raise ValueError('Invalid reviewer or duplicate confirmation')
        c=next((c for c in self.last['candidates'] if c['version']==request.get('candidate_version')),None)
        if c is None:raise ValueError('Wrong candidate/config/run/map version')
        self.track=dict(identity_source=copy.deepcopy(request));self.measure(f,c)
        r['track']=self.track_record(f,c)
        r['accounting']['measured_target']=c['count']
        if ledger is not None:
            ledger['flags'][c['rows']] |= 16
            ambiguous=np.asarray(c['rows'],dtype=int)[(ledger['flags'][c['rows']]&2)!=0]
            ledger['label'][ambiguous]=5
            r['accounting']['labels']=dict(zip(LABELS,map(int,np.bincount(ledger['label'],minlength=len(LABELS)))))
