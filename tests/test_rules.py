import copy
import json
from pathlib import Path
import tempfile
import unittest
from fixture_helpers import ROOT, sample, write_rules
from rules import load_rules, validate_rules
from common import RuleSet, RuleError


class RuleTests(unittest.TestCase):
    def test_four_case_rules_are_valid(self):
        for case in ('commerce','inventory','training','administration'):
            with self.subTest(case=case):
                rules = load_rules(ROOT / 'examples' / case / 'rules.json')
                self.assertEqual(validate_rules(rules), [])
                self.assertEqual(rules.schema_version, '1.0')

    def assert_invalid(self, change, expected_path):
        data = sample(); change(data)
        issues = validate_rules(RuleSet.from_dict(data, ROOT / 'rules.json'))
        self.assertTrue(issues)
        self.assertTrue(any(expected_path in i.source_ref['rule_path'] for i in issues), issues)

    def test_unknown_field_and_negative_tolerance_rejected(self):
        edits = [
            (lambda d:d.update(unknown=True), '$.unknown'),
            (lambda d:d['tasks'][0]['fields'][-1].update(tolerance='-0.01'), '.tolerance'),
            (lambda d:d['tasks'][0]['fields'][0].update(tolerance='1'), '.tolerance'),
            (lambda d:d['tasks'][0]['fields'][-1].update(type='date'), '.date_format'),
            (lambda d:d['tasks'][0].update(right_table='orders'), '.right_table'),
            (lambda d:d['tables'][1].update(id='orders'), '.id'),
            (lambda d:d['tasks'][0].update(keys=['missing']), '.keys'),
            (lambda d:d['tasks'][0].update(keys=['amount']), '.keys'),
            (lambda d:d['tasks'][0]['fields'][1].update(left_column='A'), '.left_column'),
            (lambda d:d['tasks'][0]['fields'][1].update(id='order'), '.id'),
            (lambda d:d['tasks'][0]['fields'][1].update(left_column='Z'), '.left_column'),
            (lambda d:d['tables'][0].update(header_row=True), '.header_row'),
            (lambda d:d['tables'][0].update(data_range='F2:A9'), '.data_range'),
            (lambda d:d['tables'][0].update(data_range='A2:XFE3'), '.data_range'),
            (lambda d:d['tables'][0].update(data_range='A1:F9'), '.header_row'),
            (lambda d:d['tables'][0]['exclusions'][0].update(rows=[10]), '.exclusions'),
            (lambda d:d['tables'][0].update(source_id='absent'), '.source_id'),
            (lambda d:d['tables'][0].update(sheet=None), '.sheet'),
            (lambda d:d['sources'][0].update(path='https://example.test/private.xlsx'), '.path'),
            (lambda d:d['tasks'][0]['fields'][-1]['context']['currency']['left'].update(literal='CNY'), '.context'),
            (lambda d:d['tasks'][0].update(fields=None), '.fields'),
            (lambda d:d.update(tasks={}), '.tasks'),
            (lambda d:d['sources'][0].update(format='xls'), '.format'),
        ]
        for edit, path in edits:
            with self.subTest(path=path): self.assert_invalid(edit,path)

    def test_load_rejects_duplicate_json_keys_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'rules.json'
            for content in ('{"schema_version":"1.0","schema_version":"1.0"}', '{"tasks":NaN}', '[]', '{broken'):
                with self.subTest(content=content):
                    p.write_text(content)
                    with self.assertRaises(RuleError): load_rules(p)

    def test_all_excluded_and_oversized_range_rejected(self):
        self.assert_invalid(lambda d:d['tables'][0].update(exclusions=[{'rows':list(range(2,10)),'reason':'all'}]),'.exclusions')
        self.assert_invalid(lambda d:d['tables'][0].update(data_range='A2:F50002'),'.data_range')

    def test_csv_sheet_encoding_and_conditionals(self):
        d=sample('inventory'); d['tables'][0]['sheet']='Sheet1'
        self.assertTrue(validate_rules(RuleSet.from_dict(d,ROOT/'rules.json')))
        d=sample('inventory'); d['sources'][0]['encoding']='nonexistent-encoding'
        self.assertTrue(validate_rules(RuleSet.from_dict(d,ROOT/'rules.json')))
        for value in (True,1,None,[],{},''):
            d=sample(); d['tasks'][0]['fields'][-1]['tolerance']=value
            self.assertTrue(validate_rules(RuleSet.from_dict(d,ROOT/'rules.json')))

    def test_rules_are_copied_from_callers_payload(self):
        d=sample(); r=RuleSet.from_dict(d,ROOT/'rules.json')
        d['sources'][0]['path']='changed'
        self.assertEqual(r.sources[0]['path'],'inputs.xlsx')


if __name__=='__main__': unittest.main()
