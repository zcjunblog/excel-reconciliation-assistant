"""Reproducible standard/WorkBuddy archives; completed manifest published last."""
import argparse
import json
from pathlib import Path
import tempfile
import zipfile
from distribution import ROOT,SOURCE,NAME,snapshot,_parse_info,workbuddy_entry,digest,publish_files,package_payloads


def build(out=None):
    payloads,version=snapshot(); fields,body,_=_parse_info(payloads['SKILL.md'].decode('utf-8'),payloads['VERSION'].decode('utf-8'))
    target=Path(out) if out is not None else ROOT/'releases'/version
    if target.exists() or target.is_symlink(): raise ValueError('Release output already exists; refusing overwrite')
    target=target.absolute()
    if target.resolve()==SOURCE or SOURCE in target.resolve().parents: raise ValueError('Release output overlaps Skill source')
    profile_raw=(ROOT/'distribution/workbuddy.json').read_bytes(); profile=json.loads(profile_raw)
    buddy=workbuddy_entry(fields,body,version,profile)
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.skill-build-',dir=target.parent) as tmp:
        stage=Path(tmp).resolve(); packages=[]
        for kind in ('standard','workbuddy'):
            filename=NAME+('-workbuddy' if kind=='workbuddy' else '')+'-'+version+'.zip'; entries=[]
            with zipfile.ZipFile(stage/filename,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
                for name,original in package_payloads(payloads,kind).items():
                    data=buddy if kind=='workbuddy' and name=='SKILL.md' else original
                    info=zipfile.ZipInfo(NAME+'/'+name,(2026,11,6,0,0,0)); info.create_system=3
                    info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644<<16
                    archive.writestr(info,data)
                    entries.append({'path':name,'bytes':len(data),'sha256':digest(data)})
            with zipfile.ZipFile(stage/filename) as archive:
                if archive.testzip() is not None: raise ValueError('Archive integrity check failed')
            raw=(stage/filename).read_bytes()
            packages.append({'profile':kind,'archive':filename,'bytes':len(raw),'sha256':digest(raw),'files':entries})
        manifest={'schema_version':'1.0','name':NAME,'version':version,'packages':packages}
        (stage/'SHA256SUMS').write_text(''.join(p['sha256']+'  '+p['archive']+'\n' for p in packages),encoding='utf-8')
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if snapshot()[0]!=payloads or (ROOT/'distribution/workbuddy.json').read_bytes()!=profile_raw: raise ValueError('Skill source changed during build')
        directory=publish_files(stage,[p['archive'] for p in packages]+['SHA256SUMS','manifest.json'],target)
    return {'version':version,'directory':str(directory),'packages':[{k:v for k,v in p.items() if k!='files'} for p in packages]}


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path)
    try: result=build(parser.parse_args().out)
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=True)); return 1
    print(json.dumps(result,ensure_ascii=True)); return 0


if __name__=='__main__': raise SystemExit(main())
