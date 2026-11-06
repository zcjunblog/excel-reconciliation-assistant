"""One bounded synthetic end-to-end sample; no maximum-capacity certification."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from smoke_archive import _delivery,_workbook_counts
from prepare_showcase import _frozen


def main():
    if not __debug__:
        print(json.dumps({'status':'blocked','error':'Benchmark validation requires assertions; run without -O or PYTHONOPTIMIZE'}));return 1
    _frozen();out=ROOT/'outputs/m6-performance'/uuid.uuid4().hex[:10];out.mkdir(parents=True)
    for side in ('left','right'):
        with (out/(side+'.csv')).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['资产编号','领用人','数量','单位','金额','币种'])
            indices=range(5000) if side=='left' else reversed(range(5000))
            for i in indices:
                owner='模拟成员'+str(i%20)
                if side=='right' and i%100==0:owner='已调整'+str(i%20)
                amount='99.99' if side=='right' and i%250==0 else '100.00'
                writer.writerow([f'{i:08d}',owner,'10','台',amount,'CNY'])
    rules=json.loads((ROOT/'examples/release-cases/negative-delta/rules.json').read_text(encoding='utf-8'))
    for source in rules['sources']:source['path']=source['id']+'.csv'
    for table in rules['tables']:table['data_range']='A2:F5001'
    rule=out/'rules.json';rule.write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('left.csv','right.csv','rules.json')}
    args=[sys.executable,str(ROOT/'skills/excel-reconciliation-assistant/scripts/reconcile_tool.py'),'run','--rules',str(rule),'--output',str(out/'result-v001'),'--authorize',str(out/'left.csv'),'--authorize',str(out/'right.csv')]
    start=time.perf_counter();process=subprocess.run(args,capture_output=True,timeout=140);elapsed=time.perf_counter()-start
    summary=json.loads(process.stdout);assert process.returncode==0 and summary['status']=='complete',summary
    receipt=_delivery(out/'result-v001');field_path=out/'result-v001/工作资料/字段结果.jsonl';counts=collections.Counter();pairs=set();count=0
    for line in field_path.read_text(encoding='utf-8').splitlines():
        f=json.loads(line);counts[f['status']]+=1;count+=1
        i=int(f['key'][0]);assert f['key']==[f'{i:08d}']
        assert (f['left']['ref']['row'],f['right']['ref']['row'])==(i+2,5001-i)
        pairs.add(tuple(f['key']))
        expected='different' if (f['field_id']=='owner' and i%100==0) or (f['field_id']=='amount' and i%250==0) else 'exact'
        assert f['status']==expected
        if f['field_id']=='amount' and i%250==0:assert f['delta']=='-0.01'
    assert count==15000 and len(pairs)==5000 and counts=={'exact':14930,'different':70},counts
    sheets=_workbook_counts(out/'result-v001/核对结果.xlsx');assert sheets['匹配索引']==5000 and sheets['差异明细']==70
    assert all(hashlib.sha256((out/name).read_bytes()).hexdigest()==value for name,value in hashes.items());_frozen()
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss;rss=rss/(1024*1024) if platform.system()=='Darwin' else rss/1024
    result={'stage':'M6','passed':True,'scope':'One synthetic full CLI sample on current machine; no largest-capacity, concurrency, cross-OS or arbitrary-customer-data claim','python':platform.python_version(),'os':platform.system(),'architecture':platform.machine(),'input_rows_per_side':5000,'input_columns':6,'matched_pairs':5000,'field_comparisons':15000,'field_counts':{'exact':14930,'different':70,'within_rule':0,'not_comparable':0},'native_cli_status':summary['status'],'cli_exit_code':process.returncode,'full_cli_seconds':round(elapsed,4),'child_max_rss_mib':round(rss,2),'memory_scope':'OS child-process maximum RSS; not total simultaneous process-tree memory','verified_delivery_files':len(receipt['files']),'source_sha256':hashes,'receipt_sha256':hashlib.sha256((out/'result-v001/交付清单.json').read_bytes()).hexdigest(),'output':out.relative_to(ROOT).as_posix(),'m1_and_m5_unchanged':True}
    record=out/'performance.json';result['output_record']=record.relative_to(ROOT).as_posix()
    with record.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
