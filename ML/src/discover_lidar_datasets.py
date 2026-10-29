"""Source-preserving public dataset access checks; never accepts agreements or emails authors."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import tarfile
from urllib.parse import urljoin
import requests

SOURCES={
 'laseract':'https://raphaelmemmesheimer.github.io/laseract/',
 'laseract_sha':'https://laseract.onwai.eu/data/SHA256SUMS',
 'hmpear':'https://www.lidarhumanmotion.net/hmpear/',
 'freemotion':'https://4dvlab.github.io/project_page/LiveHPS.html',
 'freemotion_drive':'https://drive.google.com/drive/folders/1BRpczJHyzte4NNTrTZVHzU6MZu4hTbAz',
 'lidarhuman26m':'https://raw.githubusercontent.com/jingyi-zhang/LiDARCap/master/README.md',
 'ntu120':'https://raw.githubusercontent.com/shahroudy/NTURGB-D/master/README.md',
}


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            url=dict(attrs).get('href')
            if url:self.links.append(url)


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def run(out,destination):
    out.mkdir(parents=True,exist_ok=False);destination.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        name,url=item
        try:
            with requests.get(url,timeout=25) as r:
                payload=r.content
                (out/(name+'.response')).write_bytes(payload)
                return {'name':name,'url':url,'final_url':r.url,'status':r.status_code,
                        'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
                        'content_type':r.headers.get('Content-Type'),'content_length':r.headers.get('Content-Length')}
        except requests.RequestException as exc:return {'name':name,'url':url,'error':str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:checks=list(pool.map(fetch,SOURCES.items()))
    (out/'ACCESS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    page=(out/'laseract.response').read_text(encoding='utf-8');parser=Links();parser.feed(page)
    urls=[urljoin(SOURCES['laseract'],u) for u in parser.links]
    core=next(u for u in urls if u.endswith('/laseract_core.tar'))
    person=next(u for u in urls if u.endswith('/laseract_person.tar'))
    sums=(out/'laseract_sha.response').read_text(encoding='utf-8')
    expected={line.split()[-1].lstrip('*'):line.split()[0] for line in sums.splitlines() if len(line.split())==2}
    (out/'DOWNLOAD_LINKS.json').write_text(json.dumps({'core':core,'person':person,'expected_sha256':expected},indent=2),encoding='utf-8')
    target=destination/'laseract_core.tar';h=hashlib.sha256()
    with requests.get(core,stream=True,timeout=45) as r:
        r.raise_for_status()
        if shutil.disk_usage(destination).free<100*1024**2:raise OSError('Disk space')
        with target.open('xb') as f:
            for block in r.iter_content(1024*1024):f.write(block);h.update(block)
    assert h.hexdigest()==expected[target.name], 'Author core SHA mismatch'
    members=[];text_members=[]
    with tarfile.open(target,'r:') as tar:
        for m in tar:
            members.append({'path':m.name,'bytes':m.size,'regular_file':m.isfile()})
            if m.isfile() and m.size<2*1024**2 and any(word in m.name.lower() for word in ['license','datasheet','label','split','readme']):
                f=tar.extractfile(m)
                if f is not None:
                    with f:raw=f.read()
                    local='core_'+m.name.replace('/','_').replace('\\','_')
                    (out/local).write_bytes(raw);text_members.append(local)
    (out/'CORE_AUDIT.json').write_text(json.dumps({'path':str(target),'sha256':h.hexdigest(),
         'author_sha_match':True,'bytes':target.stat().st_size,'members':members,'inspection_files':text_members},indent=2),encoding='utf-8')
    print('source checks',checks,flush=True);print('core verified',target.stat().st_size,'bytes',len(members),'members',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True);a=p.parse_args();run(a.output,a.destination)
