# SDD ledger — plan: memory-bank/implementation-plan.md

范围：用户授权“继续M4”，执行M4.1导出与M4.2完整交付；M5技能入口/安装包不提前声称完成。基线f6477a9，分支feat/m4-delivery。

- 基线：工作树干净，78个测试通过；原M3真实文件重排专项回归已补齐，不再延期。
- Pre-flight: write_workbook消费已守恒的TaskResult，M4.2运行器负责RuleSet/IntakeResult/RunResult与独立任务失败；完整任务结果不能在来源变化或全局预算失败后交付。
- Pre-flight: 数值/日期展示用numeric_lexeme/date_lexeme，输出来源字符串惰性；内部JSONL保留每个字段和原值，XLSX默认例外字段+全量匹配索引，不截断。
- Ruling: 沿用前两阶段新分支工作方式，避免重试无响应原生worktree；同目录隔离弱于worktree。阶段账本代替不兼容M4.x标题的task-start脚本，阶段提交与测试证据照常保留。
- Ruling: 已授权设计明确采用Python/openpyxl生成跨客户端运行工具；生产导出按该方案实现，不让宿主安装开发机Artifact运行时。表格技能用于回读/预览；代价是样式与安全需本工具自行验证。
- Ruling: CLI新增显式--authorize文件参数（可重复），原计划run示例补齐该参数；规则引用不构成授权，缺少授权不自动扫描。成本是宿主调用需传入已获用户授权的实际文件清单。
- Ruling: 交付目录采用独占创建、逐文件复制回读、交付中标记与清单最后发布，而非可能覆盖竞争目录的rename。失败清理只移除本次创建文件；代价是目录在复制期间可见，使用方必须以有效交付清单为完成依据。
- Ruling: 新增250MiB全交付累计字节预算（含Excel、MD、JSONL和清单），避免Excel降级后内部资料无限输出。该值是拒绝阈值，不是已认证性能容量。
- Ruling: CLI以spawn隔离进程实施硬时限，包含进程启动、读取、计算与交付；模块API仍使用Budget协作检查。代价是CLI有进程启动开销，宿主应调用CLI获得硬时限。
- 实施证据：导出与CLI测试先因模块/入口缺失失败；部分复制与交付期间来源变化、异常写入清理、长文本行高、未关联表的跨文件状态、JSON浮点精度标记均先复现后修复。全套104测试通过（最终审查前），四行业5任务人工答案与真实CLI产物已一致；20,001例外字段分2片（20,000+1）回读不丢失，耗时仅本机记录，不作性能承诺。
- 初轮办公验收：macOS WPS实开商贸交付副本，中文/前导零/颜色正确，横向冻结前4列有效，按“有差异”筛出2条；文本公式未执行。原件与正式交付不在UI中保存。长日期换行行高已补回归，最终样张复查尚待完成。

## 完成与最终审查

- Task M4.1: complete — 首次实现c1500ee，审查修复de183f0；tests/test_export.py与全套116测试通过。20,001例外实际文件分片20,000+1，ID完整唯一；WPS最终商贸副本和文本专项原生截图已保存，UI关闭不保存，交付与副本SHA一致。
- Task M4.2: complete — 首次实现f625323，审查修复de183f0；tests/test_cli.py、test_delivery.py、test_m4_review.py与全套116测试通过；四行业5任务真实CLI/人工答案、实际清单/每文件SHA和14份原始摘要均通过，Python3.9.6 -S CSV降级完整交付通过。完整验证命令：bundled Python3.12 `tools/verify_m4.py`，输出stage=M4、passed=true、unit_tests=116。
- 独立整阶段审查：f6477a9..f625323，104项既有测试在仓库外副本通过；发现2项Critical、7项Important与1项Minor，具体见evidence/m4/README.md。未安排重复审查，以失败回归和最终全套作为修复验证。
- Final: fixed 交付子目录链接/替换越界 — test_publication_refuses_injected_directory_symlink RED→GREEN，suite116/116。
- Final: fixed 计划文件名误当所有权、失败清理删除替换文件或未知空目录 — test_timeout_cleanup_never_owns_merely_planned_paths与test_normal_failure_preserves_foreign_empty_directory_and_replacement RED→GREEN；另以真实复制期间超时验证并发文件保留，suite116/116。
- Final: fixed symlink上级暂存根不一致及交付后摘要异常 — test_symlinked_output_parent_uses_one_physical_staging_root RED→GREEN，suite116/116。
- Final: fixed 非UTF-8 stdout在成功后崩溃 — test_non_utf8_stdout_is_valid_machine_json_after_success RED→GREEN，suite116/116。
- Final: fixed 硬超时泄漏openpyxl工作表临时XML — test_timeout_during_real_xlsx_save_cleans_library_temp_xml在真实保存点RED→GREEN，suite116/116。
- Final: fixed 同表不同规则的人类可读任务歧义 — test_different_rules_for_same_tables_have_distinct_visible_task_names RED→GREEN，suite116/116。
- Final: fixed 无效键重复条目、位置丢失及逐行扫描原因 — test_invalid_key_is_one_located_record_per_source_row RED→GREEN；改为源坐标索引，suite116/116。
- Final: fixed XLSX降级丢失表读取范围元数据 — test_xlsx_downgrade_keeps_per_table_intake_scope_metadata RED→GREEN，suite116/116。
- Final: fixed 导出视图先物化后限额 — test_output_budget_rejects_before_detail_rows_are_materialized RED→GREEN；另复用键/上下文文本，suite116/116。
- Final: regraded 报告在Excel未生成时仍承诺“明细在Excel”由Minor升为Important：影响用户判断实际文件是否缺失，违反实际交付范围原则；test_downgrade_report_does_not_promise_a_missing_excel_file RED→GREEN，suite116/116。没有未修复Minor。
- Final: Ruling: 审查未重新认证M2 ZIP/远端扫描、M3编号/规范化碰撞/公式语义的所有上限 — 沿用既有实现和本轮全套回归，入口仍执行其预算，不把本轮样张当成极限重认证；成本是未测上限组合仍可能有容量问题，保留M6。
- Final: Ruling: 不同设备/系统办公显示、负差额实际办公样张与M5包/真实客户端尚无证据 — M4按本机WPS与真实文件完成，跨设备显示明确保留M6、安装/客户端保留M5，不提前宣称兼容；成本是尚不能保证其他环境相同表现。
- Final: Ruling: 最终行高与WPS视觉由主线程完成，独立审查未作视觉复核 — 以原生截图、实际交互和文件摘要留证，库回读单列；成本是视觉评价不是第二位办公用户的独立判断，M6仍需真实用户复核。

## 最终证据与下一步

- evidence/m4/verification.json：116测试、四案例5任务、20,001分片、代码/测试SHA与M1摘要；原始日志及完整交付在outputs忽略目录。
- evidence/m4/office-qa.json与6张原生UI图：最终商贸交付commerce-v004副本、文本专项样张、筛选与冻结证据；正式交付未在UI改写。
- evidence/m4/python39-no-deps.json：Python3.9.6 -S实际CSV核对/MD/JSON输出，partial/退出2，Excel缺依赖实际未生成。
- 已更新design/todo/Agent/README与运行、布局、预算说明。下一步M5标准SKILL.md、通用/WorkBuddy分发包、独立解压烟测和可用客户端实跑；本轮不提审、不公开仓库、不发布市场。
