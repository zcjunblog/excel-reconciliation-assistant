import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile
from distribution_helpers import NAME,tool


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.dir=Path(self.temp.name).resolve()

    def release(self):
        builder=tool(self,'build_release'); release=self.dir/'release'; builder.build(release); return release

    def test_independent_archives_replay_all_cases_and_explicit_downgrade(self):
        smoke=tool(self,'smoke_archive'); release=self.release(); out=self.dir/'独立 提取与验证'
        result=smoke.verify(release,out)
        self.assertTrue(result['passed']); self.assertEqual(result['case_tasks'],10)
        self.assertEqual(len(result['profiles']),2)
        for profile in result['profiles']:
            self.assertTrue(profile['installed_cli_only']); self.assertEqual(len(profile['cases']),4)
            self.assertEqual(profile['csv_no_dependencies']['status'],'partial')
            self.assertFalse(profile['csv_no_dependencies']['xlsx_generated'])
        self.assertTrue((out/'verification.json').is_file())

    def test_checksum_tamper_and_existing_output_refuse_execution(self):
        smoke=tool(self,'smoke_archive'); release=self.release()
        manifest=json.loads((release/'manifest.json').read_text()); p=release/manifest['packages'][0]['archive']
        with p.open('ab') as f: f.write(b'tampered')
        out=self.dir/'invalid'
        with self.assertRaises(ValueError): smoke.verify(release,out)
        self.assertFalse(out.exists())
        existing=self.dir/'existing'; existing.mkdir(); (existing/'keep').write_text('foreign')
        with self.assertRaises(ValueError): smoke.verify(release,existing)
        self.assertEqual((existing/'keep').read_text(),'foreign')

    def test_relative_interpreter_path_remains_valid_after_changing_work_directory(self):
        import sys
        smoke=tool(self,'smoke_archive'); release=self.release()
        relative=Path(os.path.relpath(sys.executable,Path.cwd()))
        result=smoke.verify(release,self.dir/'relative-python',python=relative)
        self.assertTrue(result['passed'])

    def test_traversal_duplicate_symlink_or_missing_member_is_rejected_before_run(self):
        smoke=tool(self,'smoke_archive'); builder=tool(self,'build_release')
        for kind in ('traversal','duplicate','symlink','missing'):
            with self.subTest(kind=kind):
                release=self.dir/kind; builder.build(release); manifest=json.loads((release/'manifest.json').read_text())
                item=manifest['packages'][0]; archive=release/item['archive']
                with zipfile.ZipFile(archive) as z: entries=[(i,z.read(i)) for i in z.infolist()]
                with warnings.catch_warnings(),zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                    warnings.simplefilter('ignore',UserWarning)
                    for i,data in entries:
                        if kind=='missing' and i.filename==NAME+'/scripts/checks.py': continue
                        if kind=='symlink' and i.filename==NAME+'/scripts/checks.py': i.external_attr=0o120777<<16
                        z.writestr(i,data)
                    if kind=='traversal': z.writestr('../escape.txt','bad')
                    if kind=='duplicate': z.writestr(NAME+'/VERSION','0.1.0\n')
                item['sha256']=hashlib.sha256(archive.read_bytes()).hexdigest(); item['bytes']=archive.stat().st_size
                (release/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError): smoke.verify(release,self.dir/(kind+'-out'))
                self.assertFalse((self.dir/'escape.txt').exists()); self.assertFalse((self.dir/(kind+'-out')).exists())

    def test_missing_wrong_duplicate_or_extra_sha256sums_block_before_execution(self):
        from unittest.mock import patch
        smoke=tool(self,'smoke_archive')
        for kind in ('missing','wrong','duplicate','extra'):
            with self.subTest(kind=kind):
                release=self.dir/kind; tool(self,'build_release').build(release); sums=release/'SHA256SUMS'
                text=sums.read_text()
                if kind=='missing': sums.unlink()
                elif kind=='wrong': sums.write_text('0'*64+text[64:])
                elif kind=='duplicate': sums.write_text(text+text.splitlines()[0]+'\n')
                else: sums.write_text(text+'0'*64+'  extra.zip\n')
                with patch.object(smoke,'_run',side_effect=AssertionError('Archive executed before checksum-list validation')):
                    with self.assertRaises((ValueError,OSError)): smoke.verify(release,self.dir/(kind+'-out'))

    def test_oracle_verifies_exact_pairs_and_full_field_set_not_separate_row_sets(self):
        smoke=tool(self,'smoke_archive'); result=smoke.verify(self.release(),self.dir/'replay')
        folder=self.dir/'replay/standard/cases/inventory-v001'
        p=folder/'工作资料/字段结果.jsonl'; fields=[json.loads(l) for l in p.read_text().splitlines()]
        import copy
        for mutation in ('pair','field-set'):
            with self.subTest(mutation=mutation):
                changed=copy.deepcopy(fields)
                if mutation=='pair': next(f for f in changed if f['left']['ref']['row']==2 and f['status']=='exact')['right']['ref']['row']=2
                else: changed[0]=changed[1].copy()
                p.write_text(''.join(json.dumps(f)+'\n' for f in changed))
                with self.assertRaises(ValueError): smoke._oracle(folder,'inventory')


if __name__=='__main__': unittest.main()
