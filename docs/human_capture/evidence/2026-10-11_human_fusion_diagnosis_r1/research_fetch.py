"""Public primary metadata/source downloads; never run upstream code."""
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
OUT=Path(__file__).resolve().parent/"research"
OUT.mkdir(exist_ok=False)

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"HUMAN-FUSION-read-only-research/1.0"})
    with urllib.request.urlopen(req,timeout=25) as r:return r.read()

def save(name,body):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("xb") as f:f.write(body)

repos={
 "koide3/hdl_people_tracking":["background_subtractor.hpp","person_classifier.hpp","hdl_people_detection_nodelet.cpp"],
 "nilushacj/O-LiPeDeT-Overhead-LiDAR-Person-Detection-and-Tracking":["train.py","voxelnext_crane.yaml","pointpillars_crane.yaml"],
 "baberjunaid/LiDAR_Tracking_3D":["Track_3D.cpp","tracking.cpp","package.xml"],
 "4DVLab/LiveHPS":["models.py","test.py"],
 "charlesq34/pointnet2":["pointnet2_cls_msg.py","pointnet_util.py"],
 "thkreutz/umosmots":["README.md"],
 "tusen-ai/SimpleTrack":["association.py","config.md"],
}
manifest=[]
for repo,wanted in repos.items():
    row={"repo":repo,"url":"https://github.com/"+repo,"files":[]}
    try:
        meta=json.loads(get("https://api.github.com/repos/"+repo));branch=meta["default_branch"]
        commit=json.loads(get("https://api.github.com/repos/"+repo+"/commits/"+branch));head=commit["sha"]
        tree=json.loads(get("https://api.github.com/repos/"+repo+"/git/trees/"+head+"?recursive=1"))
        row.update(head=head,license=meta.get("license"),last_commit=commit["commit"]["committer"]["date"],tree_truncated=tree.get("truncated"))
        prefix=Path(repo.replace("/","__"));save(prefix/"tree.json",json.dumps(tree,indent=2).encode())
        paths=[t["path"] for t in tree["tree"] if t["type"]=="blob"]
        chosen=[p for p in paths if any(p.endswith(w) for w in wanted)]
        if repo=="baberjunaid/LiDAR_Tracking_3D":chosen+= [p for p in paths if p.endswith(".cpp")][:2]
        if repo=="thkreutz/umosmots":chosen+= [p for p in paths if p.endswith(".py")][:2]
        for p in sorted(set(chosen))[:5]:
            url="https://raw.githubusercontent.com/"+repo+"/"+head+"/"+p
            try:
                body=get(url);save(prefix/p,body)
                row["files"].append({"path":p,"url":url,"sha256":hashlib.sha256(body).hexdigest(),"bytes":len(body)})
            except Exception as e:row["files"].append({"path":p,"error":str(e)})
    except Exception as e:row["error"]=str(e)
    manifest.append(row);print(repo,row.get("head"),[f["path"] for f in row["files"]],row.get("error"),flush=True)
for doi in ["10.1080/01691864.2022.2126732","10.3390/s23104781"]:
    url="https://api.crossref.org/works/"+urllib.parse.quote(doi,safe="")
    try:
        body=get(url);save("crossref_"+doi.replace("/","_")+".json",body)
        doc=json.loads(body);print("Crossref",doi,doc["message"].get("title"),flush=True)
        manifest.append({"database":"Crossref","endpoint":url,"doi":doi,"title":doc["message"].get("title"),"sha256":hashlib.sha256(body).hexdigest()})
    except Exception as e:manifest.append({"database":"Crossref","endpoint":url,"error":str(e)});print("Crossref",doi,str(e),flush=True)
save("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2).encode("utf-8"))
