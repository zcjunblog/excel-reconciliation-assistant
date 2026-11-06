<p align="center">
  <img src="docs/images/excel-reconciliation-cover.png" alt="Excel表格核对助手：从业务表格到可追溯的核对结果。概念宣传图，非实际软件界面。" width="100%">
</p>

<p align="center"><img src="distribution/marketplace/logo-512.png" alt="Excel表格核对助手 Logo" width="72" height="72"></p>
<h1 align="center">Excel表格核对助手</h1>
<p align="center"><strong>让每一处表格差异，都能定位、解释和复核。</strong></p>
<p align="center">Excel Reconciliation Assistant<br>面向各行业与多种 Agent 客户端的表格核对 Skill</p>
<p align="center">
  <a href="releases/0.1.1/excel-reconciliation-assistant-0.1.1.zip">标准 Skill</a> ·
  <a href="releases/0.1.1/excel-reconciliation-assistant-workbuddy-0.1.1.zip">WorkBuddy 安装包</a> ·
  <a href="#工作流程">工作流程</a> ·
  <a href="#真实演示">真实演示</a> ·
  <a href="#快速开始">快速开始</a>
</p>

订单与交付表对不上，台账与盘点记录存在差异，名单有重复编号，版本变化难以回查。表格核对需要看见差异，也需要知道差异来自哪里、按什么规则判断、哪些记录仍待确认。

**Excel表格核对助手将用户提供的 XLSX、CSV 按明确的业务编号与字段规则进行核对，生成可筛选的结果工作簿、核对报告和待确认事项，并保留原行、原列与原始值。**

Agent 理解任务、整理规则并解释结果；确定性工具执行读取、关联、比较与文件生成。原表只读，每次交付独立版本，补充规则后可重新核对并保留旧结果。

## 核心能力

| 业务中的常见问题 | 助手提供的支持 |
| --- | --- |
| 两张表的行序、列序不同 | 按唯一业务键或复合键关联，分别记录左右字段映射 |
| 有些记录只出现在一侧 | 分别列出两侧独有记录，保留原行位置 |
| 编号重复、为空或存在一对多关系 | 隔离相关原行，整理待确认事项，避免任意配对 |
| 编号含前导零或格式容易被转换 | 保留文本原文；`0007` 与 `7` 默认不同，规范化需明确规则 |
| 数量、金额或日期需要按口径比较 | 使用精确十进制、明确容差与单位/币种；日期解释和精度缺口保持可见 |
| 公式看似有值，实际缓存未确认 | 区分公式文本、已保存缓存与实际重算，保留缓存新鲜度限制 |
| 差异结论难以复核 | 记录文件、工作表、原行列、左右原值、差额与判定原因 |

支持同一工作簿中的两张表、不同文件的数据表，以及多个独立任务逐对执行。输入为 XLSX／CSV；交付为 XLSX、Markdown、JSON／JSONL。CSV 是输入格式，不生成 CSV 结果表。

## 适用场景

| 场景 | 典型核对任务 |
| --- | --- |
| 商贸与项目交付 | 按订单号、行号核对数量、金额与交付记录 |
| 库存与现场盘点 | 按商品编号、仓位核对台账、实盘与单位 |
| 培训、活动与报名 | 按报名编号核对名单、签到和字段变化 |
| 行政与资产管理 | 按资产编号核对领用人、数量、状态或价值 |
| 其他业务清单 | 在明确范围与字段含义后，复用相同规则结构 |

## 工作流程

| 阶段 | 处理内容 | 可以查看的结果 |
| --- | --- | --- |
| **01 · 资料与范围** | 登记已授权来源，选择工作表、表头、数据范围和排除行 | 来源登记、实际范围和原始摘要 |
| **02 · 规则准备** | 明确基准/比较侧、业务键、字段映射、类型、容差和单位 | 可保存、可复用的核对规则 |
| **03 · 结构预检** | 检查文件、表头、列映射、格式与范围；暴露规则缺口 | 预检报告与阻断说明 |
| **04 · 业务关联** | 按精确键关联唯一记录，隔离重复键和空键 | 全量匹配索引与逐侧行分类 |
| **05 · 字段核对** | 比较原值与规范化值，区分一致、规则内一致、差异及不可比 | 左右原值、差额、原因和来源坐标 |
| **06 · 文件交付** | 生成白蓝工作簿、报告、待确认事项与结构化工作资料 | 实际文件清单及逐文件 SHA-256 |
| **07 · 人工复核** | 回查原表，确认歧义；补充规则后另建版本重跑 | 旧版保留、新版结果与新的确认依据 |

**执行完整表示指定规则已执行完毕，仍可能存在业务差异。** 重复键、空键、不可比较字段和未生成格式会明确说明；业务处理由使用者结合原表确认。

## 真实演示

以下全部使用合成数据，由当前 0.1.0 工具实际生成。展示文件保留原始清单与摘要，可下载检查。

### 一份清单的数量与金额变化

基准清单与比较清单的行序不同，按资产编号精确对应。金额币种在原表中明确为 CNY，数量单位为台，差额方向固定为**比较侧减基准侧**。

| 编号 | 字段 | 基准值 | 比较值 | 差额 | 判定 |
| --- | --- | --- | --- | --- | --- |
| `0007` | 数量 | 10 | 8 | -2 | 有差异 |
| `0007` | 金额 | 100.00 | 89.75 | -10.25 | 有差异 |
| `0008` | 金额 | 0.10 | 0.30 | +0.20 | 有差异 |

2 对记录、6 次非键字段比较：3 处完全一致、3 处差异，执行状态为 `complete`。这份结果说明规则执行完整，业务仍有差异。

[基准原表](examples/release-cases/negative-delta/基准清单.csv) · [比较原表](examples/release-cases/negative-delta/比较清单.csv) · [明确规则](examples/release-cases/negative-delta/rules.json) · [结果工作簿](examples/showcase-v1/negative-delta/核对结果.xlsx) · [核对报告](examples/showcase-v1/negative-delta/核对报告.md)

<p align="center"><img src="docs/images/negative-delta-details-render.png" alt="真实负差额工作簿的差异明细局部：编号、字段、左右原值和差额" width="100%"></p>

上图由实际结果工作簿的差异明细 C1:G4 只读渲染，展示局部数据；没有重新排写结果或修改工作簿。

### 四组行业案例

| 案例 | 演示内容 | 原表与规则 | 实际交付 |
| --- | --- | --- | --- |
| 订单与交付 | 复合键、容差、币种差异、重复及缺失记录 | [输入与规则](examples/commerce) | [Excel](examples/showcase-v1/commerce/核对结果.xlsx) · [报告](examples/showcase-v1/commerce/核对报告.md) |
| 库存盘点 | 行列重排、前导零、数量与单位差异 | [输入与规则](examples/inventory) | [Excel](examples/showcase-v1/inventory/核对结果.xlsx) · [报告](examples/showcase-v1/inventory/核对报告.md) |
| 报名与签到 | 时间解释、文本、空值与容差规则 | [输入与规则](examples/training) | [Excel](examples/showcase-v1/training/核对结果.xlsx) · [报告](examples/showcase-v1/training/核对报告.md) |
| 资产台账 | 两种公式策略、缓存缺失及原值追溯 | [输入与规则](examples/administration) | [Excel](examples/showcase-v1/administration/核对结果.xlsx) · [报告](examples/showcase-v1/administration/核对报告.md) |

[完整案例说明](examples/README.md) · [全部演示文件摘要](examples/showcase-v1/showcase-manifest.json)

<p align="center"><img src="docs/images/commerce-overview-render.png" alt="商贸合成案例的真实核对概览：数量、任务状态与阅读导航" width="100%"></p>

上图为实际工作簿“核对概览”A1:L28 的只读渲染，非办公软件界面截图。完整内容请下载工作簿查看。

## 交付内容

| 文件 | 用途 |
| --- | --- |
| **核对结果.xlsx** | 查看概览、规则与范围、全部例外字段、两侧独有、待确认记录、匹配索引和数值汇总 |
| **核对报告.md** | 了解本次范围、数量、主要差异与未完成事项 |
| **待确认事项.md** | 集中处理重复键、空键、公式缓存及口径缺口 |
| **工作资料/** | 回查全量字段结果、逐源行分类、来源、范围和规则 |
| **交付清单.json** | 确认实际生成的文件、格式、字节数与摘要 |

结果工作簿提供文字状态、筛选、冻结窗格、来源坐标与分片导航。报告展示主要例外，完整记录保留在工作簿和 JSONL；超过输出范围时说明实际完成内容，不静默截断。

## 快速开始

### 在 Agent 客户端中使用

1. 下载并按[安装指南](docs/installation.md)安装整个技能目录；WorkBuddy 使用专用 ZIP 导入。
2. 选择 Python 3.9+，运行技能目录中的 `scripts/doctor.py`；需要 Excel 时加 `--require-xlsx`。XLSX 需要 `openpyxl>=3.1,<4`。
3. 提供需核对文件与明确规则，打开新任务调用技能。

可以这样提出任务：

> 核对这两份资产清单。按资产编号对应，比较领用人、数量和金额，金额绝对差额 0.01 以内视为容差内一致。编号保持原样，原表只读。生成 Excel、核对报告和待确认事项，保留原行定位。若字段或单位不明确，请列出需要确认的问题。

### 安装包

- [标准 Skill 0.1.1](releases/0.1.1/excel-reconciliation-assistant-0.1.1.zip)
- [WorkBuddy 0.1.1](releases/0.1.1/excel-reconciliation-assistant-workbuddy-0.1.1.zip)
- [SHA256SUMS](releases/0.1.1/SHA256SUMS) · [逐资源清单](releases/0.1.1/manifest.json)

无模型 API 密钥要求；能否执行取决于客户端的文件读写、Python 执行能力及其权限范围。CSV 可只用标准库完成核对与 Markdown／JSON 交付；缺少 Excel 依赖时明确说明未生成 XLSX。

### 在本地运行合成案例

```sh
python3 skills/excel-reconciliation-assistant/scripts/reconcile_tool.py run \
  --rules examples/commerce/rules.json \
  --authorize examples/commerce/inputs.xlsx \
  --output outputs/commerce-v001
```

结构预检将 `run` 改为 `inspect`，并使用另一个新输出目录。每个来源逐个传入 `--authorize`；规则引用不能替代授权，已有输出目录拒绝覆盖。

退出码 `0` 表示执行完整或预检就绪，`2` 表示待确认/部分完成，`1` 表示阻断/错误。此商贸样例含待确认记录，预期退出 `2`。详细参数见[执行与交付](docs/delivery.md)。

## 客户端与验证范围

| 客户端 | 当前证据 |
| --- | --- |
| WorkBuddy V5.9.3 | 最终包导入、显式技能调用、实际 Excel 与报告、本机文件回读通过 |
| Codex CLI | 已安装技能发现、doctor／inspect／run、实际交付与摘要回读通过 |
| Claude Code、Cursor、GitHub Copilot CLI、Gemini CLI、OpenCode | 官方目录说明已核对，项目/用户目录隔离安装通过；尚未实跑这些宿主 |

[安装路径与能力边界](docs/installation.md) · [M5 客户端证据](evidence/m5/README.md)

本机已检查 WPS 中文、列宽、筛选、冻结、前导零与惰性文本。不同设备/系统、其他宿主及复杂大表仍需实际验收。20,001 条例外的分片回读已通过；容量阈值是拒绝上限，不能当作性能承诺。

## 使用边界

- 首版处理 XLSX 与 CSV；不直接处理截图、扫描件、XLS、在线业务账号或实时数据库。
- 业务键、对应关系、单位/币种和关键数值解释需有明确依据；不自动近似匹配、聚合或换算。
- 保留源文件，只在新版本目录交付；单元格中的指令、公式样式文本和外链不会被执行。
- 工具不会重算公式。已保存缓存的存在不代表结果已更新；公式策略和新鲜度限制单独记录。
- 核对结果供回查与复核，不能替代付款、库存调整、审批或其他业务操作。

## 开发与验证

```sh
python3 -m unittest discover -s tests -q
```

开发验证依赖见 `tools/requirements-m5.txt`。用例覆盖授权、原值与坐标、类型、精确差额、歧义隔离、数量守恒、交付摘要、独立解压与安装边界。生产包不包含测试或人工答案。

- [产品设计与阶段待办](memory-bank/design.md) · [待办](memory-bank/todo.md)
- [规则协议](docs/rules-protocol.md) · [工作簿布局](docs/workbook-layout.md)
- [M1 材料与容量范围](evidence/m1/README.md) · [M2 来源读取](evidence/m2/README.md)
- [M3 确定性比较](evidence/m3/README.md) · [M4 文件与办公验证](evidence/m4/README.md)
- [M5 分发与客户端](evidence/m5/README.md) · [渠道说明](docs/distribution.md)
- [M6 展示、错误规则盲测与性能样本](evidence/m6/README.md)

当前发布候选为 0.1.1，采用 [MIT 许可证](LICENSE)，计划免费发布 WorkBuddy。GitHub 仓库将在 WorkBuddy 审核通过后公开；SkillHub 暂缓。尚未市场提审。发布状态以[发布准备记录](docs/release-readiness.md)为准。

Created by [zcjunblog](https://github.com/zcjunblog)
