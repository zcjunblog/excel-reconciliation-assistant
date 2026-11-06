import copy
import json
import unittest
from dataclasses import replace
from comparison_helpers import ROOT, read_case, table, task, cell
from common import IntakeError
from matching import associate


class MatchingTests(unittest.TestCase):
    def assert_partition(self,name):
        rules,tables,_=read_case(name)
        oracle=json.loads((ROOT/'examples'/name/'expected.json').read_text(encoding='utf-8'))
        for rule,expected in zip(rules.tasks,oracle['tasks']):
            result=associate(tables[rule['left_table']],tables[rule['right_table']],rule)
            self.assertEqual([[p.left.row,p.right.row] for p in result.unique_pairs],expected['matched_pairs'])
            for side in ('left','right'):
                self.assertEqual([r.row for r in getattr(result,side+'_only')],expected['only_rows'][side])
                self.assertEqual([r.row for r in getattr(result,side+'_invalid')],expected['invalid_rows'][side])
                self.assertEqual(sorted(r.row for g in result.duplicate_groups for r in getattr(g,side)),expected['duplicate_rows'][side])

    def test_commerce_explicit_partition(self): self.assert_partition('commerce')
    def test_inventory_composite_key(self): self.assert_partition('inventory')
    def test_training_and_administration_partition(self):
        self.assert_partition('training'); self.assert_partition('administration')

    def test_duplicate_on_either_side_isolates_both(self):
        for left,right,want in [([['a',1],['a',2]],[['a',3]],(2,1)),([['a',1]],[['a',2],['a',3]],(1,2)),([['a',1],['a',2]],[['a',3],['a',4]],(2,2)),([['a',1],['a',2]],[['b',3]],(2,0))]:
            with self.subTest(want=want):
                result=associate(table('left',left),table('right',right),task())
                self.assertEqual(result.unique_pairs,[])
                self.assertEqual((len(result.duplicate_groups[0].left),len(result.duplicate_groups[0].right)),want)

    def test_normalization_collision_and_numeric_id_invalid(self):
        rule=task(); rule['fields'][0]['normalize']=['trim','nfkc','casefold']
        left=table('left',[[' A ',1],['ａ',2],[None,3],[10000000000000001,4]])
        right=table('right',[['a',9],['10000000000000001',4]])
        result=associate(left,right,rule)
        self.assertEqual(len(result.duplicate_groups),1)
        self.assertEqual([r.row for r in result.left_invalid],[4,5])
        self.assertIn('numeric_identifier_precision_risk',{i.code for i in result.issues})
        self.assertEqual([r.row for r in result.right_only],[3])

    def test_leading_zero_case_punctuation_and_spaces_preserved_by_default(self):
        left=table('left',[['0010',1],['a-b',2],[' A ',3],['a',4]])
        right=table('right',[['10',1],['ab',2],['A',3],['a',4]])
        result=associate(left,right,task())
        self.assertEqual([(p.left.row,p.right.row) for p in result.unique_pairs],[(5,5)])
        self.assertEqual([r.row for r in result.left_only],[2,3,4])

    def test_formula_and_empty_normalized_keys_never_match(self):
        rule=task(); rule['fields'][0]['normalize']=['trim']; rule['formula_policy']='cached'
        left=table('left',[[cell('=1',column='A',kind='formula',formula='=1',cached='a',cache_type='string'),1],[' ',2],[False,3]])
        right=table('right',[['a',1],[' ',2],[False,3]])
        result=associate(left,right,rule)
        self.assertEqual(result.unique_pairs,[]); self.assertEqual(len(result.left_invalid),3)
        self.assertEqual(len(result.right_invalid),2)

    def test_composite_keys_are_tuples_not_joined_strings(self):
        rule=task(); rule['keys']=['id','value']
        rule['fields'].append({'id':'other','left_column':'C','right_column':'C','left_header':'context','right_header':'context','type':'text'})
        left=table('left',[['a|b','c','x'],['a','b|c','y']]); right=table('right',[['a','b|c','y'],['a|b','c','x']])
        result=associate(left,right,rule)
        self.assertEqual([(p.left.row,p.right.row) for p in result.unique_pairs],[(2,3),(3,2)])

    def test_row_order_does_not_drive_matching_and_output_is_deterministic(self):
        left=table('left',[['a',1],['b',2]]); right=table('right',[['b',2],['a',1]])
        first=associate(left,right,task())
        left.rows.reverse(); right.rows.reverse()
        second=associate(left,right,task())
        self.assertEqual([(p.key,p.left.row,p.right.row) for p in first.unique_pairs],[(p.key,p.left.row,p.right.row) for p in second.unique_pairs])

    def test_wrong_tables_and_missing_key_mapping_block(self):
        rule=task()
        with self.assertRaises(IntakeError): associate(table('right',[['a',1]]),table('left',[['a',1]]),rule)
        rule['keys']=['absent']
        with self.assertRaises(IntakeError): associate(table('left',[['a',1]]),table('right',[['a',1]]),rule)

    def test_empty_or_fully_excluded_input_never_completes(self):
        empty=table('left',[])
        with self.assertRaises(IntakeError): associate(empty,table('right',[['a',1]]),task())
        empty.selected_rows=[2]; empty.excluded_rows={2:'排除全部'}
        with self.assertRaises(IntakeError): associate(empty,table('right',[['a',1]]),task())

    def test_mixed_source_or_sheet_identity_in_table_rejected(self):
        for changed in ({'source_id':'another_source'},{'sheet':'another_sheet'}):
            left=table('left',[['a',1]])
            value=left.rows[0].cells['B']; left.rows[0].cells['B']=replace(value,ref=replace(value.ref,**changed))
            with self.assertRaises(IntakeError): associate(left,table('right',[['a',1]]),task())


if __name__=='__main__': unittest.main()
