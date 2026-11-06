"""M3 proof against independent oracles plus a bounded 200k-field synthetic probe."""
from pathlib import Path
import copy
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
from common import Budget, BudgetExceeded
from rules import load_rules
from intake import inspect_sources, read_tables, verify_sources_unchanged
from matching import associate
from compare import compare_task
from checks import verify_coverage


def inputs(path):
    rules=load_rules(path); budget=Budget()
    # Known synthetic fixtures only; production authorization must come from the host/user.
    authorized={(path.parent/s['path']).resolve() for s in rules.sources}
    intake=inspect_sources(rules,authorized,budget); tables=read_tables(intake,rules,budget)
    assert intake.status=='ready',[(i.code,i.source_ref) for i in intake.issues]
    return rules,budget,intake,tables


def exceptions(result):
    return [{'left_row':f.left.ref.row,'right_row':f.right.ref.row,'field':f.field_id,'status':f.status,'delta':f.delta,
             'left_cell':f.left.ref.column+str(f.left.ref.row),'right_cell':f.right.ref.column+str(f.right.ref.row),'reason':f.reason}
            for f in result.field_results if f.status!='exact']


def main():
    log=io.StringIO(); suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    tests=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    out=ROOT/'outputs/m3-verification'; out.mkdir(parents=True,exist_ok=True)
    (out/'unittest.log').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful(): print(log.getvalue()); return 1
    cases=[]
    for name in ('commerce','inventory','training','administration'):
        path=ROOT/'examples'/name/'rules.json'; rules,budget,intake,tables=inputs(path)
        expected=json.loads((path.parent/'expected.json').read_text(encoding='utf-8'))
        for task,want in zip(rules.tasks,expected['tasks']):
            association=associate(tables[task['left_table']],tables[task['right_table']],task)
            result=compare_task(association,task,budget)
            assert not verify_coverage(result)
            assert result.field_counts==want['field_counts']
            assert exceptions(result)==want['exceptions']
            assert [[p.left.row,p.right.row] for p in association.unique_pairs]==want['matched_pairs']
            assert result.row_counts['different_pairs']==want['different_pairs']
            assert result.row_counts['not_comparable_pairs']==want['not_comparable_pairs']
            cases.append({'case':name,'task_id':task['id'],'status':result.status,'manual_oracle_matches':True,'row_counts':result.row_counts,'field_counts':result.field_counts,
                          'exceptions':exceptions(result),'warnings':sorted({w for f in result.field_results for w in f.warnings}),'totals':result.totals})
        assert verify_sources_unchanged(intake,rules,budget)
    manifest=json.loads((ROOT/'examples/manifest.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in manifest['files'])
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp).resolve(); n=50000
        def rows(reverse=False):
            yield 'id,v1,v2,v3,v4\n'
            for i in reversed(range(n)) if reverse else range(n):
                last='4.01' if reverse and i==n-1 else '4'
                yield f'{i:06d},1,2,3,{last}\n'
        for side,reverse in (('left',False),('right',True)):
            (directory/(side+'.csv')).write_bytes(''.join(rows(reverse)).encode('utf-8'))
        fields=[{'id':'id','left_column':'A','right_column':'A','left_header':'id','right_header':'id','type':'identifier'}]
        for i in range(1,5):
            fields.append({'id':f'v{i}','left_column':chr(65+i),'right_column':chr(65+i),'left_header':f'v{i}','right_header':f'v{i}','type':'decimal','parse_numeric_text':True})
        payload={'schema_version':'1.0','sources':[{'id':s,'path':s+'.csv','format':'csv'} for s in ('left','right')],
                 'tables':[{'id':s,'source_id':s,'sheet':None,'header_row':1,'data_range':'A2:E50001','exclusions':[]} for s in ('left','right')],
                 'tasks':[{'id':'probe','left_table':'left','right_table':'right','keys':['id'],'fields':fields,'formula_policy':'pending'}]}
        p=directory/'rules.json'; p.write_text(json.dumps(payload),encoding='utf-8')
        start=time.perf_counter(); rules,budget,intake,tables=inputs(p); read_seconds=time.perf_counter()-start
        start=time.perf_counter(); association=associate(tables['left'],tables['right'],rules.tasks[0]); associate_seconds=time.perf_counter()-start
        start=time.perf_counter(); result=compare_task(association,rules.tasks[0],budget); compare_seconds=time.perf_counter()-start
        assert result.field_counts=={'exact':199999,'within_rule':0,'different':1,'not_comparable':0}
        difference=next(f for f in result.field_results if f.status=='different')
        assert (difference.left.ref.row,difference.right.ref.row,difference.field_id,difference.delta)==(50001,2,'v4','0.01')
        second=copy.deepcopy(rules.tasks[0]); second['id']='probe_second'
        try: compare_task(associate(tables['left'],tables['right'],second),second,budget)
        except BudgetExceeded: pass
        else: raise AssertionError('Repeated tasks bypassed the cumulative comparison budget')
        assert verify_sources_unchanged(intake,rules,budget)
        probe={'rows_per_side':n,'fields_per_pair':4,'field_comparisons':200000,'field_counts':result.field_counts,'row_order':'right_reversed',
               'read_seconds':round(read_seconds,4),'associate_seconds':round(associate_seconds,4),'compare_and_coverage_seconds':round(compare_seconds,4),
               'cumulative_budget_rejected_second_task':True,'sources_unchanged':True,'scope':'CSV输入→关联→比较→覆盖检查；不含结果文件导出或客户端'}
    code={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('skills/excel-reconciliation-assistant/scripts','tests') for p in sorted((ROOT/folder).glob('*.py'))}
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record={'stage':'M3','passed':True,'python':platform.python_version(),'os':platform.system(),'unit_tests':tests.testsRun,'failures':len(tests.failures),'errors':len(tests.errors),
            'case_tasks':len(cases),'m1_manifest_unchanged':True,'cases':cases,'probe':probe,'process_peak_rss_mib':round(rss/(1024*1024) if platform.system()=='Darwin' else rss/1024,2),
            'code_sha256':code,'not_verified':['M4导出及Excel/WPS视觉','M5包与客户端','最大宽表/不同系统/复杂样式完整性能']}
    destination=ROOT/'evidence/m3'; destination.mkdir(parents=True,exist_ok=True)
    (destination/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'stage':'M3','passed':True,'unit_tests':tests.testsRun,'oracle_tasks':len(cases),'probe':probe,'peak_rss_mib':record['process_peak_rss_mib']},ensure_ascii=False))
    return 0


if __name__=='__main__': raise SystemExit(main())
