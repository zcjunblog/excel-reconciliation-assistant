"""Shared contracts for deterministic intake; no business matching or comparison."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import copy
import hashlib
import json
import re
import time


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    source_ref: Any = None
    severity: str = 'error'


class RuleError(ValueError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__('; '.join(i.message for i in issues))


class IntakeError(ValueError):
    def __init__(self, code: str, message: str, source_ref: Any = None, fatal: bool = False):
        self.issue = Issue(code, message, source_ref, 'fatal' if fatal else 'error')
        super().__init__(message)


class BudgetExceeded(IntakeError):
    def __init__(self, limit: str):
        super().__init__('budget_exceeded', '超过资源预算：'+limit, {'limit': limit}, fatal=True)


@dataclass
class Budget:
    max_file_bytes: int = 20 * 1024 * 1024
    max_zip_bytes: int = 100 * 1024 * 1024
    max_member_bytes: int = 50 * 1024 * 1024
    max_total_zip_bytes: int = 250 * 1024 * 1024
    max_zip_members: int = 10000
    max_table_rows: int = 50000
    max_table_columns: int = 200
    max_total_rows: int = 200000
    max_total_cells: int = 2000000
    max_scan_rows: int = 200000
    max_scan_cells: int = 2000000
    max_record_bytes: int = 1024 * 1024
    max_text_chars: int = 32000
    max_comparisons: int = 200000
    max_sheet_rows: int = 20000
    max_output_rows: int = 100000
    max_output_cells: int = 2000000
    max_output_sheets: int = 50
    max_output_bytes: int = 50 * 1024 * 1024
    max_artifact_bytes: int = 250 * 1024 * 1024
    max_seconds: float = 120.0
    started: float = field(default_factory=time.monotonic)
    counters: dict[str, int] = field(default_factory=dict)

    def check(self):
        if time.monotonic() - self.started > self.max_seconds:
            raise BudgetExceeded('max_seconds')

    def enforce(self, name: str, value: int):
        self.check()
        if value > getattr(self, name):
            raise BudgetExceeded(name)

    def charge(self, counter: str, amount: int, limit: str):
        value = self.counters.get(counter, 0) + amount
        self.enforce(limit, value)
        self.counters[counter] = value


def column_number(name: str) -> int:
    n = 0
    for c in name:
        n = n * 26 + ord(c) - 64
    return n


def column_name(n: int) -> str:
    result = ''
    while n:
        n, r = divmod(n-1, 26)
        result = chr(65+r) + result
    return result


def parse_range(value: str) -> tuple[int, int, int, int]:
    m = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]*):([A-Z]{1,3})([1-9][0-9]*)', value)
    if not m:
        raise ValueError('数据范围必须为A2:D10形式')
    c1,r1,c2,r2 = m.groups()
    bounds = column_number(c1),int(r1),column_number(c2),int(r2)
    if not (1 <= bounds[0] <= bounds[2] <= 16384 and 1 <= bounds[1] <= bounds[3] <= 1048576):
        raise ValueError('数据范围倒置或超过Excel坐标边界')
    return bounds


@dataclass
class RuleSet:
    path: Path
    payload: Any

    @classmethod
    def from_dict(cls, payload: Any, path: Path) -> RuleSet:
        return cls(Path(path).absolute(), copy.deepcopy(payload))

    @property
    def schema_version(self): return self.payload.get('schema_version')
    @property
    def sources(self): return self.payload.get('sources', [])
    @property
    def tables(self): return self.payload.get('tables', [])
    @property
    def tasks(self): return self.payload.get('tasks', [])

    def fingerprint(self) -> str:
        data = json.dumps(self.payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        return hashlib.sha256((str(self.path)+'\n'+data).encode()).hexdigest()


TaskRule = dict[str, Any]


@dataclass(frozen=True)
class CellRef:
    source_id: str
    table_id: str
    sheet: Optional[str]
    row: int
    column: str
    physical_lines: Optional[tuple[int, int]] = None


@dataclass(frozen=True)
class CellValue:
    ref: CellRef
    raw: Any
    raw_type: str
    numeric_lexeme: Optional[str] = None
    number_format: Optional[str] = None
    formula: Optional[str] = None
    cached: Any = None
    cache_type: Optional[str] = None
    date_lexeme: Optional[str] = None


@dataclass
class RowData:
    row: int
    cells: dict[str, CellValue]


@dataclass
class TableData:
    id: str
    header: dict[str, str]
    rows: list[RowData]
    selected_rows: list[int]
    excluded_rows: dict[int, str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SourceSnapshot:
    id: str
    path: Path
    sha256: str
    bytes: int
    identity: tuple[int, int]
    data: bytes = field(repr=False)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntakeResult:
    source_snapshots: dict[str, SourceSnapshot] = field(default_factory=dict)
    table_previews: dict[str, dict] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    blocked_table_ids: set[str] = field(default_factory=set)
    global_blocked: bool = False
    rules_fingerprint: str = ''
    table_count: int = 0
    registered_table_ids: set[str] = field(default_factory=set)

    @property
    def status(self):
        if self.global_blocked or len(self.blocked_table_ids) == self.table_count:
            return 'blocked'
        return 'partial' if self.blocked_table_ids else 'ready'


@dataclass
class MatchedPair:
    left: RowData
    right: RowData
    key: tuple[str, ...]
    date_systems: dict[str, str] = field(default_factory=dict)


@dataclass
class AmbiguousGroup:
    key: tuple[str, ...]
    left: list[RowData]
    right: list[RowData]


@dataclass
class AssociationResult:
    task_id: str
    left: TableData
    right: TableData
    task_rule: TaskRule
    unique_pairs: list[MatchedPair]
    left_only: list[RowData]
    right_only: list[RowData]
    duplicate_groups: list[AmbiguousGroup]
    left_invalid: list[RowData]
    right_invalid: list[RowData]
    included_rows: dict[str, tuple[int, ...]]
    selected_rows: dict[str, tuple[int, ...]]
    excluded_rows: dict[str, dict[int, str]]
    issues: list[Issue] = field(default_factory=list)


@dataclass
class FieldResult:
    result_id: str
    task_id: str
    key: tuple[str, ...]
    field_id: str
    left: CellValue
    right: CellValue
    normalized_left: Any
    normalized_right: Any
    status: str
    reason: str
    delta: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)


@dataclass
class TaskResult:
    association: AssociationResult
    field_results: list[FieldResult]
    issues: list[Issue]
    row_counts: dict
    field_counts: dict
    status: str
    row_statuses: list[dict] = field(default_factory=list)
    totals: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ExportRecord:
    path: Path
    kind: str
    status: str
    sha256: str
    bytes: int


@dataclass
class RunResult:
    rules: RuleSet
    intake: IntakeResult
    task_results: list[TaskResult]
    task_statuses: list[dict]
    issues: list[Issue]
    status: str
    mode: str = 'run'
    unavailable_formats: list[dict] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    run_id: str = ''
    skill_version: str = ''

    @property
    def source_snapshots(self): return self.intake.source_snapshots
