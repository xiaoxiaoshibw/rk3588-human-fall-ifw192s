import datetime
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

OUT = Path(__file__).parent
BASE = 'http://127.0.0.1:18094/session/ses_eff575a5affevftT6g3Dzvg05e/'
QUERY = '?' + urllib.parse.urlencode({'directory': 'D:/Code/ldiar'})
if (OUT / '10_compact_meta.json').exists():
    raise SystemExit('No evidence overwrite')
start = time.monotonic()
meta = {'start': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'session': 'ses_eff575a5affevftT6g3Dzvg05e', 'providerID': 'opencode-go',
        'modelID': 'deepseek-v4.1-flash', 'db': 'default'}
try:
    data = json.dumps({'providerID': 'opencode-go', 'modelID': 'deepseek-v4.1-flash'}).encode()
    request = urllib.request.Request(BASE+'summarize'+QUERY, data=data,
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=55) as response:
        meta.update(http=response.status, response=json.load(response))
except Exception as error:
    meta['error'] = str(error)
meta['elapsed_s'] = time.monotonic() - start
(OUT / '10_compact_meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
messages = json.load(urllib.request.urlopen(BASE+'message'+QUERY, timeout=10))
(OUT / '10_compact_messages.json').write_text(json.dumps(messages, ensure_ascii=False), encoding='utf-8')
summaries = [item['info'] for item in messages if item.get('info', {}).get('summary')]
meta['summaries'] = [{key: info.get(key) for key in ('id','summary','finish','modelID','providerID','error')} for info in summaries]
(OUT / '10_compact_verified.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
print(json.dumps(meta))


