# M3 记录关联与字段比较

状态：确定性Python引擎已实现；结果文件、交付CLI和可安装Skill尚未完成。引擎不读取额外业务目录、不修改输入、不执行公式。

## 任务调用

在M2明确授权、规则校验与读取成功后，使用同一个Budget继续执行：

```python
from matching import associate
from compare import compare_task
from checks import verify_coverage
from intake import verify_sources_unchanged

task = rules.tasks[0]
association = associate(tables[task['left_table']], tables[task['right_table']], task)
result = compare_task(association, task, budget)
assert not verify_coverage(result)
assert verify_sources_unchanged(intake, rules, budget)
```

示例承接[读取接口](intake.md)，只使用已登记的内存表。宿主应处理IntakeError/BudgetExceeded并保留失败状态，不能把异常或缺失任务换成零差异。整批预算/来源变化须丢弃整批完整结论，M4统一运行器尚未实现。

`associate(left, right, task)`校验逻辑表、表头、原行与来源一致性，按显式单键/复合键分组。字段类型与规范化顺序参与内部元组键，显示键保留字符串分量，不拼成容易碰撞的分隔字符串。任一侧重复，则两侧该组全部隔离；空键、公式键、数值型编号与规范化后空键进入无效区。每次按源行号确定输出顺序，不按当前数组顺序配对。

`compare_task(association, task, budget)`拒绝关联后改动规则，先计入累计字段预算，再比较每个唯一匹配对的非键字段。随后生成记录/字段计数、互斥行状态、按任务/字段/上下文分段的数值汇总，执行独立覆盖检查，并在返回前复查时限。低层`compare_pair`不包含任务级预算和守恒，不能单独当作完整任务执行器。

## 状态与计数

字段状态为exact、within_rule、different、not_comparable；“规则内一致”包含非零差额在容差内、以及不同原文本经显式规范化相等。找到对应记录不代表字段一致。差额固定比较侧减基准侧。

TaskResult状态：

- `complete`：当前范围与规则下执行完整，可以包含差异和两侧独有记录；**不等于业务一致或业务正确**。
- `needs_confirmation`：存在重复/无效键、不可比字段或缓存新鲜度限制。具体原因在关联issues、FieldResult.reason/warnings中，不能只看issues长度。
- 结构、来源变化、预算或守恒失败抛定位异常，不能得到可冒充完整结果的半份TaskResult。

每侧selected=included+excluded；included=unique_matched+only+duplicate_ambiguous+invalid_key。每个唯一匹配对×每个非键字段恰有一条结果。different_pairs与not_comparable_pairs可能重叠，互斥行状态按not_comparable > different > within_rule > exact归类。

`verify_coverage`从捕获的输入行号检查分类分区，逐条核对任务/键/源单元格与字段身份、明细delta，再核验分母、记录状态、字段计数及分段汇总。篡改一条delta、漏一条字段、重复结果、漏排除行或摘要不符都不能通过。

## 类型与计算边界

- 文本和编号不隐式转数值、不自动trim/casefold/NFKC；只使用规则明确列出的操作。原值保持在CellValue，规范化值另存。
- null/空串为缺失，0不是缺失。默认缺失不可比；明确nullable时两空可一致，单空为差异。缺映射列属于结构失败。
- 数值使用源XML词法或显式允许的CSV十进制文本。原生浮点缺少可靠词法时不假称精确。CSV不隐式接受千分位、符号金额、百分号、科学文本和数字周围空格。
- Decimal采用显式独立Context，计算不继承宿主的prec/Emax/Emin/trap。最多1000位系数（含末尾零）、调整指数绝对值1000；越界保留原值并标numeric_out_of_range，不截断或舍入。此限制适用于本版可计算数值，不限制作为文本保留的长编号。
- 币种/单位必须有同口径依据，不换算。分段汇总仅加总可比较的数值；上下文不一致/缺失、值不可比或允许的两空均另计排除，不用零填充，不能把不同字段、币种、单位或任务混成总额。
- 日期文本按显式格式，数字日期使用明确epoch。1900虚构2月29日不可比；1904序号0可恢复为1904-01-01。数值日期带库无法可靠保留的亚毫秒精度时需确认。
- XLSX `t="d"`的date_lexeme保留原始ISO文本，比较时恢复时区/微秒；不使用库已丢失时区或舍入的raw值代替。超过已支持的ISO精度或缺少可靠源词法时不冒充相等。显式时区偏移不同/有无不同进入待确认，不换算时区；日期字段不丢掉非零时间。
- 普通公式默认pending；缓存缺失/错误优先给具体原因。显式cached才使用有效缓存，附cache_freshness_unverified。内部表结构引用及公式字符串不误作外部工作簿；真实外部工作簿引用不可比。数组/dataTable等区域仍按M2边界阻断相关表，不重算任何公式。

M4原值展示应采用date_lexeme/数值词法与原类型，保留库转换值供诊断，避免给用户展示已丢失时区或精度的“原值”。内部十进制结果一律字符串。

## 已验证及待补

77个测试及四组5任务的人工预期答案通过；20万字段合成验证含右侧倒序、唯一0.01差异、累计预算拒绝下一任务和来源摘要不变。Python3.9.6标准库CSV完整读取/关联/比较烟测通过，不需要openpyxl；XLSX测试使用Python3.12.14/openpyxl3.1.5。

复现：`python3 -m unittest discover -s tests -v`；`python3 tools/verify_m3.py`额外产生版本化证据和忽略目录日志，不改写M1原始案例。具体范围见[evidence/m3](../evidence/m3/README.md)。

尚未验证：真实源文件重排行列后更新映射/重新登记的专项回归（Minor延期M4）；现有案例已覆盖两表不同列序/行序。M4导出/办公软件、M5包和客户端、多系统与最大宽表性能均不属于本轮已完成能力。
