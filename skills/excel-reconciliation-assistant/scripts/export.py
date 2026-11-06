"""Atomic blue/white XLSX export with literal source text and bounded, verified views."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import unicodedata
from common import ExportRecord, IntakeError
from export_rows import SheetData, build_views, overview_rows
from presentation import ExactNumber

ILLEGAL_XML=re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _limit(budget,name,value):
    budget.check()
    if value>getattr(budget,name):
        raise IntakeError('export_limit','结果工作簿超过导出预算，未生成截断文件',{'limit':name,'actual':value})


def _prepared(value,budget):
    fmt=None
    if isinstance(value,ExactNumber): value,fmt=value.excel()
    if isinstance(value,str):
        if len(value)>min(budget.max_text_chars,32767):
            raise IntakeError('export_text_limit','工作簿单元格文本超限；完整原值保留在工作资料')
        if ILLEGAL_XML.search(value): raise IntakeError('export_text_invalid','来源包含Excel无法无损保存的控制字符，未生成工作簿')
    if isinstance(value,float) and not math.isfinite(value): raise IntakeError('export_number_invalid','不能把非有限值写为Excel数值')
    return value,fmt


def _shards(views,budget):
    if not 1<=budget.max_sheet_rows<=1048575:
        raise IntakeError('invalid_output_budget','单片行数预算无效')
    result=[]
    for view in views:
        count=math.ceil(len(view.rows)/budget.max_sheet_rows)
        for i in range(count):
            name=view.name if count==1 else f'{view.name}_{i+1:02d}'
            result.append(SheetData(name,view.headers,view.rows[i*budget.max_sheet_rows:(i+1)*budget.max_sheet_rows],view.freeze,view.state_column))
    _limit(budget,'max_output_sheets',len(result))
    _limit(budget,'max_output_rows',sum(len(s.rows) for s in result))
    return result


def _write_cell(ws,row,column,value,budget):
    prepared,fmt=_prepared(value,budget); c=ws.cell(row,column,prepared)
    if isinstance(prepared,str): c.data_type='s'; c.number_format=fmt or '@'
    elif fmt: c.number_format=fmt
    return c


def _style_detail(ws,view,style,budget):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    width=len(view.headers)
    ws.sheet_view.showGridLines=False; ws.sheet_view.zoomScale=85
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0
    ws.print_title_rows='1:1'
    ws.freeze_panes=view.freeze; ws.auto_filter.ref=f'A1:{get_column_letter(width)}{len(view.rows)+1}'
    ws.sheet_properties.tabColor=style['accent']
    for col,label in enumerate(view.headers,1):
        c=_write_cell(ws,1,col,label,budget)
        c.font=Font(name=style['font'],size=11,bold=True,color='FFFFFF')
        c.fill=PatternFill('solid',fgColor=style['blue']); c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
        c.border=Border(right=Side(style='thin',color='FFFFFF'))
        if label in ('基准原值','比较原值','基准核对值','比较核对值'): size=27
        elif '摘要' in label or label in ('具体原因','来源字段','单位/币种依据','上下文','原因/规则'): size=36
        elif 'SHA' in label: size=36
        elif label=='任务': size=24
        elif label=='业务键': size=29
        elif '原行' in label or '原列' in label or label.endswith('字段') and label!='字段': size=16
        elif '结果编号' in label: size=38
        else: size=20
        ws.column_dimensions[get_column_letter(col)].width=size
    ws.row_dimensions[1].height=34
    state_fills={'有差异':style['different'],'不可比较':style['not_comparable'],'规则内一致':style['within_rule']}
    for row,values in enumerate(view.rows,2):
        budget.check(); line_count=1
        state=values[view.state_column-1] if view.state_column else None
        fill=state_fills.get(state,style['stripe'] if row%2==0 else 'FFFFFF')
        for col,value in enumerate(values,1):
            c=_write_cell(ws,row,col,value,budget)
            c.font=Font(name=style['font'],size=style['body_size'],color=style['ink'])
            c.fill=PatternFill('solid',fgColor=fill)
            numeric=isinstance(c.value,(int,float)) and type(c.value) is not bool
            c.alignment=Alignment(horizontal='right' if numeric else 'left',indent=1 if numeric else 0,vertical='top',wrap_text=True)
            available=max(8,ws.column_dimensions[get_column_letter(col)].width-6)
            lengths=[sum(2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in text) for text in str(c.value or '').splitlines()]
            lines=sum(max(1,math.ceil(length/available)) for length in lengths)
            # Office wraps at punctuation as well as width; allow an extra line after a wrap.
            if any(length>available for length in lengths): lines+=1
            line_count=max(line_count,lines)
        ws.row_dimensions[row].height=min(120,max(28,20*line_count))
    ws.print_options.horizontalCentered=True


def _style_overview(ws,rows,navigation,style,budget):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.hyperlink import Hyperlink
    from openpyxl.utils import get_column_letter
    ws.sheet_view.showGridLines=False; ws.sheet_view.zoomScale=85
    ws.sheet_properties.tabColor=style['blue']; ws.print_area=f'A1:K{len(rows)}'
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A3; ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=1
    widths=[26,12,20,13,13,13,13,13,13,15,20]
    for col,width in enumerate(widths,1): ws.column_dimensions[get_column_letter(col)].width=width
    for row,values in enumerate(rows,1):
        ws.row_dimensions[row].height=27
        for col,value in enumerate(values,1):
            c=_write_cell(ws,row,col,value,budget)
            c.font=Font(name=style['font'],size=11,color=style['ink'])
            c.fill=PatternFill('solid',fgColor='FFFFFF'); c.alignment=Alignment(vertical='center',wrap_text=False)
        if values[0]=='任务' or values[0]=='表格':
            for c in ws[row]:
                c.fill=PatternFill('solid',fgColor=style['blue']); c.font=Font(name=style['font'],size=10,bold=True,color='FFFFFF')
                c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
            ws.row_dimensions[row].height=34
        elif values[0] in ('字段核对汇总','阅读与复核','说明'):
            ws.cell(row,1).font=Font(name=style['font'],size=12,bold=True,color=style['blue'])
            for c in ws[row]: c.border=Border(bottom=Side(style='thin',color=style['line']))
        elif row>=13 and values[0] and values[1] in ('基准','比较'):
            for c in ws[row]:
                c.fill=PatternFill('solid',fgColor=style['stripe']); c.alignment=Alignment(horizontal='center' if c.column>=4 else 'left',vertical='center',wrap_text=True)
            ws.row_dimensions[row].height=34
        elif row in navigation:
            c=ws.cell(row,1); name=navigation[row]
            c.hyperlink=Hyperlink(ref=c.coordinate,location="'"+name.replace("'","''")+"'!A1",display=name)
            c.font=Font(name=style['font'],size=11,color=style['accent'],underline='single')
    ws['A2'].font=Font(name=style['font'],size=style['title_size'],bold=True,color=style['blue']); ws.row_dimensions[2].height=35
    ws['A3'].font=Font(name=style['font'],size=10,color=style['muted'])
    ws['B5'].font=Font(name=style['font'],size=11,bold=True,color=style['accent'])
    for lo,hi in ((1,3),(4,6),(7,9),(10,11)):
        for row in (7,8):
            for col in range(lo,hi+1): ws.cell(row,col).fill=PatternFill('solid',fgColor=style['pale_blue'])
        ws.cell(7,lo).font=Font(name=style['font'],size=10,color=style['muted'])
        ws.cell(7,lo).alignment=Alignment(vertical='center',wrap_text=True)
        ws.cell(8,lo).font=Font(name=style['font'],size=20,bold=True,color=style['blue'])
        ws.cell(8,lo).alignment=Alignment(horizontal='left',vertical='center')
    ws.row_dimensions[7].height=32; ws.row_dimensions[8].height=36


def _verify_saved(path,overview,specs,budget):
    from openpyxl import load_workbook
    wb=load_workbook(path,read_only=True,data_only=False,keep_links=False)
    try:
        expected={'核对概览':overview,**{s.name:[s.headers]+s.rows for s in specs}}
        if wb.sheetnames!=list(expected): raise IntakeError('export_readback','导出工作表清单不一致')
        for name,rows in expected.items():
            ws=wb[name]
            if ws.max_row!=len(rows): raise IntakeError('export_readback','导出行数不一致',{'sheet':name})
            for index,(actual,source) in enumerate(zip(ws.iter_rows(),rows),1):
                budget.check()
                for c,value in zip(actual,source):
                    want,_=_prepared(value,budget)
                    if want=='': want=None
                    if c.value!=want or c.data_type=='f': raise IntakeError('export_readback','导出值、原文本或类型回读不一致',{'sheet':name,'row':index,'column':c.column})
    finally: wb.close()


def write_workbook(results,rules,staging_dir,budget,task_statuses=None,issues=(),run_status=None):
    try:
        from openpyxl import Workbook
    except ImportError as e: raise IntakeError('missing_dependency','Excel输出需要openpyxl>=3.1,<4；未生成工作簿') from e
    directory=Path(staging_dir); final=directory/'核对结果.xlsx'
    if final.exists() or final.is_symlink(): raise IntakeError('output_exists','工作簿已存在，拒绝覆盖')
    views,found=build_views(results,rules,issues); shards=_shards(views,budget)
    partial=len(found)!=len(rules.tasks) or any(s.get('status')=='blocked' for s in (task_statuses or []))
    status='partial' if partial else 'needs_confirmation' if any(r.status=='needs_confirmation' for r in results) else 'complete'
    if run_status in ('partial','blocked'): status=run_status
    overview,navigation=overview_rows(results,rules,found,[(s.name,len(s.rows)) for s in shards],status)
    _limit(budget,'max_output_cells',len(overview)*11+sum((len(s.rows)+1)*len(s.headers) for s in shards))
    # Validate every text before materializing an Office workbook; no silent truncation.
    for s in shards:
        for row in [s.headers]+s.rows:
            for value in row: _prepared(value,budget)
    style=json.loads((Path(__file__).resolve().parents[1]/'templates/workbook-style.json').read_text(encoding='utf-8'))
    wb=Workbook(); ws=wb.active; ws.title='核对概览'; _style_overview(ws,overview,navigation,style,budget)
    for s in shards: _style_detail(wb.create_sheet(s.name),s,style,budget)
    temp=None; created=False; published=False
    try:
        with tempfile.NamedTemporaryFile(prefix='.xlsx-',suffix='.xlsx',dir=directory,delete=False) as handle: temp=Path(handle.name)
        wb.save(temp); _limit(budget,'max_output_bytes',temp.stat().st_size)
        _verify_saved(temp,overview,shards,budget); budget.check()
        if final.exists(): raise IntakeError('output_exists','保存期间目标文件已出现，拒绝覆盖')
        # Exclusive destination creation also prevents replacing an unexpected concurrent file.
        with final.open('xb') as target, temp.open('rb') as source:
            created=True
            import shutil
            shutil.copyfileobj(source,target)
        raw=final.read_bytes(); published=True
        return ExportRecord(final,'xlsx','generated',hashlib.sha256(raw).hexdigest(),len(raw))
    except IntakeError:
        if created: final.unlink(missing_ok=True)
        raise
    except (OSError,ValueError,TypeError) as e:
        if created: final.unlink(missing_ok=True)
        raise IntakeError('export_failed','工作簿未成功保存，未登记为已生成') from e
    finally:
        wb.close()
        if created and not published: final.unlink(missing_ok=True)
        if temp is not None: temp.unlink(missing_ok=True)
