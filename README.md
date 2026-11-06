<h1 align="center">Excel表格核对助手</h1>
<p align="center"><strong>让每一处表格差异，都能定位、解释和复核。</strong></p>
<p align="center">Excel Reconciliation Assistant<br>面向各行业与多种Agent客户端的表格核对Skill</p>

将用户提供的业务表格按明确的字段与匹配规则进行核对，整理缺失记录、重复编号和字段差异，形成便于筛选的结果工作簿与可追溯报告。

**M2来源读取与规则预检已完成，正在为关联与比较引擎准备下一阶段。尚无可安装Skill、完整核对交付工具或已验证的客户端兼容列表。** 以下业务能力仍为首版设计方向。

## 计划解决的问题

| 常见任务 | 拟提供的结果 |
| --- | --- |
| 订单与发货记录不一致 | 按业务编号关联记录，列出缺失、重复与数量差异 |
| 两份名册或台账对不上 | 核对对应字段，定位仅在某一侧出现的记录 |
| 同一份资料存在多个版本 | 保留旧值、新值与来源位置，输出变化明细 |
| 金额、日期或编号格式不同 | 按记录在案的规则比较，单独列出解释不确定的字段 |
| 核对结论无法回查 | 提供文件、工作表、原行号、原列和原始值 |

拟以XLSX与CSV为首版输入，支持同一工作簿中的两张表或两个文件中的数据表；更多表格按基准表逐对核对。具体范围、规则与待验证事项见设计文档。

## 计划工作流程

资料登记 → 选择工作表与数据范围 → 建立字段映射与匹配规则 → 数据核对 → 差异分类 → 结果工作簿与报告 → 人工复核与修订。

输入资料充分时直接按已记录规则生成初稿；关键编号、单位或业务对应关系有歧义时，集中保留待确认事项。原表保持只读。

## 跨客户端方向

采用标准Agent Skill目录与通用文件接口。Agent负责理解任务和解释结果，Python工具负责确定性核对与文件导出；WorkBuddy等平台展示字段通过独立分发适配维护。

设计目标包括WorkBuddy及具备技能加载、文件读写和Python执行能力的其他Agent客户端。实际安装路径、运行能力及验证状态将在实现阶段分别记录。

## 项目资料

- [产品设计与核对规则](memory-bank/design.md)
- [初始化与后续开发待办](memory-bank/todo.md)
- [规则协议与数据结构](docs/rules-protocol.md)
- [四组跨行业合成验收案例](examples/README.md)
- [结果工作簿布局](docs/workbook-layout.md)
- [模块接口与分步实施计划](memory-bank/implementation-plan.md)
- [M1验证证据与容量边界](evidence/m1/README.md)
- [M2读取接口与运行边界](docs/intake.md)
- [M2测试与来源验证记录](evidence/m2/README.md)
- [项目协作约定](Agent.md)
- [GitHub仓库](https://github.com/zcjunblog/excel-reconciliation-assistant)

仓库初始化采用私有设置；正式版本、许可证、公开计划及市场发布待后续确定。

Created by [zcjunblog](https://github.com/zcjunblog)
