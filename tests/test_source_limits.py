import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile
from fixture_helpers import ROOT, csv_case, workbook_case, write_rules, authorize, mutate_xlsx
from common import Budget
from rules import load_rules
from intake import inspect_sources, verify_sources_unchanged


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name).resolve()

    def inspect(self,path,budget=None,authorized=None):
        rules=load_rules(path)
        return rules,inspect_sources(rules,authorize(rules) if authorized is None else authorized,budget or Budget())

    def codes(self,result): return {i.code for i in result.issues}

    def test_source_not_authorized_and_changed_hash_blocked(self):
        p=csv_case(self.dir)
        rules,intake=self.inspect(p,authorized=set())
        self.assertEqual(intake.status,'blocked'); self.assertIn('source_not_authorized',self.codes(intake))
        rules,intake=self.inspect(p)
        self.assertEqual(intake.status,'ready')
        (self.dir/'left.csv').write_text('id,value\na,99\nb,2\n')
        self.assertFalse(verify_sources_unchanged(intake,rules,Budget()))
        self.assertTrue(intake.global_blocked); self.assertIn('source_changed',self.codes(intake))

    def test_immutable_snapshot_and_original_hash(self):
        p=csv_case(self.dir); rules,intake=self.inspect(p)
        for snap in intake.source_snapshots.values():
            self.assertEqual(snap.sha256,hashlib.sha256(snap.path.read_bytes()).hexdigest())
            self.assertEqual(snap.sha256,hashlib.sha256(snap.data).hexdigest())
            self.assertEqual(snap.bytes,len(snap.data))

    def test_symlink_target_requires_explicit_authorization(self):
        p=csv_case(self.dir); (self.dir/'alias.csv').symlink_to(self.dir/'left.csv')
        d=load_rules(p).payload; d['sources'][0]['path']='alias.csv'; write_rules(self.dir,d)
        rules,intake=self.inspect(p,authorized={self.dir/'alias.csv',self.dir/'right.csv'})
        self.assertIn('left',intake.blocked_table_ids); self.assertIn('source_not_authorized',self.codes(intake))
        rules,intake=self.inspect(p,authorized={self.dir/'left.csv',self.dir/'right.csv'})
        self.assertEqual(intake.status,'ready')

    def test_directories_devices_and_fifo_rejected_without_read(self):
        p=csv_case(self.dir); d=load_rules(p).payload
        (self.dir/'fifo.csv').parent.mkdir(exist_ok=True)
        os.mkfifo(self.dir/'fifo.csv')
        for path in (self.dir,self.dir/'fifo.csv',Path('/dev/null')):
            with self.subTest(path=path):
                d['sources'][0]['path']=str(path); write_rules(self.dir,d)
                rules,intake=self.inspect(p,authorized={path,self.dir/'right.csv'})
                self.assertIn('source_not_regular',self.codes(intake))

    def test_same_physical_file_and_hardlink_not_registered_twice(self):
        p=csv_case(self.dir); d=load_rules(p).payload
        for path in ('left.csv','linked.csv'):
            if path=='linked.csv': os.link(self.dir/'left.csv',self.dir/path)
            d['sources'][1]['path']=path; write_rules(self.dir,d)
            rules,intake=self.inspect(p)
            self.assertIn('duplicate_source',self.codes(intake)); self.assertNotIn('right',intake.source_snapshots)

    def test_file_size_and_deadline_are_global_failures(self):
        p=csv_case(self.dir)
        for budget in (Budget(max_file_bytes=3),Budget(max_seconds=-1)):
            rules,intake=self.inspect(p,budget)
            self.assertTrue(intake.global_blocked); self.assertEqual(intake.status,'blocked')
            self.assertIn('budget_exceeded',self.codes(intake))

    def test_zip_budget_and_duplicate_members(self):
        p=workbook_case(self.dir)
        for budget in (Budget(max_zip_members=1),Budget(max_member_bytes=10),Budget(max_zip_bytes=10),Budget(max_total_zip_bytes=10)):
            with self.subTest(budget=budget):
                _,intake=self.inspect(p,budget)
                self.assertTrue(intake.global_blocked); self.assertIn('budget_exceeded',self.codes(intake))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(self.dir/'inputs.xlsx','a') as z: z.writestr('xl/workbook.xml','duplicate')
        _,intake=self.inspect(p)
        self.assertIn('invalid_zip',self.codes(intake))

    def test_zip_traversal_macros_external_links_and_encryption(self):
        for member in ('../escape.xml','/absolute.xml','xl/vbaProject.bin','xl/externalLinks/externalLink1.xml'):
            with self.subTest(member=member):
                p=workbook_case(self.dir,{member:b'untrusted'})
                _,intake=self.inspect(p)
                self.assertIn('unsafe_workbook',self.codes(intake))
        p=workbook_case(self.dir)
        data=bytearray((self.dir/'inputs.xlsx').read_bytes())
        for sig,offset in ((b'PK\x03\x04',6),(b'PK\x01\x02',8)):
            pos=0
            while True:
                pos=data.find(sig,pos)
                if pos<0: break
                data[pos+offset] |= 1; pos+=4
        (self.dir/'inputs.xlsx').write_bytes(data)
        _,intake=self.inspect(p)
        self.assertIn('unsafe_workbook',self.codes(intake))

    def test_disguised_macro_content_and_dtd_rejected(self):
        for changes in (
            {'[Content_Types].xml':lambda b:b.replace(b'spreadsheetml.sheet.main+xml',b'ms-excel.sheet.macroEnabled.main+xml')},
            {'xl/workbook.xml':b'<!DOCTYPE a [<!ENTITY x "x">]><a>&x;</a>'},
        ):
            p=workbook_case(self.dir,changes); _,intake=self.inspect(p)
            self.assertIn('unsafe_workbook',self.codes(intake))

    def test_corrupt_file_does_not_become_empty_success(self):
        p=workbook_case(self.dir); (self.dir/'inputs.xlsx').write_bytes(b'not a zip')
        _,intake=self.inspect(p)
        self.assertEqual(intake.status,'blocked'); self.assertIn('invalid_zip',self.codes(intake))

    def test_custom_table_and_cumulative_budgets_before_allocation(self):
        p=csv_case(self.dir)
        for budget in (Budget(max_table_rows=1),Budget(max_table_columns=1),Budget(max_total_rows=3),Budget(max_total_cells=7)):
            _,intake=self.inspect(p,budget)
            self.assertTrue(intake.global_blocked)


if __name__=='__main__': unittest.main()
