<h1 align="center">Excel表格核对助手</h1>
<p align="center"><strong>让每一处表格差异，都能定位、解释和复核。</strong></p>
<p align="center">Excel Reconciliation Assistant<br>面向各行业与多种Agent客户端的表格核对Skill</p>

将用户提供的业务表格按明确的字段与匹配规则进行核对，整理缺失记录、重复编号和字段差异，形成便于筛选的结果工作簿与可追溯报告。

**M0–M5已完成。** 已交付标准Skill、0.1.0通用/WorkBuddy安装包与独立解压验证，并通过本机真实Codex CLI、WorkBuddy调用。其他客户端完成官方目录说明与隔离安装验证；尚未提审或公开发布。

## 核心用途

| 常见任务 | 核对结果 |
| --- | --- |
| 订单与发货记录不一致 | 按业务编号关联记录，列出缺失、重复与数量差异 |
| 两份名册或台账对不上 | 核对对应字段，定位仅在某一侧出现的记录 |
| 同一份资料存在多个版本 | 保留旧值、新值与来源位置，输出变化明细 |
| 金额、日期或编号格式不同 | 按记录在案的规则比较，单独列出解释不确定的字段 |
| 核对结论无法回查 | 提供文件、工作表、原行号、原列和原始值 |

支持XLSX与CSV输入，同一工作簿中的两张表或不同文件中的数据表均可按明确规则核对；多表采用独立任务逐对执行。重复键、空键与不可比较字段保持可见，不任意去重或配对。

## 工作流程

资料登记 → 选择工作表与数据范围 → 建立字段映射与匹配规则 → 数据核对 → 差异分类 → 结果工作簿与报告 → 人工复核与修订。

工具按已记录的范围与字段规则生成核对草稿，原表只读。关键编号、单位或业务对应关系有歧义时保留待确认事项；“执行完整”不等于“业务一致”。

## 安装包

[下载标准Skill](releases/0.1.0/excel-reconciliation-assistant-0.1.0.zip) · [下载WorkBuddy包](releases/0.1.0/excel-reconciliation-assistant-workbuddy-0.1.0.zip) · [核对SHA-256](releases/0.1.0/SHA256SUMS)

当前为0.1.0阶段构建包，供安装与验收。标准包遵循同一技能目录，WorkBuddy包补充平台展示元数据；两者调用相同的确定性核对工具。

## 安装与使用

标准Skill包含完整工具、规则Schema、合成示例与运行说明。选择对应客户端的技能目录，放入整个`excel-reconciliation-assistant`文件夹，再打开新任务调用技能；WorkBuddy使用独立元数据配置的ZIP导入。

1. 安装Skill，运行环境检查，确认CSV与XLSX能力。
2. 提供需核对的文件，说明业务编号、对应字段与允许的容差。
3. Agent建立规则并预检，使用确定性工具执行核对。
4. 获取结果工作簿、可追溯报告和待确认事项，回查原表后处理业务决定。

详细目录、安装命令与能力边界见[安装指南](docs/installation.md)；实际安装、解压运行与宿主调用分别记录在[M5验证证据](evidence/m5/README.md)。

## 本地运行

Python 3.9及以上；XLSX需要`openpyxl>=3.1,<4`。CSV计算与MD/JSON交付可使用标准库。以下命令使用仓库合成案例，输出目录必须尚不存在：

```sh
python3 skills/excel-reconciliation-assistant/scripts/reconcile_tool.py run \
  --rules examples/commerce/rules.json \
  --authorize examples/commerce/inputs.xlsx \
  --output outputs/commerce-v001
```

先检查结构可将`run`改为`inspect`。授权文件需逐个传入`--authorize`，规则引用不能替代用户授权。退出码0表示执行完整或预检就绪，2表示待确认/部分完成，1表示阻断/错误；此商贸样例故意包含待确认记录，预期退出2。

交付包含**核对结果.xlsx、核对报告.md、待确认事项.md、完整结构化工作资料及实际文件清单**。每个文件登记摘要，超限不静默截断，已有版本不覆盖；缺依赖或部分任务失败时说明实际完成范围。详见[运行与交付说明](docs/delivery.md)。

四行业5个任务与独立人工答案一致；20,001条例外字段按20,000+1分片回读通过。已在macOS WPS检查中文、编号、筛选、冻结与惰性文本。不同设备和操作系统、最大复杂表性能仍待后续实测；本机真实Codex CLI与WorkBuddy调用已通过，其他客户端状态见M5证据。

## 跨客户端方向

采用标准Agent Skill目录与通用文件接口。Agent负责理解任务和解释结果，Python工具负责确定性核对与文件导出；WorkBuddy等平台展示字段通过独立分发适配维护。

设计目标包括WorkBuddy及具备技能加载、文件读写和Python执行能力的其他Agent客户端。已按当前官方文档提供Codex、Claude Code、Cursor、GitHub Copilot CLI、Gemini CLI和OpenCode目录与安装器。目录安装验证与实际宿主验收分别记录，不据此承诺所有版本、云端surface或受限环境均可运行。

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
- [M3关联、比较与状态说明](docs/comparison.md)
- [M3独立答案与边界验证](evidence/m3/README.md)
- [M4运行与文件交付](docs/delivery.md)
- [M4文件、分片和办公验证](evidence/m4/README.md)
- [项目协作约定](Agent.md)
- [GitHub仓库](https://github.com/zcjunblog/excel-reconciliation-assistant)

仓库初始化采用私有设置；正式版本、许可证、公开计划及市场发布待后续确定。

Created by [zcjunblog](https://github.com/zcjunblog)
