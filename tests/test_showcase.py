"""User-facing examples must be real, reproducible tool deliveries without private paths."""
import json
import hashlib
import os
import shutil
import subprocess
import sys
from unittest.mock import patch
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
        for name,body in [('doc.md','/Users/example/private/file.csv'),('receipt.json','{"path":"C:\\\\Users\\\\example\\\\private"}'),('fields.jsonl','{"note":"wbSeedToken=example"}')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/name).write_text(body)
                if name.endswith(('.json','.jsonl')): json.loads(body)
                with self.assertRaisesRegex(ValueError,'Private path or token marker'): module.audit_public_tree(root)
        root=self.dir/'xlsx';root.mkdir()
        with zipfile.ZipFile(root/'result.xlsx','w') as z:z.writestr('xl/worksheets/sheet1.xml','<t>/Users/example/private/file.csv</t>')
        with self.assertRaises(ValueError): module.audit_public_tree(root)

    def project_copy(self,name):
        root=self.dir/name;root.mkdir()
        for folder in ('tools','skills','examples','releases'):
            shutil.copytree(ROOT/folder,root/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        (root/'evidence/m6').mkdir(parents=True)
        for name in ('performance.json','reproduce_benchmark.py'):
            shutil.copyfile(ROOT/'evidence/m6'/name,root/'evidence/m6'/name)
        return root

    @unittest.skipUnless(shutil.which('git') and (ROOT/'.git').exists(),'Needs a Git checkout to exercise checkout byte filters')
    def test_git_checkout_filters_preserve_all_frozen_and_receipted_bytes(self):
        from distribution import RESOURCES,NAME
        paths=[f['path'] for f in json.loads((ROOT/'examples/manifest.json').read_text())['files']]
        paths+=['skills/'+NAME+'/'+name for name in RESOURCES]
        paths+=['examples/showcase-v1/'+f['path'] for f in json.loads((ROOT/'examples/showcase-v1/showcase-manifest.json').read_text())['files']]
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/'examples/release-cases/negative-delta').glob('*') if p.is_file()]
        for name in paths:
            baseline=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
            checkout=subprocess.check_output(['git','-c','core.autocrlf=true','cat-file','--filters','HEAD:'+name],cwd=ROOT)
            self.assertEqual(checkout,baseline,name)

    def test_public_audit_rejects_missing_non_directory_or_empty_input(self):
        module=tool(self,'prepare_showcase');plain=self.dir/'file.md';plain.write_text('data');empty=self.dir/'empty';empty.mkdir()
        for path in (self.dir/'missing',plain,empty):
            with self.subTest(path=path.name),self.assertRaises(ValueError):module.audit_public_tree(path)

    def test_only_frozen_synthetic_sources_rules_and_oracles_are_accepted(self):
        module=tool(self,'prepare_showcase')
        for kind in ('file-link','parent-link','source-drift','rule-drift','oracle-drift'):
            with self.subTest(kind=kind):
                root=self.project_copy(kind);case=root/'examples/release-cases/negative-delta';outside=self.dir/(kind+'-external');outside.mkdir()
                if kind=='parent-link':
                    shutil.move(str(case),outside/'case');case.symlink_to(outside/'case',target_is_directory=True)
                elif kind=='oracle-drift':
                    with (case/'expected.json').open('a') as f:f.write('\n')
                else:
                    for name in ('基准清单.csv','比较清单.csv'):
                        src=case/name;raw=src.read_bytes().replace('许林'.encode(),'SyntheticPrivatePerson123'.encode()).replace('陈溪'.encode(),'SyntheticPrivatePerson123'.encode())
                        if kind=='source-drift':src.write_bytes(raw)
                        else:
                            dest=outside/name;dest.write_bytes(raw)
                            if kind=='file-link':src.unlink();src.symlink_to(dest)
                    if kind=='rule-drift':
                        rules=json.loads((case/'rules.json').read_text())
                        for source in rules['sources']:source['path']=str(outside/source['path'])
                        (case/'rules.json').write_text(json.dumps(rules,ensure_ascii=False))
                target=self.dir/(kind+'-public')
                with patch.object(module,'ROOT',root),patch.object(module,'SOURCE',root/'skills/excel-reconciliation-assistant'):
                    with self.assertRaises(ValueError):module.prepare(target)
                self.assertFalse(target.exists())

    def test_registered_source_hash_must_match_approved_bytes_even_after_restoration(self):
        module=tool(self,'prepare_showcase');root=self.project_copy('restoration');case=root/'examples/release-cases/negative-delta';run=module._run
        def changed(python,cli,args,cwd,expected,*rest,**kwargs):
            if Path(args[args.index('--rules')+1])!=case/'rules.json':return run(python,cli,args,cwd,expected,*rest,**kwargs)
            originals={p:p.read_bytes() for p in case.glob('*.csv')}
            try:
                for p,raw in originals.items():p.write_bytes(raw.replace('许林'.encode(),'SyntheticPrivatePerson123'.encode()).replace('陈溪'.encode(),'SyntheticPrivatePerson123'.encode()))
                return run(python,cli,args,cwd,expected,*rest,**kwargs)
            finally:
                for p,raw in originals.items():p.write_bytes(raw)
        with patch.object(module,'ROOT',root),patch.object(module,'SOURCE',root/'skills/excel-reconciliation-assistant'),patch.object(module,'_run',changed):
            with self.assertRaises(ValueError):module.prepare(self.dir/'restored-public')
        self.assertFalse((self.dir/'restored-public').exists())

    def test_foreign_target_objects_block_publication_and_are_not_deleted(self):
        module=tool(self,'prepare_showcase');from delivery_guard import DeliveryGuard
        original_open=DeliveryGuard.open;original_entry=DeliveryGuard.publish_entry
        for phase,kind in [('before','file'),('before','directory'),('before','link'),('after','file')]:
            with self.subTest(phase=phase,kind=kind):
                target=self.dir/(phase+'-'+kind);foreign=target/'scratch-notes.md';outside=self.dir/'outside.txt';outside.write_text('foreign source')
                def add(guard):
                    if kind=='file':foreign.write_text('/Users/example/accountSnapshot')
                    elif kind=='directory':foreign.mkdir()
                    else:foreign.symlink_to(outside)
                def opening(guard,name):
                    handle=original_open(guard,name)
                    if (phase=='before' and name=='training/核对结果.xlsx') or (phase=='after' and name=='showcase-manifest.json'):add(guard)
                    return handle
                def entry(guard,name,data):
                    original_entry(guard,name,data)
                    if phase=='after':add(guard)
                with patch.object(DeliveryGuard,'open',opening),patch.object(DeliveryGuard,'publish_entry',entry):
                    with self.assertRaises(ValueError):module.prepare(target)
                self.assertTrue(foreign.exists());self.assertFalse((target/'showcase-manifest.json').exists())
                self.assertFalse((target/'commerce/核对结果.xlsx').exists())

    def test_benchmark_reproduction_preserves_historical_record_and_writes_new_run_record(self):
        root=self.project_copy('benchmark');baseline=root/'evidence/m6/performance.json';before=baseline.read_bytes()
        process=subprocess.run([sys.executable,str(root/'evidence/m6/reproduce_benchmark.py')],cwd=root,capture_output=True,timeout=140)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(baseline.read_bytes(),before,'Reproduction overwrote accepted evidence')
        result=json.loads(process.stdout);record=root/result['output']/'performance.json'
        self.assertEqual(json.loads(record.read_text()),result)

    def test_optimized_benchmark_refuses_to_claim_validation(self):
        root=self.project_copy('optimized')
        process=subprocess.run([sys.executable,'-O',str(root/'evidence/m6/reproduce_benchmark.py')],cwd=root,capture_output=True,timeout=140)
        self.assertNotEqual(process.returncode,0,'Optimized execution cannot silently disable validation')
        self.assertNotIn('"passed": true',process.stdout.decode())
        self.assertEqual(json.loads(process.stdout)['status'],'blocked')


if __name__=='__main__': unittest.main()
