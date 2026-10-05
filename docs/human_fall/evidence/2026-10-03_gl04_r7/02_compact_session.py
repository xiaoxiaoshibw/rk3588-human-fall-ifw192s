import datetime,json,pathlib,time,urllib.request,urllib.parse
out=pathlib.Path(__file__).parent
session='ses_f01ba3f48ffepSrGKkcHrb3onk'
query=urllib.parse.urlencode({'directory':'D:/Code/ldiar'})
url='http://127.0.0.1:18092/session/'+session+'/summarize?'+query
start=time.monotonic()
body={'providerID':'opencode-go','modelID':'deepseek-v4.1-flash'}
record={'session':session,'body':body,'start':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()}
try:
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=300) as res:
        record.update(http_status=res.status,response=res.read().decode())
except Exception as e: record['error']=str(e)
record.update(elapsed_s=time.monotonic()-start,end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat())
(out/'04_compaction_result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
raise SystemExit(1 if 'error' in record else 0)
