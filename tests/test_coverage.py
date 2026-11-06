import copy
import unittest
from comparison_helpers import read_case, table, task
from common import Budget
from matching import associate
from compare import compare_task
from checks import verify_coverage


class CoverageTests(unittest.TestCase):
    def commerce(self):
        rules,tables,b=read_case('commerce'); rule=rules.tasks[0]
        return compare_task(associate(tables['orders'],tables['delivery'],rule),rule,b)

    def test_coverage_detects_missing_or_duplicate_result(self):
        original=self.commerce(); self.assertEqual(verify_coverage(original),[])
        for mutation in ('missing_field','duplicate_field','missing_pair','wrong_counts','wrong_ref','missing_only','missing_excluded'):
            result=copy.deepcopy(original)
            if mutation=='missing_field': result.field_results.pop()
            elif mutation=='duplicate_field': result.field_results.append(copy.deepcopy(result.field_results[0]))
            elif mutation=='missing_pair': result.association.unique_pairs.pop()
            elif mutation=='wrong_counts': result.field_counts['exact']+=1
            elif mutation=='wrong_ref': result.field_results[0].task_id='another_task'
            elif mutation=='missing_only': result.association.left_only.clear()
            elif mutation=='missing_excluded': result.association.excluded_rows['left'].clear()
            with self.subTest(mutation=mutation): self.assertTrue(verify_coverage(result))

    def test_difference_and_not_comparable_rows_overlap_but_rollup_does_not(self):
        rules,tables,b=read_case('inventory'); rule=rules.tasks[0]
        result=compare_task(associate(tables['ledger'],tables['count'],rule),rule,b)
        self.assertEqual(result.row_counts['different_pairs'],2)
        self.assertEqual(result.row_counts['not_comparable_pairs'],2)
        self.assertEqual(result.row_counts['row_status_counts'],{'exact':1,'within_rule':0,'different':1,'not_comparable':2})
        self.assertEqual(verify_coverage(result),[])

    def test_segmented_decimal_totals_do_not_mix_currency_or_fields(self):
        rules,tables,b=read_case('commerce'); rule=rules.tasks[0]
        result=compare_task(associate(tables['orders'],tables['delivery'],rule),rule,b)
        amount=[s for s in result.totals if s['field_id']=='amount' and s['comparable_context']]
        self.assertEqual(len(amount),1)
        self.assertEqual(amount[0]['included_pairs'],2)
        self.assertEqual(amount[0]['left_total'],'150')
        self.assertEqual(amount[0]['right_total'],'150.03')
        self.assertEqual(amount[0]['delta_sum'],'0.03')
        self.assertEqual(sum(s['excluded_pairs'] for s in result.totals if s['field_id']=='amount'),1)
        corrupted=copy.deepcopy(result); corrupted.totals[0]['included_pairs']+=1
        self.assertTrue(verify_coverage(corrupted))

    def test_multi_task_results_retain_separate_sources_and_result_ids(self):
        rules,tables,b=read_case('administration'); results=[]
        for rule in rules.tasks: results.append(compare_task(associate(tables[rule['left_table']],tables[rule['right_table']],rule),rule,b))
        ids=[f.result_id for result in results for f in result.field_results]
        self.assertEqual(len(set(ids)),12)
        self.assertEqual({f.right.ref.table_id for f in results[0].field_results},{'handover'})
        self.assertEqual({f.right.ref.table_id for f in results[1].field_results},{'revision'})
        self.assertTrue(all(not verify_coverage(result) for result in results))

    def test_numeric_detail_delta_must_agree_with_normalized_values(self):
        for delta in ('999',None,'NaN'):
            result=self.commerce(); result.field_results[2].delta=delta
            with self.subTest(delta=delta): self.assertTrue(verify_coverage(result))


if __name__=='__main__': unittest.main()
