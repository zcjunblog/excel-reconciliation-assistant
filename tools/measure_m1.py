"""仅探测读取与物化资源，不执行生产核对或导出。"""
from pathlib import Path
import csv
import json
import platform
import resource
import time
import zipfile
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    temp = ROOT / 'tmp/m1-probe'
    temp.mkdir(parents=True, exist_ok=True)
    csv_path = temp / 'probe.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ID'] + ['V'+str(i) for i in range(1,20)])
        for i in range(50000):
            w.writerow([f'S{i:06d}'] + [str((i+j)%1000) for j in range(19)])
    start = time.perf_counter()
    data = []
    for _ in range(2):
        with csv_path.open(encoding='utf-8', newline='') as f:
            reader=csv.reader(f); next(reader)
            data.append(list(reader))
    csv_seconds = time.perf_counter()-start
    assert len(data[0])==len(data[1])==50000
    assert sum(len(r) for table in data for r in table)==2000000
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    csv_peak_mib=rss/(1024*1024) if platform.system()=='Darwin' else rss/1024
    del data
    xlsx_path = temp / 'probe.xlsx'
    start = time.perf_counter()
    views=[]
    for cached in (False, True):
        wb=load_workbook(xlsx_path,read_only=True,data_only=cached,keep_links=False)
        sheet=wb['Probe']; sheet.reset_dimensions()
        count=0
        for row in sheet.iter_rows():
            count += sum(c.value is not None for c in row)
        assert count==100010
        views.append(count); wb.close()
    xlsx_seconds=time.perf_counter()-start
    with zipfile.ZipFile(xlsx_path) as z:
        expanded=sum(i.file_size for i in z.infolist())
    result={
        'stage':'M1','date':'2026-11-06','environment':{'os':platform.system(),'machine':platform.machine(),'python':platform.python_version()},
        'csv':{'physical_files':1,'logical_reads':2,'data_rows_per_read':50000,'columns':20,'aggregate_materialized_cells':2000000,'file_bytes':csv_path.stat().st_size,'read_and_materialize_seconds':round(csv_seconds,4),'process_peak_rss_mib':round(csv_peak_mib,2)},
        'xlsx':{'data_rows':10000,'columns':10,'data_cells':100000,'views':views,'file_bytes':xlsx_path.stat().st_size,'expanded_bytes':expanded,'dual_stream_read_seconds':round(xlsx_seconds,4)},
        'limitations':['一次本机合成读取探测，不含关联、比较、导出或客户端开销','XLSX只测10万数据单元格，不证明200万单元格全链路容量','峰值RSS含Python与库开销；双CSV读取同一合成物理文件，受缓存影响']
    }
    dest=ROOT/'evidence/m1/capacity-probe.json'; dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
