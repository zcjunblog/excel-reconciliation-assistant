import copy
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from openpyxl import load_workbook
from delivery_helpers import results_for, synthetic_rules
from comparison_helpers import table, task
from common import Budget, IntakeError
from matching import associate
from compare import compare_task
from export import write_workbook


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)

    def test_full_match_index_and_exception_sheets(self):
        rules,results=results_for()
        record=write_workbook(results,rules,self.dir,Budget())
        path=self.dir/'核对结果.xlsx'
        self.assertTrue(path.is_file()); self.assertEqual(record.sha256,hashlib.sha256(path.read_bytes()).hexdigest())
        wb=load_workbook(path); self.addCleanup(wb.close)
        self.assertEqual(wb.sheetnames[0],'核对概览')
        self.assertEqual(wb['匹配索引'].max_row,4)
        self.assertEqual(wb['差异明细'].max_row,5)
        self.assertEqual(wb['差异明细'].freeze_panes,'E2')
        self.assertEqual(wb['差异明细'].auto_filter.ref,f'A1:U5')
        headers={c.value:c.column for c in wb['差异明细'][1]}
        self.assertEqual([wb['差异明细'].cell(r,headers['状态']).value for r in range(2,6)],['规则内一致','有差异','有差异','不可比较'])
        self.assertEqual(wb['差异明细'].cell(2,headers['基准原行']).value,2)
        self.assertEqual(wb['差异明细'].cell(2,headers['比较原列']).value,'B')
        self.assertEqual(wb['核对概览']['A8'].value,3)
        self.assertEqual(wb['核对概览']['D8'].value,2)
        self.assertEqual(wb['核对概览']['G8'].value,1)
        self.assertEqual(wb['核对概览']['J8'].value,5)

    def test_untrusted_text_stays_inert_and_precision_is_retained(self):
        rule=task()
        values=['=1+1','+cmd|x','-1+2','@SUM(A1:A2)','\t=NOW()','第一行\n第二行','https://example.test/file','00000012345678901234567']
        left=table('left',[[str(i),v] for i,v in enumerate(values)])
        right=table('right',[[str(i),'changed'] for i in range(len(values))])
        result=compare_task(associate(left,right,rule),rule,Budget())
        rules=synthetic_rules(result)
        write_workbook([result],rules,self.dir,Budget())
        wb=load_workbook(self.dir/'核对结果.xlsx'); self.addCleanup(wb.close)
        ws=wb['差异明细']; headers={c.value:c.column for c in ws[1]}
        self.assertEqual([ws.cell(r,headers['基准原值']).value for r in range(2,10)],values)
        for row in ws.iter_rows(min_row=2):
            for c in row:
                self.assertNotEqual(c.data_type,'f'); self.assertIsNone(c.hyperlink)

    def test_zero_record_categories_only_in_overview(self):
        rules,results=results_for('training'); write_workbook(results,rules,self.dir,Budget())
        wb=load_workbook(self.dir/'核对结果.xlsx'); self.addCleanup(wb.close)
        self.assertIn('匹配索引',wb.sheetnames)
        self.assertNotIn('空白明细',wb.sheetnames)
        self.assertEqual(wb['核对概览']['D8'].value,0)

    def test_sharding_and_failed_export_not_registered(self):
        rules,results=results_for('commerce')
        write_workbook(results,rules,self.dir,Budget(max_sheet_rows=2))
        wb=load_workbook(self.dir/'核对结果.xlsx'); self.addCleanup(wb.close)
        self.assertEqual(wb['差异明细_01'].max_row,3); self.assertEqual(wb['差异明细_02'].max_row,3)
        links=[c.hyperlink.location for row in wb['核对概览'] for c in row if c.hyperlink]
        self.assertTrue(any('差异明细_02' in s for s in links))
        for options in ({'max_output_rows':1},{'max_output_cells':5},{'max_output_bytes':1},{'max_output_sheets':1}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(IntakeError): write_workbook(results,rules,Path(tmp),Budget(**options))
                self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_existing_file_and_interrupted_save_preserved(self):
        rules,results=results_for()
        original=self.dir/'核对结果.xlsx'; original.write_bytes(b'keep-existing')
        with self.assertRaises(IntakeError): write_workbook(results,rules,self.dir,Budget())
        self.assertEqual(original.read_bytes(),b'keep-existing'); original.unlink()
        with patch('openpyxl.workbook.workbook.Workbook.save',side_effect=OSError('disk full')):
            with self.assertRaises(IntakeError): write_workbook(results,rules,self.dir,Budget())
        self.assertEqual(list(self.dir.iterdir()),[])

    def test_modified_summary_cannot_export_as_valid(self):
        rules,results=results_for(); results[0].field_counts['exact']+=1
        with self.assertRaises(IntakeError): write_workbook(results,rules,self.dir,Budget())
        self.assertFalse((self.dir/'核对结果.xlsx').exists())

    def test_failed_final_copy_leaves_no_workbook(self):
        rules,results=results_for()
        import shutil
        copy_file=shutil.copyfileobj
        def interrupted(src,dst,*args):
            if Path(getattr(dst,'name','')).name=='核对结果.xlsx':
                dst.write(src.read(20)); raise RuntimeError('unexpected write interruption')
            return copy_file(src,dst,*args)
        with patch('shutil.copyfileobj',side_effect=interrupted):
            with self.assertRaises(RuntimeError): write_workbook(results,rules,self.dir,Budget())
        self.assertEqual(list(self.dir.iterdir()),[])

    def test_multiline_and_iso_text_have_enough_row_height(self):
        rule=task(); values=['第一行\n第二行\n第三行','2026-11-06T08:09:10.123456+08:00']
        left=table('left',[[str(i),v] for i,v in enumerate(values)])
        right=table('right',[[str(i),'changed'] for i in range(len(values))])
        result=compare_task(associate(left,right,rule),rule,Budget())
        write_workbook([result],synthetic_rules(result),self.dir,Budget())
        wb=load_workbook(self.dir/'核对结果.xlsx'); self.addCleanup(wb.close)
        self.assertGreaterEqual(wb['差异明细'].row_dimensions[2].height,60)
        self.assertGreaterEqual(wb['差异明细'].row_dimensions[3].height,60)


if __name__=='__main__': unittest.main()
