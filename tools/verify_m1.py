"""M1规格材料检查；核对明确指定的坐标/分区，不推导关联、不运行业务比较。"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries, coordinate_from_string, column_index_from_string
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify():
    schema = read_json(ROOT / 'schemas/reconciliation-rules.schema.json')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    checks = 0
    manifest = read_json(ROOT / 'examples/manifest.json')
    for entry in manifest['files']:
        p = ROOT / entry['path']
        assert p.stat().st_size == entry['bytes'], entry['path']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry['sha256'], entry['path']
        checks += 1
    cases = []
    for name in ('commerce', 'inventory', 'training', 'administration'):
        directory = ROOT / 'examples' / name
        rule = read_json(directory / 'rules.json')
        expected = read_json(directory / 'expected.json')
        validator.validate(rule)
        sources = {s['id']: s for s in rule['sources']}
        tables = {t['id']: t for t in rule['tables']}
        handles = {}
        for sid, src in sources.items():
            assert not Path(src['path']).is_absolute()
            p = directory / src['path']
            if src['format'] == 'xlsx':
                handles[sid] = (load_workbook(p, data_only=False), load_workbook(p, data_only=True))
            else:
                with p.open(encoding=src.get('encoding', 'utf-8-sig'), newline='') as f:
                    handles[sid] = list(csv.reader(f))

        def cell(table_id, address, cached=False):
            t = tables[table_id]
            h = handles[t['source_id']]
            if sources[t['source_id']]['format'] == 'xlsx':
                return h[int(cached)][t['sheet']][address].value
            col, row = coordinate_from_string(address)
            return h[row-1][column_index_from_string(col)-1]

        for check in expected['cell_checks']:
            assert cell(check['table'], check['cell']) == check['value'], (name, check)
            checks += 1
        for check in expected['formula_checks']:
            assert cell(check['table'], check['cell']) == check['formula'], (name, check)
            assert cell(check['table'], check['cell'], cached=True) == check['cached'], (name, check)
            checks += 2
        assert {t['id'] for t in rule['tasks']} == {t['id'] for t in expected['tasks']}
        for oracle in expected['tasks']:
            task = next(t for t in rule['tasks'] if t['id'] == oracle['id'])
            fields = {f['id']: f for f in task['fields']}
            assert set(task['keys']) < set(fields)
            assert len(fields) == len(task['fields'])
            for side, index in (('left', 0), ('right', 1)):
                table_id = task[side+'_table']
                table = tables[table_id]
                c1, r1, c2, r2 = range_boundaries(table['data_range'])
                assert table['header_row'] < r1
                assert oracle['selected'][side] == r2-r1+1
                excluded = {r for e in table['exclusions'] for r in e['rows']}
                assert excluded == set(oracle['excluded_rows'][side])
                classified = [p[index] for p in oracle['matched_pairs']]
                for category in ('only_rows', 'duplicate_rows', 'invalid_rows'):
                    classified += oracle[category][side]
                assert len(classified) == len(set(classified)), (name, oracle['id'], 'overlap')
                assert set(classified).isdisjoint(excluded)
                assert set(classified) | excluded == set(range(r1, r2+1)), (name, 'uncovered row')
                for field in fields.values():
                    assert c1 <= column_index_from_string(field[side+'_column']) <= c2
                    assert cell(table_id, field[side+'_column']+str(table['header_row'])) == field[side+'_header']
                checks += 5
            counts = oracle['field_counts']
            assert sum(counts.values()) == len(oracle['matched_pairs'])*(len(fields)-len(task['keys']))
            ex = oracle['exceptions']
            unique = {(e['left_row'], e['right_row'], e['field']) for e in ex}
            assert len(unique) == len(ex)
            totals = Counter(e['status'] for e in ex)
            for status in ('within_rule', 'different', 'not_comparable'):
                assert totals[status] == counts[status]
            for status in ('different', 'not_comparable'):
                assert len({(e['left_row'],e['right_row']) for e in ex if e['status']==status}) == oracle[status+'_pairs']
            for e in ex:
                assert [e['left_row'],e['right_row']] in oracle['matched_pairs']
                f = fields[e['field']]
                assert e['field'] not in task['keys']
                for side in ('left','right'):
                    assert e[side+'_cell'] == f[side+'_column']+str(e[side+'_row'])
                if e['status']=='not_comparable':
                    assert e['delta'] is None
            checks += 8+len(ex)
        if name=='commerce':
            wb = handles['book'][0]
            assert wb['订单'].row_dimensions[4].hidden
            assert wb['订单'].auto_filter.ref == 'A1:F8'
            checks += 2
        for sid, h in handles.items():
            if sources[sid]['format']=='xlsx':
                for wb in h:
                    wb.close()
        cases.append({'case':name,'tasks':len(rule['tasks']),'source_files':len(sources),'oracle':'explicit_coordinates_and_counts'})
    # 结构协议的负例；这些不替代M2的路径/业务键/范围语义测试。
    import copy
    sample = read_json(ROOT / 'examples/commerce/rules.json')
    bad_examples=[]
    bad=copy.deepcopy(sample); bad['unknown_option']=True; bad_examples.append(bad)
    bad=copy.deepcopy(sample); bad['tasks'][0]['fields'][-1]['tolerance']='-0.01'; bad_examples.append(bad)
    bad=copy.deepcopy(sample); bad['tasks'][0]['formula_policy']='recalculate'; bad_examples.append(bad)
    bad=copy.deepcopy(sample); bad['tasks'][0]['fields'][0]['tolerance']='1'; bad_examples.append(bad)
    for bad in bad_examples:
        try:
            validator.validate(bad)
        except ValidationError:
            checks += 1
        else:
            raise AssertionError('Invalid schema example accepted')
    return {'stage':'M1','passed':True,'checks':checks,'cases':cases,'schema_negative_cases':len(bad_examples),
            'scope':'材料结构、原坐标事实、人工答案分区及守恒；未执行生产关联、比较、导出或客户端测试'}


if __name__ == '__main__':
    result = verify()
    dest = ROOT / 'evidence/m1/verification.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
