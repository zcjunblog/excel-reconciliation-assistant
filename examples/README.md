# 合成验收案例

全部人物、编号、数量和金额为本项目虚构测试数据，不含真实客户资料。输入表不包含核对结论；`expected.json`由M1按下述业务事实逐项指定，未调用核对引擎生成。M3应原样作为独立验收答案使用；禁止为了通过实现而自动改写答案。

| 目录 | 输入 | 独立预期重点 |
| --- | --- | --- |
| commerce | 一个XLSX，两张表、不同列序和行序 | 7对7条：唯一关联3对；基准独有1、比较独有2；重复组左右2/1条；各1空键。金额100→100.01在0.01容差边界；50→50.02超出；同一编号USD/CNY不可比。 |
| inventory | 两份CSV，SKU+仓位复合键 | 5对5条：唯一关联4对，各1独有；0007两仓位不能合并，0010和10不能合并；箱/件不可直接减，空数量不等于0。 |
| training | 两份CSV，报名号匹配 | 5对5条：唯一关联3对，各1独有、1空键；同名王宁分别按报名号；显式trim消除姓名空格；01/02/2026不按ISO日期猜测。 |
| administration | 一个XLSX，基准+两张比较表 | 两个独立任务各3对3唯一关联；同一组公式缓存分别按默认pending与显式cached核对。缓存有值/缺失/错误三种情况，缓存有值也不能声称已重算。 |

每个目录含`rules.json`和人工指定`expected.json`。预期答案以原始行号列出所有关联分类和每个非exact字段；其余已匹配字段在`field_counts.exact`中独立核算。`cell_checks`固定关键源坐标与原值，`formula_checks`同时固定公式与缓存。

行政XLSX的公式缓存是受控OOXML测试夹具：构建器先正常导出，再只修改指定公式单元格的缓存，以制造“缺缓存”和“错误缓存”。不运行办公软件重算该输入，否则测试事实会被改变。该定向XML编辑用于库缺少的缓存控制能力，不是生产核对算法。

验证：`python3 tools/verify_m1.py`（开发依赖见`tools/requirements-m1.txt`）。该工具检查协议结构、输入坐标、答案守恒、覆盖完整与哈希，**不执行键关联或业务字段比较**；通过只说明测试材料自洽，不说明Skill已经可用。构建与测量记录见`evidence/m1/`。输入文件哈希固定在`examples/manifest.json`，重建后必须重新审查再更新清单。

## 可下载的真实演示结果

M6使用同一0.1.0生产CLI重新生成[showcase-v1](showcase-v1)。四行业五任务加一份负差额任务，共六任务；每份结果保留Excel、报告、待确认、全量工作资料和实际清单。[逐文件摘要](showcase-v1/showcase-manifest.json)登记全部输出SHA，原始14份冻结文件未改写。

| 演示 | 实际结果 |
| --- | --- |
| 商贸 | [Excel](showcase-v1/commerce/核对结果.xlsx) · [报告](showcase-v1/commerce/核对报告.md) |
| 库存 | [Excel](showcase-v1/inventory/核对结果.xlsx) · [报告](showcase-v1/inventory/核对报告.md) |
| 培训 | [Excel](showcase-v1/training/核对结果.xlsx) · [报告](showcase-v1/training/核对报告.md) |
| 行政 | [Excel](showcase-v1/administration/核对结果.xlsx) · [报告](showcase-v1/administration/核对报告.md) |
| 负差额 | [原表/规则/手工预期](release-cases/negative-delta) · [Excel](showcase-v1/negative-delta/核对结果.xlsx) · [报告](showcase-v1/negative-delta/核对报告.md) |

重新生成使用新目录：`python3 tools/prepare_showcase.py --output <新的目录>`。产物运行ID与时间会不同，业务结果及来源摘要应一致。

本版新增负差额案例的输入、规则和手写预期固定于[资源清单](release-cases/manifest.json)。生成器拒绝链接/越界或摘要变化，并对照实际登记来源SHA。重现不覆盖showcase-v1。
