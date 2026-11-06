"""Source inspection and table reading coordinator; inputs remain unchanged."""
from __future__ import annotations

import os
from pathlib import Path
from common import Budget, IntakeError, IntakeResult, Issue, RuleSet, parse_range
from rules import validate_rules
from source_guard import inspect_zip, snapshot_file


def _record_failure(intake, issue, table_ids):
    intake.issues.append(issue)
    intake.blocked_table_ids.update(table_ids)
    if issue.severity=='fatal':
        intake.global_blocked=True


def _table_budgets(rules, budget):
    rows=cells=0
    for table in rules.tables:
        c1,r1,c2,r2=parse_range(table['data_range'])
        height=r2-r1+1; width=c2-c1+1
        budget.enforce('max_table_rows',height); budget.enforce('max_table_columns',width)
        rows+=height; cells+=height*width
        budget.enforce('max_total_rows',rows); budget.enforce('max_total_cells',cells)


def inspect_sources(rules: RuleSet, authorized_paths: set[Path], budget: Budget) -> IntakeResult:
    intake=IntakeResult(table_count=len(rules.tables) if isinstance(rules.payload,dict) and isinstance(rules.tables,list) else 0)
    problems=validate_rules(rules)
    if problems:
        intake.issues.extend(problems); intake.global_blocked=True; return intake
    intake.rules_fingerprint=rules.fingerprint()
    all_ids={t['id'] for t in rules.tables}
    # Do not resolve symlink aliases in the authorization set on the caller's behalf.
    authorized={Path(os.path.abspath(p)) for p in authorized_paths}
    try:
        _table_budgets(rules,budget)
    except IntakeError as e:
        _record_failure(intake,e.issue,all_ids); return intake
    seen=set()
    for source in rules.sources:
        sid=source['id']; affected={t['id'] for t in rules.tables if t['source_id']==sid}
        try:
            budget.check()
            snap=snapshot_file(sid,rules.path.parent/source['path'],authorized,budget)
            if snap.identity in seen: raise IntakeError('duplicate_source','同一物理文件不能重复登记',{'source_id':sid})
            seen.add(snap.identity)
            if snap.path.suffix.lower()!='.'+source['format']:
                raise IntakeError('unsupported_format','文件扩展名与声明格式不符',{'source_id':sid})
            if source['format']=='xlsx': snap.metadata.update(inspect_zip(snap.data,budget))
            intake.source_snapshots[sid]=snap
        except IntakeError as e:
            _record_failure(intake,Issue(e.issue.code,e.issue.message,e.issue.source_ref or {'source_id':sid},e.issue.severity),affected)
            if intake.global_blocked:
                intake.blocked_table_ids.update(all_ids); break
    return intake


def verify_sources_unchanged(intake: IntakeResult, rules: RuleSet, budget: Budget) -> bool:
    if intake.global_blocked: return False
    all_ids={t['id'] for t in rules.tables}
    if intake.rules_fingerprint!=rules.fingerprint():
        _record_failure(intake,Issue('rules_changed','预检后规则发生变化，需重新登记',severity='fatal'),all_ids)
        return False
    for sid,snap in intake.source_snapshots.items():
        try:
            current=snapshot_file(sid,snap.path,{snap.path},budget)
            if current.sha256!=snap.sha256 or current.identity!=snap.identity:
                raise IntakeError('source_changed','来源在登记后发生变化，需重新读取',{'source_id':sid},fatal=True)
        except IntakeError as e:
            issue=e.issue if e.issue.severity=='fatal' else Issue('source_changed','来源在登记后不可用',{'source_id':sid},'fatal')
            _record_failure(intake,issue,all_ids); return False
    return True
