"""Explicit typed parsing; exact Decimal arithmetic isolated from caller context."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, DivisionByZero, Overflow, Context, ROUND_HALF_EVEN, localcontext
import re
from normalization import normalize_text

PLAIN_DECIMAL=re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)')
ISO_DATE=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
ISO_DATETIME=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?')


def exact_context(precision):
    return Context(prec=precision,rounding=ROUND_HALF_EVEN,Emin=-999999,Emax=999999,capitals=1,clamp=0,flags=[],traps=[InvalidOperation,DivisionByZero,Overflow])


@dataclass
class Parsed:
    value: object = None
    normalized: object = None
    reason: str = ''


def decimal_value(text):
    try: value=Decimal(text)
    except (InvalidOperation,ValueError,TypeError): return Parsed(reason='numeric_value_invalid')
    if not value.is_finite(): return Parsed(reason='numeric_value_invalid')
    if len(value.as_tuple().digits)>1000 or abs(value.adjusted())>1000:
        return Parsed(reason='numeric_out_of_range')
    return Parsed(value,str(value))


def precise_sum(values):
    if not values: return None
    precision=max(28,max(v.adjusted() for v in values)-min(v.as_tuple().exponent for v in values)+len(str(len(values)))+3)
    with localcontext(exact_context(precision)):
        return sum(values,Decimal(0))


def precise_difference(right,left):
    precision=max(28,max(right.adjusted(),left.adjusted())-min(right.as_tuple().exponent,left.as_tuple().exponent)+3)
    with localcontext(exact_context(precision)):
        return right-left


def _date_value(cell,field,side,date_system):
    value=cell.raw; kind=field['type']; fmt=field['date_format'][side]
    native_iso=cell.raw_type=='date' and cell.date_lexeme is not None
    if native_iso:
        value=cell.date_lexeme; fmt='ISO8601'
        try:
            if ISO_DATE.fullmatch(value): value=date.fromisoformat(value)
            elif ISO_DATETIME.fullmatch(value): value=datetime.fromisoformat(value[:-1]+'+00:00' if value.endswith('Z') else value)
            else: return Parsed(reason='date_precision_unverified')
        except (ValueError,TypeError): return Parsed(reason='date_format_mismatch')
    elif cell.raw_type=='date' and cell.numeric_lexeme is None and cell.ref.sheet is not None:
        return Parsed(reason='date_lexeme_missing')
    if cell.raw_type=='date' and cell.numeric_lexeme is not None:
        serial=decimal_value(cell.numeric_lexeme)
        if serial.reason: return serial
        if date_system not in ('1900','1904'): return Parsed(reason='date_system_unknown')
        if date_system=='1900' and Decimal(60)<=serial.value<Decimal(61): return Parsed(reason='excel_phantom_date')
        if kind=='date' and serial.value!=serial.value.to_integral_value(): return Parsed(reason='date_has_time')
        with localcontext(exact_context(2100)):
            milliseconds=serial.value*Decimal(86400000)
            if kind=='datetime' and milliseconds!=milliseconds.to_integral_value(): return Parsed(reason='date_precision_unverified')
        if date_system=='1904' and Decimal(0)<=serial.value<Decimal(1) and isinstance(value,time):
            value=datetime.combine(date(1904,1,1),value)
    if cell.raw_type=='string' and isinstance(value,str):
        try:
            if fmt=='ISO8601':
                if kind=='date':
                    if not ISO_DATE.fullmatch(value): return Parsed(reason='date_format_mismatch')
                    value=date.fromisoformat(value)
                else:
                    if not ISO_DATETIME.fullmatch(value): return Parsed(reason='date_format_mismatch')
                    value=datetime.fromisoformat(value[:-1]+'+00:00' if value.endswith('Z') else value)
            else:
                directives=re.findall(r'%([A-Za-z%])',fmt)
                if not {'Y','m','d'}<=set(directives) or any(d not in ('Y','m','d','H','M','S','f','z','%') for d in directives):
                    return Parsed(reason='date_format_unsupported')
                if kind=='datetime' and not {'H','M'}<=set(directives): return Parsed(reason='datetime_time_missing')
                value=datetime.strptime(value,fmt)
        except (ValueError,TypeError,OverflowError,re.error): return Parsed(reason='date_format_mismatch')
    elif cell.raw_type!='date': return Parsed(reason='type_mismatch')
    if kind=='date':
        if isinstance(value,datetime):
            if value.tzinfo is not None: return Parsed(reason='date_has_timezone')
            if value.time()!=time(): return Parsed(reason='date_has_time')
            value=value.date()
        if not isinstance(value,date): return Parsed(reason='type_mismatch')
    elif not isinstance(value,datetime): return Parsed(reason='datetime_time_missing')
    return Parsed(value,value.isoformat())


def parse_value(cell,field,side,date_system=None):
    value=cell.raw; kind=field['type']
    if value is None or value=='': return Parsed()
    if kind in ('identifier','text'):
        if cell.raw_type!='string' or not isinstance(value,str): return Parsed(reason='type_mismatch')
        normalized=normalize_text(value,field.get('normalize',[]))
        return Parsed(normalized,normalized) if normalized!='' else Parsed()
    if kind=='decimal':
        if cell.raw_type=='string':
            if not field.get('parse_numeric_text',False): return Parsed(reason='numeric_text_disabled')
            if not isinstance(value,str) or not PLAIN_DECIMAL.fullmatch(value): return Parsed(reason='numeric_text_invalid')
            return decimal_value(value)
        if cell.raw_type!='number' or type(value) is bool: return Parsed(reason='type_mismatch')
        text=cell.numeric_lexeme
        if text is None:
            if type(value) is int: text=str(value)
            else: return Parsed(reason='numeric_lexeme_missing')
        return decimal_value(text)
    if kind in ('date','datetime'): return _date_value(cell,field,side,date_system)
    return Parsed(reason='unsupported_type')
