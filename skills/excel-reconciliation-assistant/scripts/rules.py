"""Strict v1 structure/semantic validation using only the Python standard library."""
from __future__ import annotations

import codecs
import json
from pathlib import Path
import re
from common import Issue, RuleError, RuleSet, column_number, parse_range

ID = r'[a-z][a-z0-9_]{0,63}'
COL = r'[A-Z]{1,3}'
TOL = r'(0|[1-9][0-9]*)(\.[0-9]+)?'


def validate_rules(rules: RuleSet) -> list[Issue]:
    issues = []

    def error(path, message):
        issues.append(Issue('invalid_rules', message, {'rule_path': path}))

    def obj(value, path, allowed, required):
        if not isinstance(value, dict):
            error(path, '应为对象'); return False
        for key in value.keys()-set(allowed): error(path+'.'+str(key), '未知规则选项')
        for key in set(required)-value.keys(): error(path+'.'+key, '缺少必填规则')
        return True

    def text(value, path, pattern=None):
        if not isinstance(value, str) or not value or (pattern and not re.fullmatch(pattern, value)):
            error(path, '文本值或格式无效'); return False
        return True

    def array(value, path, low, high):
        if not isinstance(value, list) or not low <= len(value) <= high:
            error(path, '数组类型或长度无效'); return []
        return value

    def ident(value, path): return text(value, path, ID)

    def col(value, path):
        return text(value,path,COL) and (column_number(value)<=16384 or not error(path,'列超过XFD'))

    data = rules.payload
    if not obj(data,'$',('schema_version','sources','tables','tasks'),('schema_version','sources','tables','tasks')):
        return issues
    if data.get('schema_version') != '1.0': error('$.schema_version','仅支持规则协议1.0')
    source_map, table_map = {}, {}
    for i, source in enumerate(array(data.get('sources'),'$.sources',1,5)):
        p=f'$.sources[{i}]'
        if not obj(source,p,('id','path','format','encoding'),('id','path','format')): continue
        sid=source.get('id')
        if ident(sid,p+'.id'):
            if sid in source_map: error(p+'.id','来源ID重复')
            source_map[sid]=source
        location=source.get('path')
        if text(location,p+'.path'):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://',location) or '\x00' in location:
                error(p+'.path','仅允许授权的本地文件路径')
        fmt=source.get('format')
        if fmt not in ('xlsx','csv'): error(p+'.format','仅支持xlsx与csv')
        if 'encoding' in source:
            if text(source['encoding'],p+'.encoding'):
                try: codecs.lookup(source['encoding'])
                except LookupError: error(p+'.encoding','未知字符编码')
            if fmt!='csv': error(p+'.encoding','encoding仅适用于CSV')
    for i, table in enumerate(array(data.get('tables'),'$.tables',2,5)):
        p=f'$.tables[{i}]'
        names=('id','source_id','sheet','header_row','data_range','exclusions')
        if not obj(table,p,names,names): continue
        tid=table.get('id'); sid=table.get('source_id')
        if ident(tid,p+'.id'):
            if tid in table_map: error(p+'.id','表ID重复')
            table_map[tid]=table
        if not isinstance(sid,str) or sid not in source_map: error(p+'.source_id','引用来源不存在')
        else:
            fmt=source_map[sid].get('format')
            if fmt=='csv' and table.get('sheet') is not None: error(p+'.sheet','CSV工作表必须为null')
            if fmt=='xlsx': text(table.get('sheet'),p+'.sheet')
        hr=table.get('header_row')
        if type(hr) is not int or not 1<=hr<=1048576: error(p+'.header_row','表头行无效')
        bounds=None
        if isinstance(table.get('data_range'),str):
            try: bounds=parse_range(table['data_range'])
            except ValueError as e: error(p+'.data_range',str(e))
        else: error(p+'.data_range','数据范围须为字符串')
        if bounds:
            c1,r1,c2,r2=bounds
            if r2-r1+1>50000 or c2-c1+1>200: error(p+'.data_range','单表范围超过5万行或200列')
            if type(hr) is int and hr>=r1: error(p+'.header_row','表头必须位于数据范围之前')
        excluded=set()
        for j, exclusion in enumerate(array(table.get('exclusions'),p+'.exclusions',0,50000)):
            ep=f'{p}.exclusions[{j}]'
            if not obj(exclusion,ep,('rows','reason'),('rows','reason')): continue
            text(exclusion.get('reason'),ep+'.reason')
            for row in array(exclusion.get('rows'),ep+'.rows',1,50000):
                if type(row) is not int or not bounds or not bounds[1]<=row<=bounds[3]: error(ep+'.rows','排除行超出数据范围')
                elif row in excluded: error(ep+'.rows','重复排除行')
                else: excluded.add(row)
        if bounds and len(excluded)==bounds[3]-bounds[1]+1: error(p+'.exclusions','不能排除全部数据记录')
    task_ids=set()
    for i, task in enumerate(array(data.get('tasks'),'$.tasks',1,4)):
        p=f'$.tasks[{i}]'; names=('id','left_table','right_table','keys','fields','formula_policy')
        if not obj(task,p,names,names): continue
        tid=task.get('id')
        if ident(tid,p+'.id'):
            if tid in task_ids: error(p+'.id','任务ID重复')
            task_ids.add(tid)
        for side in ('left','right'):
            value=task.get(side+'_table')
            if not isinstance(value,str) or value not in table_map: error(p+'.'+side+'_table','引用表不存在')
        if task.get('left_table')==task.get('right_table'): error(p+'.right_table','不能将同一逻辑表与自身比较')
        if task.get('formula_policy') not in ('pending','cached'): error(p+'.formula_policy','公式策略须为pending或cached')
        fields={}; used={'left':set(),'right':set()}
        for j, f in enumerate(array(task.get('fields'),p+'.fields',2,200)):
            fp=f'{p}.fields[{j}]'
            required=('id','left_column','right_column','left_header','right_header','type')
            optional=('normalize','nullable','parse_numeric_text','tolerance','date_format','context')
            if not obj(f,fp,required+optional,required): continue
            fid=f.get('id')
            if ident(fid,fp+'.id'):
                if fid in fields: error(fp+'.id','字段ID重复')
                fields[fid]=f
            for side in ('left','right'):
                c=f.get(side+'_column'); cp=fp+'.'+side+'_column'
                if col(c,cp):
                    if c in used[side]: error(cp,'同侧列重复绑定')
                    used[side].add(c)
                    t=table_map.get(task.get(side+'_table')) if isinstance(task.get(side+'_table'),str) else None
                    if t and isinstance(t.get('data_range'),str):
                        try:
                            c1,_,c2,_=parse_range(t['data_range'])
                            if not c1<=column_number(c)<=c2: error(cp,'映射列超出数据范围')
                        except ValueError: pass
                text(f.get(side+'_header'),fp+'.'+side+'_header')
            kind=f.get('type')
            if kind not in ('identifier','text','decimal','date','datetime'): error(fp+'.type','不支持的字段类型')
            for option in ('nullable','parse_numeric_text'):
                if option in f and type(f[option]) is not bool: error(fp+'.'+option,'须为布尔值')
            allowed={'nullable'}
            if kind in ('identifier','text'):
                allowed.add('normalize')
                if 'normalize' in f:
                    ns=array(f['normalize'],fp+'.normalize',0,3)
                    if any(not isinstance(n,str) or n not in ('trim','casefold','nfkc') for n in ns) or len({str(n) for n in ns})!=len(ns): error(fp+'.normalize','规范化选项无效或重复')
            elif kind=='decimal':
                allowed.update(('parse_numeric_text','tolerance','context'))
                if 'tolerance' in f: text(f['tolerance'],fp+'.tolerance',TOL)
                if 'context' in f:
                    context=f['context']; cp=fp+'.context'
                    if obj(context,cp,('currency','unit'),()):
                        if not context: error(cp,'上下文不能为空')
                        for name,pair in context.items():
                            if name not in ('currency','unit'): continue
                            if obj(pair,cp+'.'+name,('left','right'),('left','right')):
                                for side,value in pair.items():
                                    sp=cp+'.'+name+'.'+side
                                    if not obj(value,sp,('literal','column'),()): continue
                                    if len(value)!=1: error(sp,'固定值或列只能选择一个')
                                    if 'literal' in value: text(value['literal'],sp+'.literal')
                                    if 'column' in value and col(value['column'],sp+'.column'):
                                        t=table_map.get(task.get(side+'_table')) if isinstance(task.get(side+'_table'),str) else None
                                        if t:
                                            try:
                                                c1,_,c2,_=parse_range(t['data_range'])
                                                if not c1<=column_number(value['column'])<=c2: error(sp+'.column','上下文列超出数据范围')
                                            except (ValueError,KeyError,TypeError): pass
            elif kind in ('date','datetime'):
                allowed.add('date_format')
                df=f.get('date_format')
                if obj(df,fp+'.date_format',('left','right'),('left','right')):
                    for side in ('left','right'): text(df.get(side),fp+'.date_format.'+side)
            for option in set(optional)-allowed:
                if option in f: error(fp+'.'+option,'此字段类型不支持该选项')
        keys=array(task.get('keys'),p+'.keys',1,8); seen=set()
        for key in keys:
            if not isinstance(key,str) or key not in fields: error(p+'.keys','键字段不存在'); continue
            if key in seen: error(p+'.keys','键字段重复')
            seen.add(key)
            if fields[key].get('type') not in ('identifier','text'): error(p+'.keys','键仅支持identifier或text')
        if fields and seen==fields.keys(): error(p+'.fields','至少需要一个非键比较字段')
    return issues


def load_rules(path: Path) -> RuleSet:
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('JSON字段重复：'+k)
            result[k]=v
        return result
    def invalid_constant(value): raise ValueError('JSON不允许非有限值：'+value)
    path=Path(path)
    try:
        with path.open('rb') as f:
            raw=f.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('规则文件超过1MiB')
        payload=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid_constant)
    except (OSError,ValueError,UnicodeError,RecursionError) as e:
        raise RuleError([Issue('invalid_rules_file',str(e),{'rule_path':'$'})]) from e
    rules=RuleSet.from_dict(payload,path)
    issues=validate_rules(rules)
    if issues: raise RuleError(issues)
    return rules
