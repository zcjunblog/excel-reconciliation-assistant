import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from fixture_helpers import ROOT, csv_case, workbook_case, write_rules, authorize, sheet_xml, update_sheet, workbook_epoch
from common import Budget
from rules import load_rules
from intake import inspect_sources, read_tables


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name).resolve()

    def run_case(self,path,budget=None):
        rules=load_rules(path); budget=budget or Budget()
        intake=inspect_sources(rules,authorize(rules),budget)
        return rules,intake,read_tables(intake,rules,budget)

    def codes(self,intake): return {i.code for i in intake.issues}

    def test_four_case_headers_and_source_coordinates(self):
        for case in ('commerce','inventory','training','administration'):
            with self.subTest(case=case):
                directory=ROOT/'examples'/case
                expected=json.loads((directory/'expected.json').read_text())
                rules,intake,tables=self.run_case(directory/'rules.json')
                self.assertEqual(intake.status,'ready',intake.issues)
                self.assertEqual(set(tables),{t['id'] for t in rules.tables})
                for check in expected['cell_checks']:
                    col=''.join(c for c in check['cell'] if c.isalpha()); row=int(check['cell'][len(col):])
                    if row in tables[check['table']].excluded_rows: continue
                    record=next(r for r in tables[check['table']].rows if r.row==row)
                    self.assertEqual(record.cells[col].raw,check['value'])
                    self.assertEqual(record.cells[col].ref.column,col)
                for check in expected['formula_checks']:
                    row=int(check['cell'][1:]); value=next(r for r in tables[check['table']].rows if r.row==row).cells['C']
                    self.assertEqual(value.formula,check['formula']); self.assertEqual(value.cached,check['cached'])
                self.assertEqual(set(intake.table_previews),set(tables))
                for snap in intake.source_snapshots.values(): self.assertEqual(snap.sha256,hashlib.sha256(snap.path.read_bytes()).hexdigest())

    def test_hidden_filter_and_explicit_exclusion_are_distinct(self):
        _,_,tables=self.run_case(ROOT/'examples/commerce/rules.json')
        orders=tables['orders']
        self.assertEqual(orders.selected_rows,list(range(2,10)))
        self.assertEqual([r.row for r in orders.rows],list(range(2,9)))
        self.assertEqual(orders.excluded_rows,{9:'显式排除合计行'})
        self.assertEqual(orders.metadata['hidden_rows'],[4])
        self.assertEqual(orders.metadata['auto_filter'],'A1:F8')

    def test_csv_multiline_blank_rows_and_original_text(self):
        path=csv_case(self.dir,'id,value\n"00\n01",1\n\n')
        _,intake,tables=self.run_case(path)
        self.assertEqual(intake.status,'ready')
        self.assertEqual(tables['left'].rows[0].cells['A'].raw,'00\n01')
        self.assertEqual(tables['left'].rows[0].cells['A'].ref.physical_lines,(2,3))
        self.assertEqual(tables['left'].rows[1].cells['A'].ref.physical_lines,(4,4))
        self.assertEqual(tables['left'].rows[1].cells['A'].raw,'')

    def test_csv_utf8_bom_and_explicit_gb18030(self):
        for enc in ('utf-8-sig','gb18030'):
            p=csv_case(self.dir,'id,value\n编号甲,1\n编号乙,2\n',encoding=enc)
            if enc=='utf-8-sig':
                r=load_rules(p).payload
                for s in r['sources']: s.pop('encoding')
                write_rules(self.dir,r)
            _,intake,tables=self.run_case(p)
            self.assertEqual(intake.status,'ready',intake.issues)
            self.assertEqual(tables['left'].rows[0].cells['A'].raw,'编号甲')

    def test_missing_header_duplicate_width_decode_and_empty_block_table(self):
        bad=[('wrong,value\na,1\nb,2\n','header_mismatch'),('id,id\na,1\nb,2\n','duplicate_header'),('id,value\na\nb,2\n','csv_width_mismatch'),('id,value\n"open,1\nb,2\n','invalid_csv'),('id,value\n,\n,\n','empty_table'),('','empty_table')]
        for content,code in bad:
            with self.subTest(code=code):
                p=csv_case(self.dir,left=content,right='id,value\na,1\nb,2\n')
                _,intake,tables=self.run_case(p)
                self.assertEqual(intake.status,'partial',intake.issues)
                self.assertEqual(set(tables),{'right'})
                self.assertIn(code,self.codes(intake))
        p=csv_case(self.dir); (self.dir/'left.csv').write_bytes(b'id,value\n\xff,1\nb,2\n')
        _,intake,tables=self.run_case(p); self.assertIn('invalid_encoding',self.codes(intake)); self.assertNotIn('left',tables)

    def test_missing_sheet_and_merged_ranges_block_only_affected_table(self):
        p=workbook_case(self.dir); d=load_rules(p).payload; d['tables'][0]['sheet']='不存在'; write_rules(self.dir,d)
        _,intake,tables=self.run_case(p)
        self.assertIn('missing_sheet',self.codes(intake)); self.assertEqual(set(tables),{'delivery'})
        for ref in ('A1:B1','C2:C3'):
            p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':lambda b:update_sheet(b,merge=ref)})
            _,intake,tables=self.run_case(p)
            self.assertIn('merged_range',self.codes(intake)); self.assertEqual(set(tables),{'delivery'})

    def test_fake_dimension_is_not_allocated(self):
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':lambda b:update_sheet(b,dimension='A1:XFD1048576')})
        _,intake,tables=self.run_case(p)
        self.assertEqual(intake.status,'ready',intake.issues); self.assertEqual(len(tables['orders'].rows),7)
        self.assertEqual(tables['orders'].metadata['declared_dimension'],'A1:XFD1048576')

    def test_small_range_cannot_bypass_scan_budget(self):
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':lambda b:update_sheet(b,far_row=200001)})
        _,intake,tables=self.run_case(p)
        self.assertEqual(tables,{}); self.assertTrue(intake.global_blocked); self.assertIn('budget_exceeded',self.codes(intake))
        p=csv_case(self.dir,'id,value\na,1\nb,2\nc,3\n')
        _,intake,tables=self.run_case(p,Budget(max_scan_rows=3))
        self.assertTrue(intake.global_blocked); self.assertEqual(tables,{})

    def test_scan_cell_budget_and_large_shared_strings(self):
        p=workbook_case(self.dir)
        _,intake,tables=self.run_case(p,Budget(max_scan_cells=5))
        self.assertTrue(intake.global_blocked); self.assertEqual(tables,{})
        xml=b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>'+b'X'*32001+b'</t></si></sst>'
        p=workbook_case(self.dir,{'xl/sharedStrings.xml':xml})
        _,intake,tables=self.run_case(p)
        self.assertTrue(intake.global_blocked); self.assertEqual(tables,{})

    def test_csv_record_and_cell_limits_are_global(self):
        for content,budget in [('id,value\na,'+'x'*20+'\nb,2\n',Budget(max_record_bytes=15)),('id,value\na,'+'x'*10+'\nb,2\n',Budget(max_text_chars=5))]:
            p=csv_case(self.dir,content)
            _,intake,tables=self.run_case(p,budget)
            self.assertTrue(intake.global_blocked); self.assertEqual(tables,{})

    def test_numeric_xml_lexeme_and_types_are_preserved(self):
        xml=sheet_xml([(1,{'A':'id','B':'value'}),(2,{'A':'0007','B':0.1}),(3,{'A':'0008','B':0})],dimension='A1:B3')
        xml=xml.replace(b'<v>0.1</v>',b'<v>0.10000000000000001</v>')
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':xml,'xl/worksheets/sheet2.xml':xml})
        d=load_rules(p).payload
        for t in d['tables']: t['data_range']='A2:B3'; t['exclusions']=[]
        d['tasks'][0]['keys']=['id']; d['tasks'][0]['fields']=[{'id':'id','left_column':'A','right_column':'A','left_header':'id','right_header':'id','type':'identifier'},{'id':'value','left_column':'B','right_column':'B','left_header':'value','right_header':'value','type':'decimal'}]
        write_rules(self.dir,d)
        _,intake,tables=self.run_case(p)
        self.assertEqual(intake.status,'ready',intake.issues)
        self.assertEqual(tables['orders'].rows[0].cells['A'].raw,'0007')
        self.assertEqual(tables['orders'].rows[0].cells['B'].numeric_lexeme,'0.10000000000000001')
        self.assertEqual(tables['orders'].rows[1].cells['B'].raw,0)
        self.assertEqual(tables['orders'].rows[1].cells['B'].raw_type,'number')

    def test_epoch_metadata_both_date_systems(self):
        for epoch in ('0','1'):
            p=workbook_case(self.dir,{'xl/workbook.xml':lambda b:workbook_epoch(b,epoch)})
            _,intake,tables=self.run_case(p)
            self.assertEqual(intake.status,'ready',intake.issues)
            self.assertEqual(tables['orders'].metadata['date_system'],'1904' if epoch=='1' else '1900')

    def test_changed_rule_or_symlink_target_invalidates_snapshot(self):
        p=csv_case(self.dir); rules=load_rules(p); b=Budget(); intake=inspect_sources(rules,authorize(rules),b)
        rules.tasks[0]['formula_policy']='cached'
        self.assertEqual(read_tables(intake,rules,b),{}); self.assertIn('rules_changed',self.codes(intake))
        p=csv_case(self.dir); (self.dir/'alias.csv').symlink_to(self.dir/'left.csv')
        d=load_rules(p).payload; d['sources'][0]['path']='alias.csv'; write_rules(self.dir,d)
        rules=load_rules(p); b=Budget(); intake=inspect_sources(rules,authorize(rules),b)
        (self.dir/'alias.csv').unlink(); (self.dir/'alias.csv').symlink_to(self.dir/'right.csv')
        self.assertEqual(read_tables(intake,rules,b),{}); self.assertIn('source_changed',self.codes(intake))

    def test_csv_reads_without_openpyxl_and_xlsx_reports_dependency(self):
        p=csv_case(self.dir)
        with patch.dict(sys.modules,{'openpyxl':None}):
            _,intake,tables=self.run_case(p)
            self.assertEqual(intake.status,'ready'); self.assertEqual(len(tables),2)
            p=workbook_case(self.dir); _,intake,tables=self.run_case(p)
            self.assertEqual(tables,{}); self.assertIn('missing_dependency',self.codes(intake))

    def test_data_range_past_end_and_no_selected_content(self):
        p=csv_case(self.dir,'id,value\na,1\n',right='id,value\na,1\nb,2\n')
        _,intake,tables=self.run_case(p)
        self.assertIn('range_outside_data',self.codes(intake)); self.assertNotIn('left',tables)

    def test_malformed_rule_after_inspection_is_blocked(self):
        p=csv_case(self.dir); rules=load_rules(p); b=Budget(); intake=inspect_sources(rules,authorize(rules),b)
        rules.payload['tables']=None
        self.assertEqual(read_tables(intake,rules,b),{})
        self.assertTrue(intake.global_blocked); self.assertIn('rules_changed',self.codes(intake))

    def test_numeric_lexeme_length_cannot_bypass_cell_limit(self):
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':lambda b:b.replace(b'<ns0:v>2</ns0:v>',b'<ns0:v>'+b'9'*32001+b'</ns0:v>',1)})
        # Verify the synthetic mutation actually introduced the target, independent of XML prefixes.
        import zipfile
        with zipfile.ZipFile(self.dir/'inputs.xlsx') as z:
            if b'9'*32001 not in z.read('xl/worksheets/sheet1.xml'):
                xml=sheet_xml([(1,{'A':'id','B':'value'}),(2,{'A':'a','B':1}),(3,{'A':'b','B':2})],dimension='A1:B3')
                p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':xml.replace(b'<v>1</v>',b'<v>'+b'9'*32001+b'</v>',1)})
        _,intake,tables=self.run_case(p)
        self.assertTrue(intake.global_blocked); self.assertEqual(tables,{})

    def test_array_formula_range_isolated_before_child_values_used(self):
        from xml.etree import ElementTree as ET
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        def array(data):
            root=ET.fromstring(data); cell=next(c for c in root.iter(ns+'c') if c.get('r')=='E2')
            ET.SubElement(cell,ns+'f',{'t':'array','ref':'E2:E3'}).text='SUM(D2:D3)'
            return ET.tostring(root,encoding='utf-8')
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':array})
        _,intake,tables=self.run_case(p)
        self.assertEqual(set(tables),{'delivery'})
        self.assertIn('unsupported_formula',self.codes(intake))

    def test_inline_phonetic_readings_do_not_change_display_text(self):
        from xml.etree import ElementTree as ET
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        def phonetic(data):
            root=ET.fromstring(data); cell=next(c for c in root.iter(ns+'c') if c.get('r')=='A2')
            cell.clear(); cell.set('r','A2'); cell.set('t','inlineStr')
            inline=ET.SubElement(cell,ns+'is')
            ET.SubElement(inline,ns+'t').text='東京'
            ph=ET.SubElement(inline,ns+'rPh',{'sb':'0','eb':'2'}); ET.SubElement(ph,ns+'t').text='とうきょう'
            return ET.tostring(root,encoding='utf-8')
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':phonetic})
        _,intake,tables=self.run_case(p)
        self.assertEqual(intake.status,'ready',intake.issues)
        self.assertEqual(tables['orders'].rows[0].cells['A'].raw,'東京')

    def test_bad_numeric_in_one_sheet_preserves_other_sheet(self):
        from xml.etree import ElementTree as ET
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        def invalid(data):
            root=ET.fromstring(data); cell=next(c for c in root.iter(ns+'c') if c.get('r')=='D2')
            cell.find(ns+'v').text='not-a-number'
            return ET.tostring(root,encoding='utf-8')
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':invalid})
        _,intake,tables=self.run_case(p)
        self.assertEqual(set(tables),{'delivery'})
        self.assertEqual(intake.status,'partial'); self.assertIn('invalid_workbook',self.codes(intake))

    def test_renamed_shared_strings_still_receive_cell_budget(self):
        from xml.etree import ElementTree as ET
        import zipfile
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        with zipfile.ZipFile(ROOT/'examples/commerce/inputs.xlsx') as z:
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
        root.clear(); root.tag=ns+'sst'
        si=ET.SubElement(root,ns+'si'); ET.SubElement(si,ns+'t').text='X'*32001
        def use_shared(data):
            worksheet=ET.fromstring(data); cell=next(c for c in worksheet.iter(ns+'c') if c.get('r')=='A2')
            cell.clear(); cell.set('r','A2'); cell.set('t','s'); ET.SubElement(cell,ns+'v').text='0'
            return ET.tostring(worksheet,encoding='utf-8')
        p=workbook_case(self.dir,{
            'xl/sharedStrings.xml':None,'xl/strings2.xml':ET.tostring(root,encoding='utf-8'),
            '[Content_Types].xml':lambda b:b.replace(b'sharedStrings.xml',b'strings2.xml'),
            'xl/_rels/workbook.xml.rels':lambda b:b.replace(b'sharedStrings.xml',b'strings2.xml'),
            'xl/worksheets/sheet1.xml':use_shared})
        _,intake,tables=self.run_case(p)
        self.assertEqual(tables,{}); self.assertTrue(intake.global_blocked)

    def test_rich_inline_runs_preserve_display_order(self):
        from xml.etree import ElementTree as ET
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        def rich(data):
            root=ET.fromstring(data); cell=next(c for c in root.iter(ns+'c') if c.get('r')=='A2')
            cell.clear(); cell.set('r','A2'); cell.set('t','inlineStr')
            inline=ET.SubElement(cell,ns+'is')
            for text in ('东','京'):
                run=ET.SubElement(inline,ns+'r'); ET.SubElement(run,ns+'t').text=text
            return ET.tostring(root,encoding='utf-8')
        p=workbook_case(self.dir,{'xl/worksheets/sheet1.xml':rich})
        _,_,tables=self.run_case(p); self.assertEqual(tables['orders'].rows[0].cells['A'].raw,'东京')


if __name__=='__main__': unittest.main()
