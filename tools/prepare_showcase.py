"""Publish real synthetic CLI outputs and receipts, after independent answer and path checks."""
import argparse
import copy
import shutil
import subprocess
import uuid
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from distribution import ROOT,SOURCE,NAME,digest,DeliveryGuard,snapshot
from smoke_archive import _run,_delivery,_oracle
from common import IntakeError

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
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir():raise ValueError('Public audit requires a real directory')
    checked=0; expanded=0
    for path in sorted(folder.rglob('*')):
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
    if not checked:raise ValueError('Public audit requires a nonempty directory')
    return {'passed':True,'files_checked':checked,'office_xml_bytes_checked':expanded,'scope':'Known developer path/token markers plus synthetic-source review; not a general PII detector'}


def _regular_relative(relative):
    relative=Path(relative)
    if relative.is_absolute() or '..' in relative.parts:raise ValueError('Fixture path escaped the approved repository')
    current=ROOT
    for part in relative.parts:
        current=current/part
        if current.is_symlink():raise ValueError('Approved fixtures cannot contain file or ancestor symlinks')
    if not current.is_file():raise ValueError('Approved fixture is not a regular file')
    return current


def _approved_bytes(relative,approved):
    name=Path(relative).as_posix()
    if name not in approved:raise ValueError('Source is outside the approved synthetic resource set')
    item=approved[name];path=_regular_relative(name)
    if path.stat().st_size!=item['bytes']:raise ValueError('Frozen fixture size changed')
    with path.open('rb') as stream:raw=stream.read(item['bytes']+1)
    if len(raw)!=item['bytes'] or digest(raw)!=item['sha256']:raise ValueError('Frozen fixture digest changed')
    return raw


def _frozen():
    originals=_json(_regular_relative('examples/manifest.json'))['files']
    extra=_json(_regular_relative('examples/release-cases/manifest.json'))
    wanted={'examples/release-cases/negative-delta/'+n for n in ('rules.json','expected.json','基准清单.csv','比较清单.csv')}
    if extra.get('synthetic') is not True or {v['path'] for v in extra['files']}!=wanted or len(extra['files'])!=4:
        raise ValueError('M6 synthetic resource inventory changed')
    approved={v['path']:v for v in [*originals,*extra['files']]}
    if len(approved)!=len(originals)+4:raise ValueError('Duplicate fixture inventory entries')
    for name in approved:_approved_bytes(name,approved)
    release=ROOT/'releases/0.1.0';manifest=_json(release/'manifest.json')
    for item in manifest['packages']:
        if digest((release/item['archive']).read_bytes())!=item['sha256']:raise ValueError('M5 archive changed')
    standard=manifest['packages'][0]
    with zipfile.ZipFile(release/standard['archive']) as z:
        for name,data in snapshot()[0].items():
            if z.read(NAME+'/'+name)!=data:raise ValueError('Skill source changed from accepted M5 release')
    return approved


def _registered_sources(folder,rules,expected):
    registered=_json(folder/'工作资料/来源索引.json')
    if len(registered)!=len(expected) or {v['id'] for v in registered}!=set(expected):raise ValueError('Registered source set differs from approved inputs')
    for source in registered:
        item=expected[source['id']]
        if source['registered'] is not True or source['sha256']!=item['sha256'] or source['bytes']!=item['bytes'] or source['name']!=Path(item['path']).name:
            raise ValueError('Registered source differs from approved synthetic bytes')
    wanted=copy.deepcopy(rules)
    for source in wanted['sources']:source['path']=Path(source['path']).name
    if _json(folder/'工作资料/核对规则.json')['rules']!=wanted:raise ValueError('Executed rules differ from reviewed rules')


def _check_destination(guard,records):
    expected={v['path'] for v in records};directories={p.as_posix() for name in expected for p in Path(name).parents if p!=Path('.')}
    files=set();dirs=set()
    for path in guard.root.rglob('*'):
        name=path.relative_to(guard.root).as_posix()
        if path.is_symlink():raise ValueError('Unexpected link in public destination')
        if path.is_dir():dirs.add(name)
        elif path.is_file():files.add(name)
        else:raise ValueError('Unexpected public destination file type')
    if files!=expected or dirs!=directories:raise ValueError('Public destination resource set changed')
    for item in records:
        guard.validate(item['path']);path=guard.root/item['path']
        if path.stat().st_size!=item['bytes'] or digest(path.read_bytes())!=item['sha256']:raise ValueError('Public destination differs from audited bytes')
    audit_public_tree(guard.root)


def _publish_reviewed(stage,records,output,manifest):
    guard=DeliveryGuard(output,stage,uuid.uuid4().hex)
    try:
        for item in records:
            with (stage/item['path']).open('rb') as source,guard.open(item['path']) as target:shutil.copyfileobj(source,target)
        _check_destination(guard,records)
        guard.publish_entry('showcase-manifest.json',manifest)
        _check_destination(guard,[*records,{'path':'showcase-manifest.json','bytes':len(manifest),'sha256':digest(manifest)}])
    except BaseException:
        guard.cleanup();raise


def prepare(output):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('Public output already exists; refusing overwrite')
    for protected in [SOURCE,ROOT/'releases',*[ROOT/'examples'/c for c in CASES]]:
        if output.resolve()==protected or protected in output.resolve().parents:raise ValueError('Showcase output overlaps protected source/release')
    approved=_frozen();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.showcase-',dir=output.parent) as tmp:
        stage=Path(tmp).resolve(); cases=[]
        for case in CASES:
            rules_path=ROOT/'examples'/case/'rules.json';rules=json.loads(_approved_bytes(rules_path.relative_to(ROOT),approved));target=stage/Path(case).name
            auth=[];expected_sources={}
            for source in rules['sources']:
                if Path(source['path']).is_absolute():raise ValueError('Example rules cannot authorize an absolute source')
                relative=(rules_path.parent/source['path']).relative_to(ROOT).as_posix()
                _approved_bytes(relative,approved);path=_regular_relative(relative)
                expected_sources[source['id']]=approved[relative]
                auth.extend(['--authorize',str(path.resolve())])
            expected=0 if case.endswith('negative-delta') else 2
            summary=_run(Path(sys.executable),SOURCE/'scripts/reconcile_tool.py',['run','--rules',rules_path,'--output',target,*auth],stage,expected)
            receipt=_delivery(target);_registered_sources(target,rules,expected_sources);tasks=_oracle(target,case)
            cases.append({'case':Path(case).name,'input_rules':rules_path.relative_to(ROOT).as_posix(),'status':summary['status'],'tasks':tasks,'delivery_files':len(receipt['files'])+1,'receipt_sha256':digest((target/'交付清单.json').read_bytes())})
        _frozen();audit=audit_public_tree(stage)
        names=sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file())
        files=[{'path':name,'bytes':(stage/name).stat().st_size,'sha256':digest((stage/name).read_bytes())} for name in names]
        result={'stage':'M6','skill_version':'0.1.0','passed':True,'synthetic':True,'case_tasks':sum(len(c['tasks']) for c in cases),'cases':cases,'files':files,'audit':audit,'m1_originals_unchanged':True,'m5_packages_unchanged':True}
        manifest=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        (stage/'showcase-manifest.json').write_bytes(manifest)
        audit_public_tree(stage)
        _publish_reviewed(stage,files,output,manifest)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:result=prepare(args.output)
    except (ValueError,OSError,IntakeError,subprocess.SubprocessError,zipfile.BadZipFile,ET.ParseError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=True));return 1
    print(json.dumps({k:result[k] for k in ('stage','passed','case_tasks','m1_originals_unchanged','m5_packages_unchanged')},ensure_ascii=True));return 0


if __name__=='__main__':raise SystemExit(main())
