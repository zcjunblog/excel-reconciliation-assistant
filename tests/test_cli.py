import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fixture_helpers import ROOT, csv_case, write_rules, mutate_xlsx, sample

CLI=ROOT/'skills/excel-reconciliation-assistant/scripts/reconcile_tool.py'


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name).resolve()

    def run_cli(self,mode,path,out,authorize=True,no_site=False,extra=()):
        data=json.loads(path.read_text(encoding='utf-8'))
        args=[sys.executable]+(['-S'] if no_site else [])+[str(CLI),mode,'--rules',str(path),'--output',str(out)]
        if authorize:
            for source in data['sources']: args+=['--authorize',str((path.parent/source['path']).resolve())]
        args+=list(extra)
        run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=25)
        self.assertTrue(run.stdout,run.stderr)
        return run.returncode,json.loads(run.stdout)

    def test_commerce_end_to_end_readback(self):
        from openpyxl import load_workbook
        path=ROOT/'examples/commerce/rules.json'; out=self.dir/'v001'
        source=path.parent/'inputs.xlsx'; digest=hashlib.sha256(source.read_bytes()).hexdigest()
        code,status=self.run_cli('run',path,out)
        self.assertEqual(code,2,status); self.assertEqual(status['status'],'needs_confirmation')
        self.assertTrue((out/'核对结果.xlsx').exists())
        self.assertTrue((out/'核对报告.md').exists()); self.assertTrue((out/'待确认事项.md').exists())
        manifest=json.loads((out/'交付清单.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'],'needs_confirmation'); self.assertEqual(manifest['mode'],'run')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)
        wb=load_workbook(out/'核对结果.xlsx'); self.addCleanup(wb.close)
        self.assertEqual(wb['差异明细'].max_row,5); self.assertEqual(wb['匹配索引'].max_row,4)

    def test_inspect_does_not_claim_comparison(self):
        code,status=self.run_cli('inspect',ROOT/'examples/commerce/rules.json',self.dir/'inspect')
        self.assertEqual(code,0,status); self.assertEqual(status['status'],'ready')
        self.assertFalse((self.dir/'inspect/核对结果.xlsx').exists())
        manifest=json.loads((self.dir/'inspect/交付清单.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['mode'],'inspect'); self.assertEqual(manifest['tasks'],[])
        self.assertNotIn('字段结果.jsonl',[Path(f['path']).name for f in manifest['files']])
        self.assertIn('未执行关联或字段比较',(self.dir/'inspect/预检报告.md').read_text(encoding='utf-8'))

    def test_partial_task_and_existing_output(self):
        folder=self.dir/'inputs'; folder.mkdir()
        mutate_xlsx(folder/'inputs.xlsx',{},ROOT/'examples/administration/inputs.xlsx')
        data=sample('administration'); data['tables'][2]['sheet']='missing-sheet'
        path=write_rules(folder,data); out=self.dir/'partial'
        code,status=self.run_cli('run',path,out)
        self.assertEqual(code,2,status); self.assertEqual(status['status'],'partial')
        manifest=json.loads((out/'交付清单.json').read_text(encoding='utf-8'))
        self.assertEqual([t['status'] for t in manifest['tasks']],['needs_confirmation','blocked'])
        lines=(out/'工作资料/字段结果.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines),6)
        keep=out/'keep.txt'; keep.write_text('preserve')
        code,status=self.run_cli('run',path,out)
        self.assertEqual(code,1); self.assertEqual(keep.read_text(),'preserve')
        self.assertEqual(status['errors'][0]['code'],'output_exists')

    def test_authorization_is_not_implied_by_rules(self):
        path=csv_case(self.dir); out=self.dir/'unauthorized'
        code,status=self.run_cli('run',path,out,authorize=False)
        self.assertEqual(code,1); self.assertEqual(status['status'],'blocked')
        self.assertTrue(any(e['code']=='source_not_authorized' for e in status['errors']))
        self.assertFalse((out/'核对结果.xlsx').exists())

    def test_missing_dependency_csv_reports_actual_files_and_xlsx_explains(self):
        code,status=self.run_cli('run',ROOT/'examples/inventory/rules.json',self.dir/'csv-no-deps',no_site=True)
        self.assertEqual(code,2,status); self.assertEqual(status['status'],'partial')
        out=self.dir/'csv-no-deps'
        self.assertFalse((out/'核对结果.xlsx').exists()); self.assertTrue((out/'核对报告.md').exists())
        manifest=json.loads((out/'交付清单.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['unavailable_formats'][0]['code'],'missing_dependency')
        code,status=self.run_cli('inspect',ROOT/'examples/commerce/rules.json',self.dir/'xlsx-no-deps',no_site=True)
        self.assertEqual(code,1,status); self.assertEqual(status['status'],'blocked')
        self.assertTrue(any(e['code']=='missing_dependency' for e in status['errors']))

    def test_hard_timeout_does_not_leave_complete_delivery(self):
        path=csv_case(self.dir); out=self.dir/'timeout'
        code,status=self.run_cli('run',path,out,extra=['--timeout','0.000001'])
        self.assertEqual(code,1,status); self.assertEqual(status['errors'][0]['code'],'execution_timeout')
        self.assertFalse((out/'交付清单.json').exists())
        self.assertEqual(list(self.dir.glob('.reconcile-*')),[])

    def test_complete_with_differences_is_not_business_pass(self):
        path=csv_case(self.dir,left='id,value\na,1\nb,2\n',right='id,value\na,1\nb,3\n')
        code,status=self.run_cli('run',path,self.dir/'different')
        self.assertEqual(code,0,status); self.assertEqual(status['status'],'complete')
        self.assertEqual(status['different_fields'],1)
        text=(self.dir/'different/核对报告.md').read_text(encoding='utf-8')
        self.assertNotIn('核对通过',text); self.assertIn('有差异',text)


if __name__=='__main__': unittest.main()
