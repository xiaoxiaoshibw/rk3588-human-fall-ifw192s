"""Reuse the audited range downloader, isolating all new evidence and data."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import requests


def run(env, evidence, destination, freeze):
    if not freeze.is_file():
        raise ValueError('E01 freeze must exist before independent-environment acquisition')
    evidence.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    prior=Path('docs/evidence/2026-10-22_public_lidar_training/mmfi_download.py')
    spec=importlib.util.spec_from_file_location('audited_mmfi_download',prior)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.HERE=evidence.resolve()
    original=module.RangeFile

    class CheckedRangeFile(original):
        def __init__(self,url):
            self.url,self.pos,self.downloaded=url,0,0
            with requests.get(url+'&causal_probe=1',headers={'Range':'bytes=0-0'},timeout=45) as r:
                r.raise_for_status()
                content_range=r.headers.get('Content-Range','')
                if r.status_code!=206 or len(r.content)!=1 or not content_range.startswith('bytes 0-0/'):
                    raise ValueError('Server did not honor exact HTTP Range')
                self.size=int(content_range.split('/')[-1])
                (evidence/(env+'_HTTP_PROBE.json')).write_text(json.dumps({'status':r.status_code,
                    'content_range':content_range,'bytes':len(r.content),'url':url}),encoding='utf-8')
    module.RangeFile=CheckedRangeFile
    source,members=module.inventory(env)
    required=sum(m.file_size+len(m.filename)*2+256 for m in members)+512*1024**2
    free=shutil.disk_usage(destination).free
    (evidence/(env+'_DISK.json')).write_text(json.dumps({'free_bytes':free,'required_bytes':required,
        'source_archive_bytes':source.size,'freeze_path':str(freeze)}),encoding='utf-8')
    if free<required:raise OSError('Insufficient disk space')
    module.download(env,destination)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--env',default='E02',choices=['E02','E03','E04'])
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    run(a.env,a.evidence,a.destination,a.freeze)
