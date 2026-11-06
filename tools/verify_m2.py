"""Run M2 proof, inspect synthetic sources, record hashes; never rebuild the oracle."""
from pathlib import Path
import hashlib
import io
import json
import platform
import resource
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/excel-reconciliation-assistant/scripts'))
from common import Budget
from rules import load_rules
from intake import inspect_sources,read_tables


def inspect_case(path):
    rules=load_rules(path)
    # Explicit authorization of known, synthetic development fixtures only.
    authorized={(path.parent/s['path']).resolve() for s in rules.sources}
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in authorized}
    budget=Budget(); intake=inspect_sources(rules,authorized,budget); tables=read_tables(intake,rules,budget)
    assert intake.status=='ready',[(i.code,i.source_ref) for i in intake.issues]
    assert set(tables)=={t['id'] for t in rules.tables}
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in authorized)
    return {'status':intake.status,'source_hashes_unchanged':True,'tables':{tid:{'selected':len(t.selected_rows),'included':len(t.rows),'excluded':len(t.excluded_rows),'date_system':t.metadata.get('date_system')} for tid,t in tables.items()}}


def main():
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    log=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    out=ROOT/'outputs/m2-verification'; out.mkdir(parents=True,exist_ok=True)
    (out/'unittest.log').write_text(log.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():
        print(log.getvalue()); return 1
    checks={name:inspect_case(ROOT/'examples'/name/'rules.json') for name in ('commerce','inventory','training','administration')}
    manifest=json.loads((ROOT/'examples/manifest.json').read_text())
    assert all(hashlib.sha256((ROOT/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in manifest['files'])
    # Narrow tables at the default row boundary; not a wide-table/full-pipeline certification.
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp).resolve()
        text='id,value\n'+''.join(f'S{i:06d},{i%1000}\n' for i in range(50000))
        for side in ('left','right'): (directory/(side+'.csv')).write_bytes(text.encode('utf-8'))
        payload=json.loads((ROOT/'examples/inventory/rules.json').read_text())
        payload['sources']=[{'id':s,'path':s+'.csv','format':'csv'} for s in ('left','right')]
        payload['tables']=[{'id':s,'source_id':s,'sheet':None,'header_row':1,'data_range':'A2:B50001','exclusions':[]} for s in ('left','right')]
        payload['tasks']=[{'id':'probe','left_table':'left','right_table':'right','keys':['id'],'formula_policy':'pending','fields':[
            {'id':'id','left_column':'A','right_column':'A','left_header':'id','right_header':'id','type':'identifier'},
            {'id':'value','left_column':'B','right_column':'B','left_header':'value','right_header':'value','type':'decimal','parse_numeric_text':True}]}]
        p=directory/'rules.json'; p.write_text(json.dumps(payload),encoding='utf-8')
        started=time.perf_counter(); probe=inspect_case(p)
        probe['read_seconds']=round(time.perf_counter()-started,4)
        probe['scope']='两份50,000行x2列CSV的生产读取器；未执行关联/比较/导出'
    import openpyxl
    code={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for d in ('skills/excel-reconciliation-assistant/scripts','tests') for p in sorted((ROOT/d).glob('*.py'))}
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record={'stage':'M2','passed':True,'python':platform.python_version(),'openpyxl':openpyxl.__version__,'os':platform.system(),
            'unit_tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'cases':checks,
            'm1_manifest_unchanged':True,'reader_probe':probe,'elapsed_seconds':round(time.perf_counter()-start,4),
            'process_peak_rss_mib':round(rss/(1024*1024) if platform.system()=='Darwin' else rss/1024,2),
            'code_sha256':code,'not_verified':['M3关联与比较','M4结果导出与办公软件UI','最大宽表和全链路容量','Agent客户端调用与分发']}
    dest=ROOT/'evidence/m2'; dest.mkdir(parents=True,exist_ok=True)
    (dest/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'stage':'M2','passed':True,'unit_tests':result.testsRun,'reader_probe':probe,'peak_rss_mib':record['process_peak_rss_mib']},ensure_ascii=False))
    return 0


if __name__=='__main__': raise SystemExit(main())
