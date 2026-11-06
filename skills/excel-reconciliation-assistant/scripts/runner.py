"""Authorized intake-to-comparison orchestration; no publication or source writes."""
from __future__ import annotations
import uuid
from common import RunResult, Issue, IntakeError
from intake import inspect_sources,read_tables,verify_sources_unchanged
from matching import associate
from compare import compare_task


def execute(rules,authorized_paths,budget,mode='run'):
    if mode not in ('run','inspect'): raise IntakeError('invalid_mode','仅支持inspect或run')
    intake=inspect_sources(rules,authorized_paths,budget)
    tables=read_tables(intake,rules,budget)
    if intake.global_blocked:
        raise IntakeError('intake_blocked','来源变化或全局预算使整批中止',{'issues':[i.code for i in intake.issues]},fatal=True)
    if mode=='inspect':
        return RunResult(rules,intake,[],[],list(intake.issues),intake.status,mode,budget=budget,run_id=uuid.uuid4().hex)
    results=[]; states=[]; issues=list(intake.issues)
    for task in rules.tasks:
        budget.check()
        missing=[task[s+'_table'] for s in ('left','right') if task[s+'_table'] not in tables]
        if missing:
            states.append({'task_id':task['id'],'status':'blocked','unavailable_tables':missing})
            continue
        try:
            result=compare_task(associate(tables[task['left_table']],tables[task['right_table']],task),task,budget)
            results.append(result); states.append({'task_id':task['id'],'status':result.status})
            issues.extend(result.issues)
        except IntakeError as e:
            if e.issue.severity=='fatal': raise
            issues.append(e.issue); states.append({'task_id':task['id'],'status':'blocked','reason':e.issue.code})
    referenced={t[s+'_table'] for t in rules.tasks for s in ('left','right')}
    unused=[t['id'] for t in rules.tables if t['id'] not in referenced]
    for tid in unused: issues.append(Issue('unused_table','来源表未配置核对任务，未宣称已比较',{'table_id':tid},'warning'))
    if not results: status='blocked'
    elif len(results)!=len(rules.tasks) or intake.status=='partial' or unused: status='partial'
    elif any(r.status=='needs_confirmation' for r in results): status='needs_confirmation'
    else: status='complete'
    if not verify_sources_unchanged(intake,rules,budget): raise IntakeError('source_changed','来源在核对期间发生变化，整批结论失效',fatal=True)
    return RunResult(rules,intake,results,states,issues,status,mode,budget=budget,run_id=uuid.uuid4().hex)
