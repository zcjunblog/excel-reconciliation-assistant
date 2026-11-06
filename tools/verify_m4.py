"""M4 reproducible CLI/oracle, receipt and actual 20,001-detail export proof."""
from pathlib import Path
import collections
import hashlib
import io
import json
import platform
import resource
import subprocess
import sys
import time
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from comparison_helpers import table,task
from delivery_helpers import synthetic_rules
from common import Budget
from matching import associate
from compare import compare_task
from export import write_workbook
from openpyxl import load_workbook


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read_json(path): return json.loads(path.read_text(encoding='utf-8'))
def records(path): return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def main():
    out=ROOT/'outputs/m4-verification'/('run-'+uuid.uuid4().hex[:8]); out.mkdir(parents=True)
    log=io.StringIO(); tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
    (out/'unittest.log').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful(): print(log.getvalue()); return 1
    cases=[]
    for name in ('commerce','inventory','training','administration'):
        rule_path=ROOT/'examples'/name/'rules.json'; rules=read_json(rule_path)
        destination=out/(name+'-v001')
        args=[sys.executable,str(ROOT/'skills/excel-reconciliation-assistant/scripts/reconcile_tool.py'),'run','--rules',str(rule_path),'--output',str(destination)]
        for source in rules['sources']: args+=['--authorize',str((rule_path.parent/source['path']).resolve())]
        started=time.perf_counter(); process=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=130)
        summary=json.loads(process.stdout); assert process.returncode==2 and summary['status']=='needs_confirmation',summary
        manifest=read_json(destination/'交付清单.json')
        actual={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}-{'交付清单.json'}
        assert actual=={f['path'] for f in manifest['files']}
        for entry in manifest['files']:
            path=destination/entry['path']; assert sha(path)==entry['sha256'] and path.stat().st_size==entry['bytes']
        all_fields=records(destination/'工作资料/字段结果.jsonl'); all_rows=records(destination/'工作资料/关联结果.jsonl')
        checks=read_json(destination/'工作资料/检查记录.json'); expected=read_json(rule_path.parent/'expected.json')
        wb=load_workbook(destination/'核对结果.xlsx',read_only=True,data_only=False,keep_links=False)
        try:
            assert sum(wb[n].max_row-1 for n in wb.sheetnames if n.startswith('匹配索引'))==sum(len(t['matched_pairs']) for t in expected['tasks'])
            assert sum(wb[n].max_row-1 for n in wb.sheetnames if n.startswith('差异明细'))==sum(len(t['exceptions']) for t in expected['tasks'])
            for ws in wb:
                for row in ws:
                    assert all(c.data_type!='f' for c in row)
        finally: wb.close()
        tasks=[]
        for want in expected['tasks']:
            fields=[f for f in all_fields if f['task_id']==want['id']]
            count={s:sum(f['status']==s for f in fields) for s in ('exact','within_rule','different','not_comparable')}
            assert count==want['field_counts']
            exceptions=[{'left_row':f['left']['ref']['row'],'right_row':f['right']['ref']['row'],'field':f['field_id'],'status':f['status'],'delta':f['delta'],
                         'left_cell':f['left']['ref']['column']+str(f['left']['ref']['row']),'right_cell':f['right']['ref']['column']+str(f['right']['ref']['row']),'reason':f['reason']} for f in fields if f['status']!='exact']
            assert exceptions==want['exceptions']
            check=next(c for c in checks if c['task_id']==want['id']); assert check['coverage_issues']==[]
            for side in ('left','right'):
                rows=[r for r in all_rows if r['task_id']==want['id'] and r['side']==side]
                assert len(rows)==want['selected'][side]
                for state,key in (('excluded','excluded_rows'),(side+'_only','only_rows'),('duplicate_ambiguous','duplicate_rows'),('invalid_key','invalid_rows')):
                    assert [r['row'] for r in rows if r['status']==state]==want[key][side]
                assert [r['row'] for r in rows if r['status']=='unique_matched']==sorted(p[0 if side=='left' else 1] for p in want['matched_pairs'])
            tasks.append({'task_id':want['id'],'manual_oracle_matches':True,'field_counts':count,'source_row_records':sum(want['selected'].values())})
        cases.append({'case':name,'status':summary['status'],'exit_code':process.returncode,'tasks':tasks,'artifact_count':len(manifest['files'])+1,
                      'full_field_records':len(all_fields),'source_row_records':len(all_rows),'manifest_sha256':sha(destination/'交付清单.json'),
                      'workbook_sha256':sha(destination/'核对结果.xlsx'),'seconds':round(time.perf_counter()-started,4),'output':destination.relative_to(ROOT).as_posix()})
    # 6,667 pairs x three differing fields = exactly 20,001 exception records.
    n=6667; rule=task()
    template=rule['fields'][1]
    rule['fields']=[rule['fields'][0]]+[{**template,'id':'v'+str(i),'left_column':chr(65+i),'right_column':chr(65+i),'left_header':'v'+str(i),'right_header':'v'+str(i)} for i in range(1,4)]
    left=table('left',[[f'{i:06d}','a','a','a'] for i in range(n)])
    right=table('right',[[f'{i:06d}','b','b','b'] for i in reversed(range(n))])
    left.header=right.header={'A':'id','B':'v1','C':'v2','D':'v3'}
    b=Budget(); started=time.perf_counter(); result=compare_task(associate(left,right,rule),rule,b)
    assert result.field_counts=={'exact':0,'within_rule':0,'different':20001,'not_comparable':0}
    rules=synthetic_rules(result)
    shard_out=out/'shard-20001'; shard_out.mkdir(); receipt=write_workbook([result],rules,shard_out,b)
    wb=load_workbook(receipt.path,read_only=True,data_only=False)
    try:
        assert wb['差异明细_01'].max_row==20001 and wb['差异明细_02'].max_row==2
        ids=[row[17] for name in ('差异明细_01','差异明细_02') for row in wb[name].iter_rows(min_row=2,values_only=True)]
        assert len(ids)==len(set(ids))==20001
        assert wb['匹配索引'].max_row==6668
    finally: wb.close()
    probe={'exception_records':20001,'shard_rows':[20000,1],'unique_result_ids':20001,'matched_pairs':6667,'no_truncation':True,
           'workbook_bytes':receipt.bytes,'sha256':receipt.sha256,'compare_export_readback_seconds':round(time.perf_counter()-started,4)}
    manifest=read_json(ROOT/'examples/manifest.json'); assert all(sha(ROOT/f['path'])==f['sha256'] for f in manifest['files'])
    code={p.relative_to(ROOT).as_posix():sha(p) for folder in ('skills/excel-reconciliation-assistant/scripts','tests') for p in sorted((ROOT/folder).glob('*.py'))}
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record={'stage':'M4','passed':True,'python':platform.python_version(),'os':platform.system(),'unit_tests':tests.testsRun,'failures':len(tests.failures),'errors':len(tests.errors),
            'cases':cases,'case_tasks':sum(len(c['tasks']) for c in cases),'m1_manifest_unchanged':True,'unchanged_files':len(manifest['files']),'probe':probe,
            'process_peak_rss_mib':round(rss/(1024*1024) if platform.system()=='Darwin' else rss/1024,2),'code_sha256':code,
            'not_verified':['不同设备或操作系统上的办公显示','M5可安装Skill和客户端运行','所有阈值组合的最大容量性能']}
    evidence=ROOT/'evidence/m4'; evidence.mkdir(exist_ok=True,parents=True)
    (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k in ('stage','passed','unit_tests','case_tasks','m1_manifest_unchanged','probe','process_peak_rss_mib')},ensure_ascii=False))
    return 0


if __name__=='__main__': raise SystemExit(main())
