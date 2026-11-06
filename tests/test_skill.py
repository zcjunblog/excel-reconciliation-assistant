"""Portable skill discovery, installed-resource and runtime contracts."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from fixture_helpers import ROOT,csv_case

NAME='excel-reconciliation-assistant'
SOURCE=ROOT/'skills'/NAME


class SkillTests(unittest.TestCase):
    def test_entry_references_and_bundled_originals_are_self_contained(self):
        entry=SOURCE/'SKILL.md'; self.assertTrue(entry.is_file(),'Missing discoverable Skill entrypoint')
        front,body=entry.read_text(encoding='utf-8').split('---\n')[1:]
        fields={k:json.loads(v.strip()) for k,v in (line.split(':',1) for line in front.splitlines())}
        self.assertEqual(set(fields),{'name','description'}); self.assertEqual(fields['name'],NAME)
        self.assertTrue(1<=len(fields['description'])<=1024)
        for p in SOURCE.rglob('*.md'):
            for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if target.startswith(('https://','http://','#')): continue
                path=(p.parent/target.split('#')[0]).resolve()
                self.assertTrue(path.is_file(),(p,target)); self.assertIn(SOURCE.resolve(),path.parents)
        self.assertEqual((SOURCE/'references/reconciliation-rules.schema.json').read_bytes(),(ROOT/'schemas/reconciliation-rules.schema.json').read_bytes())
        for name in ('commerce','inventory','training','administration'):
            case=ROOT/'examples'/name; target=SOURCE/'references/examples'/name
            self.assertEqual((case/'rules.json').read_bytes(),(target/'rules.json').read_bytes())
            rules=json.loads((case/'rules.json').read_text())
            for source in rules['sources']:
                self.assertEqual((case/source['path']).read_bytes(),(target/source['path']).read_bytes())
        self.assertEqual(list((SOURCE/'references').rglob('expected.json')),[])

    def doctor(self,source=SOURCE,no_site=False,extra=()):
        args=[sys.executable]+(['-S'] if no_site else [])+[str(source/'scripts/doctor.py'),*extra]
        result=subprocess.run(args,capture_output=True,timeout=15)
        self.assertTrue(result.stdout,result.stderr)
        return result.returncode,json.loads(result.stdout)

    def test_doctor_uses_selected_runtime_and_keeps_csv_without_optional_dependency(self):
        code,data=self.doctor(); self.assertEqual(code,0,data); self.assertTrue(data['capabilities']['xlsx'])
        self.assertEqual(data['skill_version'],(SOURCE/'VERSION').read_text().strip())
        code,data=self.doctor(no_site=True); self.assertEqual(code,0,data)
        self.assertTrue(data['capabilities']['csv']); self.assertFalse(data['capabilities']['xlsx'])
        code,data=self.doctor(no_site=True,extra=('--require-xlsx',)); self.assertEqual(code,1,data)

    def test_missing_resources_are_reported_as_blocked_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/NAME; shutil.copytree(SOURCE,source)
            schema=source/'references/reconciliation-rules.schema.json'
            schema.unlink(missing_ok=True)
            code,data=self.doctor(source); self.assertEqual(code,1,data)
            self.assertEqual(data['status'],'blocked')
            self.assertTrue(any(i['code']=='missing_resource' for i in data['issues']))

    def test_run_from_installed_copy_records_its_actual_version(self):
        with tempfile.TemporaryDirectory(prefix='skill 版本 ') as tmp:
            base=Path(tmp).resolve(); source=base/'已安装技能'/NAME; shutil.copytree(SOURCE,source)
            (source/'VERSION').write_text('2.3.4\n')
            inputs=base/'用户资料'; inputs.mkdir(); path=csv_case(inputs); output=base/'业务交付'
            args=[sys.executable,str(source/'scripts/reconcile_tool.py'),'run','--rules',str(path),'--output',str(output)]
            for name in ('left.csv','right.csv'): args+=['--authorize',str(inputs/name)]
            result=subprocess.run(args,cwd=base,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout).get('skill_version'),'2.3.4')
            self.assertEqual(json.loads((output/'交付清单.json').read_text()).get('skill_version'),'2.3.4')
            self.assertEqual(json.loads((output/'工作资料/执行摘要.json').read_text()).get('skill_version'),'2.3.4')


if __name__=='__main__': unittest.main()
