"""Verified range download into a NEW archive; original files are never replaced."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import requests


def run(url,expected,destination,evidence,workers=6,chunk_mib=8,prefix_source=None,prefix_bytes=0):
    if not 1 <= workers <= 32 or not 1 <= chunk_mib <= 32 or prefix_bytes < 0:
        raise ValueError('Invalid download concurrency/chunk/prefix')
    with requests.get(url,headers={'Range':'bytes=0-0'},timeout=45) as r:
        r.raise_for_status();header=r.headers.get('Content-Range','')
        if r.status_code!=206 or len(r.content)!=1 or not header.startswith('bytes 0-0/'):
            raise ValueError('Server must honor exact HTTP byte ranges')
        size=int(header.split('/')[-1])
    free=shutil.disk_usage(destination.parent).free
    if free<size+1024**3:raise OSError('Insufficient disk space')
    if prefix_bytes > size or (prefix_bytes and prefix_source is None):raise ValueError('Invalid prefix source')
    chunks=[(start,min(start+chunk_mib*1024**2,size)-1) for start in range(prefix_bytes,size,chunk_mib*1024**2)]
    lock=threading.Lock();done=[];started=time.time()
    with destination.open('xb') as f:
        f.truncate(size)
        if prefix_bytes:
            digest=hashlib.sha256();remaining=prefix_bytes
            with prefix_source.open('rb') as prior:
                while remaining:
                    block=prior.read(min(1024**2,remaining))
                    if not block:raise ValueError('Truncated prefix source')
                    f.write(block);digest.update(block);remaining-=len(block)
            f.flush()
            (evidence/'PREFIX.json').write_text(json.dumps({'source':str(prefix_source),'bytes':prefix_bytes,
                'local_sha256':digest.hexdigest(),'status':'partial bytes only; not accepted until complete author SHA matches'}),encoding='utf-8')
        def job(pair):
            lo,hi=pair
            for attempt in range(4):
                try:
                    with requests.get(url,headers={'Range':'bytes=%d-%d'%(lo,hi)},timeout=90) as r:
                        r.raise_for_status();payload=r.content
                        if r.status_code!=206 or r.headers.get('Content-Range')!='bytes %d-%d/%d'%(lo,hi,size) or len(payload)!=hi-lo+1:
                            raise ValueError('Range response mismatch')
                    with lock:
                        f.seek(lo);f.write(payload);done.append(pair)
                        f.flush()
                        with (evidence/'CHUNKS.jsonl').open('a',encoding='utf-8') as ledger:
                            ledger.write(json.dumps({'begin':lo,'end_inclusive':hi,'sha256':hashlib.sha256(payload).hexdigest()})+'\n')
                        (evidence/'ARCHIVE_PROGRESS.json').write_text(json.dumps({'completed_chunks':len(done),'total_chunks':len(chunks),
                            'downloaded_bytes':prefix_bytes+sum(b-a+1 for a,b in done),'total_bytes':size,'prefix_bytes':prefix_bytes}),encoding='utf-8')
                    return len(payload)
                except (requests.RequestException,ValueError):
                    if attempt==3:raise
                    time.sleep(attempt+1)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i,_ in enumerate(pool.map(job,chunks)):
                if i%32==0:print('archive chunks',i+1,'/',len(chunks),flush=True)
    with destination.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    record={'url':url,'path':str(destination),'bytes':size,'sha256':actual,'author_sha256':expected,
            'sha_match':actual==expected,'disk_free_before':free,'started_unix_s':started,'elapsed_s':time.time()-started,
            'range_probe':header,'download_chunks':len(chunks),'workers':workers,'chunk_mib':chunk_mib,'prefix_bytes':prefix_bytes}
    (evidence/'ARCHIVE_DOWNLOAD.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    if actual!=expected:raise ValueError('Author SHA256 mismatch; keep failed archive isolated')
    print('download verified',json.dumps(record),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--destination',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6);p.add_argument('--chunk-mib',type=int,default=8)
    p.add_argument('--prefix-source',type=Path);p.add_argument('--prefix-bytes',type=int,default=0)
    a=p.parse_args();run(a.url,a.sha256,a.destination,a.evidence,a.workers,a.chunk_mib,a.prefix_source,a.prefix_bytes)
