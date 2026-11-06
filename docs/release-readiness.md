# 发布与审核记录

更新日期：2026-11-06。0.1.4已免费提交WorkBuddy审核。用户最新明确要求“直接开源”，本轮立即公开GitHub，取代此前等待审核的顺序；WorkBuddy审核结果独立，SkillHub暂缓。

## 可直接审阅的材料

| 材料 | 文件 |
| --- | --- |
| 正式产品说明与七步流程 | [README](../README.md) |
| 白蓝宽封面 | [封面PNG](images/excel-reconciliation-cover.png)，2172×724 |
| 真实结果预览 | [商贸概览](images/commerce-overview-render.png) · [负差额概览](images/negative-delta-overview-render.png) · [负差额明细](images/negative-delta-details-render.png) |
| 原始Logo与上传候选 | [Logo](images/excel-reconciliation-logo.png)；[512px PNG](../distribution/marketplace/logo-512.png)，237,554字节 |
| 中英文上架说明 | [中文](../distribution/marketplace/description-zh.md) · [英文](../distribution/marketplace/description-en.md) |
| 展示字段、示例与资源索引 | [listing.json](../distribution/marketplace/listing.json) |
| 真实四行业与负差额演示 | [案例索引](../examples/README.md) · [逐文件摘要](../examples/showcase-v1/showcase-manifest.json) |
| 通用/WorkBuddy安装包 | [0.1.4目录](../releases/0.1.4) · [SHA256SUMS](../releases/0.1.4/SHA256SUMS) |
| 已验证的客户端和范围 | [M5证据](../evidence/m5/README.md) |

本次实际确认页要求头像512×512px、不大于500KB、JPG/PNG；已上传237,554字节PNG并检查预览。代码包上传控件要求ZIP≤3MB；实际包已解析通过。公开技能文档与当前上传控件的约束分别记录，以本次页面回执为准。

## 状态与待办

| 项目 | 状态 | 依据或下一步 |
| --- | --- | --- |
| 核对引擎与分发 | 已验收 | 0.1.0双包、原始14份夹具与M5实际客户端证据 |
| 真实可下载案例 | 已准备 | 五案例六任务，独立人工预期与实际清单逐项回读 |
| 正式README、Logo与封面 | 已准备，Logo已上传 | 图片为内置imagegen生成；封面标为概念图，实际工作簿另行预览 |
| 错误规则盲测、容量样本与办公复核 | 本机检查及最终回归通过 | [M6证据](../evidence/m6/README.md)：盲测暴露并记录草稿问题，五案例WPS查看，5000对/15000字段完整CLI样本 |
| 真人办公用户复核 | 待完成 | 用户或办公同事下载样张，检查差额、原行定位、筛选与确认事项 |
| 跨设备/操作系统、其余五宿主 | 未验证 | 可在声明当前验证范围后分阶段补测，不声称全平台实跑 |
| 发布许可证 | 已选择MIT | 根目录与0.1.4双包内包含同一份[MIT许可证](../LICENSE) |
| 公开范围与收费 | 已获最新授权 | GitHub立即以MIT开源；WorkBuddy免费提审，审核状态独立 |
| WorkBuddy提审 | 已提交审核 | 0.1.4 · os_5a4af3ee62a8592f；价格免费，页面预计7个工作日内出结果，尚未获批/上线 |
| SkillHub | 仅核验公开规则 | 尚未登录实名、验证标识归属或上传；用户已决定暂缓 |

## 原批准顺序与最新调整

用户已批准[MIT许可证](https://opensource.org/license/mit)、WorkBuddy免费首发、审核通过后再公开GitHub；SkillHub暂缓。已补入根目录与包内同一份MIT文件，版权为2026 zcjunblog。0.1.1仅新增许可证和更新VERSION，实际市场解析因样例目录嵌套过深被拒；0.1.2增加WorkBuddy专用目录适配。保留0.1.0和0.1.1双包，不覆盖历史案例和证据。

真人试阅、其他设备/系统与五宿主仍未完成，发布授权不替代这些证据。此前的等待条件已被用户“直接开源”指令取代，当前允许直接公开主仓库；WorkBuddy审核仍按实际回执记录。

## WorkBuddy提审步骤（已授权，按实际状态记录）

1. 复核最终许可、版本、介绍、示例、Logo与包摘要。
2. 打开WorkBuddy开放平台的技能创建入口，上传对应平台ZIP，等待解析结果。
3. 核对中英文展示名、介绍与等长非空示例，上传已审阅Logo；分类按实际页面可选项确定。
4. 查看平台风险/错误提示及具体上传要求，不自动改权限、接受协议或跳过校验。
5. 已获用户授权，完成核对后提交审核，保存回执；分别记录“已上传并解析”“已提交”“审核通过”“市场已上线”。

当前字段依据[WorkBuddy官方技能文档](https://open.workbuddy.cn/docs/skill)：标准name、展示名、中英介绍、作者、版本与中英示例。官方说明中的示例对应详情页“试试这样用”；README图片不会自动变成市场图文案例展示。当前尚未确认自助图文案例编辑入口。

## SkillHub边界

M5已通过官方[公开教程](https://skillhub.cn/tutorials#publish-via-cli)核对独立发布、实名、全局唯一slug及license等要求。本轮Web抓取该教程超时，没有据此改变M5已核对结论；正式选择该渠道时须重新核验登录身份、标识归属及当前表单。未为本账号预留slug，也未将WorkBuddy上线视为SkillHub已收录。

## 真人试阅清单

请用[负差额工作簿](../examples/showcase-v1/negative-delta/核对结果.xlsx)和两份[原始CSV](../examples/release-cases/negative-delta)完成一次实际试阅，记录使用的软件、设备和问题：

- `0007`数量10→8是否显示-2，金额100.00→89.75是否显示-10.25。
- 从差异明细的原行/列能否回查两份CSV，行序不同是否仍对应正确。
- 文字、列宽、筛选、冻结和待确认说明是否易读。
- 商贸案例的重复编号、空编号和币种问题是否容易发现。

这份清单是待执行的人工验收，不由自动脚本或代理自己勾成通过。

目录适配验证与提交记录见[0.1.2执行记录](../memory-bank/release-0.1.2.md)。0.1.1解析失败属于市场开包阶段，尚未进入审核。

0.1.2市场解析继续提示中英文示例各最多3条；0.1.3已精简市场快捷示例并加入构建前校验。正式首发状态以[0.1.3执行记录](../memory-bank/release-0.1.3.md)为准，历史版本归档保留。

0.1.3已解析成功但未提交。用户要求正式概述，能力介绍是包内只读字段；0.1.4已更新中英文概述，当前状态以[0.1.4执行记录](../memory-bank/release-0.1.4.md)为准。

## 0.1.4 实际提交回执

2026-11-06：用户明确同意删除未提审0.1.3草稿后，平台显示删除成功；旧安装包与资料保留。0.1.4重新解析成功，技能ID为`os_5a4af3ee62a8592f`。正式中英介绍来自包内，中文概述含场景、交付、回查、六步流程及只读/规则范围说明；确认页已回读。

市场分类为数据分析、效率工具；服务类目为工具→办公；512px Logo上传与实际预览通过，最终确认页明确价格免费。点击提交后显示“已提交审核，预计7个工作日内出结果”。详细字段与本地截图SHA见[提交记录](../evidence/releases/0.1.4/workbuddy-submission.json)。原始浏览器截图留在忽略目录，不提交公开仓库。

WorkBuddy后续仍需核验审核结果和市场是否上线；GitHub已获最新直接开源授权，不再等待审核。GitHub公开不代表市场审核通过。SkillHub保持暂缓；真人和其他环境验证保持待办。

## GitHub直接开源执行

用户最新授权直接公开。README已完善开源首页与v0.1.4下载说明；现有双包、许可和历史资料保持不变。公开与Release实际结果见[evidence/releases/0.1.4/github-publication.json](../evidence/releases/0.1.4/github-publication.json)。

### GitHub公开结果

已公开仓库并发布[v0.1.4 Release](https://github.com/zcjunblog/excel-reconciliation-assistant/releases/tag/v0.1.4)。两ZIP、SHA256SUMS和manifest共四文件均经认证及匿名回读，内容与本地完全一致；README匿名可读，四张产品/工作簿图片加载正常。最新主分支包含公开状态记录，v0.1.4标签保持在发布准备提交f368aa4，不改写标签或安装包。本轮未重查WorkBuddy审核，不据GitHub公开宣称市场上线。
