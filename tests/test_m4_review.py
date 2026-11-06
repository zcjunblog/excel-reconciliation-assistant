"""Regression proofs from the independent whole-M4 review."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from fixture_helpers import ROOT, SCRIPTS, authorize, csv_case, write_rules
from delivery_helpers import results_for
from common import Budget, IntakeError
from rules import load_rules
from runner import execute
from export import write_workbook
from report import write_reports,finalize_delivery
from reconcile_tool import run_job,_cleanup_interrupted


class M4ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name).resolve()

    def delivery(self):
        rules=load_rules(ROOT/'examples/commerce/rules.json'); b=Budget()
        run=execute(rules,authorize(rules),b); stage=self.dir/'stage'; stage.mkdir()
        files=[write_workbook(run.task_results,rules,stage,b)]+write_reports(run,stage)
        return run,files

    def test_publication_refuses_injected_directory_symlink(self):
        run,files=self.delivery(); out=self.dir/'result'; foreign=self.dir/'foreign'; foreign.mkdir()
        copy_file=shutil.copyfileobj
        def injected(src,dst):
            copy_file(src,dst)
            if Path(dst.name).name=='核对结果.xlsx': (out/'工作资料').symlink_to(foreign,target_is_directory=True)
        with patch('report.shutil.copyfileobj',side_effect=injected):
            with self.assertRaises(IntakeError): finalize_delivery(run,files,out)
        self.assertEqual(list(foreign.iterdir()),[])
        self.assertTrue((out/'工作资料').is_symlink())
        self.assertFalse((out/'交付清单.json').exists())

    def test_timeout_cleanup_never_owns_merely_planned_paths(self):
        out=self.dir/'result'; out.mkdir(); foreign=out/'核对报告.md'; foreign.write_text('foreign')
        (out/'foreign-empty').mkdir()
        (out/'.交付中.json').write_text(json.dumps({'run_id':'own-run','files':['核对报告.md']}))
        _cleanup_interrupted(out,'own-run')
        self.assertEqual(foreign.read_text(),'foreign'); self.assertTrue((out/'foreign-empty').is_dir())

    def test_normal_failure_preserves_foreign_empty_directory_and_replacement(self):
        run,files=self.delivery(); out=self.dir/'result'; copy_file=shutil.copyfileobj
        def interrupted(src,dst):
            copy_file(src,dst); target=Path(dst.name)
            if target.name=='核对结果.xlsx':
                target.unlink(); target.write_bytes(b'foreign replacement')
                (out/'foreign-empty').mkdir(); raise OSError('interrupted')
        with patch('report.shutil.copyfileobj',side_effect=interrupted):
            with self.assertRaises(OSError): finalize_delivery(run,files,out)
        self.assertEqual((out/'核对结果.xlsx').read_bytes(),b'foreign replacement')
        self.assertTrue((out/'foreign-empty').is_dir())

    def test_symlinked_output_parent_uses_one_physical_staging_root(self):
        path=csv_case(self.dir); alias=self.dir/'alias'; real=self.dir/'real'; real.mkdir(); alias.symlink_to(real,target_is_directory=True)
        code,status=run_job('run',path,alias/'result',authorize(load_rules(path)),Budget())
        self.assertEqual(code,0,status); self.assertTrue((real/'result/交付清单.json').is_file())

    def test_non_utf8_stdout_is_valid_machine_json_after_success(self):
        path=csv_case(self.dir); out=self.dir/'result'; env={**os.environ,'PYTHONIOENCODING':'cp1252'}
        args=[sys.executable,str(SCRIPTS/'reconcile_tool.py'),'run','--rules',str(path),'--output',str(out)]
        for p in authorize(load_rules(path)): args+=['--authorize',str(p)]
        result=subprocess.run(args,capture_output=True,env=env,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr.decode('ascii',errors='replace'))
        self.assertEqual(json.loads(result.stdout)['status'],'complete')

    def test_timeout_during_real_xlsx_save_cleans_library_temp_xml(self):
        path=csv_case(self.dir); out=self.dir/'result'; system_temp=self.dir/'system-temp'; system_temp.mkdir()
        marker=self.dir/'writer-entered.txt'; wrapper=self.dir/'slow_writer.py'
        wrapper.write_text("import sys,time\nfrom pathlib import Path\nsys.path.insert(0,"+repr(str(SCRIPTS))+")\nfrom openpyxl.worksheet._writer import WorksheetWriter\noriginal=WorksheetWriter.close\ndef slow(self):\n original(self)\n Path("+repr(str(marker))+").write_text(str(self.out))\n time.sleep(5)\nWorksheetWriter.close=slow\nfrom reconcile_tool import main\nif __name__=='__main__': raise SystemExit(main())\n",encoding='utf-8')
        args=[sys.executable,str(wrapper),'run','--rules',str(path),'--output',str(out),'--timeout','2']
        for p in authorize(load_rules(path)): args+=['--authorize',str(p)]
        result=subprocess.run(args,capture_output=True,env={**os.environ,'TMPDIR':str(system_temp)},timeout=15)
        self.assertEqual(result.returncode,1,result.stderr); self.assertEqual(json.loads(result.stdout)['errors'][0]['code'],'execution_timeout')
        self.assertTrue(marker.exists(),'The timeout must interrupt actual XLSX writing, not startup')
        self.assertEqual(list(system_temp.glob('openpyxl.*')),[])
        self.assertFalse((out/'交付清单.json').exists()); self.assertEqual(list(self.dir.glob('.reconcile-*')),[])

    def test_different_rules_for_same_tables_have_distinct_visible_task_names(self):
        path=csv_case(self.dir,right='id,value\na,1\nb,3\n'); data=json.loads(path.read_text())
        second=copy.deepcopy(data['tasks'][0]); second['id']='tolerant'; second['fields'][1]['tolerance']='1'; data['tasks'].append(second)
        write_rules(self.dir,data); out=self.dir/'result'
        code,status=run_job('run',path,out,authorize(load_rules(path)),Budget()); self.assertEqual(code,0,status)
        from openpyxl import load_workbook
        wb=load_workbook(out/'核对结果.xlsx'); self.addCleanup(wb.close)
        labels={row[0].value for row in wb['匹配索引'].iter_rows(min_row=2)}
        self.assertEqual(len(labels),2); self.assertTrue(any('tolerant' in label for label in labels))

    def test_invalid_key_is_one_located_record_per_source_row(self):
        path=csv_case(self.dir,left='id,value\na,1\n,2\n'); out=self.dir/'result'
        code,status=run_job('run',path,out,authorize(load_rules(path)),Budget()); self.assertEqual(code,2,status)
        from openpyxl import load_workbook
        wb=load_workbook(out/'核对结果.xlsx'); self.addCleanup(wb.close); ws=wb['待确认记录']
        self.assertEqual(ws.max_row,3)
        for row in ws.iter_rows(min_row=2,values_only=True):
            self.assertEqual(row[2],'无效业务键'); self.assertEqual(row[6],3); self.assertEqual(row[7],'A')

    def test_xlsx_downgrade_keeps_per_table_intake_scope_metadata(self):
        path=ROOT/'examples/commerce/rules.json'; out=self.dir/'result'
        code,status=run_job('run',path,out,authorize(load_rules(path)),Budget(max_output_rows=1)); self.assertEqual(code,2,status)
        scope=out/'工作资料/读取范围.json'; self.assertTrue(scope.exists())
        data=json.loads(scope.read_text()); table=next(t for t in data if t['table_id']=='orders')
        self.assertEqual(table['preview']['metadata']['hidden_rows'],[4])
        self.assertEqual(table['preview']['metadata']['auto_filter'],'A1:F8')
        self.assertEqual(table['preview']['metadata']['date_system'],'1900')

    def test_downgrade_report_does_not_promise_a_missing_excel_file(self):
        path=ROOT/'examples/commerce/rules.json'; out=self.dir/'result'
        code,status=run_job('run',path,out,authorize(load_rules(path)),Budget(max_output_rows=1)); self.assertEqual(code,2,status)
        self.assertNotIn('完整明细保留在Excel及工作资料',(out/'核对报告.md').read_text())

    def test_timeout_cleanup_preserves_foreign_files_created_during_copy(self):
        path=csv_case(self.dir); out=self.dir/'result'; wrapper=self.dir/'slow_copy.py'; marker=self.dir/'copy-entered'
        wrapper.write_text("import sys,time,shutil\nfrom pathlib import Path\nsys.path.insert(0,"+repr(str(SCRIPTS))+")\noriginal=shutil.copyfileobj\ndef slow(src,dst,*args):\n original(src,dst,*args)\n if str(getattr(dst,'name','')).endswith('核对结果.xlsx') and Path(dst.name).parent==Path("+repr(str(out))+"):\n  parent=Path(dst.name).parent\n  (parent/'核对报告.md').write_text('foreign')\n  (parent/'foreign-empty').mkdir()\n  Path("+repr(str(marker))+").write_text('entered')\n  time.sleep(5)\nshutil.copyfileobj=slow\nfrom reconcile_tool import main\nif __name__=='__main__': raise SystemExit(main())\n",encoding='utf-8')
        args=[sys.executable,str(wrapper),'run','--rules',str(path),'--output',str(out),'--timeout','2']
        for p in authorize(load_rules(path)): args+=['--authorize',str(p)]
        result=subprocess.run(args,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,1); self.assertEqual(json.loads(result.stdout)['errors'][0]['code'],'execution_timeout')
        self.assertTrue(marker.exists())
        self.assertEqual((out/'核对报告.md').read_text(),'foreign'); self.assertTrue((out/'foreign-empty').is_dir())
        self.assertFalse((out/'核对结果.xlsx').exists()); self.assertFalse((out/'交付清单.json').exists())

    def test_output_budget_rejects_before_detail_rows_are_materialized(self):
        rules,results=results_for()
        with patch('export.build_views',side_effect=AssertionError('detail rows were materialized')):
            with self.assertRaises(IntakeError) as error: write_workbook(results,rules,self.dir,Budget(max_output_cells=1))
        self.assertEqual(error.exception.issue.code,'export_limit')


if __name__=='__main__': unittest.main()
