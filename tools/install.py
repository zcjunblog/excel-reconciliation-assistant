"""Install a complete Skill explicitly; never overwrite an existing installation."""
import argparse
import json
from pathlib import Path
import tempfile
from distribution import SOURCE,NAME,snapshot,digest,DeliveryGuard
from delivery_guard import identity
import uuid

CLIENTS={'generic':('.agents/skills','.agents/skills'),'codex':('.agents/skills','.agents/skills'),
         'claude':('.claude/skills','.claude/skills'),'cursor':('.cursor/skills','.cursor/skills'),
         'copilot':('.github/skills','.copilot/skills'),'gemini':('.gemini/skills','.gemini/skills'),
         'opencode':('.opencode/skills','.config/opencode/skills')}


def checked_path(value):
    path=Path(value).expanduser().absolute()
    for component in reversed((path,*path.parents)):
        if component.is_symlink(): raise ValueError('Installation path contains a symlink; choose its real location explicitly')
    return path


def anchors(path):
    return {p:identity(p) for p in path.parents if p.exists()}


def check_anchors(record):
    if any(identity(p)!=expected for p,expected in record.items()): raise ValueError('Installation ancestor changed')


def verify_installed(guard,payloads,entry=False):
    expected=set(payloads) if entry else set(payloads)-{'SKILL.md'}
    directories={parent.as_posix() for name in expected for parent in Path(name).parents if parent!=Path('.')}
    actual_files=set(); actual_dirs=set()
    for p in guard.root.rglob('*'):
        name=p.relative_to(guard.root).as_posix()
        if p.is_symlink(): raise ValueError('Unexpected installed symlink')
        if p.is_dir(): actual_dirs.add(name)
        elif p.is_file(): actual_files.add(name)
        else: raise ValueError('Unexpected installed file type')
    if actual_files!=expected or actual_dirs!=directories: raise ValueError('Installed resource set changed')
    for name in expected:
        guard.validate(name)
        if digest((guard.root/name).read_bytes())!=digest(payloads[name]): raise ValueError('Installed resource checksum mismatch')


def destination(client,scope,project=None,user_root=None):
    if client not in CLIENTS or scope not in ('project','user'): raise ValueError('Unknown client or scope')
    base=Path(project or Path.cwd()) if scope=='project' else Path(user_root or Path.home())
    return checked_path(base)/CLIENTS[client][scope=='user']/NAME


def install(target,source=SOURCE,dry_run=False):
    target=checked_path(target); source=Path(source).expanduser().absolute()
    stable=anchors(target)
    if target.exists() or target.is_symlink(): raise ValueError('Installation already exists; preserve it before installing another version')
    real_target=target.resolve(); real_source=source.resolve()
    if real_target==real_source or real_source in real_target.parents or real_target in real_source.parents: raise ValueError('Installation overlaps source')
    payloads,version=snapshot(source)
    result={'version':version,'destination':str(real_target),'dry_run':dry_run,'files':len(payloads),'hashes_verified':False}
    if dry_run: return result
    check_anchors(stable)
    target.parent.mkdir(parents=True,exist_ok=True)
    checked_path(target); check_anchors(stable)
    stable=anchors(target)
    # This stage never contains a file named SKILL.md, so recursive loaders cannot discover it.
    with tempfile.TemporaryDirectory(prefix='.skill-install-',dir=target.parent) as tmp:
        checked_path(target); check_anchors(stable)
        guard=DeliveryGuard(target,Path(tmp).resolve(),uuid.uuid4().hex)
        try:
            for name,data in payloads.items():
                if name=='SKILL.md': continue
                with guard.open(name) as stream: stream.write(data)
                guard.validate(name)
                if digest((guard.root/name).read_bytes())!=digest(data): raise ValueError('Installed resource checksum mismatch')
            if snapshot(source)[0]!=payloads: raise ValueError('Skill source changed during installation')
            checked_path(target); check_anchors(stable)
            verify_installed(guard,payloads)
            guard.publish_entry('SKILL.md',payloads['SKILL.md'])
            checked_path(target); check_anchors(stable)
            verify_installed(guard,payloads,entry=True)
        except BaseException:
            guard.cleanup(); raise
    result['hashes_verified']=True; return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--client',choices=sorted(CLIENTS)); group.add_argument('--dest',type=Path,help='Custom skills root; adds the named Skill folder')
    parser.add_argument('--scope',choices=('project','user'),default='project'); parser.add_argument('--project',type=Path)
    parser.add_argument('--source',type=Path,default=SOURCE); parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.dest and (args.project or args.scope!='project'): parser.error('--dest cannot be combined with --project or user scope')
    if args.scope=='user' and args.project: parser.error('--project does not apply to user scope')
    try:
        target=args.dest/NAME if args.dest else destination(args.client,args.scope,args.project)
        result=install(target,args.source,args.dry_run)
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=True)); return 1
    print(json.dumps(result,ensure_ascii=True)); return 0


if __name__=='__main__': raise SystemExit(main())
