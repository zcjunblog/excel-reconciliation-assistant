from datetime import date, datetime, time, timezone, timedelta
from decimal import localcontext, Inexact, Rounded
import copy
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from comparison_helpers import ROOT, read_case, table, task, cell
from fixture_helpers import workbook_case, write_rules, sheet_xml, authorize
from rules import load_rules
from intake import inspect_sources, read_tables
from common import Budget, BudgetExceeded, IntakeError
from matching import associate
from compare import compare_pair, compare_task


class CompareTests(unittest.TestCase):
    def one(self,a,b,kind='text',left_context='CNY',right_context='CNY',policy='pending',**options):
        rule=task(kind,**options); rule['formula_policy']=policy
        pair=associate(table('left',[['k',a,left_context]]),table('right',[['k',b,right_context]]),rule).unique_pairs[0]
        return compare_pair(pair,rule)[0]

    def test_all_four_manual_oracles(self):
        for case in ('commerce','inventory','training','administration'):
            rules,tables,budget=read_case(case)
            oracle=json.loads((ROOT/'examples'/case/'expected.json').read_text(encoding='utf-8'))
            for rule,want in zip(rules.tasks,oracle['tasks']):
                with self.subTest(case=case,task=rule['id']):
                    result=compare_task(associate(tables[rule['left_table']],tables[rule['right_table']],rule),rule,budget)
                    self.assertEqual(result.field_counts,want['field_counts'])
                    actual=[{'left_row':f.left.ref.row,'right_row':f.right.ref.row,'field':f.field_id,'status':f.status,'delta':f.delta,'left_cell':f.left.ref.column+str(f.left.ref.row),'right_cell':f.right.ref.column+str(f.right.ref.row),'reason':f.reason} for f in result.field_results if f.status!='exact']
                    self.assertEqual(actual,want['exceptions'])
                    self.assertEqual(result.row_counts['different_pairs'],want['different_pairs'])
                    self.assertEqual(result.row_counts['not_comparable_pairs'],want['not_comparable_pairs'])
                    warnings={w for f in result.field_results for w in f.warnings}
                    self.assertTrue(set(want.get('required_warnings',[]))<=warnings)

    def test_decimal_null_tolerance_and_context(self):
        for a,b,options,status,delta in [
            ('-5','-4.99',{'tolerance':'0.01'},'within_rule','0.01'),
            ('-5','-4.989',{'tolerance':'0.01'},'different','0.011'),
            ('10.00','10',{},'exact','0.00'),
            (0,None,{},'not_comparable',None),
            (None,None,{},'not_comparable',None),
            (None,None,{'nullable':True},'exact',None),
            (None,0,{'nullable':True},'different',None),
            (True,1,{},'not_comparable',None),
        ]:
            with self.subTest(a=a,b=b):
                result=self.one(a,b,'decimal',parse_numeric_text=True,**options)
                self.assertEqual((result.status,result.delta),(status,delta))
        context={'currency':{'left':{'column':'C'},'right':{'column':'C'}}}
        result=self.one('10','10','decimal',left_context='USD',right_context='CNY',parse_numeric_text=True,context=context)
        self.assertEqual((result.status,result.reason,result.delta),('not_comparable','currency_mismatch',None))
        context={'unit':{'left':{'column':'C'},'right':{'column':'C'}}}
        result=self.one('2','20','decimal',left_context='箱',right_context='件',parse_numeric_text=True,context=context)
        self.assertEqual((result.status,result.reason),('not_comparable','unit_mismatch'))

    def test_decimal_preserves_precision_beyond_default_context(self):
        a='1000000000000000000000000000000.00000000000000000001'
        b='1000000000000000000000000000000.00000000000000000002'
        with localcontext() as ctx:
            ctx.prec=6
            result=self.one(a,b,'decimal',parse_numeric_text=True,tolerance='0')
        self.assertEqual(result.delta,'0.00000000000000000001')
        self.assertEqual(result.status,'different')

    def test_numeric_strings_require_explicit_parsing_and_plain_decimal_syntax(self):
        self.assertEqual(self.one('1','1','decimal').status,'not_comparable')
        for value in ('1,000','¥1','10%','1e3','NaN','Infinity',' 1 ','１２'):
            with self.subTest(value=value): self.assertEqual(self.one(value,value,'decimal',parse_numeric_text=True).status,'not_comparable')
        result=self.one(cell(0.1,lexeme='0.10000000000000001'),cell(0.1,table='right',lexeme='0.1'),'decimal')
        self.assertEqual(result.delta,'-0.00000000000000001')
        self.assertEqual(self.one(cell(0.1),cell(0.1,table='right'),'decimal').reason,'numeric_lexeme_missing')

    def test_extreme_numeric_values_are_visible_not_rounded_or_expanded_unbounded(self):
        for value in ('1'+'0'*1000,'0.'+'0'*1001+'1'):
            result=self.one(value,value,'decimal',parse_numeric_text=True)
            self.assertEqual((result.status,result.reason),('not_comparable','numeric_out_of_range'))

    def test_missing_context_or_formula_context_never_invents_units(self):
        ctx={'unit':{'left':{'column':'C'},'right':{'column':'C'}}}
        for value in ('',None,cell('="件"',column='C',kind='formula',formula='="件"',cached='件',cache_type='string')):
            result=self.one('1','1','decimal',parse_numeric_text=True,context=ctx,left_context=value,right_context='件')
            self.assertEqual(result.status,'not_comparable'); self.assertIsNone(result.delta)

    def test_text_normalization_is_explicit_and_both_blank_is_not_automatic(self):
        self.assertEqual(self.one(' a ','a').status,'different')
        result=self.one(' Ａ ','a',normalize=['trim','nfkc','casefold'])
        self.assertEqual((result.status,result.reason),('within_rule','explicit_normalization'))
        self.assertEqual(self.one(' a ',' a ',normalize=['trim']).status,'exact')
        self.assertEqual(self.one(' ','',normalize=['trim']).status,'not_comparable')
        self.assertEqual(self.one(' ','',normalize=['trim'],nullable=True).status,'exact')
        self.assertEqual(self.one(1,'1').status,'not_comparable')

    def test_dates_formula_cache_and_timezone(self):
        fmt={'left':'%Y-%m-%d','right':'%Y-%m-%d'}
        self.assertEqual(self.one('2026-11-06','2026-11-06','date',date_format=fmt).status,'exact')
        self.assertEqual(self.one('2026-11-06','01/02/2026','date',date_format=fmt).reason,'date_format_mismatch')
        self.assertEqual(self.one(cell(datetime(2026,11,6,12),kind='date'),cell(date(2026,11,6),table='right',kind='date'),'date',date_format=fmt).reason,'date_has_time')
        dformat={'left':'ISO8601','right':'ISO8601'}
        self.assertEqual(self.one('2026-11-06T10:00:00+08:00','2026-11-06T02:00:00+00:00','datetime',date_format=dformat).reason,'timezone_mismatch')
        self.assertEqual(self.one('2026-11-06T10:00:00','2026-11-06T10:00:00+08:00','datetime',date_format=dformat).reason,'timezone_mismatch')
        self.assertEqual(self.one('2026-11-06T10:00:00.000001','2026-11-06T10:00:00.000002','datetime',date_format=dformat).status,'different')
        self.assertEqual(self.one('2026-11-06','2026-11-06','datetime',date_format=dformat).status,'not_comparable')

    def test_formula_priority_cache_freshness_and_zero(self):
        def formula(side,cached,cache_type='number'):
            return cell('=1-1',table=side,kind='formula',formula='=1-1',cached=cached,cache_type=cache_type,lexeme=str(cached) if cache_type=='number' and cached is not None else None)
        self.assertEqual(self.one(formula('left',0),0,'decimal').reason,'formula_requires_confirmation')
        result=self.one(formula('left',0),0,'decimal',policy='cached')
        self.assertEqual(result.status,'exact'); self.assertIn('cache_freshness_unverified',result.warnings)
        result=self.one(formula('left',None,'missing'),formula('right',None,'missing'),'decimal',policy='cached',nullable=True)
        self.assertEqual(result.reason,'formula_cache_missing')
        self.assertEqual(self.one(formula('left','#DIV/0!','error'),0,'decimal').reason,'formula_error')
        for expression in ('=[Book.xlsx]S!A1',"='[Book.xlsx]Sheet-1'!A1"):
            external=cell(expression,kind='formula',formula=expression,cached=1,cache_type='number',lexeme='1')
            self.assertEqual(self.one(external,1,'decimal',policy='cached').reason,'external_formula')

    def test_same_date_across_epochs_and_excel_phantom_leap_day(self):
        rule=task('date',date_format={'left':'ISO8601','right':'ISO8601'})
        left=table('left',[['k',cell(datetime(1904,1,2),kind='date',lexeme='1463')]])
        right=table('right',[['k',cell(datetime(1904,1,2),table='right',kind='date',lexeme='1')]])
        right.metadata['date_system']='1904'
        self.assertEqual(compare_pair(associate(left,right,rule).unique_pairs[0],rule)[0].status,'exact')
        left.rows[0].cells['B']=cell(datetime(1900,2,28),kind='date',lexeme='60')
        right.rows[0].cells['B']=cell(datetime(1900,2,28),table='right',kind='date',lexeme='59')
        right.metadata['date_system']='1900'
        self.assertEqual(compare_pair(associate(left,right,rule).unique_pairs[0],rule)[0].reason,'excel_phantom_date')

    def test_numeric_datetime_submillisecond_precision_is_not_silently_lost(self):
        a=cell(datetime(1900,1,1,12),kind='date',lexeme='1.500000000001')
        b=cell(datetime(1900,1,1,12),table='right',kind='date',lexeme='1.5')
        result=self.one(a,b,'datetime',date_format={'left':'ISO8601','right':'ISO8601'})
        self.assertEqual(result.reason,'date_precision_unverified')

    def test_budget_counts_comparisons_per_task_and_prevents_partial_result(self):
        rule=task('decimal'); association=associate(table('left',[['a',1],['b',2]]),table('right',[['a',1],['b',2]]),rule)
        budget=Budget(max_comparisons=2)
        self.assertEqual(len(compare_task(association,rule,budget).field_results),2)
        with self.assertRaises(BudgetExceeded): compare_task(association,rule,budget)
        with self.assertRaises(BudgetExceeded): compare_task(association,rule,Budget(max_comparisons=1))

    def test_rule_change_after_association_is_rejected(self):
        rule=task('decimal'); association=associate(table('left',[['a',1]]),table('right',[['a',2]]),rule)
        rule['fields'][1]['tolerance']='1'
        with self.assertRaises(IntakeError): compare_task(association,rule,Budget())

    def test_invalid_offset_and_repeated_date_directives_are_uncomparable(self):
        with self.subTest(case='offset'):
            result=self.one('2026-11-06T10:00:00+00:60','2026-11-06T10:00:00+01:00','datetime',date_format={'left':'ISO8601','right':'ISO8601'})
            self.assertEqual(result.status,'not_comparable')
        with self.subTest(case='format'):
            result=self.one('2026-11-06 2026','2026-11-06 2026','date',date_format={'left':'%Y-%m-%d %Y','right':'%Y-%m-%d %Y'})
            self.assertEqual(result.status,'not_comparable')

    def test_internal_cached_formulas_are_not_external_workbook_links(self):
        for expression in ('=SUM(Table[Qty],Sheet1!A1)','=IF(A1="x[demo]","Hello!","OK")'):
            a=cell(expression,kind='formula',formula=expression,cached=1,cache_type='number',lexeme='1')
            self.assertEqual(self.one(a,1,'decimal',policy='cached').status,'exact')

    def test_deadline_checked_after_coverage_before_return(self):
        import checks
        original=checks.verify_coverage
        b=Budget(); rule=task(); association=associate(table('left',[['a','x']]),table('right',[['a','x']]),rule)
        def late(result):
            issues=original(result); b.started-=1000; return issues
        with patch('checks.verify_coverage',side_effect=late):
            with self.assertRaises(BudgetExceeded): compare_task(association,rule,b)

    def test_decimal_task_ignores_host_exponent_and_traps(self):
        rule=task('decimal',parse_numeric_text=True)
        a=associate(table('left',[['a','1']]),table('right',[['a','1000000']]),rule)
        with localcontext() as ctx:
            ctx.prec=2; ctx.Emax=5; ctx.Emin=-5; ctx.traps[Inexact]=True; ctx.traps[Rounded]=True
            result=compare_task(a,rule,Budget())
        self.assertEqual(result.field_results[0].delta,'999999')
        self.assertEqual(result.totals[0]['right_total'],'1000000')

    def test_1904_first_day_is_recovered_from_trustworthy_epoch_and_serial(self):
        for kind,right_value in (('date','1904-01-01'),('datetime','1904-01-01T00:00:00')):
            rule=task(kind,date_format={'left':'ISO8601','right':'ISO8601'})
            left=table('left',[['a',cell(time(),kind='date',lexeme='0')]])
            left.metadata['date_system']='1904'
            right=table('right',[['a',right_value]])
            result=compare_pair(associate(left,right,rule).unique_pairs[0],rule)[0]
            self.assertEqual(result.status,'exact')

    def test_native_iso_xlsx_keeps_timezone_and_microseconds(self):
        from xml.etree import ElementTree as ET
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        for left_iso,right_iso,want_status,want_reason in (
            ('2026-11-06T10:00:00+08:00','2026-11-06T10:00:00Z','not_comparable','timezone_mismatch'),
            ('2026-11-06T10:00:00.123456','2026-11-06T10:00:00.123499','different','value_mismatch')):
            with tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp).resolve()
                def xml(value):
                    root=ET.fromstring(sheet_xml([(1,{'A':'id','B':'value'}),(2,{'A':'a','B':1}),(3,{'A':'b','B':1})],dimension='A1:B3'))
                    for c in root.iter(ns+'c'):
                        if c.get('r') in ('B2','B3'):
                            c.set('t','d'); c.find(ns+'v').text=value
                    return ET.tostring(root,encoding='utf-8')
                p=workbook_case(directory,{'xl/worksheets/sheet1.xml':xml(left_iso),'xl/worksheets/sheet2.xml':xml(right_iso)})
                data=load_rules(p).payload
                for t in data['tables']: t['data_range']='A2:B3'; t['exclusions']=[]
                rule=task('datetime',date_format={'left':'ISO8601','right':'ISO8601'}); rule['left_table']='orders'; rule['right_table']='delivery'; data['tasks']=[rule]
                write_rules(directory,data); rules=load_rules(p); b=Budget()
                intake=inspect_sources(rules,authorize(rules),b); tables=read_tables(intake,rules,b)
                self.assertEqual(intake.status,'ready',intake.issues)
                result=compare_task(associate(tables['orders'],tables['delivery'],rule),rule,b)
                self.assertEqual((result.field_results[0].status,result.field_results[0].reason),(want_status,want_reason))
                self.assertEqual(result.field_results[0].left.date_lexeme,left_iso)


if __name__=='__main__': unittest.main()
