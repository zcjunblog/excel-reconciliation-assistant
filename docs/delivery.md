# M4 运行与文件交付

已实现确定性工具与本地CLI；标准Skill入口、安装包及Agent客户端实跑属于M5。下列命令在仓库根目录执行。真实业务文件只放忽略目录，不提交仓库。

## 环境与授权

Python 3.9及以上。CSV读取、关联、比较和Markdown/JSON交付使用标准库；XLSX读取与输出需要当前Python环境中的`openpyxl>=3.1,<4`。建议用项目虚拟环境安装：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'openpyxl>=3.1,<4'
```

Windows使用虚拟环境的`Scripts/python.exe`。工具不自动安装依赖、不依赖模型API、开发机绝对路径或办公软件自动化。WPS仅用于开发验收。

规则中的来源路径相对规则文件所在目录解释。规则引用不代表用户授权：宿主需把用户已提供或明确允许处理的**物理文件路径**逐个传给`--authorize`，不能用整个目录代替。不扫描规则外文件。

## 先预检，再执行

以下来源为仓库中合成样例，可安全重现；输出目录必须为尚不存在的新版本目录。

```sh
python3 skills/excel-reconciliation-assistant/scripts/reconcile_tool.py inspect \
  --rules examples/commerce/rules.json \
  --authorize examples/commerce/inputs.xlsx \
  --output outputs/commerce-inspect-v001

python3 skills/excel-reconciliation-assistant/scripts/reconcile_tool.py run \
  --rules examples/commerce/rules.json \
  --authorize examples/commerce/inputs.xlsx \
  --output outputs/commerce-run-v001
```

`inspect`完成来源登记、结构与规则预检，生成预检报告及来源/规则资料；不执行记录关联、字段比较，不生成核对结果Excel。`run`完成登记→读取→唯一键关联→字段比较→覆盖检查→工作簿/报告→摘要回读→清单发布。

stdout为一个JSON摘要；以退出码和`status`判断执行范围，不能仅检查是否出现文件：

| 退出码 | 状态 | 含义 |
| --- | --- | --- |
| 0 | run: complete；inspect: ready | 指定任务执行完整，或预检可继续；不表示业务一致。完整任务仍可能有差异或仅一侧记录。 |
| 2 | needs_confirmation / partial | 存在歧义、不可比、缓存待确认，或只有部分任务/格式完成；按实际清单与报告复核。 |
| 1 | blocked / error | 无有效核对任务，或来源变化、全局预算、规则/交付失败；不能作为完整核对结论。可隔离的输入问题可能交付状态为blocked的诊断资料。 |

`--timeout`默认120秒，CLI使用隔离进程监督整次调用；超时终止本次进程，不能继续发布完整清单。模块API的Budget为协作检查，宿主需要硬截止时应调用CLI。启动和终止清理存在操作系统开销。

## 文件与阅读顺序

1. **核对结果.xlsx**：白蓝概览、字段与规则、来源与范围、差异明细、两侧独有、待确认、全量匹配索引及按口径分段的数值汇总；只创建有内容的明细表。
2. **核对报告.md**：逐任务范围、数量与主要例外。每任务最多展示20条例外；这是阅读摘要，完整字段资料保留在下列JSONL中。
3. **待确认事项.md**：重复组全部成员、无效键、公式/类型/单位问题及定位。
4. **工作资料/**：全量字段结果JSONL、逐侧选中源行关联JSONL（含排除原因）、检查记录、来源索引、读取范围、规则与执行摘要。读取范围保留每张表的实际预览、隐藏/筛选/日期系统及阻断状态，即使XLSX降级也可追溯。来源表不默认复制；规则副本只保留原文件名，重跑需重新定位并授权。
5. **交付清单.json**：实际文件的相对路径、类型、字节数、SHA-256，以及任务状态和未生成格式。清单不列自身摘要；其他文件必须逐项一致。

Decimal及规范化数值用十进制字符串；日期用带类型标签的ISO文本，读取库返回的浮点诊断值也带类型标签。`numeric_lexeme`/`date_lexeme`保存来源词法，不能把库转换值当作未损失精度的唯一原值。原始文本在XLSX中惰性保存，无来源公式或活动外链。

有数据的任务可独立交付，失败任务明确列为未核对。全局预算/来源变化/覆盖失败则中止整批。CSV仍可在缺少openpyxl时生成完整MD/JSON资料，XLSX记为未生成，整批partial；XLSX来源缺依赖时相关表被阻断。

## 交付完整性与容量

每次新建独立版本目录，拒绝覆盖已有目录（即使为空）。工具先在私有暂存目录生成、回读并核验摘要，再独占创建目的目录复制；复制时存在`.交付中.json`标记，全部成功后最后发布`交付清单.json`并移除标记。使用方应等待有效清单，不能把复制中的目录当作完成。

创建的文件/目录在私有身份账本中登记；目录替换、链接或文件身份变化会阻断交付。清理仅移除本次创建且身份仍匹配的对象，其他写入者的文件和目录保留。取消/异常时，身份不能确定的残留版本不作为完整结果，也不能为清理它而删除未知对象。CLI监督进程的临时工作表XML也限定在本次私有暂存目录。

- 每片20,000条数据记录；累计100,000条明细（包括规则、来源、匹配索引等明细视图）、2,000,000输出单元格、50片明细、单工作簿50MiB。
- 全交付累计250MiB，包括Excel、报告、结构化资料和最终清单；此预算不代表临时副本的磁盘占用上限。
- 超过Excel预算时整体不生成XLSX，完整MD/JSON仍在全交付预算内生成，并明确标记partial/未生成原因。超过全局时间或全交付预算则阻断，无完整清单。
- 不静默保留前N条。数值超出Excel可靠精度时按文本保存；超长原值完整保留在单元格及工作资料，显示高度有限时可用编辑栏查看。

阈值是拒绝上限，不能同时取满当作性能承诺。20,001条例外分片与四行业合成任务已实际验证；不同操作系统、复杂大表及全部容量边界的性能仍需M6实测。

## 模块调用

`runner.execute(rules,authorized_paths,budget,mode='run')->RunResult`只执行已授权来源；`write_workbook`与`write_reports`返回实际文件的ExportRecord；`finalize_delivery`只接受同一个干净暂存目录中的完整登记文件。宿主不得捕获fatal后拼接旧TaskResult冒充新运行成功。

复现阶段验证：`python3 tools/verify_m4.py`。该工具只读取合成examples、在忽略目录生成新版产物，并核对人工答案与原始14份文件摘要，不改写expected。
