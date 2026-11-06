"""Versioned reports, lossless internal records and verified, last-published manifest."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from common import ExportRecord, IntakeError
from checks import verify_coverage
from intake import verify_sources_unchanged
from presentation import STATUS, json_safe, compact, task_label, reason_label, original_value, display_text, field_label
from delivery_guard import DeliveryGuard


def _digest(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''): digest.update(chunk)
    return digest.hexdigest()


def code_text(value):
    value=display_text(value).replace('\r','\\r').replace('\n',' ↵ ').replace('\t','\\t').replace('|','\\|')
    import re
    width=max([len(x) for x in re.findall(r'`+',value)]+[0])+1
    fence='`'*width
    return fence+' '+value+' '+fence


class _Writer:
    def __init__(self,root,budget):
        self.root=Path(root).resolve(); self.budget=budget
        self.total=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())

    def write(self,name,lines,kind):
        target=self.root/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.parent.resolve()!=self.root and self.root not in target.parent.resolve().parents:
            raise IntakeError('unsafe_output','输出目录越过当前版本目录')
        digest=hashlib.sha256(); size=0; created=False
        try:
            with target.open('xb') as stream:
                created=True
                for line in lines:
                    self.budget.check(); raw=line.encode('utf-8'); size+=len(raw); self.total+=len(raw)
                    self.budget.enforce('max_artifact_bytes',self.total)
                    stream.write(raw); digest.update(raw)
            return ExportRecord(target,kind,'generated',digest.hexdigest(),size)
        except Exception:
            if created: target.unlink(missing_ok=True)
            raise

    def json(self,name,value):
        return self.write(name,[json.dumps(json_safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n'],'json')


def _sources(run):
    rows=[]
    for source in run.rules.sources:
        snap=run.source_snapshots.get(source['id'])
        rows.append({'id':source['id'],'name':Path(source['path']).name,'format':source['format'],'registered':snap is not None,
                     'sha256':snap.sha256 if snap else None,'bytes':snap.bytes if snap else None,'metadata':snap.metadata if snap else {}})
    return rows


def _safe_rules(run):
    data=copy.deepcopy(run.rules.payload)
    for source in data['sources']: source['path']=Path(source['path']).name
    return {'rules':data,'source_locations':'仅保留原文件名与文件ID；重跑时需重新指定并授权来源位置','execution_fingerprint':run.intake.rules_fingerprint}


def association_records(run):
    for result in run.task_results:
        a=result.association; classified={'left':{},'right':{}}
        for pair in a.unique_pairs:
            for side in ('left','right'): classified[side][getattr(pair,side).row]=('unique_matched',pair.key)
        for side in ('left','right'):
            for row in getattr(a,side+'_only'): classified[side][row.row]=(side+'_only',None)
            for row in getattr(a,side+'_invalid'): classified[side][row.row]=('invalid_key',None)
            for group in a.duplicate_groups:
                for row in getattr(group,side): classified[side][row.row]=('duplicate_ambiguous',group.key)
            table=getattr(a,side); rows={r.row:r for r in table.rows}
            for number in a.selected_rows[side]:
                if number in a.excluded_rows[side]:
                    yield {'task_id':a.task_id,'side':side,'table_id':table.id,'row':number,'status':'excluded','reason':a.excluded_rows[side][number],'cells':{}}
                else:
                    state,key=classified[side][number]
                    yield {'task_id':a.task_id,'side':side,'table_id':table.id,'row':number,'status':state,'key':key,'cells':rows[number].cells}


def _report_lines(run):
    yield '# 表格核对报告\n\n'
    yield f'**执行状态：{STATUS.get(run.status,run.status)}。** 本文件为核对草稿；完整执行不代表业务一致。\n\n'
    yield '差额方向为比较侧减基准侧。完整逐字段记录和源行分类见工作资料；来源文件未改写。\n\n'
    for state in run.task_statuses:
        task=next(t for t in run.rules.tasks if t['id']==state['task_id'])
        yield f'## {code_text(task_label(task,run.rules))}\n\n'
        result=next((r for r in run.task_results if r.association.task_id==task['id']),None)
        if result is None:
            yield '**未核对。** 依赖的来源表不可用，不能将缺失范围视为零差异。\n\n'; continue
        a=result.association
        yield '| 侧别 | 选中 | 纳入 | 排除 | 唯一关联 | 仅本侧 | 重复歧义 | 无效键 |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n'
        for side,label in (('left','基准'),('right','比较')):
            c=result.row_counts[side]
            yield '| '+label+' | '+' | '.join(str(c[k]) for k in ('selected','included','excluded','unique_matched','only','duplicate_ambiguous','invalid_key'))+' |\n'
        counts=result.field_counts
        yield f'\n字段完全一致 {counts["exact"]} 处，规则内一致 {counts["within_rule"]} 处，有差异 {counts["different"]} 处，不可比较 {counts["not_comparable"]} 处。\n\n'
        yield f'有差异记录对 {result.row_counts["different_pairs"]}，不可比记录对 {result.row_counts["not_comparable_pairs"]}；两者可重叠，不能相加当总数。\n\n'
        exceptions=[f for f in result.field_results if f.status!='exact']
        if exceptions:
            location='工作资料' if any(f['path']=='核对结果.xlsx' for f in run.unavailable_formats) else 'Excel及工作资料'
            yield '主要差异与例外（最多展示20条；完整明细保留在'+location+'）：\n\n'
            yield '| 字段 | 状态 | 基准原值 | 比较原值 | 差额 | 原位置 |\n| --- | --- | --- | --- | --- | --- |\n'
            for f in exceptions[:20]:
                yield '| '+' | '.join(code_text(v) for v in (field_label(task,f.field_id),STATUS[f.status],original_value(f.left),original_value(f.right),f.delta,
                    f'{f.left.ref.source_id}/{f.left.ref.sheet or "CSV"}/{f.left.ref.column}{f.left.ref.row} → {f.right.ref.source_id}/{f.right.ref.sheet or "CSV"}/{f.right.ref.column}{f.right.ref.row}'))+' |\n'
            yield '\n'
    if run.unavailable_formats:
        yield '## 未生成的格式\n\n'
        for item in run.unavailable_formats: yield f'- {code_text(item["path"])}：{code_text(item["message"])}\n'
        yield '\n完整结构化资料未因此截断。\n\n'
    if run.issues:
        yield '## 范围及执行问题\n\n'
        for issue in run.issues: yield '- '+code_text(issue.code)+'：'+code_text(issue.message)+'；'+code_text(compact(issue.source_ref))+'\n'


def _pending_lines(run):
    yield '# 待确认事项\n\n'
    yield '按原文件、工作表/CSV逻辑记录和原行定位；不自动去重、聚合、补单位或重算公式。\n\n'
    count=0
    for result in run.task_results:
        a=result.association; label=task_label(a.task_rule,run.rules)
        for group in a.duplicate_groups:
            count+=1
            yield f'- {code_text(label)}：重复键 {code_text(group.key)}，基准 {len(group.left)} 条 / 比较 {len(group.right)} 条。\n'
            for side in ('left','right'):
                for row in getattr(group,side):
                    ref=next(iter(row.cells.values())).ref
                    yield f'  - {"基准" if side=="left" else "比较"}：{code_text(ref.source_id)} / {code_text(ref.sheet or "CSV记录")} / 原行 {row.row}。\n'
        for issue in a.issues:
            count+=1; yield '- '+code_text(label)+'：'+code_text(reason_label(issue.code))+'；'+code_text(compact(issue.source_ref))+'\n'
        for f in result.field_results:
            if f.status=='not_comparable' or f.warnings:
                count+=1
                reasons=[reason_label(f.reason)]+[reason_label(w) for w in f.warnings]
                yield '- '+code_text(label)+' / '+code_text(field_label(a.task_rule,f.field_id))+'：'+code_text('；'.join(reasons))+'；结果 '+code_text(f.result_id)+'\n'
    for issue in run.intake.issues:
        count+=1; yield '- 来源问题：'+code_text(issue.message)+'；'+code_text(compact(issue.source_ref))+'\n'
    if not count: yield '当前执行结果未发现需确认的键、字段或来源问题；业务差异仍请按核对报告复核。\n'


def write_reports(run,staging_dir):
    writer=_Writer(staging_dir,run.budget); files=[]
    if run.mode=='inspect':
        text='# 来源与规则预检报告\n\n状态：'+STATUS.get(run.status,run.status)+'。未执行关联或字段比较，也未生成核对结果Excel。\n\n'
        text+='来源文件 '+str(len(run.source_snapshots))+' 份；可读取表 '+str(len(run.intake.table_previews))+' 张。\n\n'
        for issue in run.issues: text+='- '+code_text(issue.code)+'：'+code_text(issue.message)+'\n'
        files.append(writer.write('预检报告.md',[text],'md'))
        files.append(writer.json('工作资料/预检.json',run.intake.table_previews))
    else:
        files.append(writer.write('核对报告.md',_report_lines(run),'md'))
        files.append(writer.write('待确认事项.md',_pending_lines(run),'md'))
        files.append(writer.write('工作资料/字段结果.jsonl',(compact(f)+'\n' for r in run.task_results for f in r.field_results),'jsonl'))
        files.append(writer.write('工作资料/关联结果.jsonl',(compact(row)+'\n' for row in association_records(run)),'jsonl'))
        checks=[{'task_id':r.association.task_id,'coverage_issues':verify_coverage(r),'row_counts':r.row_counts,'field_counts':r.field_counts,'totals':r.totals} for r in run.task_results]
        if any(c['coverage_issues'] for c in checks): raise IntakeError('coverage_failed','报告生成后覆盖检查失败，整批交付中止',fatal=True)
        files.append(writer.json('工作资料/检查记录.json',checks))
    files.append(writer.json('工作资料/来源索引.json',_sources(run)))
    files.append(writer.json('工作资料/读取范围.json',[
        {'table_id':t['id'],'definition':t,'blocked':t['id'] in run.intake.blocked_table_ids,'preview':run.intake.table_previews.get(t['id'])}
        for t in run.rules.tables]))
    files.append(writer.json('工作资料/核对规则.json',_safe_rules(run)))
    files.append(writer.json('工作资料/执行摘要.json',{'skill_version':run.skill_version,'mode':run.mode,'status':run.status,'tasks':run.task_statuses,'issues':run.issues,'unavailable_formats':run.unavailable_formats,'run_id':run.run_id}))
    return files


def _validated_files(files):
    if not files: raise IntakeError('missing_artifacts','没有可登记的交付文件')
    roots={(record.path.parent if record.path.parent.name!='工作资料' else record.path.parent.parent).resolve() for record in files}
    if len(roots)!=1: raise IntakeError('invalid_artifacts','交付文件不在同一个暂存目录')
    root=next(iter(roots)).resolve(); inventory=[]; names=set()
    for record in files:
        p=record.path
        if p.is_symlink() or not p.is_file() or root not in p.resolve().parents: raise IntakeError('invalid_artifacts','交付文件缺失、为链接或越界')
        relative=p.resolve().relative_to(root).as_posix()
        if relative in names: raise IntakeError('invalid_artifacts','交付清单出现重复文件')
        if record.bytes!=p.stat().st_size or record.sha256!=_digest(p): raise IntakeError('artifact_changed','暂存产物在登记后发生变化')
        names.add(relative); inventory.append({'path':relative,'kind':record.kind,'status':record.status,'bytes':record.bytes,'sha256':record.sha256})
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=names: raise IntakeError('unregistered_artifacts','暂存目录中存在未登记文件，拒绝隐藏或删除')
    return root,inventory


def finalize_delivery(run,files,new_dir):
    root,inventory=_validated_files(files); destination=Path(new_dir).absolute()
    if destination==root or root in destination.parents or destination in root.parents: raise IntakeError('unsafe_output','交付目录不能包含暂存目录或与其重叠')
    if destination.exists() or destination.is_symlink(): raise IntakeError('output_exists','交付版本目录已存在，拒绝覆盖')
    if not verify_sources_unchanged(run.intake,run.rules,run.budget): raise IntakeError('source_changed','来源在交付前发生变化，结果不能发布',fatal=True)
    if any(verify_coverage(r) for r in run.task_results): raise IntakeError('coverage_failed','交付前数量或来源检查失败',fatal=True)
    if run.mode=='run' and run.task_results and not any(f['kind']=='xlsx' for f in inventory) and not run.unavailable_formats:
        raise IntakeError('missing_artifacts','缺少Excel结果且未登记未生成原因')
    run.budget.enforce('max_artifact_bytes',sum(f['bytes'] for f in inventory))
    run.budget.check(); guard=DeliveryGuard(destination,root,run.run_id); destination=guard.root
    try:
        with guard.open('.交付中.json') as stream:
            stream.write(json.dumps({'run_id':run.run_id,'files':[f['path'] for f in inventory]}).encode('utf-8'))
        for entry in inventory:
            run.budget.check(); source=root/entry['path']; target=destination/entry['path']
            with source.open('rb') as src,guard.open(entry['path']) as dst:
                shutil.copyfileobj(src,dst)
            guard.validate(entry['path'])
            if _digest(target)!=entry['sha256']: raise IntakeError('delivery_readback','交付副本摘要与暂存记录不一致')
        run.budget.check()
        if not verify_sources_unchanged(run.intake,run.rules,run.budget):
            raise IntakeError('source_changed','来源在交付复制期间发生变化，未发布交付清单',fatal=True)
        for entry in inventory:
            run.budget.check(); guard.validate(entry['path'])
            if _digest(destination/entry['path'])!=entry['sha256']: raise IntakeError('artifact_changed','交付复制后文件被修改')
        manifest={'schema_version':'1.0','skill_version':run.skill_version,'run_id':run.run_id,'mode':run.mode,'status':run.status,'tasks':run.task_statuses,'files':inventory,'unavailable_formats':run.unavailable_formats,
                  'scope':'来源与规则预检；未执行核对' if run.mode=='inspect' else '指定任务、字段与范围；状态不代表业务一致'}
        raw=json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')+b'\n'
        run.budget.enforce('max_artifact_bytes',sum(f['bytes'] for f in inventory)+len(raw))
        with guard.open('交付清单.json') as stream: stream.write(raw)
        run.budget.check(); guard.unlink('.交付中.json'); return destination
    except BaseException:
        guard.cleanup()
        raise
