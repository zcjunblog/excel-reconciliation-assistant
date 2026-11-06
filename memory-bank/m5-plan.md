# Excel表格核对助手 M5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 沿用本会话原生执行方式；本文件细化用户已授权的M5范围，不新增发布或账号操作。

**Goal:** 将M4引擎封装为可独立安装和运行的标准Skill与WorkBuddy包，并分别记录安装、脚本与真实宿主调用证据。

**Architecture:** skills/excel-reconciliation-assistant为完整技能源目录，VERSION是唯一版本源。通用入口只用标准name/description；构建器为WorkBuddy注入展示字段。复制Schema与四组原始合成输入/规则供离线使用，不携带expected答案；复制内容由测试对原件SHA核验。Agent只负责明确规则和解释，继续调用M4 CLI执行核对。

**Tech Stack:** Python3.9+标准库构建/安装/CSV，openpyxl>=3.1,<4可选XLSX；无模型API、全局环境修改或开发机运行时依赖。

**Spec:** memory-bank/design.md §§1–14、§20；memory-bank/todo.md M5；docs/rules-protocol.md；M4公开CLI及文件协议。

## Global Constraints

- 只处理明确授权来源，原文件只读，版本目录不覆盖。规则引用不构成授权，退出码及partial/blocked保持真实。
- 中文名Excel表格核对助手；标准标识excel-reconciliation-assistant；首次候选版本0.1.0。许可证/公开/收费/市场发布仍待M6决定。
- 标准技能源自包含；引用资源、模板、运行依赖与合成示例须完整，不能读取仓库外文件或包含开发机绝对路径。
- 保持M1全部14份来源/规则/人工答案字节不变；包中不包含expected、用户输出、评估答案或缓存。
- 构建包可重复，两个配置只变更SKILL.md展示前置信息；已有发布/安装目录拒绝覆盖，失败不破坏已有或并发文件。
- 官方文档核对、目录安装、实际工具输出和真实客户端调用分别记录，不以一个层级代替另一个。
- SkillHub仅核验公开入口、元数据/唯一标识及归属要求；不登录实名、创建凭证、上传或发布。

## Review Focus

1. 自定义安装路径含空格或符号链接、已有同名目录、复制中断/并发文件：拒绝越界覆盖并保留非本次创建对象，由Task2验证。
2. 源目录中出现缓存、私密文件、链接、缺失引用或平台元数据覆盖版本：构建拒绝非预期内容，包不泄漏额外资料，由Task2验证。
3. 离开仓库后执行、缺少openpyxl、非UTF-8 stdout、Python3.9：正确定位资源和版本，明确降级或阻断，由Task1/3验证。
4. 两个包内容或版本漂移、提取后依赖仓库Schema/答案：实际逐项摘要及独立解压重跑四案例证明自包含，由Task2/3验证。
5. Agent收到无规则表格、重复键及编号前导零：从实际资料建立规则并调用已安装工具，不把脚本验证冒充宿主或全客户端兼容，由Task3行为/宿主测试验证。

## 文件与接口

| 文件 | 职责/接口 |
| --- | --- |
| Skill/SKILL.md、VERSION、requirements.txt、agents/openai.yaml | 发现、最小工作流、版本与运行/UI说明；沿用M2依赖文件，不重复维护，不含平台专用权限配置。 |
| Skill/references/*.md、schema、examples | 规则构造、能力边界、实际调用、行业示例；无人工答案。 |
| Skill/scripts/runtime_info.py、doctor.py | `skill_version(base=None)->str`；`diagnose(require_xlsx=False)->dict`，只检查当前Python与资源，不安装依赖。 |
| 既有report.py/reconcile_tool.py | 新输出的执行摘要、清单与stdout附加skill_version，不改变业务判定。 |
| tools/distribution.py | `source_files(source=SOURCE)->list[Path]`、`skill_info(source=SOURCE)->(fields,body,version)`、`workbuddy_entry(fields,body,version,profile=None)->bytes`、`snapshot(source=SOURCE)->(payloads,version)`。同一过滤与版本用于构建/安装。 |
| tools/build_release.py | `build(out=None)->dict`；只发布已校验的两ZIP、SHA256SUMS、manifest.json。 |
| tools/install.py | `destination(client,scope,project=None,user_root=None)->Path`；`install(target,source=SOURCE,dry_run=False)->dict`；无覆盖模式，SKILL.md最后完整发布。 |
| tools/smoke_archive.py | `verify(release,output)->dict`；安全解压自有包，在含空格/中文独立路径运行所有案例和缺依赖模式，不导入仓库生产模块。 |
| docs/installation.md、docs/distribution.md、evidence/m5 | 六客户端目录/状态、WorkBuddy导入、SkillHub发布要求及分层证据。 |

## Task 1: 自包含技能入口与运行信息

- [x] 先写tests/test_skill.py：入口/链接/Schema/示例自包含且无expected；doctor正常和-S能力真实；新交付版本与VERSION相等。先运行确认因入口/doctor/版本字段缺失失败。
- [x] 完成最小SKILL、条件参考、Schema/原始样例字节复制、可选依赖与UI元数据；不添加基线未出现的纪律强化词条。
- [x] 实现runtime_info/doctor并把skill_version加入新执行摘要、清单与stdout；不改变旧产物或比较结果。
- [x] 运行test_skill与全部既有测试；Expected: 全绿，原始14份SHA不变。提交`feat: add portable reconciliation skill and runtime diagnostics`。

## Task 2: 可重复构建与可逆安装边界

- [x] 先写tests/test_distribution.py：两配置可重复/摘要一致/只有入口差异，中英示例等长；非法元数据、缺资源、符号链接、私密/意外文件拒绝。先确认因新构建接口缺失失败。
- [x] 先写tests/test_install.py：六客户端project/user路径；dry-run无写入；真实完整安装；已存在目标/并发内容/写入失败保护；入口最后发布。先确认因安装器缺失失败。
- [x] 实现共享选源、平台注入、双包构建和安装器，沿用已验证的身份清理机制，完整入口最后发布。
- [x] 运行分发/安装与全套；Expected: 全绿。提交`feat: build and install standard and WorkBuddy skill packages`。

## Task 3: 独立解压、真实宿主与分发记录

- [x] tests/test_archive.py先覆盖篡改摘要、路径越界/重复ZIP成员、缺资源及现有输出拒绝；先确认验包接口缺失失败。
- [x] 实现smoke_archive，独立解压两个包，分别跑doctor、四案例CLI及CSV缺依赖，核对原始人工答案/实际文件SHA；Expected: 8案例10任务均与oracle一致，-S降级明确、无仓库运行时路径依赖。
- [x] 新上下文只获原始虚构CSV与已安装Skill，完成规则构造和实际工具调用；不提供预期答案。基线已在无专用Skill下运行，只用于证明复用价值，不捏造失败。
- [ ] 在本机可用WorkBuddy/Codex实际导入/发现与调用；不自动改账号权限或发布。记录实际软件/入口/结果/失败原因，无法运行的客户端仅文档/安装验证。
- [x] 用当前官方资料维护六客户端安装矩阵及SkillHub独立发布/标识归属要求；实际账号归属须以后登录实名验证，不能预先保证slug可用。
- [ ] 全套验证、一次独立整分支只读审查、必要失败回归、生成最终releases/0.1.0与摘要；更新memory-bank/README并同步GitHub。Expected: 可下载包、证据、已验证与待验证边界一致。

## 自检

接口共用source_files/skill_info/snapshot，根版本不重复维护；资源引用基于安装后的目录。Skill主体属于工具/参考入口，不是纪律约束Skill；基线未出现失败时不做无依据的多轮措辞强化。M6发布设计、Logo/封面、公开/许可证及真人验收保持未完成。
