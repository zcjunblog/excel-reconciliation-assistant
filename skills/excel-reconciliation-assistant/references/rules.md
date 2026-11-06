# v1核对规则

机器约束见[Schema](reconciliation-rules.schema.json)；完整可运行样例见[行业案例](examples.md)。根对象只包含`schema_version: "1.0"`、`sources`、`tables`、`tasks`，未知字段会拒绝。不要自行创造`match_column`等替代键名。

## 来源与范围

| 对象 | 必须明确的字段 |
| --- | --- |
| sources | id、path、format(xlsx/csv)；CSV可加encoding(默认utf-8-sig)。path相对规则文件位置，不相对当前终端目录。 |
| tables | id、source_id、sheet（CSV为null）、header_row、data_range、exclusions。表头单行，data_range为A2:D20形式且不含表头行。 |
| exclusions | 每项为row和reason，表示范围内明确排除的原行号及依据。不要擅自排除隐藏/筛选行。 |
| tasks | id、left_table、right_table、keys、fields、formula_policy。不同核对规则使用不同稳定id。 |

一个物理文件只登记一次。同一XLSX的不同工作表用不同逻辑表引用同一source_id。CSV的行号为逻辑记录号，多行引号字段的物理行范围另存追溯。XLSX有隐藏/筛选行列时默认仍纳入；合并表头/区域公式等不支持范围会明确阻断，不自动填充或重算。

规则准备需要实际表头和完整范围。可用宿主文件读取能力或在已授权文件上进行只读Python预览；不因预检需要完整规则而猜测列名/末行。未授权资料不读取。

## 字段

每项`fields`含id、left_column、right_column、left_header、right_header、type。列使用Excel字母，header必须与实际表头一致；CSV也使用此列位置。`keys`引用这些字段的id，只能为identifier或text，键不重复计入比较字段。

- `identifier`：保留编号原样及前导零。原表已保存为数值的长编号存在精度风险，不能承诺恢复原号。
- `text`：默认原样比较。用户明确要求时用normalize数组，支持的操作名称以Schema枚举为准，不自行用同义名称。
- `decimal`：使用精确十进制；数值文本只有`parse_numeric_text: true`才解析。`tolerance`为非负十进制**字符串**，缺省为"0"。差额方向固定比较减基准。
- `date`/`datetime`：必须给`date_format: {"left": "...", "right": "..."}`，可用ISO8601或明确格式；不猜月日顺序或时区。同钟面不同偏移不当成一致。
- `nullable: true`只在用户确实允许字段为空时使用；0不是缺失，缺列不是空值。双空仅在此规则允许时可一致。

数值上下文用`context.unit`/`context.currency`；每项的left/right分别为`{"column":"C"}`或`{"literal":"CNY"}`，不可同时指定column与literal。常量须有业务依据，不能凭金额列名假定币种。单位/币种不一致或缺失时保持不可比，不暗中换算。

普通公式策略为任务级`formula_policy: "pending"`或`"cached"`。cached只读取已保存结果，新鲜度始终待确认；无缓存/错误缓存/外部工作簿引用不能当成两侧一致。

## 执行边界

2–5逻辑表、1–4任务；单文件20MiB、每表5万行/200列、累计20万行/200万格、累计20万字段比较；还有ZIP实际解压、扫描、记录长度和120秒预算。Excel每片2万明细、合计10万明细/200万输出格/50片/50MiB，全交付250MiB。它们是共同生效的拒绝上限，不是能同时取满的性能承诺。

重复/空键不自动聚合配对；缺表或结构错误不伪装成零差异。单任务可隔离失败，全局预算/来源变化/覆盖检查失败中止整批。字段规则内一致、完全一致、有差异、不可比较分别保留，不能把行数和字段数混成一个分母。
