"""Workbook views assembled from verified results, without file or Office access."""
from dataclasses import dataclass
from pathlib import Path
from common import IntakeError
from checks import verify_coverage
from presentation import STATUS, ExactNumber, original_value, display_text, compact, task_label, field_label, context_label, reason_label


@dataclass
class SheetData:
    name: str
    headers: list[str]
    rows: list[list]
    freeze: str = 'C2'
    state_column: int = 0


def key_label(task,key):
    names={f['id']:f['left_header'] for f in task['fields']}
    return ' / '.join(f'{names[k]}：{v}' for k,v in zip(task['keys'],key))


def row_summary(row,table):
    return compact({table.header.get(col,col):display_text(original_value(c)) for col,c in row.cells.items()})


def build_views(results,rules,issues=()):
    declared={t['id']:t for t in rules.tasks}; found={}; tables={}
    for result in results:
        a=result.association
        if a.task_id in found or declared.get(a.task_id)!=a.task_rule or verify_coverage(result):
            raise IntakeError('invalid_export_result','任务规则、来源覆盖或摘要不一致，不能导出')
        found[a.task_id]=result; tables[a.left.id]=a.left; tables[a.right.id]=a.right
    if not results: raise IntakeError('no_valid_task','没有可导出的完整核对任务')
    differences=[]; matched=[]; pending=[]; only={'left':[],'right':[]}; totals=[]
    for result in results:
        a=result.association; task=a.task_rule; label=task_label(task,rules)
        fields={f['id']:f for f in task['fields']}
        for f in result.field_results:
            if f.status!='exact':
                numeric=fields[f.field_id]['type']=='decimal'
                checked=lambda v:ExactNumber(v) if numeric and v is not None else v
                differences.append([label,STATUS[f.status],key_label(task,f.key),field_label(task,f.field_id),original_value(f.left),original_value(f.right),ExactNumber(f.delta) if f.delta is not None else None,
                    context_label(f.context),reason_label(f.reason),f.left.ref.source_id,f.left.ref.sheet or 'CSV记录',f.left.ref.row,f.left.ref.column,
                    f.right.ref.source_id,f.right.ref.sheet or 'CSV记录',f.right.ref.row,f.right.ref.column,f.result_id,checked(f.normalized_left),checked(f.normalized_right),
                    '；'.join(reason_label(w) for w in f.warnings)])
            if f.status=='not_comparable' or f.warnings:
                pending.append([label,'两侧','字段待确认',key_label(task,f.key),f.left.ref.source_id+' / '+f.right.ref.source_id,
                    (f.left.ref.sheet or 'CSV')+' / '+(f.right.ref.sheet or 'CSV'),f'{f.left.ref.row} / {f.right.ref.row}',f.left.ref.column+' / '+f.right.ref.column,
                    f.result_id,'；'.join([reason_label(f.reason)]+[reason_label(w) for w in f.warnings]),field_label(task,f.field_id)])
        row_states={(r['left_row'],r['right_row']):r for r in result.row_statuses}
        for pair in a.unique_pairs:
            state=row_states[(pair.left.row,pair.right.row)]; lc=next(iter(pair.left.cells.values())).ref; rc=next(iter(pair.right.cells.values())).ref
            matched.append([label,key_label(task,pair.key),lc.source_id,lc.sheet or 'CSV记录',pair.left.row,rc.source_id,rc.sheet or 'CSV记录',pair.right.row,
                state['field_counts']['exact'],state['field_counts']['within_rule'],state['field_counts']['different'],state['field_counts']['not_comparable'],STATUS[state['status']]])
        for side,table in (('left',a.left),('right',a.right)):
            for row in getattr(a,side+'_only'):
                ref=next(iter(row.cells.values())).ref
                key=' / '.join(f"{fields[k][side+'_header']}：{display_text(original_value(row.cells[fields[k][side+'_column']]))}" for k in task['keys'])
                only[side].append([label,'仅基准侧' if side=='left' else '仅比较侧',key,ref.source_id,ref.sheet or 'CSV记录',row.row,row_summary(row,table)])
            for row in getattr(a,side+'_invalid'):
                ref=next(iter(row.cells.values())).ref
                reasons=[reason_label(i.code) for i in a.issues if getattr(i.source_ref,'row',None)==row.row and getattr(i.source_ref,'table_id',None)==table.id]
                pending.append([label,'基准' if side=='left' else '比较','无效业务键','',ref.source_id,ref.sheet or 'CSV记录',row.row,'','','；'.join(reasons),row_summary(row,table)])
            for group in a.duplicate_groups:
                for row in getattr(group,side):
                    ref=next(iter(row.cells.values())).ref
                    pending.append([label,'基准' if side=='left' else '比较','重复键歧义',key_label(task,group.key),ref.source_id,ref.sheet or 'CSV记录',row.row,'','',
                        f'基准{len(group.left)}条 / 比较{len(group.right)}条；未任意配对',row_summary(row,table)])
        for t in result.totals:
            totals.append([label,field_label(task,t['field_id']),context_label(t['context']),'同口径' if t['comparable_context'] else '口径不一致',t['included_pairs'],t['excluded_pairs'],
                ExactNumber(t['left_total']) if t['left_total'] is not None else None,ExactNumber(t['right_total']) if t['right_total'] is not None else None,ExactNumber(t['delta_sum']) if t['delta_sum'] is not None else None])
    for issue in issues:
        ref=issue.source_ref if isinstance(issue.source_ref,dict) else {}
        pending.append(['运行预检','来源','结构或执行问题','',ref.get('source_id',''),ref.get('sheet',''),ref.get('row',''),ref.get('column',''),'',issue.message,compact(ref)])
    mappings=[]
    definitions={t['id']:t for t in rules.tables}; sources={s['id']:s for s in rules.sources}
    for task in rules.tasks:
        for f in task['fields']:
            mappings.append([task_label(task,rules),f['left_header'],'业务键' if f['id'] in task['keys'] else '比较字段',task['left_table'],f['left_column'],f['left_header'],
                task['right_table'],f['right_column'],f['right_header'],f['type'],'、'.join(f.get('normalize',[])) or '保持原样',f.get('tolerance','0') if f['type']=='decimal' else '',compact(f.get('context',{})),task['formula_policy']])
    source_rows=[]
    for t in rules.tables:
        table=tables.get(t['id']); meta=table.metadata if table else {}; source=sources[t['source_id']]
        source_rows.append([t['id'],t['source_id'],Path(source['path']).name,t['sheet'] or 'CSV记录',t['header_row'],t['data_range'],meta.get('source_bytes'),meta.get('source_sha256','未取得'),
            compact(meta.get('hidden_rows',[])),compact(meta.get('hidden_columns',[])),meta.get('auto_filter') or '无',compact(t['exclusions']),'已核对' if table else '未核对'])
    views=[SheetData('字段与规则',['任务','字段','用途','基准表ID','基准列','基准表头','比较表ID','比较列','比较表头','类型','文本规则','绝对容差','单位/币种依据','公式策略'],mappings),
           SheetData('来源与范围',['逻辑表','文件ID','原文件名','工作表/记录','表头行','数据范围','文件字节数','来源SHA-256','隐藏行（仍纳入）','隐藏列（仍纳入）','筛选范围（仍纳入）','显式排除','覆盖状态'],source_rows)]
    views.extend([
      SheetData('差异明细',['任务','状态','业务键','字段','基准原值','比较原值','差额（比较减基准）','上下文','原因/规则','基准文件ID','基准工作表','基准原行','基准原列','比较文件ID','比较工作表','比较原行','比较原列','结果编号','基准核对值','比较核对值','说明'],differences,'E2',2),
      SheetData('仅基准侧',['任务','状态','业务键','文件ID','工作表/记录','原行','源字段摘要'],only['left'],'D2',2),
      SheetData('仅比较侧',['任务','状态','业务键','文件ID','工作表/记录','原行','源字段摘要'],only['right'],'D2',2),
      SheetData('待确认记录',['任务','侧别','待确认类型','业务键','文件ID','工作表/记录','原行/记录','原列','对应结果编号','具体原因','来源字段'],pending,'E2'),
      SheetData('匹配索引',['任务','业务键','基准文件ID','基准工作表','基准原行','比较文件ID','比较工作表','比较原行','完全一致字段','规则内一致字段','有差异字段','不可比字段','行状态'],matched,'C2',13),
      SheetData('数值汇总',['任务','字段','上下文','口径状态','纳入记录对','排除记录对','基准合计','比较合计','差额合计'],totals,'C2')])
    return [v for v in views if v.rows],found


def overview_rows(results,rules,found,shards,status):
    rows=[]
    def add(values=()): rows.append(list(values)+[None]*(11-len(values)))
    add(); add(['Excel 表格核对结果']); add(['按明确规则核对，保留每一处差异的来源。']); add()
    add(['执行状态',STATUS.get(status,status),'核对草稿：完整执行不代表业务一致。']); add()
    add(['唯一关联（对）',None,None,'字段有差异（处）',None,None,'字段不可比（处）',None,None,'重复 / 无效源行'])
    add([sum(r.row_counts['unique_pairs'] for r in results),None,None,sum(r.field_counts['different'] for r in results),None,None,sum(r.field_counts['not_comparable'] for r in results),None,None,
        sum(r.row_counts[s]['duplicate_ambiguous']+r.row_counts[s]['invalid_key'] for r in results for s in ('left','right'))])
    add(); add(['以上按已执行任务计数，未核对范围在下表明确列出。']); add()
    add(['任务','侧别','来源表','选择记录','纳入记录','显式排除','唯一关联','仅本侧','重复歧义','无效键','执行状态'])
    for task in rules.tasks:
        result=found.get(task['id'])
        for side in ('left','right'):
            counts=result.row_counts[side] if result else None
            table=next(t for t in rules.tables if t['id']==task[side+'_table'])
            source=next(s for s in rules.sources if s['id']==table['source_id'])
            name=table['sheet'] or Path(source['path']).name
            add([task_label(task,rules),'基准' if side=='left' else '比较',name]+([counts[k] for k in ('selected','included','excluded','unique_matched','only','duplicate_ambiguous','invalid_key')] if counts else ['未核对']*7)+[STATUS[result.status] if result else '未核对'])
    add(); add(['字段核对汇总']); add(['任务','匹配对数','完全一致','规则内一致','有差异','不可比较','字段总数','差异记录对','不可比记录对'])
    for task in rules.tasks:
        r=found.get(task['id'])
        add([task_label(task,rules)]+([r.row_counts['unique_pairs']]+[r.field_counts[s] for s in ('exact','within_rule','different','not_comparable')]+[len(r.field_results),r.row_counts['different_pairs'],r.row_counts['not_comparable_pairs']] if r else ['未核对']*8))
    add(); add(['阅读与复核']); add(['表格','明细条数','用途'])
    navigation={}
    for name,count in shards:
        add([name,count,'点击表名查看；可筛选、可回查原位置。']); navigation[len(rows)]=name
    add(); add(['说明'])
    for text in ('差额方向：比较侧减基准侧；“规则内一致”与“完全一致”分别统计。',
                 '不同币种/单位不直接汇总；数值汇总列明纳入及排除记录对。',
                 '隐藏行列与筛选行默认纳入；仅规则明确的行被排除。',
                 '来源文本按原样保存；精确数值超出Excel可靠精度时以文本保留。',
                 'Excel日期序号与ISO词法保留，可靠解析值见核对值或工作资料。',
                 '全部字段与来源关联明细见“工作资料”；原文件未改写。'):
        add([text])
    return rows,navigation
