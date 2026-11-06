"""合成测试构造；只在临时目录写文件，不改写examples或人工答案。"""
import copy
import json
from pathlib import Path
import sys
import zipfile

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
