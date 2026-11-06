"""Sparse XML preflight plus bounded openpyxl formula/cache reads. Never saves input."""
from __future__ import annotations
from datetime import date, datetime, time, timedelta
import io
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET
from common import IntakeError, column_name, column_number, parse_range
from table_data import Grid, RawCell, wanted

NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def _scan_strings(archive, budget):
    manifest=ET.fromstring(archive.read('[Content_Types].xml'))
    members=[e.get('PartName','').lstrip('/') for e in manifest if e.get('ContentType','').endswith('.sharedStrings+xml')]
    if not members: return
    if len(members)!=1 or members[0] not in archive.namelist():
        raise IntakeError('invalid_workbook','共享字符串资源缺失或声明重复')
    count=0
    with archive.open(members[0]) as stream:
        context=ET.iterparse(stream,events=('start','end')); _,root=next(context)
        for event,element in context:
            if event=='end' and element.tag==NS+'si':
                budget.check(); count+=1; budget.enforce('max_scan_cells',count)
                budget.enforce('max_text_chars',sum(len(t.text or '') for t in element.iter(NS+'t')))
                element.clear(); root.clear()


def _scan_sheet(archive, name, selected, budget, scanned):
    cells={}; metadata={'hidden_rows':[],'hidden_column_ranges':[],'merged_ranges':[],'unsupported_formula_ranges':[],'auto_filter':None,'declared_dimension':None}
    current_row=0; last_col=0; max_col=0
    with archive.open(name) as stream:
        context=ET.iterparse(stream,events=('start','end'))
        for event,e in context:
            budget.check()
            tag=e.tag
            if event=='start' and tag==NS+'row':
                r=int(e.get('r',current_row+1))
                if r<=current_row or r>1048576: raise IntakeError('invalid_workbook','工作表行坐标无效或顺序异常')
                scanned['rows']+=r-current_row; current_row=r; last_col=0
                budget.enforce('max_scan_rows',scanned['rows'])
                if e.get('hidden') in ('1','true'): metadata['hidden_rows'].append(r)
            if event!='end': continue
            if tag==NS+'c':
                address=e.get('r',column_name(last_col+1)+str(current_row))
                m=re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]*)',address)
                if not m: raise IntakeError('invalid_workbook','单元格坐标无效')
                col=column_number(m[1]); row=int(m[2])
                if row!=current_row or not last_col<col<=16384: raise IntakeError('invalid_workbook','单元格重复、错行或顺序异常')
                last_col=col; max_col=max(max_col,col)
                scanned['cells']+=1; budget.enforce('max_scan_cells',scanned['cells'])
                inline_container=e.find(NS+'is')
                inline=''
                if inline_container is not None:
                    # rPh holds phonetic guides, not the visible cell text.
                    for child in inline_container:
                        if child.tag==NS+'t': inline+=child.text or ''
                        elif child.tag==NS+'r': inline+=''.join(t.text or '' for t in child.findall(NS+'t'))
                v=e.find(NS+'v'); numeric=v.text if v is not None else None
                formula=e.find(NS+'f'); formula_text=formula.text if formula is not None else None
                budget.enforce('max_text_chars',len(inline))
                budget.enforce('max_text_chars',len(numeric or ''))
                if formula_text is not None: budget.enforce('max_text_chars',len(formula_text))
                if formula is not None and formula.get('t','normal') not in ('normal','shared'):
                    formula_range=formula.get('ref',address)
                    parse_range(formula_range if ':' in formula_range else formula_range+':'+formula_range)
                    metadata['unsupported_formula_ranges'].append(formula_range)
                if wanted(row,col,selected):
                    cells[(row,col)]={'type':e.get('t','n'),'numeric':numeric,'inline':inline,'formula_present':formula is not None,'formula_text':formula_text}
                e.clear()
            elif tag==NS+'dimension': metadata['declared_dimension']=e.get('ref')
            elif tag==NS+'col':
                lo,hi=int(e.get('min','0')),int(e.get('max','0'))
                if not 1<=lo<=hi<=16384: raise IntakeError('invalid_workbook','列定义范围无效')
                if e.get('hidden') in ('1','true'): metadata['hidden_column_ranges'].append((lo,hi))
            elif tag==NS+'mergeCell':
                ref=e.get('ref',''); parse_range(ref if ':' in ref else ref+':'+ref)
                metadata['merged_ranges'].append(ref)
            elif tag==NS+'autoFilter': metadata['auto_filter']=e.get('ref')
            elif tag==NS+'row': e.clear()
    metadata['actual_max_row']=current_row; metadata['actual_max_column']=max_col
    return Grid({},current_row,max_col,metadata),cells


def _kind(value, cell):
    if cell.data_type=='e': return 'error'
    if value is None: return 'missing'
    if type(value) is bool: return 'boolean'
    if isinstance(value,(datetime,date,time,timedelta)): return 'date'
    if isinstance(value,(int,float)): return 'number'
    return 'string'


def _read_table_values(formula_book,cache_book,table,grid,raw,budget):
    left=formula_book[table['sheet']]; right=cache_book[table['sheet']]
    left.reset_dimensions(); right.reset_dimensions()
    c1,r1,c2,r2=parse_range(table['data_range'])
    for low,high in ((table['header_row'],table['header_row']),(r1,min(r2,grid.max_row))):
        if high<low: continue
        values=left.iter_rows(min_row=low,max_row=high,min_col=c1,max_col=c2)
        caches=right.iter_rows(min_row=low,max_row=high,min_col=c1,max_col=c2)
        for row,(normal,cached) in enumerate(zip(values,caches),low):
            budget.check()
            for col,(a,b) in enumerate(zip(normal,cached),c1):
                entry=raw.get((row,col))
                if entry is None: continue
                formula=a.value if a.data_type=='f' else None
                if formula is not None and not isinstance(formula,str):
                    formula='='+entry['formula_text'] if entry['formula_text'] is not None else None
                value=formula if entry['formula_present'] else a.value
                if entry['type']=='inlineStr': value=entry['inline']
                kind='formula' if entry['formula_present'] else _kind(value,a)
                lex=entry['numeric'] if entry['type']=='n' else None
                grid.cells[(row,col)]=RawCell(value,kind,lex,a.number_format,formula,b.value if entry['formula_present'] else None,_kind(b.value,b) if entry['formula_present'] else None)


def read_xlsx(snapshot, tables, budget):
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise IntakeError('missing_dependency','读取XLSX需要openpyxl>=3.1,<4，请在宿主的独立Python环境安装；CSV模式无需此依赖',{'source_id':snapshot.id}) from e
    handles=[]
    try:
        scanned={'rows':0,'cells':0}; grids={}; lexical={}; sheet_errors={}
        with zipfile.ZipFile(io.BytesIO(snapshot.data)) as archive:
            _scan_strings(archive,budget)
            book=ET.fromstring(archive.read('xl/workbook.xml'))
            rels=ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            targets={}
            for rel in rels:
                if rel.get('Type','').endswith('/worksheet'):
                    if rel.get('TargetMode')=='External': raise IntakeError('unsafe_workbook','工作表不能指向外部来源')
                    target=rel.get('Target','')
                    target=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl',target))
                    if target.startswith('../') or target not in archive.namelist(): raise IntakeError('invalid_workbook','工作表资源缺失或路径无效')
                    targets[rel.get('Id')]=target
            sheets={s.get('name'):targets.get(s.get(REL)) for s in book.iter(NS+'sheet')}
            props=book.find(NS+'workbookPr'); epoch='1904' if props is not None and props.get('date1904') in ('1','true') else '1900'
            by_member={}
            for t in tables:
                member=sheets.get(t['sheet'])
                if member: by_member.setdefault(member,[]).append(t)
            # Scan all worksheet content, including sheets outside the selected table ranges.
            members={n for n in archive.namelist() if n.startswith('xl/worksheets/') and n.endswith('.xml')} | set(targets.values())
            for member in sorted(members):
                try:
                    grid,raw=_scan_sheet(archive,member,by_member.get(member,[]),budget,scanned)
                    grid.metadata.update(format='xlsx',date_system=epoch,scanned_rows=scanned['rows'],scanned_cells=scanned['cells'])
                    grids[member]=grid; lexical[member]=raw
                except IntakeError as e:
                    if e.issue.severity=='fatal': raise
                    sheet_errors[member]=e
                except (ET.ParseError,ValueError,TypeError,KeyError) as e:
                    sheet_errors[member]=IntakeError('invalid_workbook','工作表结构或坐标无法可靠读取',{'source_id':snapshot.id})
        budget.check()
        formula_book=load_workbook(io.BytesIO(snapshot.data),read_only=True,data_only=False,keep_links=False)
        handles.append(formula_book)
        cache_book=load_workbook(io.BytesIO(snapshot.data),read_only=True,data_only=True,keep_links=False)
        handles.append(cache_book)
        result={}
        for table in tables:
            member=sheets.get(table['sheet'])
            if not member or table['sheet'] not in formula_book.sheetnames:
                continue  # Coordinator records a table-local missing_sheet issue.
            if member in sheet_errors:
                result[table['sheet']]=sheet_errors[member]; continue
            grid=grids[member]; raw=lexical[member]
            try:
                _read_table_values(formula_book,cache_book,table,grid,raw,budget)
                result[table['sheet']]=grid
            except IntakeError as e:
                if e.issue.severity=='fatal': raise
                sheet_errors[member]=e; result[table['sheet']]=e
            except (ValueError,TypeError,IndexError,KeyError,OverflowError,ET.ParseError) as e:
                error=IntakeError('invalid_workbook','工作表单元格类型或缓存无法可靠读取',{'source_id':snapshot.id,'sheet':table['sheet']})
                sheet_errors[member]=error; result[table['sheet']]=error
        return result
    except IntakeError:
        raise
    except (ET.ParseError,KeyError,ValueError,TypeError,IndexError,OverflowError,OSError,zipfile.BadZipFile) as e:
        raise IntakeError('invalid_workbook','工作簿内容或坐标无法可靠读取',{'source_id':snapshot.id}) from e
    finally:
        for handle in handles: handle.close()
