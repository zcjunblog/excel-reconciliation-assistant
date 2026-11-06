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
    intake.registered_table_ids=set(all_ids)
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
    all_ids=intake.registered_table_ids
    try:
        unchanged=intake.rules_fingerprint==rules.fingerprint()
    except (ValueError,TypeError,RecursionError):
        unchanged=False
    if not unchanged:
        _record_failure(intake,Issue('rules_changed','预检后规则发生变化，需重新登记',severity='fatal'),all_ids)
        return False
    for sid,snap in intake.source_snapshots.items():
        try:
            source=next(s for s in rules.sources if s['id']==sid)
            if (rules.path.parent/source['path']).resolve(strict=True)!=snap.path:
                raise IntakeError('source_changed','来源路径指向发生变化，需重新登记',{'source_id':sid},fatal=True)
            current=snapshot_file(sid,snap.path,{snap.path},budget)
            if current.sha256!=snap.sha256 or current.identity!=snap.identity:
                raise IntakeError('source_changed','来源在登记后发生变化，需重新读取',{'source_id':sid},fatal=True)
        except (IntakeError,OSError,RuntimeError) as e:
            if not isinstance(e,IntakeError):
                e=IntakeError('source_changed','来源路径在登记后不可用',{'source_id':sid},fatal=True)
            issue=e.issue if e.issue.severity=='fatal' else Issue('source_changed','来源在登记后不可用',{'source_id':sid},'fatal')
            _record_failure(intake,issue,all_ids); return False
    return True


def read_tables(intake: IntakeResult, rules: RuleSet, budget: Budget) -> dict:
    from csv_reader import read_csv
    from table_data import build_table
    from xlsx_reader import read_xlsx
    if not verify_sources_unchanged(intake,rules,budget): return {}
    all_ids={t['id'] for t in rules.tables}; output={}
    expected={t['id']:{} for t in rules.tables}
    for task in rules.tasks:
        for side in ('left','right'):
            target=expected[task[side+'_table']]
            for field in task['fields']:
                col=field[side+'_column']; header=field[side+'_header']
                if col in target and target[col]!=header:
                    _record_failure(intake,Issue('conflicting_headers','多个任务对同一表列声明了不同表头',{'table_id':task[side+'_table'],'column':col}),[task[side+'_table']])
                target[col]=header
    for source in rules.sources:
        sid=source['id']; selected=[t for t in rules.tables if t['source_id']==sid and t['id'] not in intake.blocked_table_ids]
        if not selected or sid not in intake.source_snapshots: continue
        try:
            snap=intake.source_snapshots[sid]
            if source['format']=='csv': grids={None:read_csv(snap,source,selected,budget)}
            else: grids=read_xlsx(snap,selected,budget)
            for table in selected:
                try:
                    grid=grids.get(table['sheet'])
                    if grid is None: raise IntakeError('missing_sheet','指定工作表不存在或不是数据工作表',{'source_id':sid,'table_id':table['id'],'sheet':table['sheet']})
                    if isinstance(grid,IntakeError):
                        raise IntakeError(grid.issue.code,grid.issue.message,{'source_id':sid,'table_id':table['id'],'sheet':table['sheet']})
                    result=build_table(table,grid,sid,expected[table['id']])
                    output[table['id']]=result
                    intake.table_previews[table['id']]={'header':result.header,'selected_rows':len(result.selected_rows),'included_rows':len(result.rows),'excluded_rows':result.excluded_rows,'metadata':result.metadata}
                except IntakeError as e:
                    _record_failure(intake,e.issue,[table['id']])
        except IntakeError as e:
            _record_failure(intake,e.issue,[t['id'] for t in selected])
            if intake.global_blocked:
                intake.blocked_table_ids.update(all_ids); intake.table_previews.clear(); return {}
    if not verify_sources_unchanged(intake,rules,budget):
        intake.table_previews.clear(); return {}
    return output
