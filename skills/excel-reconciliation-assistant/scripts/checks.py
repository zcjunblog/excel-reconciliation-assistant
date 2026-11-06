"""Independent coverage checks against captured source rows and actual field records."""
from __future__ import annotations
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
from common import Issue
from typed_values import precise_sum, precise_difference

STATUSES=('exact','within_rule','different','not_comparable')


def verify_coverage(result):
    issues=[]; a=result.association; task=a.task_rule
    def fail(code): issues.append(Issue(code,'来源覆盖、明细或摘要不一致',{'task_id':a.task_id},'fatal'))
    pairs={(p.left.row,p.right.row):p for p in a.unique_pairs}
    if len(pairs)!=len(a.unique_pairs): fail('duplicate_pair')
    expected_rows={}
    for side,index in (('left',0),('right',1)):
        included=list(a.included_rows[side]); selected=list(a.selected_rows[side]); excluded=a.excluded_rows[side]
        if not included or not selected: fail('empty_source_range')
        classified=[key[index] for key in pairs]
        classified.extend(r.row for r in getattr(a,side+'_only'))
        classified.extend(r.row for r in getattr(a,side+'_invalid'))
        classified.extend(r.row for group in a.duplicate_groups for r in getattr(group,side))
        if Counter(classified)!=Counter(included) or len(set(included))!=len(included): fail('row_partition_mismatch')
        if set(included)&set(excluded) or Counter(selected)!=Counter(included+list(excluded)): fail('selected_coverage_mismatch')
        expected_rows[side]={'selected':len(selected),'included':len(included),'excluded':len(excluded),'unique_matched':len(pairs),
            'only':len(getattr(a,side+'_only')),'duplicate_ambiguous':sum(len(getattr(g,side)) for g in a.duplicate_groups),'invalid_key':len(getattr(a,side+'_invalid'))}
    fields={f['id']:f for f in task['fields'] if f['id'] not in task['keys']}
    expected={(left,right,fid) for left,right in pairs for fid in fields}
    actual=[]; result_ids=[]; per_pair=defaultdict(list)
    for f in result.field_results:
        key=(f.left.ref.row,f.right.ref.row); fid=f.field_id
        actual.append((*key,fid)); result_ids.append(f.result_id); per_pair[key].append(f)
        if key not in pairs or fid not in fields:
            fail('unexpected_field_result'); continue
        pair=pairs[key]; rule=fields[fid]
        if f.task_id!=a.task_id or f.key!=pair.key or f.status not in STATUSES: fail('field_identity_mismatch')
        if pair.left.cells.get(rule['left_column'])!=f.left or pair.right.cells.get(rule['right_column'])!=f.right: fail('field_source_mismatch')
        if f.status=='not_comparable' and f.delta is not None: fail('invalid_uncomparable_delta')
        if rule['type']=='decimal' and f.status!='not_comparable' and f.normalized_left is not None and f.normalized_right is not None:
            try:
                delta=Decimal(f.delta) if isinstance(f.delta,str) else None
                expected_delta=precise_difference(Decimal(f.normalized_right),Decimal(f.normalized_left))
                if delta is None or not delta.is_finite() or delta!=expected_delta: fail('numeric_delta_mismatch')
            except (InvalidOperation,TypeError,ValueError): fail('numeric_delta_mismatch')
    if Counter(actual)!=Counter(expected): fail('field_coverage_mismatch')
    if len(set(result_ids))!=len(result_ids): fail('duplicate_result_id')
    counts=Counter(f.status for f in result.field_results)
    if result.field_counts!={s:counts[s] for s in STATUSES}: fail('field_counts_mismatch')
    different={key for key,records in per_pair.items() if any(f.status=='different' for f in records)}
    uncertain={key for key,records in per_pair.items() if any(f.status=='not_comparable' for f in records)}
    status_counts=Counter(); row_summaries={}
    for key in pairs:
        statuses=Counter(f.status for f in per_pair[key]); status=next((s for s in reversed(STATUSES) if statuses[s]),'exact')
        status_counts[status]+=1; row_summaries[key]={'left_row':key[0],'right_row':key[1],'status':status,'field_counts':{s:statuses[s] for s in STATUSES}}
    expected_rows.update(unique_pairs=len(pairs),different_pairs=len(different),not_comparable_pairs=len(uncertain),row_status_counts={s:status_counts[s] for s in STATUSES})
    if result.row_counts!=expected_rows: fail('row_counts_mismatch')
    actual_summaries={(r['left_row'],r['right_row']):r for r in result.row_statuses}
    if len(actual_summaries)!=len(result.row_statuses) or actual_summaries!=row_summaries: fail('row_status_mismatch')
    pending=a.duplicate_groups or a.left_invalid or a.right_invalid or uncertain or any(f.warnings for f in result.field_results)
    if result.status!=('needs_confirmation' if pending else 'complete'): fail('task_status_mismatch')
    # Every numeric field result belongs to exactly one segment; contexts never get merged across fields.
    decimal_ids={fid for fid,f in fields.items() if f['type']=='decimal'}
    numeric=defaultdict(list)
    for f in result.field_results:
        if f.field_id in decimal_ids: numeric[(f.field_id,json.dumps(f.context,sort_keys=True,ensure_ascii=False))].append(f)
    segments={}
    for segment in result.totals:
        key=(segment['field_id'],json.dumps(segment['context'],sort_keys=True,ensure_ascii=False))
        if key in segments: fail('duplicate_total_segment')
        segments[key]=segment
    if set(segments)!=set(numeric): fail('total_segment_coverage_mismatch')
    for key,records in numeric.items():
        if key not in segments: continue
        segment=segments[key]; context=records[0].context
        valid=all(isinstance(v['left'],str) and v['left']!='' and v['left']==v['right'] for v in context.values())
        included=[f for f in records if valid and f.status!='not_comparable' and f.normalized_left is not None and f.normalized_right is not None]
        if segment['task_id']!=a.task_id or segment['comparable_context']!=valid or segment['included_pairs']!=len(included) or segment['excluded_pairs']!=len(records)-len(included): fail('total_counts_mismatch')
        try:
            left=precise_sum([Decimal(f.normalized_left) for f in included]); right=precise_sum([Decimal(f.normalized_right) for f in included])
            expected_sums=[format(left,'f') if left is not None else None,format(right,'f') if right is not None else None,format(precise_difference(right,left),'f') if left is not None else None]
            if [segment[k] for k in ('left_total','right_total','delta_sum')]!=expected_sums: fail('total_values_mismatch')
        except (InvalidOperation,TypeError,ValueError): fail('invalid_numeric_result')
    return issues
