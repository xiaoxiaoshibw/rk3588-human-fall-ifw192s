"""Collect the v2/cross-environment/multi-environment numbers into one comparison file."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCES={
 'e01_deep_v2':('mmfi_deep256/SUMMARY.json',('scores',)),
 'e02_deep_v2':('cross_e02/E02_deep256_EVAL.json',('scores',)),
 'e03_deep_v2':('cross_e03/E03_deep256_EVAL.json',('scores',)),
 'e04_deep_v2':('cross_e04/E04_deep256_EVAL.json',('scores',)),
 'e03_rf_e01':('cross_e03_rf/E03_rf30_EVAL.json',('scores',)),
 'e04_rf_e01':('cross_e04_rf/E04_rf30_EVAL.json',('scores',)),
 'e04_deep_multi':('multi_e123_to_e04/MULTI_SUMMARY.json',('splits','test')),
 'e04_rf_multi':('rf_multi_e123_to_e04/RF_MULTI_SUMMARY.json',('scores',)),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric(scores):
    return {k:{s:scores[k][s] for s in ('accuracy','macro_f1')} for k in ('window','sequence_mean_probability')}


def run(root,out):
    rows={}
    for name,(rel,path) in SOURCES.items():
        value=json.loads((root/rel).read_text(encoding='utf-8'))
        for key in path:value=value[key]
        if name=='e04_deep_multi':
            rows[name]={'window':{'accuracy':value['accuracy'],'macro_f1':value['macro_f1']},
                        'sequence_mean_probability':{'accuracy':value['sequence_accuracy'],'macro_f1':value['sequence_macro_f1']}}
        else:
            rows[name]=metric(value)
        rows[name]['source']=str(root/rel);rows[name]['source_sha256']=sha(root/rel)
    out.write_text(json.dumps({'created':'2026-10-22','units':'inherited sequence action labels; window 30, stride 10',
        'chance_accuracy':round(1/27,6),'rows':rows,
        'prior_round':{'e01_rf30':{'window':{'accuracy':0.6328,'macro_f1':0.6265},
                                   'sequence_mean_probability':{'accuracy':0.6593,'macro_f1':0.6518},
                                   'source':'ML/docs/causal_lidar_20261022.md'},
                       'e02_rf30':{'window':{'accuracy':0.3578,'macro_f1':0.3193},
                                   'sequence_mean_probability':{'accuracy':0.3741,'macro_f1':0.3382},
                                   'source':'ML/docs/causal_lidar_20261022.md'},
                       'e01_deep_v1':{'window':{'accuracy':0.2410150891632373,'macro_f1':0.21904222014062316},
                                      'sequence_mean_probability':{'accuracy':0.31851851851851853,'macro_f1':0.2771473651599959},
                                      'source':'docs/evidence/2026-10-22_deep_lidar_sources/mmfi_deep/SUMMARY.json'}}},
        indent=2),encoding='utf-8')
    print(json.dumps({k:{m:(round(v[m]['accuracy'],4) if m in v else None) for m in ('window','sequence_mean_probability')} for k,v in rows.items()},indent=1))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.root,a.output)