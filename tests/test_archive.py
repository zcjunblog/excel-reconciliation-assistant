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


if __name__=='__main__': unittest.main()
