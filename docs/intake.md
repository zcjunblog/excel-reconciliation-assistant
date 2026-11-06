# M2 来源读取与规则预检

状态：M2读取模块已实现，M3关联/比较另见[比较说明](comparison.md)；M4交付CLI和M5可安装Skill尚未实现。`ready`仅表示登记/读取阶段可继续，不表示表格数据相等。

## 接口与使用

生产模块位于`skills/excel-reconciliation-assistant/scripts/`，可在具备Python3.9+的宿主中执行。CSV与规则预检仅用标准库；XLSX依赖`requirements.txt`中的openpyxl。依赖由宿主选择隔离环境安装，模块不会修改全局环境。

```python
from pathlib import Path
from common import Budget
from rules import load_rules
from intake import inspect_sources, read_tables

rules = load_rules(Path('已授权任务/rules.json'))
# 必须来自用户/宿主的明确文件授权；不能仅因规则引用就自动授权。
authorized = {Path('已授权任务/基准.csv').resolve(), Path('已授权任务/比较.csv').resolve()}
budget = Budget()
intake = inspect_sources(rules, authorized, budget)
tables = read_tables(intake, rules, budget)
# 继续前检查intake.status、issues与blocked_table_ids；没有返回的表不是空表通过。
```

`load_rules`对不合法JSON、重复JSON键、未知字段、错误引用/键类型/范围/映射/容差等抛`RuleError`，其中issues按JSON路径定位。规则文件上限1MiB。`validate_rules`仅做规则校验，不读取业务文件。

`inspect_sources`只读常规授权文件，登记真实路径、物理文件身份、SHA-256和不可变字节快照；拒绝设备/FIFO/目录和未授权链接目标。同一物理文件不能用别名或硬链接重复登记。表范围和累计预算在分配前验证；XLSX同时检查声明和实际解压长度、重复成员、损坏流、加密/宏/外部工作簿链接/DTD等。XML编码当前限于无NUL的UTF-8兼容表示，不声称支持所有OOXML编码/布局。

`read_tables`只解析登记快照，并在前后核对来源路径/身份/摘要和规则指纹。返回成功表字典，问题保留在原IntakeResult：

- `ready`：当前阶段所有表可继续；只读取，没有关联或比较。
- `partial`：部分表不可读取，其他表仍可继续；后续核对须按任务依赖判定。
- `blocked`：全部表不可用，或全局预算/来源变化失败；没有可继续的整批结果。

表头、缺表、合并、选区、可隔离的单表值解码错误等阻断相关表；共享元数据或ZIP损坏可使整个物理来源不可用，但保留独立来源。预算/来源变化中止整批并清空预览。部分成功不隐去未读表。

## 原值和位置

TableData包含原列字母/表头、selected_rows、excluded_rows、实际纳入的RowData和元数据。CellValue保留源文件ID、表ID、工作表、原行/列、原类型/值、原数值词法、显示格式、普通公式与缓存类型/值。CSV另有逻辑记录号和原始物理起止行，文本前导零/空串保留，不先转数字。

M3补充：CellValue可选date_lexeme保存XLSX `t="d"`原始ISO日期文本，避免第三方库转换时丢失时区或亚毫秒。比较与后续原值展示须采用该词法；raw仍保留库转换值，不冒充未损失精度的唯一来源。

XLSX先流式扫描实际XML，忽略伪造维度声明，保存选区所需原始词法，再用openpyxl对明确范围读取公式/缓存双视图。不重算公式、不打开链接、不回写输入。内联富文本只拼接显示片段，排除注音；共享字符串按包声明发现实际成员并受字符预算约束。隐藏行列和筛选范围披露，默认均包含。

数组、dataTable及其他非普通/共享公式区域当前不能可靠表达全区域来源，**与选区相交的表会被明确阻断**；不能把子单元格缓存当作独立常量。此限制不等于支持这类公式，需后续专门扩展。普通公式的“是否比较/缓存新鲜度”由M3按既定协议处理，读取成功不代表可比较。

## 已验证范围

41个单元测试、四组合成案例和14份M1文件摘要检查通过。生产读取器处理过两份各50,000行×2列CSV，未测宽表最大容量或完整核对/导出。Python3.9.6禁用第三方site-packages后的CSV标准库检查通过；XLSX使用Python3.12.14/openpyxl3.1.5验证。不同系统/客户端尚未验证。

时限目前通过循环和阶段边界协作检查；一次第三方库调用期间不硬中断。硬进程超时属于后续CLI/宿主运行控制，不将该检查宣传成严格实时上限。

开发复现：在独立环境安装XLSX依赖后运行`python3 -m unittest discover -s tests -v`，或`python3 tools/verify_m2.py`生成材料验证与窄表读取记录。测试仅使用合成资料。实际证据见[evidence/m2](../evidence/m2/README.md)。
