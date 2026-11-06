"""Publish real synthetic CLI outputs and receipts, after independent answer and path checks."""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from distribution import ROOT,SOURCE,NAME,digest,publish_files,snapshot
from smoke_archive import _run,_delivery,_oracle

CASES=('commerce','inventory','training','administration','release-cases/negative-delta')
PRIVATE=re.compile(r'(?i)(/users/|/home/|/private/var/|/var/folders/|/tmp/|\b[a-z]:[\\/]+|wbSeedToken|accountSnapshot|Bearer\s+\S+|sk-[a-z0-9]{12,})')


def _json(path):return json.loads(path.read_text(encoding='utf-8'))


def _strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for key,item in value.items():yield str(key);yield from _strings(item)
    elif isinstance(value,list):
        for item in value:yield from _strings(item)


def audit_public_tree(folder):
    """Known path/token marker check only; synthetic-data review is still required."""
    checked=0; expanded=0
    for path in sorted(Path(folder).rglob('*')):
        if path.is_symlink():raise ValueError('Public examples cannot contain links')
        if path.is_dir():continue
        if not path.is_file() or path.stat().st_size>50*1024*1024:raise ValueError('Unexpected or oversized public file')
        checked+=1
        if path.suffix=='.xlsx':
            with zipfile.ZipFile(path) as z:
                if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('Public office archive expanded budget exceeded')
                texts=[]
                for member in z.infolist():
                    if member.filename.endswith(('.xml','.rels')):
                        raw=z.read(member);expanded+=len(raw)
                        element=ET.fromstring(raw)
                        texts.extend(element.itertext())
                        texts.extend(v for e in element.iter() for v in e.attrib.values())
        elif path.suffix in ('.json','.jsonl'):
            raw=path.read_text(encoding='utf-8')
            values=[json.loads(line) for line in raw.splitlines()] if path.suffix=='.jsonl' else [json.loads(raw)]
            texts=[text for value in values for text in _strings(value)]
        elif path.suffix=='.md':texts=[path.read_text(encoding='utf-8')]
        else:raise ValueError('Unsupported public example resource: '+path.name)
        if any(PRIVATE.search(text) for text in texts):raise ValueError('Private path or token marker in public example: '+path.name)
    return {'passed':True,'files_checked':checked,'office_xml_bytes_checked':expanded,'scope':'Known developer path/token markers plus synthetic-source review; not a general PII detector'}


def _frozen():
    originals=_json(ROOT/'examples/manifest.json')['files']
    if not all(digest((ROOT/f['path']).read_bytes())==f['sha256'] for f in originals):raise ValueError('M1 frozen file changed')
    release=ROOT/'releases/0.1.0';manifest=_json(release/'manifest.json')
    for item in manifest['packages']:
        if digest((release/item['archive']).read_bytes())!=item['sha256']:raise ValueError('M5 archive changed')
    standard=manifest['packages'][0]
    with zipfile.ZipFile(release/standard['archive']) as z:
        for name,data in snapshot()[0].items():
            if z.read(NAME+'/'+name)!=data:raise ValueError('Skill source changed from accepted M5 release')


def prepare(output):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('Public output already exists; refusing overwrite')
    for protected in [SOURCE,ROOT/'releases',*[ROOT/'examples'/c for c in CASES]]:
        if output.resolve()==protected or protected in output.resolve().parents:raise ValueError('Showcase output overlaps protected source/release')
    _frozen();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.showcase-',dir=output.parent) as tmp:
        stage=Path(tmp).resolve(); cases=[]
        for case in CASES:
            rules_path=ROOT/'examples'/case/'rules.json';rules=_json(rules_path);target=stage/Path(case).name
            auth=[value for source in rules['sources'] for value in ('--authorize',str((rules_path.parent/source['path']).resolve()))]
            expected=0 if case.endswith('negative-delta') else 2
            summary=_run(Path(sys.executable),SOURCE/'scripts/reconcile_tool.py',['run','--rules',rules_path,'--output',target,*auth],stage,expected)
            receipt=_delivery(target);tasks=_oracle(target,case)
            cases.append({'case':Path(case).name,'input_rules':rules_path.relative_to(ROOT).as_posix(),'status':summary['status'],'tasks':tasks,'delivery_files':len(receipt['files'])+1,'receipt_sha256':digest((target/'交付清单.json').read_bytes())})
        _frozen();audit=audit_public_tree(stage)
        names=sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file())
        files=[{'path':name,'bytes':(stage/name).stat().st_size,'sha256':digest((stage/name).read_bytes())} for name in names]
        result={'stage':'M6','skill_version':'0.1.0','passed':True,'synthetic':True,'case_tasks':sum(len(c['tasks']) for c in cases),'cases':cases,'files':files,'audit':audit,'m1_originals_unchanged':True,'m5_packages_unchanged':True}
        (stage/'showcase-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        audit_public_tree(stage)
        publish_files(stage,names+['showcase-manifest.json'],output)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:result=prepare(args.output)
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=True));return 1
    print(json.dumps({k:result[k] for k in ('stage','passed','case_tasks','m1_originals_unchanged','m5_packages_unchanged')},ensure_ascii=True));return 0


if __name__=='__main__':raise SystemExit(main())
