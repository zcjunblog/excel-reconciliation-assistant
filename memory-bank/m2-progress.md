# SDD ledger — plan: memory-bank/implementation-plan.md

范围：本轮仅M2.1与M2.2，用户已授权“进入M2”。M3–M4保留未执行。起点d4b83e8，分支feat/m2-intake。

- 基线：M1材料检查153项通过，工作树初始干净。
- Pre-flight: M2.1生产RuleSet/Issue/Budget与IntakeResult，M2.2消费同一结构；来源快照须保留只读字节，不能在两阶段之间按未经校验路径重新读取。
- Pre-flight: read_tables返回成功TableData字典，失败信息写回同一IntakeResult；全局超限/来源变化清空全部可用表，单表结构失败只阻断相关表，后续M4据此生成partial。
- Ruling: 原生create_worktree接口长时间无返回，终止等待后git worktree list确认没有创建任何隔离工作区；在干净原检出切换feat/m2-intake继续，避免重复创建请求与开发阻塞。成本是同一目录隔离较弱，main在阶段整合前保持不变。
- Ruling: 既有计划使用M2.1/M2.2标题，不符合task-start脚本的Task N解析格式；用本账本和原计划逐步记录，不改写任务内容。后续阶段仍保持独立提交。
- Ruling: 来源字节检查拆到source_guard.py，由intake协调，避免将授权/ZIP扫描与具体表格解析混在一个大文件；共同使用SourceSnapshot与Budget。只增加内部模块，不改变公开接口，成本是多一个打包资源文件须在M5验证。
- M2.1 RED: 规则测试因rules模块缺失失败；来源测试因intake模块缺失失败。
- M2.1 GREEN: 规则6个测试、来源11个测试共17个通过（含多组参数负例）。授权清单使用明确的规范化物理路径，符号链接别名不自动授权目标；macOS临时目录/var与/private/var别名差异已在测试夹具中显式resolve，不放宽授权规则。
- Task M2.1: complete — RuleSet/Issue/Budget、严格JSON结构及语义、来源只读快照/SHA、ZIP实际解压计数、授权/重复物理来源/特殊文件隔离均完成。verify_sources_unchanged供M2.2在读取前后复用；M2.2尚未完成。
- M2.2 RED: 新读取测试因read_tables不存在失败；接入后四组来源、编码、坐标、公式缓存、伪维度与实际扫描等测试通过。
- Ruling: 数组/dataTable等非普通或共享公式区域在选区内时阻断相关表，不返回未证实的子单元格常量。原因是M2尚不能可靠表达其区域来源；成本是这类表暂不能直接继续核对，需要另行整理或后续扩展，不能宣称已支持该类公式。
- M2.2 RED→GREEN: 对登记后规则畸变、过长数值词法、非文本codec和数组区域补回归；非文本codec识别须用非空字符串encode，空字节decode会短路而漏检。
- Final review: 独立只读审查报告6项Important、0项已证实Critical、无Minor；审查未覆盖最大容量、真实客户端或M3业务语义。
- Final: fixed 非文本codec — test_non_text_codec_rejected RED→GREEN。
- Final: fixed 内联注音串入显示值 — test_inline_phonetic_readings_do_not_change_display_text RED→GREEN；普通富文本分段显示同测通过。
- Final: fixed 数组对象/子区域缓存误当原值 — test_array_formula_range_isolated_before_child_values_used RED→GREEN；采取前述明确阻断策略，未宣称已支持。
- Final: fixed 单工作表损坏吞掉其他表 — test_bad_numeric_in_one_sheet_preserves_other_sheet RED→GREEN，保留delivery并标partial。
- Final: fixed 非标准位置SST绕过字符限制 — test_renamed_shared_strings_still_receive_cell_budget RED→GREEN，按包内容类型发现实际资源；工作表按关系/实际成员扫描。
- Final: fixed 损坏DEFLATE流抛未捕获异常 — test_corrupt_deflate_stream_becomes_source_issue RED→GREEN，转invalid_zip并保留独立CSV来源。
- Task M2.2: complete — 全套41个测试通过，四组原输入与所有M1摘要不变；生产读取器处理两份50,000行×2列CSV，Python3.9.6 -S标准库CSV烟测通过。CSV窄表时长/内存不等于宽表、匹配比较或导出容量。
- 未验证：M3关联/比较、M4导出/办公软件、最大宽表/全链路性能、客户端调用。时限为协作检查，不将库调用期间的硬中断称为已实现。
