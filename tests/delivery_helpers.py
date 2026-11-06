from comparison_helpers import read_case
from matching import associate
from compare import compare_task
from common import RuleSet
from pathlib import Path


def results_for(name='commerce'):
    rules,tables,budget=read_case(name)
    return rules,[compare_task(associate(tables[t['left_table']],tables[t['right_table']],t),t,budget) for t in rules.tasks]


def synthetic_rules(result):
    a=result.association
    return RuleSet.from_dict({'schema_version':'1.0','sources':[{'id':s,'path':s+'.csv','format':'csv'} for s in ('left','right')],
        'tables':[{'id':s,'source_id':s,'sheet':None,'header_row':1,'data_range':f'A2:C{max(a.selected_rows[s])}','exclusions':[]} for s in ('left','right')],
        'tasks':[a.task_rule]},Path('synthetic-rules.json'))
