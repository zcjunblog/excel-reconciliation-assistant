"""Explicitly authorized CLI with isolated output and a hard process deadline."""
from __future__ import annotations
import argparse
import json
import math
import multiprocessing
from pathlib import Path
import shutil
import tempfile
import uuid
from common import Budget, IntakeError, RuleError, Issue
from rules import load_rules
from runner import execute
from export import write_workbook
from presentation import json_safe
from delivery_guard import cleanup_interrupted
import report


def _failure(issue):
    issues=issue if isinstance(issue,list) else [issue]
    return 1,{'status':'blocked','errors':json_safe(issues[:20]),'issue_count':len(issues)}


def run_job(mode,rules_path,new_dir,authorized_paths,budget=None,*,staging_dir=None,run_id=None):
    budget=budget or Budget(); output=Path(new_dir).absolute()
    owned=None
    try:
        if output.exists() or output.is_symlink(): raise IntakeError('output_exists','交付版本目录已存在，拒绝覆盖')
        output.parent.mkdir(parents=True,exist_ok=True)
        if staging_dir is None:
            owned=tempfile.TemporaryDirectory(prefix='.reconcile-',dir=output.parent)
            stage=Path(owned.name).resolve()
        else: stage=Path(staging_dir).resolve()
        rules=load_rules(Path(rules_path))
        run=execute(rules,set(authorized_paths),budget,mode)
        if run_id: run.run_id=run_id
        files=[]
        if mode=='run' and run.task_results:
            try:
                files.append(write_workbook(run.task_results,rules,stage,budget,run.task_statuses,run.issues,run.status))
            except IntakeError as error:
                if error.issue.severity=='fatal': raise
                run.unavailable_formats.append({'path':'核对结果.xlsx','code':error.issue.code,'message':error.issue.message})
                run.status='partial'
        files+=report.write_reports(run,stage)
        report.finalize_delivery(run,files,output)
        code=0 if run.status in ('complete','ready') else 1 if run.status=='blocked' else 2
        return code,{'skill_version':run.skill_version,'status':run.status,'mode':mode,'output':str(output),'run_id':run.run_id,
                     'tasks':run.task_statuses,'different_fields':sum(r.field_counts['different'] for r in run.task_results),
                     'not_comparable_fields':sum(r.field_counts['not_comparable'] for r in run.task_results),
                     'errors':json_safe(run.issues[:20]),'issue_count':len(run.issues),
                     'unavailable_formats':run.unavailable_formats,
                     'files':[f.path.relative_to(stage).as_posix() for f in files]+['交付清单.json']}
    except RuleError as error: return _failure(error.issues)
    except IntakeError as error: return _failure(error.issue)
    except (OSError,ValueError,TypeError) as error:
        return _failure(Issue('execution_failed','执行或文件写入失败，未登记完整交付',{'error_type':type(error).__name__}))
    finally:
        if owned: owned.cleanup()


def _worker(connection,mode,rules_path,output,authorized,timeout,stage,run_id):
    try:
        # openpyxl's intermediate worksheet XML must be killed/cleaned with this stage.
        tempfile.tempdir=stage
        result=run_job(mode,rules_path,output,authorized,Budget(max_seconds=timeout),staging_dir=stage,run_id=run_id)
        connection.send(result)
    except Exception:
        connection.send(_failure(Issue('execution_failed','执行进程异常退出，未登记完整交付')))
    finally: connection.close()


def _cleanup_interrupted(output,run_id,staging_dir=None):
    cleanup_interrupted(output,run_id,staging_dir)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Excel表格核对助手：只读来源、确定性核对、独立版本交付')
    parser.add_argument('mode',choices=('inspect','run'))
    parser.add_argument('--rules',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--authorize',action='append',default=[],type=Path,metavar='FILE',help='用户已授权的物理文件；可重复，不能用目录代替')
    parser.add_argument('--timeout',type=float,default=120.0,help='整次调用硬时限（秒，含进程启动）')
    args=parser.parse_args(argv); output=args.output.absolute()
    result=None
    if not math.isfinite(args.timeout) or args.timeout<=0:
        result=_failure(Issue('invalid_timeout','时限必须为正有限秒数'))
    elif output.exists() or output.is_symlink(): result=_failure(Issue('output_exists','交付版本目录已存在，拒绝覆盖'))
    else:
        run_id=uuid.uuid4().hex
        try:
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.reconcile-',dir=output.parent) as stage:
                context=multiprocessing.get_context('spawn'); reader,writer=context.Pipe(duplex=False)
                process=context.Process(target=_worker,args=(writer,args.mode,args.rules,output,args.authorize,args.timeout,stage,run_id))
                process.start(); writer.close()
                # Read while the child runs, so a diagnostics pipe can never deadlock join().
                if reader.poll(args.timeout):
                    try: result=reader.recv()
                    except EOFError: result=_failure(Issue('execution_failed','执行进程未返回结果'))
                    process.join(1)
                else:
                    result=_failure(Issue('execution_timeout','超过整次执行时限，未登记完整交付'))
                if process.is_alive(): process.terminate(); process.join()
                reader.close()
                if result[1].get('errors',[{}]) and result[1]['errors'][0].get('code')=='execution_timeout': _cleanup_interrupted(output,run_id,stage)
        except (OSError,ValueError) as error:
            result=_failure(Issue('execution_failed','无法启动或完成隔离执行',{'error_type':type(error).__name__}))
    print(json.dumps(result[1],ensure_ascii=True,allow_nan=False))
    return result[0]


if __name__=='__main__': raise SystemExit(main())
