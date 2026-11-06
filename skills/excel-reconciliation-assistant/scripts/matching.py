"""Exact keyed association, with all ambiguous groups isolated on both sides."""
from __future__ import annotations
import copy
from decimal import Decimal, InvalidOperation
from common import AssociationResult, AmbiguousGroup, IntakeError, Issue, MatchedPair
from normalization import normalize_text


def _validate_inputs(left,right,task):
    if left.id!=task.get('left_table') or right.id!=task.get('right_table') or left.id==right.id:
        raise IntakeError('invalid_association_input','关联输入表与任务指定的左右表不一致')
    fields=task.get('fields',[]); keys=task.get('keys',[])
    if not fields or not keys or len({f['id'] for f in fields})!=len(fields):
        raise IntakeError('invalid_association_rule','字段或键未明确指定')
    mapping={f['id']:f for f in fields}
    if len(set(keys))!=len(keys) or any(k not in mapping or mapping[k]['type'] not in ('identifier','text') for k in keys):
        raise IntakeError('invalid_association_rule','键引用无效或类型不支持')
    for side,table in (('left',left),('right',right)):
        if not table.rows or not table.selected_rows:
            raise IntakeError('empty_table','空范围或全排除表不能作为已核对输入',{'table_id':table.id})
        for f in fields:
            if table.header.get(f[side+'_column'])!=f[side+'_header']:
                raise IntakeError('invalid_association_input','映射字段或实际表头不匹配',{'table_id':table.id,'field':f['id']})
        row_ids=[r.row for r in table.rows]
        selected=set(table.selected_rows); excluded=set(table.excluded_rows)
        if len(set(row_ids))!=len(row_ids) or len(selected)!=len(table.selected_rows) or set(row_ids)&excluded or set(row_ids)|excluded!=selected:
            raise IntakeError('invalid_association_input','输入行号、纳入与排除范围不守恒',{'table_id':table.id})
        identities={(c.ref.source_id,c.ref.sheet) for row in table.rows for c in row.cells.values()}
        if len(identities)!=1:
            raise IntakeError('invalid_association_input','同一逻辑表包含不一致的来源或工作表',{'table_id':table.id})
        for row in table.rows:
            for column,c in row.cells.items():
                if c.ref.row!=row.row or c.ref.column!=column or c.ref.table_id!=table.id:
                    raise IntakeError('invalid_association_input','单元格来源定位与输入表不一致',{'table_id':table.id,'row':row.row})


def _key(row,fields,side,issues):
    values=[]
    for field in fields:
        c=row.cells.get(field[side+'_column'])
        reason=None
        if c is None: reason='missing_key_field'
        elif c.formula is not None or c.raw_type=='formula': reason='formula_key'
        elif c.raw is None or c.raw=='': reason='missing_key'
        elif c.raw_type!='string' or not isinstance(c.raw,str):
            reason='invalid_key_type'
            if field['type']=='identifier' and c.raw_type=='number':
                reason='numeric_identifier'
                try:
                    number=Decimal(c.numeric_lexeme if c.numeric_lexeme is not None else str(c.raw))
                    if number.is_finite() and (number.copy_abs()>=Decimal('1e15') or len(number.as_tuple().digits)>15):
                        reason='numeric_identifier_precision_risk'
                except (InvalidOperation,ValueError): pass
        if reason is None:
            value=normalize_text(c.raw,field.get('normalize',[]))
            if value=='': reason='missing_key'
        if reason:
            issues.append(Issue(reason,'业务键无效，保留原行待确认',c.ref if c is not None else {'row':row.row,'field_id':field['id']}))
            return None
        values.append((field['type'],value))
    return tuple(values)


def associate(left,right,task):
    _validate_inputs(left,right,task)
    fields={f['id']:f for f in task['fields']}; keys=[fields[k] for k in task['keys']]
    groups={'left':{},'right':{}}; invalid={'left':[],'right':[]}; issues=[]
    for side,table in (('left',left),('right',right)):
        for row in sorted(table.rows,key=lambda r:r.row):
            key=_key(row,keys,side,issues)
            if key is None: invalid[side].append(row)
            else: groups[side].setdefault(key,[]).append(row)
    pairs=[]; ambiguous=[]; only={'left':[],'right':[]}
    for key in sorted(groups['left'].keys() | groups['right'].keys()):
        a=groups['left'].get(key,[]); b=groups['right'].get(key,[])
        display_key=tuple(value for kind,value in key)
        if len(a)>1 or len(b)>1: ambiguous.append(AmbiguousGroup(display_key,a,b))
        elif a and b: pairs.append(MatchedPair(a[0],b[0],display_key,{s:t.metadata.get('date_system') for s,t in (('left',left),('right',right))}))
        else: only['left'].extend(a); only['right'].extend(b)
    pairs.sort(key=lambda p:(p.left.row,p.right.row))
    for side in only: only[side].sort(key=lambda r:r.row)
    return AssociationResult(task['id'],left,right,copy.deepcopy(task),pairs,only['left'],only['right'],ambiguous,invalid['left'],invalid['right'],
        {s:tuple(sorted(r.row for r in t.rows)) for s,t in (('left',left),('right',right))},
        {s:tuple(t.selected_rows) for s,t in (('left',left),('right',right))},
        {s:dict(t.excluded_rows) for s,t in (('left',left),('right',right))},issues)
