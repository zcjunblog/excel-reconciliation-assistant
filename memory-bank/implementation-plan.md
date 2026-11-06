# Excel表格核对助手 M2–M4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 用户已授权并完成M2–M4，具体验收与决策见各阶段progress文件。M5尚未开始。

**Goal:** 在不改写来源文件的前提下，按v1规则完成XLSX/CSV核对，生成可追溯、可筛选的实际文件。

**Architecture:** Agent提出并解释规则；独立Python模块依次预检、读取、关联、类型比较、计数和导出。模块只消费协议化数据，不依赖某客户端、模型API或开发机路径。来源失败、歧义、部分完成与完整交付严格区分。

**Tech Stack:** Python3.9+、stdlib csv/decimal/hashlib/zipfile/json/dataclasses、openpyxl3.1.x；JSON Schema作为结构规格，生产语义校验用明确校验器，避免把jsonschema开发依赖强加给宿主。测试采用unittest。

**Spec:** [产品设计](design.md)、[规则协议v1](../docs/rules-protocol.md)、[JSON Schema](../schemas/reconciliation-rules.schema.json)、[工作簿布局](../docs/workbook-layout.md)、[人工预期案例](../examples/README.md)。冲突时v1规则协议优先于M0提案；范围扩展须记录理由。

## Global Constraints

- Python3.9+；不修改宿主全局环境，不预设模型API密钥，不把开发机运行时打入包。
- 原文件只读，来源SHA-256前后相同；输出新版本目录，拒绝覆盖现有目录。
- 不按行序配对，不猜业务键，不去重、不聚合、不换算币种/单位。
- 2–5张逻辑表、1–4任务；单文件20MiB、XLSX解压100MiB/成员50MiB/累计250MiB/10,000成员；全局预算失败中止。
- 单表50,000记录/200列，不同逻辑表累计200,000记录/2,000,000矩形单元格；逐任务累计200,000字段比较。
- 单文件扫描最多200,000行/2,000,000单元格，CSV逻辑记录1MiB，文本32,000字符；时限120秒。
- 明细20,000行分片、累计100,000明细/2,000,000输出单元格/50片/50MiB；不得静默截断。
- 数值比较使用源数值词法和Decimal；公式不重算，默认pending，缓存缺失/错误不能通过。
- 不把库回读、图像渲染或目录安装等同于实际办公软件/客户端验证。

## Review Focus

1. 选中小范围但ZIP/共享字符串/远端单元格巨大：读取前后预算都要执行，由M2.1/M2.2负责。
2. 数值型编号已丢精度，或规范化使不同编号碰撞：隔离而不猜原号，由M3.1负责。
3. 一次运行有成功与失败任务：成功任务可交付，整批必须partial，由M4.2负责。
4. 公式缓存存在但过期未知、外部公式未读：不宣称重新计算，由M3.2负责。
5. 输出量超限及保存中断：不留下被清单误报为完整的半截XLSX，由M4.1/M4.2负责。

## 模块与接口

以下路径以`skills/excel-reconciliation-assistant/scripts/`为基准，M2已实现公共协议、规则和来源读取。intake内部拆分source_guard、csv_reader、xlsx_reader、table_data，公开接口保持不变。测试从该目录导入模块；未来CLI同目录运行，相对资源路径从`__file__`解析。

| 文件 | 职责与公开接口 |
| --- | --- |
| common.py | dataclass协议与错误；`Budget`、`Issue(code, message, source_ref, severity)`；不包含业务比较。 |
| rules.py | `load_rules(path: Path) -> RuleSet`；`validate_rules(rules: RuleSet) -> list[Issue]`。未知选项拒绝，校验类型条件、引用、键与范围语义；不读取业务文件。 |
| intake.py | `inspect_sources(rules: RuleSet, authorized_paths: set[Path], budget: Budget) -> IntakeResult`；`read_tables(intake: IntakeResult, rules: RuleSet, budget: Budget) -> dict[str, TableData]`。登记物理文件哈希和只读快照，失败表不返回伪空数据。 |
| matching.py | `associate(left: TableData, right: TableData, task: TaskRule) -> AssociationResult`。输出匹配对、两侧独有、重复组、无效键及排除引用。 |
| compare.py | `compare_pair(pair: MatchedPair, task: TaskRule) -> list[FieldResult]`；`compare_task(association: AssociationResult, task: TaskRule, budget: Budget) -> TaskResult`。键不计比较字段。 |
| checks.py | `verify_coverage(result: TaskResult) -> list[Issue]`。逐侧行覆盖、重复计数、字段分母与明细去重守恒，不从自己导出的摘要反推“通过”。 |
| export.py | `write_workbook(results: list[TaskResult], rules: RuleSet, staging_dir: Path, budget: Budget) -> ExportRecord`。预估/实时预算，全部来源文本惰性，失败不返回成功路径。 |
| report.py | `write_reports(run: RunResult, staging_dir: Path) -> list[ExportRecord]`；`finalize_delivery(run: RunResult, files: list[ExportRecord], new_dir: Path) -> Path`。实际文件摘要，独占目录、身份校验复制与清单最后发布；不覆盖竞争目录。 |
| reconcile_tool.py | `main(argv: Optional[list[str]] = None) -> int`。inspect输出预检与待确认；run输出结果；退出码0=complete，2=partial/需确认，1=blocked/error，不抛成功文案遮盖错误。 |

公共类型：`CellRef(source_id, table_id, sheet: Optional[str], row:int, column:str, physical_lines:Optional[tuple[int,int]])`；`CellValue(ref, raw, raw_type, numeric_lexeme:Optional[str], number_format:Optional[str], formula:Optional[str], cached, cache_type:Optional[str], date_lexeme:Optional[str]=None)`。M3补充date_lexeme保存原生ISO日期的时区/微秒，旧构造兼容；M4展示原值应采用源词法。原始日期、Decimal内部可用类型，序列化为带类型标签的ISO/十进制字符串，不依赖JSON浮点。

`TableData(id, header:dict[str,str], rows:list[RowData], selected_rows:list[int], excluded_rows:dict[int,str], metadata:dict)`；`RowData(row:int, cells:dict[str,CellValue])`。行号永远原始位置，不因排除/筛选重编号。`RuleSet`含sources/tables/tasks和协议版本；规则字段名完全遵循JSON Schema，不新增输出路径或隐式清洗开关。

`AssociationResult`含task_id、unique_pairs:list[MatchedPair]、left_only/right_only:list[RowData]、duplicate_groups:list[AmbiguousGroup]、left_invalid/right_invalid、两侧selected/excluded信息；`MatchedPair(left:RowData,right:RowData,key:tuple[str,...])`。无效键没有伪造key。`AmbiguousGroup`包含两侧所有成员和规范化键。

M3实际补充：AssociationResult捕获included_rows/selected_rows/excluded_rows与task_rule快照供独立守恒；MatchedPair包含date_systems字典，FieldResult包含上下文context，TaskResult包含互斥row_statuses与分段totals。具体已实现接口以common.py和docs/comparison.md为准，M4不可省略这些覆盖/来源资料。

`FieldResult`含result_id、task_id、key、field_id、left/right:CellValue、normalized_left/right、status、reason、delta:Optional[str]、warnings:list[str]。`TaskResult`含association、field_results、issues、row_counts、field_counts及status；`IntakeResult`含source_snapshots、table_previews、issues、blocked_table_ids；`RunResult`含来源快照、任务结果、问题和complete/partial/blocked状态；`ExportRecord(path, kind, status, sha256, bytes)`仅为实际文件建立成功记录，未生成文件单独登记原因。

## M2.1 规则结构与安全来源登记

Files: 新建common.py、rules.py、intake.py；测试tests/test_rules.py、tests/test_source_limits.py。

- [x] 写失败测试`test_unknown_field_and_negative_tolerance_rejected`：未知选项、identifier容差、日期缺格式、同表两侧、重复ID、无效键引用均返回定位到JSON路径的问题。
- [x] 运行`python3 -m unittest discover -s tests -p 'test_rules.py' -v`，确认因缺实现失败；只创建上述公共类型和规则校验，重跑全绿。
- [x] 写失败测试`test_source_not_authorized_and_changed_hash_blocked`、`test_zip_budget_and_duplicate_members`：未授权真实路径、符号链接越界、ZIP重复名、加密/宏/外部工作簿链接、超20MiB/100MiB/50MiB成员/10,000成员均blocked，来源文件哈希不变。
- [x] 运行对应测试确认失败；实现来源预检和流式实际字节计数，不能只检查中央目录声明值；同物理文件重复登记拒绝。
- [x] 运行`python3 -m unittest discover -s tests -p 'test_*limits.py' -v`及rules测试，全绿后提交`feat: validate reconciliation rules and source budgets`。

## M2.2 表格读取与原位置

Files: 完成intake.py；测试tests/test_intake.py；新增仅测试用畸形文件构建器tests/fixture_helpers.py。

- [x] 写失败测试`test_four_case_headers_and_source_coordinates`：原样读取四组案例；商贸订单selected8/included7/excluded9，隐藏4行仍含；CSV前导零、空串与物理行范围保留；行政6处公式/缓存与expected原值一致。
- [x] 写失败测试`test_missing_sheet_header_merge_and_bad_csv_block_table`：缺表/缺列/重名表头/表头或数据合并、乱码、宽度不齐、空表/全排除均不能返回可核对空表。UTF8/BOM与显式GB18030各有正确读取例。
- [x] 写失败测试`test_small_range_cannot_bypass_scan_budget`、`test_fake_dimension_is_not_allocated`：XFD/百万空行声明不引发矩形分配，远端实际内容、过大共享字符串、超长CSV逻辑记录触发限制。
- [x] 逐个运行确认失败；实现只读双视图读取、XLSX源XML数值词法提取和1900/1904日期元数据、实际扫描计数与范围分离；不打开写入来源。
- [x] 运行`python3 -m unittest discover -s tests -p 'test_intake.py' -v`与M2.1测试；对所有来源前后SHA相等，形成evidence/m2记录并提交`feat: read scoped XLSX and CSV with provenance`。

## M3.1 精确关联与歧义隔离

Files: 新建matching.py，测试tests/test_matching.py。

- [x] 写失败测试`test_commerce_explicit_partition`、`test_inventory_composite_key`：关联分区与人工expected完全一致；交换行序/列序后业务关联不变，原位置按新文件更新。
- [x] 写失败测试`test_duplicate_on_either_side_isolates_both`、`test_normalization_collision_and_numeric_id_invalid`：单侧重复也隔离两侧全部行；trim碰撞、两侧重复、一对多不任意配对；数值ID/长数值ID无效，文本0010与10不同。
- [x] 运行`python3 -m unittest discover -s tests -p 'test_matching.py' -v`确认失败；实现类型元组分组、显式规范化和按原位置输出。
- [x] 同样数据重复运行结果顺序确定，所有来源记录恰有一个关联分类；全套M2/M3.1全绿，提交`feat: associate unique keys and isolate ambiguous groups`。

## M3.2 类型比较与覆盖检查

Files: compare.py、checks.py；测试tests/test_compare.py、tests/test_coverage.py。

- [x] 写失败测试`test_all_four_manual_oracles`：直接读取固定expected，不重生成；逐条异常的源单元格、状态、原因、delta及field_counts相同。商贸exact5/within1/different2/not_comparable1；库存4/0/2/2；培训7/1/0/1；行政默认3/0/0/3、缓存4/0/0/2。
- [x] 写失败测试`test_decimal_null_tolerance_and_context`：0不等于空、nullable两空例外、负数、0.01边界、超边界、数值文本解析显式、币种单位不同delta为null，源XML精度不先丢给float。
- [x] 写失败测试`test_dates_formula_cache_and_timezone`：日期两种epoch、歧义文本拒绝、非零时间不截断；默认公式pending，缺缓存/错误具体原因优先；cached必有新鲜度未验证提示；外部公式不作为可用缓存。
- [x] 写失败测试`test_coverage_detects_missing_or_duplicate_result`：删除一条源行分类或字段结果必须失败；差异行与不可比行允许重叠，不用相加总数；多任务来源和预算不串。
- [x] 运行上述测试确认失败；实现Decimal比较、字段状态与独立守恒检查。运行`python3 -m unittest discover -s tests -v`，记录边界性能与oracle结果后提交`feat: compare typed fields and verify complete coverage`。

## M4.1 工作簿及内部明细

Files: export.py、templates/workbook-style.json；测试tests/test_export.py。

- [x] 写失败测试`test_full_match_index_and_exception_sheets`：商贸3对匹配全部在索引，差异4条且包括within/not_comparable，来源位置完整；零记录类别只在概览标0，不造空明细。
- [x] 写失败测试`test_untrusted_text_stays_inert`：`=...`、`+...`、`-...`、`@...`、制表符、换行、URL及长编号回读保持文本，无公式/活动超链接；内部十进制字符串保留完整精度。
- [x] 写失败测试`test_sharding_and_failed_export_not_registered`：20,001明细变2片且计数不丢，超总预算/单元格/文件大小时XLSX未生成；所有分片导航可定位。
- [x] 确认失败后实现布局规格、单一遍历写入与预估/实时预算。运行export测试和全套测试，随后实际Excel/WPS打开首份结果检查中文/筛选/冻结/编号，证据单列；无法实看则视觉验收保持未完成。
- [x] 特别复核M1渲染器局限：Artifact预览曾把文本01/0007显示为1/7，实际源类型和原值正确；不能仅凭预览认证编号显示，也不能从预览推断公式缓存存在。
- [x] 展示原日期/数值时采用M3保留的date_lexeme/numeric_lexeme与类型；不能只展示库可能已丢时区或精度的raw值。
- [x] 提交`feat: export traceable blue and white reconciliation workbook`。

## M4.2 运行、报告和交付

Files: report.py、reconcile_tool.py；测试tests/test_cli.py、tests/test_delivery.py。

- [x] 写失败测试`test_commerce_end_to_end_readback`：`python3 skills/excel-reconciliation-assistant/scripts/reconcile_tool.py run --rules examples/commerce/rules.json --authorize examples/commerce/inputs.xlsx --output outputs/test-v001`真实生成XLSX/两份MD/工作资料/清单；原件SHA不变，明细与oracle一致。
- [x] 写失败测试`test_partial_task_and_existing_output`：一个任务缺表另一个正常，退出2、整批partial，清单只列实际产物；已存在输出目录拒绝覆盖。来源执行中变化、守恒失败、磁盘写入中断无complete清单。
- [x] 写失败测试`test_inspect_does_not_claim_comparison`：inspect仅输出来源预览/规则问题，缺openpyxl的CSV模式仍能读取CSV，XLSX要求依赖的具体安装提示；不能说未生成的文件已交付。
- [x] 确认失败后实现inspect/run、暂存目录、退出码与报告模板；全套测试绿，独立目录重跑四案例与SHA回读，保存evidence/m4并提交`feat: deliver versioned reconciliation reports through CLI`。

## 计划自检与后续

已核对：规则字段与Schema一致；接口生产者/消费者使用同名类型；四个行业人工oracle不由生产工具重写；五类Review Focus分别落到失败测试；容量未通过部分不能宣称已验证。文件交付CLI属于M4；Skill流程、安装目录/构建器/Logo/正式展示README与客户端行为验证属于M5–M6，届时按当前官方文档另写计划，本计划不预先宣称全客户端可用。

每阶段完成后更新todo/design与GitHub，并告诉用户“已完成什么、当前进度、下一步做什么”。M4证据与决策见evidence/m4及memory-bank/m4-progress.md；下一步M5安装与分发。跨设备/系统办公显示仍保留M6，不提前打勾。
