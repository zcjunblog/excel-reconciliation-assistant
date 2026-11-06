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
