"""Validate then independently execute both owned release archives, outside the repository."""
import argparse
import json
import os
from pathlib import Path,PurePosixPath
import posixpath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from distribution import ROOT,NAME,RESOURCES,snapshot,_parse_info,workbuddy_entry,digest,publish_files


def _require(condition,message):
    if not condition: raise ValueError(message)


def _json(path): return json.loads(path.read_text(encoding='utf-8'))
def _jsonl(path): return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def _extract(archive,folder,entries):
    receipts={entry['path']:entry for entry in entries}
    _require(len(receipts)==len(entries) and set(receipts)==RESOURCES,'Archive manifest resources do not match Skill contract')
    expected={NAME+'/'+name for name in receipts}
    with zipfile.ZipFile(archive) as zipped:
        members=zipped.infolist(); names=[m.filename for m in members]
        _require(len(names)==len(set(names)) and set(names)==expected,'Unsafe, missing or duplicate ZIP paths')
        _require(sum(m.file_size for m in members)<=20*1024*1024,'Archive expanded byte budget exceeded')
        for member in members:
            path=PurePosixPath(member.filename)
            _require(not path.is_absolute() and '..' not in path.parts and '\\' not in member.filename and ':' not in member.filename,'Unsafe ZIP path')
            _require(not member.is_dir() and not stat.S_ISLNK(member.external_attr>>16) and member.file_size<=2*1024*1024,'Unsupported or oversized ZIP member')
            chunks=[]; size=0
            with zipped.open(member) as stream:
                for chunk in iter(lambda:stream.read(65536),b''):
                    size+=len(chunk); _require(size<=2*1024*1024,'Actual ZIP member exceeded budget'); chunks.append(chunk)
            raw=b''.join(chunks); relative=path.relative_to(NAME).as_posix(); receipt=receipts[relative]
            _require(len(raw)==receipt['bytes'] and digest(raw)==receipt['sha256'],'ZIP member checksum mismatch')
            target=folder/Path(*path.parts); target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream: stream.write(raw)


def _run(python,cli,args,cwd,expected,no_site=False):
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}; env.pop('PYTHONPATH',None)
    process=subprocess.run([str(python)]+(['-S'] if no_site else [])+[str(cli),*map(str,args)],cwd=cwd,env=env,
                           capture_output=True,timeout=140)
    _require(process.returncode==expected,'Installed CLI returned unexpected exit code: '+str(process.returncode)+' '+process.stderr.decode('utf-8',errors='replace')[-1500:])
    try: value=json.loads(process.stdout)
    except (ValueError,UnicodeDecodeError) as error: raise ValueError('Installed CLI did not return machine JSON') from error
    return value


def _delivery(folder):
    manifest=_json(folder/'交付清单.json'); files=manifest['files']
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}-{'交付清单.json'}
    _require(actual=={f['path'] for f in files} and len(actual)==len(files),'Delivery manifest inventory mismatch')
    for entry in files:
        p=folder/entry['path']
        _require(p.is_file() and p.stat().st_size==entry['bytes'] and digest(p.read_bytes())==entry['sha256'],'Delivery file checksum mismatch')
    return manifest


def _workbook_counts(path):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        workbook=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={r.attrib['Id']:r.attrib['Target'] for r in rels}
        result={}
        for sheet in workbook.find('s:sheets',ns):
            rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target=targets[rid]; target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            xml=ET.fromstring(z.read(target))
            _require(not xml.findall('.//s:f',ns),'Source text became an active workbook formula')
            result[sheet.attrib['name']]=len(xml.findall('s:sheetData/s:row',ns))-1
        return result


def _oracle(folder,case):
    wanted=_json(ROOT/'examples'/case/'expected.json')['tasks']
    fields=_jsonl(folder/'工作资料/字段结果.jsonl'); rows=_jsonl(folder/'工作资料/关联结果.jsonl'); tasks=[]
    for want in wanted:
        found=[f for f in fields if f['task_id']==want['id']]
        counts={s:sum(f['status']==s for f in found) for s in ('exact','within_rule','different','not_comparable')}
        _require(counts==want['field_counts'],'Field counts differ from independent oracle')
        exceptions=[{'left_row':f['left']['ref']['row'],'right_row':f['right']['ref']['row'],'field':f['field_id'],'status':f['status'],'delta':f['delta'],
            'left_cell':f['left']['ref']['column']+str(f['left']['ref']['row']),'right_cell':f['right']['ref']['column']+str(f['right']['ref']['row']),'reason':f['reason']}
            for f in found if f['status']!='exact']
        _require(exceptions==want['exceptions'],'Exceptions differ from independent oracle')
        for side in ('left','right'):
            source=[r for r in rows if r['task_id']==want['id'] and r['side']==side]
            _require(len(source)==want['selected'][side],'Selected source-row coverage mismatch')
            for state,key in (('excluded','excluded_rows'),(side+'_only','only_rows'),('duplicate_ambiguous','duplicate_rows'),('invalid_key','invalid_rows')):
                _require([r['row'] for r in source if r['status']==state]==want[key][side],'Source-row classification mismatch')
            _require([r['row'] for r in source if r['status']=='unique_matched']==sorted(pair[0 if side=='left' else 1] for pair in want['matched_pairs']),'Matched source-row coverage mismatch')
        tasks.append({'task_id':want['id'],'manual_oracle_matches':True,'field_counts':counts})
    if (folder/'核对结果.xlsx').exists():
        counts=_workbook_counts(folder/'核对结果.xlsx')
        _require(sum(v for k,v in counts.items() if k.startswith('匹配索引'))==sum(len(t['matched_pairs']) for t in wanted),'Workbook match-index count mismatch')
        _require(sum(v for k,v in counts.items() if k.startswith('差异明细'))==sum(len(t['exceptions']) for t in wanted),'Workbook exception count mismatch')
    return tasks


def verify(release,output,python=None):
    release=Path(release).resolve(); output=Path(output).absolute()
    if output.exists() or output.is_symlink(): raise ValueError('Verification output already exists')
    manifest=_json(release/'manifest.json'); canonical,version=snapshot()
    _require(manifest.get('name')==NAME and manifest.get('version')==version,'Release identity/version mismatch')
    packages=manifest['packages']
    _require([p['profile'] for p in packages]==['standard','workbuddy'],'Expected one standard and one WorkBuddy package')
    # Preserve the venv entrypoint: resolving its symlink would select the base interpreter.
    python=Path(python or sys.executable).expanduser().absolute(); profiles=[]
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.archive-smoke-',dir=output.parent) as tmp:
        stage=Path(tmp).resolve()
        # Validate both complete archives before executing either one.
        for item in packages:
            suffix='-workbuddy' if item['profile']=='workbuddy' else ''
            _require(item['archive']==NAME+suffix+'-'+version+'.zip','Unexpected archive path')
            archive=release/item['archive']
            _require(not archive.is_symlink() and archive.stat().st_size<=20*1024*1024,'Unsafe or oversized archive')
            raw=archive.read_bytes()
            _require(len(raw)==item['bytes'] and digest(raw)==item['sha256'],'Archive checksum mismatch')
            folder=stage/item['profile']; folder.mkdir(); _extract(archive,folder,item['files'])
            source=folder/NAME; fields,body,_=_parse_info(canonical['SKILL.md'].decode(),canonical['VERSION'].decode())
            for name,data in canonical.items():
                expected=workbuddy_entry(fields,body,version) if item['profile']=='workbuddy' and name=='SKILL.md' else data
                _require((source/name).read_bytes()==expected,'Archive drifted from canonical Skill source')
        for item in packages:
            folder=stage/item['profile']; source=folder/NAME; scripts=source/'scripts'; cases=[]
            doctor=_run(python,scripts/'doctor.py',['--require-xlsx'],folder,0)
            _require(doctor['skill_version']==version and doctor['capabilities']['xlsx'],'Installed package lacks required XLSX environment')
            for case in ('commerce','inventory','training','administration'):
                rules_path=source/'references/examples'/case/'rules.json'; rules=_json(rules_path)
                auth=[value for s in rules['sources'] for value in ('--authorize',str((rules_path.parent/s['path']).resolve()))]
                out=folder/'cases'/(case+'-v001')
                data=_run(python,scripts/'reconcile_tool.py',['run','--rules',rules_path,'--output',out,*auth],folder,2)
                _require(data['status']=='needs_confirmation' and data['skill_version']==version,'Unexpected installed execution status/version')
                delivery=_delivery(out); tasks=_oracle(out,case)
                cases.append({'case':case,'status':data['status'],'tasks':tasks,'actual_files':len(delivery['files'])+1})
            # inspect is a distinct stage, without comparison claims or field outputs.
            rules_path=source/'references/examples/commerce/rules.json'; inspection=folder/'inspect-v001'
            inspected=_run(python,scripts/'reconcile_tool.py',['inspect','--rules',rules_path,'--output',inspection,'--authorize',rules_path.parent/'inputs.xlsx'],folder,0)
            checked=_delivery(inspection)
            _require(inspected['status']=='ready' and checked['tasks']==[] and not (inspection/'核对结果.xlsx').exists(),'inspect claimed a comparison')
            # No optional packages: CSV still has full reports, XLSX explicitly absent.
            no_site=_run(python,scripts/'doctor.py',[],folder,0,True)
            _require(no_site['capabilities']['csv'] and not no_site['capabilities']['xlsx'],'No-site probe imported optional dependencies')
            rules_path=source/'references/examples/inventory/rules.json'; out=folder/'csv-no-deps-v001'
            auth=[value for s in _json(rules_path)['sources'] for value in ('--authorize',str((rules_path.parent/s['path']).resolve()))]
            data=_run(python,scripts/'reconcile_tool.py',['run','--rules',rules_path,'--output',out,*auth],folder,2,True)
            delivery=_delivery(out); _oracle(out,'inventory')
            _require(data['status']=='partial' and delivery['unavailable_formats'][0]['code']=='missing_dependency' and not (out/'核对结果.xlsx').exists(),'Missing XLSX dependency was misreported')
            profiles.append({'profile':item['profile'],'archive_sha256':item['sha256'],'skill_version':version,'python':doctor['python'],
                             'installed_cli_only':True,'inspect_ready':True,'cases':cases,'csv_no_dependencies':{'status':data['status'],'xlsx_generated':False}})
        originals=_json(ROOT/'examples/manifest.json')['files']
        _require(all(digest((ROOT/f['path']).read_bytes())==f['sha256'] for f in originals),'Original fixture/oracle changed')
        result={'stage':'M5','passed':True,'version':version,'profiles':profiles,'case_tasks':sum(len(c['tasks']) for p in profiles for c in p['cases']),
                'm1_originals_unchanged':True,'execution_scope':'Unpacked package scripts/resources only; no repository production path or PYTHONPATH during execution'}
        (stage/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        names=sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file() and p.name!='verification.json')+['verification.json']
        publish_files(stage,names,output)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--python',type=Path)
    args=parser.parse_args()
    try: result=verify(args.release,args.output,args.python)
    except (ValueError,OSError,subprocess.SubprocessError,zipfile.BadZipFile) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=True)); return 1
    print(json.dumps(result,ensure_ascii=True)); return 0


if __name__=='__main__': raise SystemExit(main())
