"""Compare only unique pairs, preserving original cells and explicit rules."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import replace
from decimal import Decimal
import json
import re
from common import FieldResult, IntakeError, TaskResult
from typed_values import parse_value, precise_difference, precise_sum

STATUSES=('exact','within_rule','different','not_comparable')


def _external_formula(formula):
    # Ignore Excel string literals and require a workbook/sheet reference token,
    # not a structured table field followed by an unrelated comma/operator.
    text=re.sub(r'"(?:[^"]|"")*"','""',formula)
    quoted=r"'(?:[^']|'')*\[[^\]]+\](?:[^']|'')*'!"
    unquoted=r"\[[^\]]+\][^!'\[\](),;+*/^&=<>\s-]*!"
    return re.search(quoted+'|'+unquoted,text) is not None


def _formula_cells(a,b,policy):
    warnings=[]; originals=(a,b)
    formulas=[c for c in originals if c.formula is not None or c.raw_type=='formula']
    if formulas and policy=='cached': warnings.append('cache_freshness_unverified')
    if any(c.formula and _external_formula(c.formula) for c in formulas): return None,'external_formula',warnings
    if any(c.cache_type=='error' for c in formulas): return None,'formula_error',warnings
    if any(c.cached is None or c.cache_type in (None,'missing') for c in formulas): return None,'formula_cache_missing',warnings
    if formulas and policy=='pending': return None,'formula_requires_confirmation',warnings
    if policy not in ('pending','cached'): raise IntakeError('invalid_comparison_rule','公式策略无效')
    if any(c.raw_type=='error' for c in originals): return None,'cell_error',warnings
    return tuple(replace(c,raw=c.cached,raw_type=c.cache_type,formula=None) if c in formulas else c for c in originals),'',warnings


def _context(pair,field):
    result={}; reason=''
    for name,rule in field.get('context',{}).items():
        values={}
        for side in ('left','right'):
            spec=rule[side]
            if 'literal' in spec: value=spec['literal']
            else:
                c=getattr(pair,side).cells.get(spec['column'])
                value=c.raw if c is not None and c.raw_type=='string' and c.formula is None else None
            values[side]=value
        result[name]=values
        if any(not isinstance(v,str) or v=='' for v in values.values()): reason=reason or name+'_context_missing'
        elif values['left']!=values['right']: reason=reason or name+'_mismatch'
    return result,reason


def compare_pair(pair,task):
    results=[]
    for field in task['fields']:
        if field['id'] in task['keys']: continue
        try: a=pair.left.cells[field['left_column']]; b=pair.right.cells[field['right_column']]
        except KeyError as e: raise IntakeError('missing_comparison_field','映射字段缺失，不能按空值比较') from e
        resolved,reason,warnings=_formula_cells(a,b,task['formula_policy'])
        context,context_error=_context(pair,field)
        reason=reason or context_error
        status='not_comparable'; delta=None; na=nb=None
        if not reason:
            pa=parse_value(resolved[0],field,'left',pair.date_systems.get('left'))
            pb=parse_value(resolved[1],field,'right',pair.date_systems.get('right'))
            na,nb=pa.normalized,pb.normalized
            reason=pa.reason or pb.reason
            if not reason:
                if pa.value is None or pb.value is None:
                    if not field.get('nullable',False): reason='required_value_missing'
                    elif pa.value is None and pb.value is None: status,reason='exact','both_missing'
                    else: status,reason='different','missing_value_mismatch'
                elif field['type']=='decimal':
                    difference=precise_difference(pb.value,pa.value); delta=format(difference,'f')
                    if difference==0: status,reason='exact','equal'
                    elif difference.copy_abs()<=Decimal(field.get('tolerance','0')): status,reason='within_rule','absolute_tolerance'
                    else: status,reason='different','tolerance_exceeded'
                elif field['type']=='datetime' and pa.value.utcoffset()!=pb.value.utcoffset(): reason='timezone_mismatch'
                elif pa.value==pb.value:
                    if field['type'] in ('text','identifier') and resolved[0].raw!=resolved[1].raw:
                        status,reason='within_rule','explicit_normalization'
                    else: status,reason='exact','equal'
                else: status,reason='different','value_mismatch'
        result_id=f"{task['id']}:{a.ref.table_id}:{a.ref.row}:{b.ref.table_id}:{b.ref.row}:{field['id']}"
        results.append(FieldResult(result_id,task['id'],pair.key,field['id'],a,b,na,nb,status,reason,delta,warnings,context))
    return results


def summarize(association,fields):
    counts=Counter(f.status for f in fields)
    per_pair=defaultdict(list)
    for f in fields: per_pair[(f.left.ref.row,f.right.ref.row)].append(f)
    row_statuses=[]; row_status_counts=Counter(); different=set(); uncertain=set()
    for pair in association.unique_pairs:
        key=(pair.left.row,pair.right.row); values=per_pair[key]; present={f.status for f in values}
        status=next((s for s in reversed(STATUSES) if s in present),'exact')
        row_status_counts[status]+=1
        if 'different' in present: different.add(key)
        if 'not_comparable' in present: uncertain.add(key)
        row_statuses.append({'left_row':key[0],'right_row':key[1],'status':status,'field_counts':{s:sum(f.status==s for f in values) for s in STATUSES}})
    rows={}
    for side in ('left','right'):
        rows[side]={'selected':len(association.selected_rows[side]),'included':len(association.included_rows[side]),'excluded':len(association.excluded_rows[side]),
                    'unique_matched':len(association.unique_pairs),'only':len(getattr(association,side+'_only')),
                    'duplicate_ambiguous':sum(len(getattr(g,side)) for g in association.duplicate_groups),'invalid_key':len(getattr(association,side+'_invalid'))}
    rows.update(unique_pairs=len(association.unique_pairs),different_pairs=len(different),not_comparable_pairs=len(uncertain),row_status_counts={s:row_status_counts[s] for s in STATUSES})
    return rows,{s:counts[s] for s in STATUSES},row_statuses


def decimal_totals(fields,task):
    decimal_ids={f['id'] for f in task['fields'] if f['type']=='decimal' and f['id'] not in task['keys']}
    groups={}
    for f in fields:
        if f.field_id not in decimal_ids: continue
        key=(f.field_id,json.dumps(f.context,sort_keys=True,ensure_ascii=False))
        groups.setdefault(key,[]).append(f)
    totals=[]
    for (fid,_),records in groups.items():
        context=records[0].context
        valid=all(isinstance(v['left'],str) and v['left']!='' and v['left']==v['right'] for v in context.values())
        included=[f for f in records if valid and f.status!='not_comparable' and f.normalized_left is not None and f.normalized_right is not None]
        left=precise_sum([Decimal(f.normalized_left) for f in included]); right=precise_sum([Decimal(f.normalized_right) for f in included])
        totals.append({'task_id':task['id'],'field_id':fid,'context':context,'comparable_context':valid,'included_pairs':len(included),'excluded_pairs':len(records)-len(included),
                       'left_total':format(left,'f') if left is not None else None,'right_total':format(right,'f') if right is not None else None,
                       'delta_sum':format(precise_difference(right,left),'f') if left is not None else None})
    return totals


def compare_task(association,task,budget):
    if association.task_rule!=task or association.task_id!=task['id']:
        raise IntakeError('rules_changed','关联后规则发生变化，必须重新关联',fatal=True)
    count=len(association.unique_pairs)*sum(f['id'] not in task['keys'] for f in task['fields'])
    budget.charge('field_comparisons',count,'max_comparisons')
    fields=[]
    for pair in association.unique_pairs:
        budget.check(); fields.extend(compare_pair(pair,task))
    rows,counts,statuses=summarize(association,fields)
    budget.check()
    pending=association.duplicate_groups or association.left_invalid or association.right_invalid or counts['not_comparable'] or any(f.warnings for f in fields)
    result=TaskResult(association,fields,list(association.issues),rows,counts,'needs_confirmation' if pending else 'complete',statuses,decimal_totals(fields,task))
    from checks import verify_coverage
    issues=verify_coverage(result)
    if issues: raise IntakeError('coverage_failed','核对覆盖或数量检查失败，不能交付完整结论',{'issues':[i.code for i in issues]},fatal=True)
    budget.check()
    return result
