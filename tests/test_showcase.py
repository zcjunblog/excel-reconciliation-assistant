"""User-facing examples must be real, reproducible tool deliveries without private paths."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from distribution_helpers import ROOT,tool


class ShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.dir=Path(self.temp.name).resolve()

    def test_five_real_case_deliveries_match_manual_answers_and_clean_receipts(self):
        module=tool(self,'prepare_showcase'); out=self.dir/'展示案例'
        result=module.prepare(out)
        self.assertTrue(result['passed']); self.assertEqual(result['case_tasks'],6)
        self.assertEqual(len(result['cases']),5)
        self.assertTrue(result['m1_originals_unchanged']); self.assertTrue(result['m5_packages_unchanged'])
        neg=out/'negative-delta/工作资料/字段结果.jsonl'
        fields=[json.loads(l) for l in neg.read_text().splitlines()]
        self.assertEqual([f['delta'] for f in fields if f['status']=='different'],['-2','-10.25','0.20'])
        self.assertEqual(json.loads((out/'negative-delta/交付清单.json').read_text())['status'],'complete')
        self.assertTrue((out/'showcase-manifest.json').exists())
        self.assertTrue(module.audit_public_tree(out)['passed'])

    def test_existing_public_output_is_not_overwritten(self):
        module=tool(self,'prepare_showcase'); out=self.dir/'existing';out.mkdir(); (out/'keep').write_text('foreign')
        with self.assertRaises(ValueError): module.prepare(out)
        self.assertEqual((out/'keep').read_text(),'foreign')

    def test_private_path_and_token_markers_in_text_or_office_xml_block_publication(self):
        module=tool(self,'prepare_showcase')
        for name,body in [('doc.md','/Users/example/private/file.csv'),('receipt.json','{"path":"C:\\\\Users\\\\example\\\\private"}'),('fields.jsonl','wbSeedToken=example')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/name).write_text(body)
                with self.assertRaises(ValueError): module.audit_public_tree(root)
        root=self.dir/'xlsx';root.mkdir()
        with zipfile.ZipFile(root/'result.xlsx','w') as z:z.writestr('xl/worksheets/sheet1.xml','<t>/Users/example/private/file.csv</t>')
        with self.assertRaises(ValueError): module.audit_public_tree(root)


if __name__=='__main__': unittest.main()
