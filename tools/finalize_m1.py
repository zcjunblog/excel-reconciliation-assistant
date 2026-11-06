"""定向制作公式缓存、隐藏/筛选输入，冻结合成案例摘要。不会读取预期答案决定输入。"""
from pathlib import Path
import hashlib
import json
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def patch_book(filename, administration=False):
    with zipfile.ZipFile(filename) as src:
        entries = [(item, src.read(item.filename)) for item in src.infolist()]
    revised = []
    for info, data in entries:
        if administration and info.filename in ('xl/worksheets/sheet2.xml', 'xl/worksheets/sheet3.xml'):
            tree = ET.fromstring(data)
            for cell in tree.iter(NS + 'c'):
                ref = cell.attrib['r']
                if ref not in ('C2', 'C3', 'C4'):
                    continue
                for child in list(cell):
                    if child.tag in (NS + 'f', NS + 'v'):
                        cell.remove(child)
                cell.attrib.pop('t', None)
                ET.SubElement(cell, NS + 'f').text = {'C2': '100+100', 'C3': '50+50', 'C4': '1/0'}[ref]
                if ref != 'C3':
                    ET.SubElement(cell, NS + 'v').text = '200' if ref == 'C2' else '#DIV/0!'
                if ref == 'C4':
                    cell.set('t', 'e')
            data = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        if not administration and info.filename == 'xl/worksheets/sheet1.xml':
            tree = ET.fromstring(data)
            for row in tree.iter(NS + 'row'):
                if row.attrib['r'] == '4':
                    row.set('hidden', '1')
            # 隐藏行和筛选都不意味着排除，只有规则中的第9行被排除。
            old = tree.find(NS + 'autoFilter')
            if old is not None:
                tree.remove(old)
            auto = ET.Element(NS + 'autoFilter', {'ref': 'A1:F8'})
            children = list(tree)
            idx = next(i for i, child in enumerate(children) if child.tag == NS + 'sheetData')
            tree.insert(idx + 1, auto)
            data = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        revised.append((info, data))
    staging = filename.with_suffix('.staging')
    with zipfile.ZipFile(staging, 'w') as dest:
        for info, data in revised:
            dest.writestr(info, data)
    staging.replace(filename)


if __name__ == '__main__':
    patch_book(ROOT / 'examples/commerce/inputs.xlsx')
    patch_book(ROOT / 'examples/administration/inputs.xlsx', administration=True)
    files = []
    for case in ('commerce', 'inventory', 'training', 'administration'):
        for p in sorted((ROOT / 'examples' / case).iterdir()):
            if p.suffix in ('.xlsx', '.csv', '.json'):
                files.append({'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    (ROOT / 'examples/manifest.json').write_text(json.dumps({'synthetic': True, 'files': files}, ensure_ascii=False, indent=2) + '\n')
    print(f'Frozen {len(files)} synthetic input/rule/oracle hashes; deliberately missing/error caches retained.')
