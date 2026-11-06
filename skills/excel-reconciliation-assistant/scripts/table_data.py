"""Internal reader grid and conversion into scoped, traceable table records."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from common import CellRef, CellValue, IntakeError, RowData, TableData, column_name, parse_range


@dataclass
class RawCell:
    raw: Any = None
    raw_type: str = 'missing'
    numeric_lexeme: Optional[str] = None
    number_format: Optional[str] = None
    formula: Optional[str] = None
    cached: Any = None
    cache_type: Optional[str] = None
    physical_lines: Optional[tuple[int,int]] = None


@dataclass
class Grid:
    cells: dict[tuple[int,int], RawCell]
    max_row: int
    max_column: int
    metadata: dict = field(default_factory=dict)


def wanted(row, column, tables):
    for t in tables:
        c1,r1,c2,r2=parse_range(t['data_range'])
        if c1<=column<=c2 and (row==t['header_row'] or r1<=row<=r2): return True
    return False


def build_table(table, grid, source_id, expected_headers):
    tid=table['id']; ref={'source_id':source_id,'table_id':tid}
    c1,r1,c2,r2=parse_range(table['data_range'])
    if grid.max_row==0: raise IntakeError('empty_table','来源中没有数据记录',ref)
    if r2>grid.max_row or c2>grid.max_column:
        raise IntakeError('range_outside_data','选择范围超出实际数据范围',ref)
    for formula_range in grid.metadata.get('unsupported_formula_ranges',[]):
        fc1,fr1,fc2,fr2=parse_range(formula_range if ':' in formula_range else formula_range+':'+formula_range)
        if fc1<=c2 and fc2>=c1 and (fr1<=r2 and fr2>=r1 or fr1<=table['header_row']<=fr2):
            raise IntakeError('unsupported_formula','选中范围包含数组、数据表或尚未支持的公式区域，不能将子单元格视为独立原值',dict(ref,formula_range=formula_range))
    for merged in grid.metadata.get('merged_ranges',[]):
        mc1,mr1,mc2,mr2=parse_range(merged if ':' in merged else merged+':'+merged)
        if mc1<=c2 and mc2>=c1 and (mr1<=r2 and mr2>=r1 or mr1<=table['header_row']<=mr2):
            raise IntakeError('merged_range','表头或数据范围与合并单元格相交，请明确整理数据',ref)
    header={column_name(c):grid.cells.get((table['header_row'],c),RawCell()).raw for c in range(c1,c2+1)}
    if any(not isinstance(v,str) or not v for v in header.values()):
        raise IntakeError('missing_header','表头有缺失或非文本字段',ref)
    if len(set(header.values()))!=len(header): raise IntakeError('duplicate_header','选择范围包含重复表头',ref)
    for column,value in expected_headers.items():
        if header.get(column)!=value:
            raise IntakeError('header_mismatch','实际表头与规则不一致',dict(ref,column=column,expected=value,actual=header.get(column)))
    excluded={r:e['reason'] for e in table['exclusions'] for r in e['rows']}
    rows=[]; has_content=False
    for row in range(r1,r2+1):
        if row in excluded: continue
        cells={}
        for col in range(c1,c2+1):
            value=grid.cells.get((row,col),RawCell())
            address=CellRef(source_id,tid,table['sheet'],row,column_name(col),value.physical_lines)
            cells[address.column]=CellValue(address,value.raw,value.raw_type,value.numeric_lexeme,value.number_format,value.formula,value.cached,value.cache_type)
            if value.raw is not None and value.raw!='': has_content=True
        rows.append(RowData(row,cells))
    if not rows or not has_content: raise IntakeError('empty_table','纳入范围没有可读取的数据内容',ref)
    metadata=dict(grid.metadata)
    metadata['hidden_rows']=[r for r in metadata.get('hidden_rows',[]) if r1<=r<=r2]
    metadata['hidden_columns']=[column_name(c) for lo,hi in metadata.get('hidden_column_ranges',[]) for c in range(max(lo,c1),min(hi,c2)+1)]
    metadata['range']=table['data_range']; metadata['selected_count']=r2-r1+1; metadata['included_count']=len(rows)
    return TableData(tid,header,rows,list(range(r1,r2+1)),excluded,metadata)
