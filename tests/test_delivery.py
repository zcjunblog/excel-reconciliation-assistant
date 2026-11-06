import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fixture_helpers import ROOT, authorize, csv_case, write_rules
from common import Budget, IntakeError
from rules import load_rules
from runner import execute
from report import write_reports, finalize_delivery
from export import write_workbook
from reconcile_tool import run_job


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name).resolve(); self.stage=self.dir/'stage'; self.stage.mkdir()

    def run_result(self,path=None,budget=None):
        rules=load_rules(path or ROOT/'examples/commerce/rules.json'); b=budget or Budget()
        return execute(rules,authorize(rules),b),b

    def test_manifest_matches_every_file_and_full_internal_rows(self):
        run,b=self.run_result(); files=[write_workbook(run.task_results,run.rules,self.stage,b)]
        files+=write_reports(run,self.stage)
        out=self.dir/'v001'; finalize_delivery(run,files,out)
        manifest=json.loads((out/'交付清单.json').read_text(encoding='utf-8'))
        listed={f['path'] for f in manifest['files']}
        actual={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}-{'交付清单.json'}
        self.assertEqual(listed,actual); self.assertNotIn('inputs.xlsx',listed)
        for f in manifest['files']:
            p=out/f['path']; self.assertEqual(p.stat().st_size,f['bytes']); self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),f['sha256'])
        fields=[json.loads(line) for line in (out/'工作资料/字段结果.jsonl').read_text().splitlines()]
        rows=[json.loads(line) for line in (out/'工作资料/关联结果.jsonl').read_text().splitlines()]
        self.assertEqual(len(fields),9); self.assertEqual(len(rows),15)
        self.assertEqual(sum(r['status']=='excluded' for r in rows),1)
        self.assertNotIn('/Users/',(out/'工作资料/核对规则.json').read_text())

    def test_checksum_tamper_or_unregistered_file_blocks_promotion(self):
        run,_=self.run_result(); files=write_reports(run,self.stage)
        files[0].path.write_text('tampered')
        with self.assertRaises(IntakeError): finalize_delivery(run,files,self.dir/'v001')
        self.assertFalse((self.dir/'v001').exists())
        run,_=self.run_result(); stage=self.dir/'another-stage'; stage.mkdir(); files=write_reports(run,stage)
        (stage/'unregistered.txt').write_text('preserve')
        with self.assertRaises(IntakeError): finalize_delivery(run,files,self.dir/'v002')
        self.assertEqual((stage/'unregistered.txt').read_text(),'preserve')

    def test_source_change_after_reports_blocks_complete_delivery(self):
        path=csv_case(self.dir); run,_=self.run_result(path); files=write_reports(run,self.stage)
        (self.dir/'left.csv').write_text('id,value\na,99\nb,2\n')
        with self.assertRaises(IntakeError): finalize_delivery(run,files,self.dir/'v001')
        self.assertFalse((self.dir/'v001/交付清单.json').exists())

    def test_artifact_budget_and_disk_error_leave_no_fake_success(self):
        path=csv_case(self.dir); out=self.dir/'too-small'; rules=load_rules(path)
        code,status=run_job('run',path,out,authorize(rules),Budget(max_artifact_bytes=1))
        self.assertEqual(code,1); self.assertEqual(status['status'],'blocked')
        self.assertFalse((out/'交付清单.json').exists())
        out=self.dir/'disk-full'
        with patch('report.write_reports',side_effect=OSError('disk full')):
            code,status=run_job('run',path,out,authorize(rules),Budget())
        self.assertEqual(code,1); self.assertFalse((out/'交付清单.json').exists())

    def test_workbook_limit_keeps_full_json_and_reports_missing_format(self):
        path=csv_case(self.dir); rules=load_rules(path); out=self.dir/'limited'
        code,status=run_job('run',path,out,authorize(rules),Budget(max_output_rows=1))
        self.assertEqual(code,2,status); self.assertEqual(status['status'],'partial')
        self.assertFalse((out/'核对结果.xlsx').exists())
        self.assertEqual(len((out/'工作资料/字段结果.jsonl').read_text().splitlines()),2)
        manifest=json.loads((out/'交付清单.json').read_text())
        self.assertEqual(manifest['unavailable_formats'][0]['code'],'export_limit')

    def test_interrupted_copy_cleans_own_partial_file(self):
        run,b=self.run_result(); files=[write_workbook(run.task_results,run.rules,self.stage,b)]+write_reports(run,self.stage)
        def interrupted(src,dst):
            dst.write(src.read(20)); raise OSError('disk full')
        with patch('report.shutil.copyfileobj',side_effect=interrupted):
            with self.assertRaises(OSError): finalize_delivery(run,files,self.dir/'interrupted')
        self.assertFalse((self.dir/'interrupted').exists())

    def test_source_change_during_delivery_copy_blocks_manifest(self):
        path=csv_case(self.dir); run,b=self.run_result(path)
        files=[write_workbook(run.task_results,run.rules,self.stage,b)]+write_reports(run,self.stage)
        import shutil
        copy_file=shutil.copyfileobj
        def changed(src,dst):
            copy_file(src,dst); (self.dir/'left.csv').write_text('id,value\na,99\nb,2\n')
        with patch('report.shutil.copyfileobj',side_effect=changed):
            with self.assertRaises(IntakeError): finalize_delivery(run,files,self.dir/'changed')
        self.assertFalse((self.dir/'changed').exists())

    def test_unused_table_keeps_partial_status_in_every_artifact(self):
        from openpyxl import load_workbook
        path=csv_case(self.dir); data=json.loads(path.read_text())
        data['tables'].append({**data['tables'][0],'id':'unused'})
        write_rules(self.dir,data); rules=load_rules(path); out=self.dir/'unused-result'
        code,status=run_job('run',path,out,authorize(rules),Budget())
        self.assertEqual(code,2); self.assertEqual(status['status'],'partial')
        wb=load_workbook(out/'核对结果.xlsx'); self.addCleanup(wb.close)
        self.assertEqual(wb['核对概览']['B5'].value,'部分完成')


if __name__=='__main__': unittest.main()
