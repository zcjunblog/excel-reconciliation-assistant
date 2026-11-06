"""One explicit resource set and one version source for all distribution surfaces."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import shutil
import sys
from urllib.parse import unquote,urlsplit
import uuid

ROOT=Path(__file__).resolve().parents[1]
NAME='excel-reconciliation-assistant'
SOURCE=ROOT/'skills'/NAME
sys.path.insert(0,str(SOURCE/'scripts'))
from delivery_guard import DeliveryGuard
from doctor import RUNTIME_MODULES

SCRIPTS=RUNTIME_MODULES
RESOURCES={'LICENSE','SKILL.md','VERSION','requirements.txt','agents/openai.yaml','templates/workbook-style.json',
           'references/rules.md','references/runtime.md','references/delivery.md','references/examples.md','references/reconciliation-rules.schema.json'}
RESOURCES.update('scripts/'+name+'.py' for name in SCRIPTS)
for case,names in {'commerce':['rules.json','inputs.xlsx'],'inventory':['rules.json','ledger.csv','count.csv'],
                   'training':['rules.json','registration.csv','attendance.csv'],'administration':['rules.json','inputs.xlsx']}.items():
    RESOURCES.update('references/examples/'+case+'/'+name for name in names)
PROFILE_KEYS={'display_name','display_name_en','description_zh','description_en','author','examples_zh','examples_en'}


def digest(data): return hashlib.sha256(data).hexdigest()


def _parse_info(text,version):
    parts=text.split('---\n',2)
    if len(parts)!=3 or parts[0] or not parts[2].strip(): raise ValueError('Expected nonempty Skill with YAML frontmatter')
    fields={}
    for line in parts[1].splitlines():
        key,value=line.split(':',1)
        if key in fields: raise ValueError('Repeated frontmatter key')
        fields[key]=json.loads(value.strip())
    if set(fields)!={'name','description'} or fields['name']!=NAME: raise ValueError('Canonical entry must contain standard name/description only')
    if not isinstance(fields['description'],str) or not 1<=len(fields['description'])<=1024: raise ValueError('Invalid Skill description')
    version=version.strip()
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',version): raise ValueError('Invalid VERSION')
    return fields,parts[2],version


def skill_info(source=SOURCE):
    source=Path(source)
    return _parse_info((source/'SKILL.md').read_text(encoding='utf-8'),(source/'VERSION').read_text(encoding='utf-8'))


def source_files(source=SOURCE):
    chosen=Path(source).expanduser().absolute()
    if chosen.is_symlink() or not chosen.is_dir(): raise ValueError('Skill source must be a real directory')
    source=chosen.resolve(); files={}; total=0
    for path in sorted(source.rglob('*')):
        rel=path.relative_to(source)
        if path.is_symlink(): raise ValueError('Symlink is not a distributable Skill resource')
        if '__pycache__' in rel.parts or path.suffix=='.pyc': continue
        if path.is_dir(): continue
        key=rel.as_posix()
        if key not in RESOURCES or not path.is_file(): raise ValueError('Unexpected Skill resource: '+key)
        size=path.stat().st_size; total+=size
        if size>2*1024*1024 or total>20*1024*1024: raise ValueError('Skill resource budget exceeded')
        if path.suffix=='.md':
            for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
                if link.startswith('#'): continue
                parsed=urlsplit(link)
                if parsed.scheme in ('https','http'): continue
                if parsed.scheme or parsed.netloc: raise ValueError('Unsupported resource link')
                local=unquote(parsed.path)
                if Path(local).is_absolute() or '\\' in local: raise ValueError('Skill links must use package-relative paths')
                dest=(path.parent/local).resolve()
                if source not in dest.parents or not dest.is_file() or dest.relative_to(source).as_posix() not in RESOURCES:
                    raise ValueError('Missing or undistributed linked resource: '+link)
        files[key]=path
    if set(files)!=RESOURCES: raise ValueError('Missing Skill resources: '+', '.join(sorted(RESOURCES-set(files))))
    return [files[key] for key in sorted(files)]


def snapshot(source=SOURCE):
    chosen=Path(source).expanduser().absolute()
    files=source_files(chosen); source=chosen.resolve()
    payloads={p.relative_to(source).as_posix():p.read_bytes() for p in files}
    if not payloads: raise ValueError('Empty Skill source')
    _,_,version=_parse_info(payloads['SKILL.md'].decode('utf-8'),payloads['VERSION'].decode('utf-8'))
    return payloads,version


def profile_path(name,profile):
    if profile=='standard': return name
    if profile!='workbuddy': raise ValueError('Unknown distribution profile')
    parts=PurePosixPath(name).parts
    if len(parts)==4 and parts[:2]==('references','examples'):
        name='references/'+parts[2]+'-'+parts[3]
    if len(PurePosixPath(name).parts)>2: raise ValueError('WorkBuddy resource exceeds market directory depth')
    return name


def package_payloads(payloads,profile):
    """Keep standard layout; adapt only sample paths for the WorkBuddy market."""
    paths={name:profile_path(name,profile) for name in payloads}
    if len(set(paths.values()))!=len(paths): raise ValueError('Distribution resource path collision')
    result={}
    for name,data in payloads.items():
        if profile=='workbuddy' and name.startswith('references/examples/') and name.endswith('/rules.json'):
            rules=json.loads(data)
            for source in rules['sources']:
                original=(PurePosixPath(name).parent/source['path']).as_posix()
                if original not in paths: raise ValueError('Example rules refer to an undistributed source')
                source['path']=PurePosixPath(paths[original]).name
            data=(json.dumps(rules,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        elif profile=='workbuddy' and name=='references/examples.md':
            text=data.decode('utf-8')
            for old,new in paths.items():
                if old.startswith('references/examples/') and old.endswith('/rules.json'):
                    case=PurePosixPath(old).parts[2]
                    text=text.replace('['+case+'/rules.json](examples/'+case+'/rules.json)',
                                      '['+case+'-rules.json]('+PurePosixPath(new).name+')')
            text=text.replace('原始案例与项目验收源文件字节一致。',
                              '原始表格与项目验收源文件字节一致；WorkBuddy包仅调整样例文件名和规则相对路径，不改业务规则或数据。')
            data=text.encode('utf-8')
        result[paths[name]]=data
    return result


def workbuddy_entry(fields,body,version,profile=None):
    profile=profile if profile is not None else json.loads((ROOT/'distribution/workbuddy.json').read_text(encoding='utf-8'))
    if not isinstance(profile,dict) or set(profile)!=PROFILE_KEYS: raise ValueError('Unexpected or missing WorkBuddy fields; VERSION cannot be overridden')
    if any(not isinstance(profile[k],str) or not profile[k].strip() for k in PROFILE_KEYS-{'examples_zh','examples_en'}):
        raise ValueError('WorkBuddy display metadata must be nonempty strings')
    examples=[profile['examples_zh'],profile['examples_en']]
    if any(not isinstance(items,list) or not items or any(not isinstance(v,str) or not v.strip() for v in items) for items in examples):
        raise ValueError('WorkBuddy examples must be nonempty lists of nonempty strings')
    if len(examples[0])!=len(examples[1]): raise ValueError('WorkBuddy examples_zh/examples_en count mismatch')
    values={**fields,**profile,'version':version}
    return ('---\n'+'\n'.join(k+': '+json.dumps(v,ensure_ascii=False) for k,v in values.items())+'\n---\n'+body).encode('utf-8')


def publish_files(stage,names,target):
    guard=DeliveryGuard(target,stage,uuid.uuid4().hex)
    verified={}
    def recheck():
        for name,expected in verified.items():
            guard.validate(name)
            if digest((guard.root/name).read_bytes())!=expected: raise ValueError('Published resource changed before completion')
    try:
        for index,name in enumerate(names):
            if index==len(names)-1: recheck()
            source=Path(stage)/name
            with source.open('rb') as src,guard.open(name) as dst: shutil.copyfileobj(src,dst)
            guard.validate(name)
            expected=digest(source.read_bytes())
            if digest((guard.root/name).read_bytes())!=expected: raise ValueError('Published resource checksum mismatch')
            verified[name]=expected
        recheck()
        return guard.root
    except BaseException:
        guard.cleanup(); raise
