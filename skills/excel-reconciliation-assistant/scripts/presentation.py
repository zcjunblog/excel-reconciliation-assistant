"""Shared reader-facing labels, exact value display and safe JSON conversion."""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import math

STATUS={'exact':'完全一致','within_rule':'规则内一致','different':'有差异','not_comparable':'不可比较','complete':'已执行','needs_confirmation':'待确认','blocked':'未核对','partial':'部分完成','ready':'预检就绪'}
REASONS={
 'equal':'值一致','both_missing':'规则允许两侧为空','absolute_tolerance':'差额在绝对容差内','explicit_normalization':'按明确文本规则一致',
 'tolerance_exceeded':'差额超出容差','value_mismatch':'字段值不同','currency_mismatch':'币种不同，未计算差额','unit_mismatch':'单位不同，未计算差额',
 'currency_context_missing':'币种依据缺失或不可读取','unit_context_missing':'计量单位依据缺失或不可读取','required_value_missing':'必填值缺失','missing_value_mismatch':'仅一侧为空',
 'formula_cache_missing':'公式没有可用缓存','formula_error':'公式缓存为错误值','formula_requires_confirmation':'公式值需确认比较策略','external_formula':'外部工作簿公式不可比较',
 'cell_error':'来源含Excel错误值','date_format_mismatch':'日期不符合指定格式','timezone_mismatch':'时区有无或偏移不同','date_has_time':'日期字段包含非零时间',
 'date_has_timezone':'日期字段包含时区','excel_phantom_date':'1900日期系统中的虚构闰日','date_precision_unverified':'源日期精度不能可靠保留','date_lexeme_missing':'缺少可靠日期源词法',
 'date_system_unknown':'日期系统未确定','datetime_time_missing':'日期时间缺少明确时间','date_format_unsupported':'日期格式包含尚未支持的规则',
 'numeric_text_disabled':'规则未允许数值文本解析','numeric_text_invalid':'数值文本格式不明确','numeric_value_invalid':'不是有限十进制数','numeric_lexeme_missing':'缺少可靠数值源词法','numeric_out_of_range':'数值超出本版精确计算范围',
 'type_mismatch':'字段类型与规则不一致','missing_key':'业务键缺失','formula_key':'公式不能作为业务键','numeric_identifier':'数值型编号需确认','numeric_identifier_precision_risk':'长数值编号存在精度风险',
 'invalid_key_type':'业务键类型不支持','missing_key_field':'键映射列缺失','duplicate_ambiguous':'同键多行，未任意配对','cache_freshness_unverified':'使用已保存缓存，新鲜度未验证'}


def reason_label(code): return REASONS.get(code,code)


def json_safe(value):
    if is_dataclass(value): return json_safe(asdict(value))
    if isinstance(value,dict): return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)): return [json_safe(v) for v in value]
    if isinstance(value,(date,datetime,time)): return {'type':type(value).__name__,'value':value.isoformat()}
    if isinstance(value,timedelta): return {'type':'duration','value':str(value)}
    if isinstance(value,Decimal): return {'type':'decimal','value':str(value)}
    if isinstance(value,Path): return value.name
    if isinstance(value,float): return {'type':'float' if math.isfinite(value) else 'nonfinite','value':repr(value)}
    return value


def compact(value): return json.dumps(json_safe(value),ensure_ascii=False,separators=(',',':'),allow_nan=False)


class ExactNumber:
    def __init__(self,text): self.text=str(text)

    def excel(self):
        try:
            d=Decimal(self.text); f=float(d)
            if d.is_finite() and len(d.as_tuple().digits)<=15 and abs(d.adjusted())<=14 and math.isfinite(f) and Decimal(str(f))==d:
                places=max(0,-d.as_tuple().exponent)
                return (int(d) if d==d.to_integral_value() else f),'0'+('.'+'0'*places if places else '')
        except (ValueError,OverflowError,InvalidOperation): pass
        return self.text,'@'


def original_value(cell):
    if cell.formula is not None: return cell.formula
    if cell.date_lexeme is not None: return cell.date_lexeme
    if cell.raw_type=='date' and cell.numeric_lexeme is not None: return 'Excel日期序号 '+cell.numeric_lexeme
    if cell.raw_type=='number' and cell.numeric_lexeme is not None: return ExactNumber(cell.numeric_lexeme)
    if isinstance(cell.raw,(date,datetime,time)): return cell.raw.isoformat()
    return cell.raw


def display_text(value):
    if isinstance(value,ExactNumber): return value.text
    if value is None: return '（空）'
    if isinstance(value,str): return value
    return str(value)


def task_label(task,rules):
    tables={t['id']:t for t in rules.tables}; sources={s['id']:s for s in rules.sources}
    labels=[]
    for side in ('left','right'):
        t=tables.get(task[side+'_table'])
        labels.append((t.get('sheet') or Path(sources[t['source_id']]['path']).stem) if t else task[side+'_table'])
    return ' 与 '.join(labels)


def field_label(task,fid):
    return next((f['left_header'] for f in task['fields'] if f['id']==fid),fid)


def context_label(context):
    labels=[]
    for name,pair in context.items():
        label={'currency':'币种','unit':'单位'}.get(name,name)
        if pair.get('left')==pair.get('right'): labels.append(f"{label}：{pair.get('left') or '未明确'}")
        else: labels.append(f"{label}：基准 {pair.get('left') or '未明确'} / 比较 {pair.get('right') or '未明确'}")
    return '；'.join(labels) or '未声明单位/币种'
