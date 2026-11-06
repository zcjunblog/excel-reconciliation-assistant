# 跨行业合成规则案例

仅用于理解字段映射和离线烟测，不是用户业务文件，不包含人工expected答案。原始案例与项目验收源文件字节一致。

| 场景 | 规则 | 关注点 |
| --- | --- | --- |
| 商贸交付 | [commerce/rules.json](examples/commerce/rules.json) | 同工作簿两表、订单+行号复合键、左右列位置不同、金额容差与币种。 |
| 库存盘点 | [inventory/rules.json](examples/inventory/rules.json) | 两份CSV、SKU+仓位、数值文本、单位依据。 |
| 培训签到 | [training/rules.json](examples/training/rules.json) | 不以同名当对应、编号和日期的明确规则。 |
| 行政资产 | [administration/rules.json](examples/administration/rules.json) | 一张基准表分别对照领用/修订表，多任务覆盖与公式策略。 |

离线测试时，规则路径选本目录对应案例；授权规则引用的**演示原始文件**；输出放工作区的新目录。演示故意包含差异和待确认数据，退出2符合设计，不能为了得到退出0而改规则/原表。

业务应用时从用户真实资料确定列、表头、范围和含义。可以复用结构，不能直接复制样例币种、键或日期格式当作用户已确认规则。
