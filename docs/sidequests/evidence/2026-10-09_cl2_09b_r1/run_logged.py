import subprocess,sys
from prepare import E,save
name=sys.argv[1];argv=[sys.executable,'-X','utf8','-B','-W','error',str(E/(name+'.py'))]
with (E/(name+'.stdout')).open('xb') as out,(E/(name+'.stderr')).open('xb') as err:
    p=subprocess.run(argv,cwd=E,stdout=out,stderr=err)
save(name+'_command.json',dict(argv=argv,cwd=str(E),exit_code=p.returncode))
print(name,p.returncode,flush=True);raise SystemExit(p.returncode)
