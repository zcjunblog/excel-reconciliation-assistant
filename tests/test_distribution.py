import copy
import hashlib
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from distribution_helpers import ROOT,SOURCE,NAME,tool,source_copy


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.dir=Path(self.temp.name).resolve()

    def test_two_packages_are_reproducible_and_only_frontmatter_differs(self):
        builder=tool(self,'build_release'); one=self.dir/'one'; two=self.dir/'two'
        builder.build(one); builder.build(two)
        manifest=json.loads((one/'manifest.json').read_text()); self.assertEqual(manifest['version'],'0.1.0')
        data=[]
        for item in manifest['packages']:
            p=one/item['archive']; self.assertEqual(p.read_bytes(),(two/item['archive']).read_bytes())
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),item['sha256'])
            with zipfile.ZipFile(p) as z:
                payload={n:z.read(n) for n in z.namelist()}
                self.assertEqual(len(payload),len(z.namelist()))
                for entry in item['files']:
                    raw=payload[NAME+'/'+entry['path']]
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256']); self.assertEqual(len(raw),entry['bytes'])
                self.assertFalse(any('__pycache__' in n or 'expected.json' in n for n in payload))
                data.append(payload)
        self.assertEqual({k for k in data[0] if data[0][k]!=data[1][k]},{NAME+'/SKILL.md'})
        self.assertEqual(data[0][NAME+'/SKILL.md'],(SOURCE/'SKILL.md').read_bytes())
        front,body=data[1][NAME+'/SKILL.md'].decode().split('---\n')[1:]
        fields={k:json.loads(v.strip()) for k,v in (line.split(':',1) for line in front.splitlines())}
        self.assertEqual(fields['version'],'0.1.0'); self.assertEqual(fields['display_name'],'Excel表格核对助手')
        self.assertEqual(len(fields['examples_zh']),len(fields['examples_en'])); self.assertGreater(len(fields['examples_zh']),0)
        self.assertEqual(body,(SOURCE/'SKILL.md').read_text().split('---\n')[2])

    def test_bad_platform_metadata_cannot_override_version_or_hide_empty_examples(self):
        d=tool(self,'distribution'); fields,body,version=d.skill_info()
        profile=json.loads((ROOT/'distribution/workbuddy.json').read_text())
        for changes in ({'version':'9.9.9'},{'name':'other'},{'examples_zh':['one'],'examples_en':[]},{'examples_zh':['']},{'author':42},{'examples_en':'hello'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): d.workbuddy_entry(fields,body,version,{**profile,**changes})

    def test_source_selection_rejects_missing_links_private_files_and_symlinks(self):
        d=tool(self,'distribution')
        for change in ('private','link','symlink','missing'):
            folder=self.dir/change; folder.mkdir(); source=source_copy(folder)
            if change=='private': (source/'references/customer-data.csv').write_text('private')
            elif change=='link':
                with (source/'SKILL.md').open('a') as f: f.write('\n[missing](references/missing.md)\n')
            elif change=='symlink':
                p=source/'templates/workbook-style.json'; p.unlink(); p.symlink_to(SOURCE/'templates/workbook-style.json')
            else: (source/'scripts/checks.py').unlink()
            with self.subTest(change=change), self.assertRaises(ValueError): d.snapshot(source)

    def test_cache_is_excluded_without_dropping_runtime_resources(self):
        d=tool(self,'distribution'); source=source_copy(self.dir)
        cache=source/'scripts/__pycache__'; cache.mkdir(); (cache/'local.pyc').write_bytes(b'cache')
        payloads,version=d.snapshot(source)
        self.assertNotIn('scripts/__pycache__/local.pyc',payloads)
        self.assertIn('scripts/checks.py',payloads); self.assertIn('references/examples/commerce/inputs.xlsx',payloads)

    def test_source_root_symlink_cannot_bypass_source_validation(self):
        d=tool(self,'distribution'); alias=self.dir/'alias'; alias.symlink_to(SOURCE,target_is_directory=True)
        with self.assertRaises(ValueError): d.snapshot(alias)

    def test_build_refuses_existing_output_and_does_not_publish_after_save_failure(self):
        builder=tool(self,'build_release'); existing=self.dir/'existing'; existing.mkdir(); (existing/'keep').write_text('foreign')
        with self.assertRaises(ValueError): builder.build(existing)
        self.assertEqual((existing/'keep').read_text(),'foreign')
        target=self.dir/'new'
        with patch('zipfile.ZipFile.writestr',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): builder.build(target)
        self.assertFalse(target.exists()); self.assertEqual(list(self.dir.glob('.skill-build-*')),[])

    def test_package_changed_during_publication_cannot_be_registered_as_complete(self):
        builder=tool(self,'build_release'); target=self.dir/'release'; copy_file=shutil.copyfileobj
        first=target/(NAME+'-0.1.0.zip')
        def mutate(src,dst,*args):
            copy_file(src,dst,*args)
            if Path(dst.name).parent==target and '-workbuddy-' in Path(dst.name).name: first.write_bytes(b'changed')
        with patch('distribution.shutil.copyfileobj',side_effect=mutate):
            with self.assertRaises(ValueError): builder.build(target)
        self.assertFalse((target/'manifest.json').exists())


if __name__=='__main__': unittest.main()
