# SDD ledger — plan: memory-bank/implementation-plan.md

范围：用户已授权“继续M3”，仅M3.1和M3.2；M4输出和M5技能分发不提前执行。基线4cbd7a3，分支feat/m3-comparison。

- 基线：工作树干净，M2全部41个测试通过。
- Pre-flight: M3.1消费M2 TableData/RowData/CellValue与TaskRule，产生AssociationResult；M3.2使用相同字段与原始CellRef，不能重新读取未授权路径或按行位置配对。
- Pre-flight: checks必须核验输入行分区、每对每字段唯一结果与摘要，不能仅检查摘要相加等于自己。关联时冻结原始行号/规则快照，防止分类遗漏被自身统计掩盖。
- Ruling: 沿用M2已采用的新分支工作方式，不重试此前无响应的原生worktree接口；main保持在阶段验收前不变。成本是同目录隔离较弱。原计划Task标题解析不兼容的记账方式也沿用M2，成本是阶段账本需人工维护。
- M3.1 RED: test_matching因matching模块不存在失败；实现后四组分区、左右重复、一对多、空/公式/数值型键、显式规范化碰撞与复合键分隔符测试通过。
- Task M3.1: complete — M2+M3.1全部51个测试通过；typed tuple键分组、确定排序与来源定位保留。normalization独立模块供关联/比较共用，M5打包需一并包含。
