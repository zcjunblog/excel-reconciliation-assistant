"""合成测试构造；只在临时目录写文件，不改写examples或人工答案。"""
import copy
import json
from pathlib import Path
import sys
import zipfile
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/excel-reconciliation-assistant/scripts'
sys.path.insert(0, str(SCRIPTS))


def sample(name='commerce'):
    return json.loads((ROOT / 'examples' / name / 'rules.json').read_text())


def csv_case(directory, left='id,value\na,1\nb,2\n', right=None, encoding='utf-8'):
    right = left if right is None else right
    (directory / 'left.csv').write_bytes(left.encode(encoding))
    (directory / 'right.csv').write_bytes(right.encode(encoding))
    data = {
        'schema_version': '1.0',
        'sources': [{'id': side, 'path': side+'.csv', 'format': 'csv', 'encoding': encoding} for side in ('left','right')],
        'tables': [{'id': side, 'source_id': side, 'sheet': None, 'header_row': 1, 'data_range': 'A2:B3', 'exclusions': []} for side in ('left','right')],
        'tasks': [{'id': 'check', 'left_table': 'left', 'right_table': 'right', 'keys': ['id'], 'formula_policy': 'pending', 'fields': [
            {'id':'id','left_column':'A','right_column':'A','left_header':'id','right_header':'id','type':'identifier'},
            {'id':'value','left_column':'B','right_column':'B','left_header':'value','right_header':'value','type':'decimal','parse_numeric_text':True}
        ]}]
    }
    return write_rules(directory, data)


def write_rules(directory, data):
    path = directory / 'rules.json'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


def mutate_xlsx(destination, changes, source=None):
    source = source or ROOT / 'examples/commerce/inputs.xlsx'
    with zipfile.ZipFile(source) as z:
        entries = {i.filename: z.read(i.filename) for i in z.infolist()}
    for name, replacement in changes.items():
        if replacement is None:
            entries.pop(name, None)
        elif callable(replacement):
            entries[name] = replacement(entries[name])
        else:
            entries[name] = replacement
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in entries.items():
            z.writestr(name, value)


def workbook_case(directory, changes=None):
    mutate_xlsx(directory / 'inputs.xlsx', changes or {})
    return write_rules(directory, sample())


def authorize(rules):
    return {(rules.path.parent / s['path']).resolve() for s in rules.sources}


def sheet_xml(rows, extra='', dimension='A1:F9'):
    body=[]
    for row_number, cells in rows:
        parts=[]
        for column, value in cells.items():
            ref=f'{column}{row_number}'
            if isinstance(value,str):
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>')
            elif value is not None:
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
        body.append(f'<row r="{row_number}">'+''.join(parts)+'</row>')
    return ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<dimension ref="{dimension}"/><sheetData>'+''.join(body)+'</sheetData>'+extra+'</worksheet>').encode()


def update_sheet(data, *, merge=None, dimension=None, far_row=None):
    ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    root=ET.fromstring(data)
    if merge:
        merges=ET.SubElement(root,ns+'mergeCells',{'count':'1'})
        ET.SubElement(merges,ns+'mergeCell',{'ref':merge})
    if dimension:
        element=root.find(ns+'dimension')
        if element is None: element=ET.SubElement(root,ns+'dimension')
        element.set('ref',dimension)
    if far_row:
        rows=root.find(ns+'sheetData')
        row=ET.SubElement(rows,ns+'row',{'r':str(far_row)})
        cell=ET.SubElement(row,ns+'c',{'r':'A'+str(far_row)})
        ET.SubElement(cell,ns+'v').text='1'
    return ET.tostring(root,encoding='utf-8')


def workbook_epoch(data, epoch):
    ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    root=ET.fromstring(data); element=root.find(ns+'workbookPr')
    if element is None: element=ET.SubElement(root,ns+'workbookPr')
    element.set('date1904',epoch)
    return ET.tostring(root,encoding='utf-8')
