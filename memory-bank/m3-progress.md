# SDD ledger — plan: memory-bank/implementation-plan.md

范围：用户已授权“继续M3”，仅M3.1和M3.2；M4输出和M5技能分发不提前执行。基线4cbd7a3，分支feat/m3-comparison。

- 基线：工作树干净，M2全部41个测试通过。
- Pre-flight: M3.1消费M2 TableData/RowData/CellValue与TaskRule，产生AssociationResult；M3.2使用相同字段与原始CellRef，不能重新读取未授权路径或按行位置配对。
- Pre-flight: checks必须核验输入行分区、每对每字段唯一结果与摘要，不能仅检查摘要相加等于自己。关联时冻结原始行号/规则快照，防止分类遗漏被自身统计掩盖。
- Ruling: 沿用M2已采用的新分支工作方式，不重试此前无响应的原生worktree接口；main保持在阶段验收前不变。成本是同目录隔离较弱。原计划Task标题解析不兼容的记账方式也沿用M2，成本是阶段账本需人工维护。
- M3.1 RED: test_matching因matching模块不存在失败；实现后四组分区、左右重复、一对多、空/公式/数值型键、显式规范化碰撞与复合键分隔符测试通过。
- Task M3.1: complete — M2+M3.1全部51个测试通过；typed tuple键分组、确定排序与来源定位保留。normalization独立模块供关联/比较共用，M5打包需一并包含。
- Ruling: M3数值计算最多1000有效数字、调整指数绝对值1000；越界原值保留，字段标numeric_out_of_range，不截断、不舍入。原因是有限Decimal仍可能用短指数触发巨大展开；成本是极端科学数值不能直接比较，需专门扩展而非冒充一致。
- Ruling: 数值型Excel日期保留原词法，1900虚构闰日标excel_phantom_date；库只保留毫秒、源词法带更细精度时标date_precision_unverified。成本是部分高精度时间需确认，不能用库已舍入值隐藏差异。
- M3.2 RED: compare与coverage测试因compare模块缺失失败；实现Decimal、日期/时区/公式策略、分段汇总和独立覆盖检查后，全套68个测试通过，5个任务与人工异常列表/字段计数完全一致。
- Final review: 一次独立只读审查发现8项Important、2项Minor。来源身份混入一项Minor按影响升级Important：错误回查位置影响追溯可信性；另一项真实文件重排专项测试保留Minor延期。M4未实现部分不在本轮验收范围，不能当作已验证。
- Ruling: 为解决原生ISO日期被库丢失时区/微秒的问题，M2只读传递最小增加可选date_lexeme，M3按源词法解释；旧构造保持默认None。成本是M4展示必须采用源词法，分发需包含更新后的读取模块；不继续信任已损失精度的raw值。
- Final: fixed 原生ISO日期时区/微秒 — test_native_iso_xlsx_keeps_timezone_and_microseconds RED→GREEN，真实临时XLSX夹具。
- Final: fixed 非法偏移/重复日期格式 — test_invalid_offset_and_repeated_date_directives_are_uncomparable RED→GREEN。
- Final: fixed 内部公式误认外部工作簿 — test_internal_cached_formulas_are_not_external_workbook_links RED→GREEN；补带引号/横线表名真实外部引用仍拒绝的回归。
- Final: fixed 空表/全排除成功 — test_empty_or_fully_excluded_input_never_completes RED→GREEN。
- Final: fixed 汇总后超时仍返回 — test_deadline_checked_after_coverage_before_return RED→GREEN。
- Final: fixed 明细delta与总额不一致未发现 — test_numeric_detail_delta_must_agree_with_normalized_values RED→GREEN。
- Final: fixed 宿主Decimal指数/trap泄漏 — test_decimal_task_ignores_host_exponent_and_traps RED→GREEN。
- Final: fixed 1904第一天丢日期 — test_1904_first_day_is_recovered_from_trustworthy_epoch_and_serial RED→GREEN。
- Final: fixed 混入错误来源/工作表 — test_mixed_source_or_sheet_identity_in_table_rejected RED→GREEN。
- Final: minor resolved in M3 acceptance: 真实源文件重排行列、更新映射并重新登记属于原M3计划验收，收尾时补齐；验证旧快照失效、新业务值一致且源坐标更新。现有生产代码无需修改，不扩展功能范围。
- Task M3.2: complete — 全套77个测试、四组5任务人工答案及20万字段合成验证通过；第二任务累计预算被拒绝，M1所有14份摘要不变；Python3.9.6 -S CSV完整关联/比较烟测通过。
- Final acceptance: 补原计划真实文件重排专项回归后，全套78个测试通过；最终证据重跑并更新代码摘要，M3无延期验收项。
