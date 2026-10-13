"""Fixed CPU experiments on frozen candidate rows. No test tuning or production writes."""
from pathlib import Path
import json,time,hashlib,sys,os
os.environ['OMP_NUM_THREADS']='4'
import numpy as np, sklearn, xgboost, torch, psutil
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from torch import nn
LAB=Path(__file__).resolve().parent
PREFIX=os.environ.get('HF_MODEL_PREFIX',''); DATA=LAB/os.environ.get('HF_DATASET','results')
A=json.loads((LAB/'results/AUDIT.json').read_text(encoding='utf8')); rows=[]
for sid in sum(A['splits'].values(),[]):
 p=DATA/f'{sid}.jsonl'
 if p.exists():rows.extend(json.loads(s) for s in p.read_text(encoding='utf8').splitlines() if s.strip())
known=[r for r in rows if r['label'] is not None];train=[r for r in known if r['sid'] in A['splits']['train']]
assert train and len(set(r['label'] for r in train))==2
X=np.array([r['features']+r['extended'] for r in rows],np.float32);train_indices=[i for i,r in enumerate(rows) if r['label'] is not None and r['sid'] in A['splits']['train']];Xt=X[train_indices];y=np.array([rows[i]['label'] for i in train_indices])
# Weight correlated frames equally per session/class instead of pretending independence.
counts={};
for r in train:counts[(r['sid'],r['label'])]=counts.get((r['sid'],r['label']),0)+1
w=np.array([1/counts[(r['sid'],r['label'])] for r in train]);w=w/w.mean()
report={'versions':{'sklearn':sklearn.__version__,'xgboost':xgboost.__version__,'torch':torch.__version__},'train_counts':{'positive':int(y.sum()),'negative':int((y==0).sum())},'rows':len(rows),'known':len(known),'models':{},'holdout_status':A['holdout_status'],'GT_policy':A['candidate_label_policy'],'independent_furniture_test':'UNKNOWN','cross_actor_scene':'UNKNOWN','fixed_threshold':.55,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'candidate_files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.glob('*.jsonl')}}
def metric(rr,prob):
 if not len(rr):return {'status':'UNKNOWN','n':0}
 yy=np.array([r['label'] for r in rr]);hit=prob>=.55;tp=int(((yy==1)&hit).sum());fp=int(((yy==0)&hit).sum());fn=int(((yy==1)&~hit).sum());tn=int(((yy==0)&~hit).sum());return {'n':len(rr),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'recall':tp/(tp+fn) if tp+fn else 'UNKNOWN','precision':tp/(tp+fp) if tp+fp else 'UNKNOWN','furniture_FPR':fp/(fp+tn) if fp+tn else 'UNKNOWN'}
def metrics(prob):return {split:metric([r for r in rows if r['label'] is not None and r['sid'] in sids],prob[[i for i,r in enumerate(rows) if r['label'] is not None and r['sid'] in sids]]) for split,sids in A['splits'].items()}
report['models']['rf51_baseline']={'candidate_metrics':metrics(np.array([r['baseline_prob'] for r in rows])),'trained_this_run':False,'training_overlap_with_sessions':'UNKNOWN: legacy model provenance not independently reconstructed'}
def tree(t):return {'children_left':t.children_left.tolist(),'children_right':t.children_right.tolist(),'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),'value':t.value[:,0,:].tolist()}
parity={}
for original_name,dim in [('rf51_candidate',51),('rf69_candidate',69),('xgb69_candidate',69)]:
 name=PREFIX+original_name
 started=time.perf_counter();model=RandomForestClassifier(n_estimators=96,max_depth=8,min_samples_leaf=3,random_state=20261011,n_jobs=4) if original_name.startswith('rf') else XGBClassifier(n_estimators=96,max_depth=4,learning_rate=.08,tree_method='hist',n_jobs=4,random_state=20261011,eval_metric='logloss')
 model.fit(Xt[:,:dim],y,sample_weight=w);elapsed=time.perf_counter()-started;prob=model.predict_proba(X[:,:dim])[:,1];dur=[]
 for r in X[:100,:dim]:
  t=time.perf_counter();model.predict_proba(r.reshape(1,-1));dur.append((time.perf_counter()-t)*1000)
 if original_name.startswith('rf'):out={'kind':'rf','n_features':dim,'trees':[tree(e.tree_) for e in model.estimators_]}
 else:
  trees=[json.loads(t) for t in model.get_booster().get_dump(dump_format='json')]
  def leaf(t,x):
   while 'leaf' not in t:
    ix=int(t['split'].removeprefix('f'));n=t['yes'] if x[ix]<t['split_condition'] else t['no'];t=next(c for c in t['children'] if c['nodeid']==n)
   return t['leaf']
  pm=float(model.predict(Xt[:1,:dim],output_margin=True)[0]);base=pm-sum(leaf(t,Xt[0]) for t in trees);out={'kind':'xgb','n_features':dim,'base_margin':base,'trees':trees};model.save_model(LAB/'models'/(PREFIX+'xgb69_native.ubj'))
 out.update(threshold=.55,feature_contract='rf51+6_height_slices(count_fraction,xy_p10_p90_width)',training_source_sha256=report['source_sha256'])
 (LAB/'models'/f'{name}.json').write_text(json.dumps(out),encoding='utf8');parity[name]={'features':X[:200,:dim].tolist(),'prob':prob[:200].tolist()}
 report['models'][name]={'train_sec':elapsed,'candidate_metrics':metrics(prob),'single_candidate_python_p50_ms':float(np.percentile(dur,50)),'single_candidate_python_p95_ms':float(np.percentile(dur,95)),'serialized_bytes':(LAB/'models'/f'{name}.json').stat().st_size}
 print(name,elapsed,report['models'][name]['candidate_metrics'],flush=True)
(LAB/'results'/(PREFIX+'MODEL_PARITY_INPUT.json')).write_text(json.dumps(parity),encoding='utf8')
# Lightweight PointNet-style shared MLP + symmetric max, no learned T-Net. Shadow only.
torch.manual_seed(20261011);torch.set_num_threads(4)
class ShadowPointNet(nn.Module):
 def __init__(self):
  super().__init__();self.point=nn.Sequential(nn.Conv1d(3,32,1),nn.ReLU(),nn.Conv1d(32,64,1),nn.ReLU(),nn.Conv1d(64,128,1),nn.ReLU());self.head=nn.Sequential(nn.Linear(128,64),nn.ReLU(),nn.Linear(64,1))
 def forward(self,x):return self.head(self.point(x).amax(dim=2)).squeeze(1)
cloud=np.array([r['points'] for r in rows],np.float32);cloud-=cloud.mean(axis=1,keepdims=True);pc=torch.from_numpy(cloud.transpose(0,2,1).copy());net=ShadowPointNet();optim=torch.optim.Adam(net.parameters(),lr=.001);start=time.perf_counter();idx=torch.tensor(train_indices);yt=torch.tensor(y,dtype=torch.float32);wt=torch.tensor(w,dtype=torch.float32)
for epoch in range(20):
 perm=torch.randperm(len(idx))
 for b in perm.split(32):
  optim.zero_grad();loss=nn.functional.binary_cross_entropy_with_logits(net(pc[idx[b]]),yt[b],weight=wt[b]);loss.backward();optim.step()
net.eval();prob=[]
with torch.no_grad():
 for batch in pc.split(128):prob.extend(net(batch).sigmoid().numpy().tolist())
dur=[]
with torch.no_grad():
 for i in range(100):
  t=time.perf_counter();net(pc[i:i+1]);dur.append((time.perf_counter()-t)*1000)
torch.save(net.state_dict(),LAB/'models'/(PREFIX+'pointnet_shadow.pt'));onnx_status={}
try:
 torch.onnx.export(net,pc[:1],str(LAB/'models'/(PREFIX+'pointnet_shadow.onnx')),opset_version=13,input_names=['points'],output_names=['logit'],dynamic_axes={'points':{0:'batch'},'logit':{0:'batch'}},dynamo=False)
 import onnx,onnxruntime as ort
 onnx.checker.check_model(str(LAB/'models'/(PREFIX+'pointnet_shadow.onnx')));session=ort.InferenceSession(str(LAB/'models'/(PREFIX+'pointnet_shadow.onnx')),providers=['CPUExecutionProvider']);op=session.run(None,{'points':pc[:10].numpy()})[0]
 with torch.no_grad():np.testing.assert_allclose(op,net(pc[:10]).numpy(),rtol=1e-4,atol=1e-4)
 onnx_status={'cpu_export_parity':'PASS','operators':sorted({n.op_type for n in onnx.load(str(LAB/'models'/(PREFIX+'pointnet_shadow.onnx'))).graph.node}),'RKNN':'NOT_RUN','RK3588_latency':'UNKNOWN'}
except Exception as e:onnx_status={'status':'FAILED','reason':repr(e),'RKNN':'NOT_RUN'}
report['models']['pointnet_shadow']={'architecture':'shared Conv1d MLP 3/32/64/128 + max + 64/1; inspired by PointNet, not official reproduction','train_epochs':20,'train_sec':time.perf_counter()-start,'parameters':sum(p.numel() for p in net.parameters()),'candidate_metrics':metrics(np.array(prob)),'p50_ms':float(np.percentile(dur,50)),'p95_ms':float(np.percentile(dur,95)),'onnx':onnx_status,'integration':'SHADOW_ONLY'}
report['rss_at_report_mb']=psutil.Process().memory_info().rss/1048576
(LAB/'results'/(PREFIX+'TRAIN_REPORT.json')).write_text(json.dumps(report,indent=2),encoding='utf8');print('DONE',report['rss_at_report_mb'],flush=True)
