# SDD ledger — plan: memory-bank/m5-plan.md

范围：用户授权“继续M5”，沿用当前会话原生执行与阶段GitHub同步。基线d8e0d7b，分支feat/m5-distribution；不进入市场发布/账号实名。

- Pre-flight: Task1生成自包含Skill目录与单一VERSION，Task2 snapshot消费相同目录，Task3只消费解压包；引用路径不能退回仓库根。接口已对齐。
- Pre-flight: Task1仅附加交付版本，M4 CLI授权/预算/状态不变；Task2安装与构建沿用可信源和身份清理，Task3对其SHA逐项回读。
- Ruling: 沿用M2–M4同目录独立分支方式，不重试曾无响应的原生worktree；用户本轮授权是既定M5的继续执行，无须重新询问产品/实施方式。代价是同目录分支弱于独立worktree隔离。
- 基线行为：无专用Skill的新上下文已正确完成指定虚构CSV核对，11源行、2匹配对、6字段比较，重复/空键与0007/7未任意合并，文本公式惰性。没有纪律失败，不据此声称Skill能修复通用Agent的业务错误；本Skill价值是复用已测引擎、统一版本/文件交付与跨客户端资源定位。5次措辞强化微测对纯工具/参考入口不适用。
- 官方资料：已实时核对Agent Skills、Codex、Claude Code、Cursor、Copilot、Gemini CLI、OpenCode和WorkBuddy；WorkBuddy抓取工具超时后直接读取其官方HTML正文。SkillHub官网跳转skillhub.cn，公开教程已核对其独立发布、实名、全局唯一slug与许可证要求；没有登录、创建凭证或发布。
- Task 1: complete — bb4d380；4项新入口/资源/doctor/安装副本版本测试先失败，实施后全套120测试通过；quick_validate已通过。开发验证工具缺PyYAML时仅装到忽略目录tmp/m5-validator-deps，未写全局或打入包。
- Task2实施调整：M2已有requirements.txt作为Excel可选依赖声明，删除Task1新增重复的requirements-optional.txt，继续使用原文件。构建与安装采用同一精确资源集合；先出现的未登记资源拒绝证明了收集检查生效。
- Task2自测：源根链接在提前resolve后绕过检查、入口发布后被替换的inode可能被误认，两项均先补失败回归并修复；主逻辑不认领其他写入者对象。完整入口通过独占硬链接最后发布，底层文件系统不支持该操作时明确失败，仍可按官方目录手动完整复制。
- Task 2: complete — cbe682b；单一选源、确定性双包、六客户端目录与安装保护，全套131测试通过。
- Task3自测：独立解压/校验新增4项，普通Python3.9虚拟环境完成双包四行业10任务及-S降级；解释器resolve丢失venv和相对解释器切换cwd问题已先复现后修复。发布过程中早期ZIP被修改、安装资源在入口发布前被修改两项先出现失败后补逐项回读；完整137测试通过。
- 真实Codex CLI正向测试已结束(exit0，turn.completed)，使用已安装Skill与指定项目venv，产出Excel和needs_confirmation结果。此前误用解析后的base Python正确降级但外层超时，不计作正向客户端通过。新上下文有Skill/无Skill均正确完成该虚构案例，不声称相对准确率提升。
- WorkBuddy：已选择候选ZIP进入导入，Mac随后锁定；未观察到导入成功，等待用户解锁，不将候选构建冒充平台接受。
- Final review：一次新上下文整分支只读审查发现6项Important、2项Minor，无Critical。6项均确认进入一次修复通道：完整祖先路径校验/物理身份检查，安装完整资源集合与外来对象保护，归档成员相对链接，全运行模块doctor且缺runtime_info也结构化阻断，SHA256SUMS在执行前验证，人工oracle逐对/逐字段集合核验。已观察6组新增回归先失败，修复后聚焦用例通过；CLI链接项目路径的结构化错误补充先失败后修复。
- Final: minor (deferred): 安装器入口硬链接保持0600（普通文件0644），当前同用户本地Agent运行可读；共享项目由其他系统用户/服务账号加载需手动授予读权限。暂不改权限默认，代价是跨账号共享入口不可读；ZIP归档入口0644，不受影响。
- Final: minor (planned documentation): 审查时尚未生成的M5证据链接与WorkBuddy措辞，按原Task3收尾补齐；不是功能修复或未执行的宿主通过声明。
- Final: Ruling: WorkBuddy导入/调用待判定 — 等待用户手动解锁后再观察，不把锁定前选择ZIP当成功 — 代价是M5客户端门禁暂不能完成。
- Final: Ruling: 其余五客户端宿主与跨系统显示未判定 — 只记录目录安装/官方资料，不扩大兼容结论 — 代价是仍需各目标环境实测。
- Final: Ruling: SkillHub归属/slug/发布未判定 — 按M5范围只核对公开要求，账号及发布留M6授权 — 代价是将来可能存在标识冲突。
- Final: Ruling: 最终包/证据/远端同步在审查时未判定 — 本轮修复后生成并核对，不预先计为完成 — 代价是最终摘要若漂移须重跑。
- Final: fixed 祖先链接/项目提前解析 — test_deep_ancestor_symlinks_are_rejected_before_dest_or_project_resolution及CLI结构化错误回归RED→GREEN，suite144/144。
- Final: fixed 外来安装资源 — test_foreign_file_directory_or_link_blocks_complete_install_and_survives_cleanup（入口前后×文件/目录/链接）RED→GREEN，suite144/144。
- Final: fixed 绝对/缓存资源引用 — test_links_must_be_relative_to_resources_that_are_actually_packaged RED→GREEN，suite144/144。
- Final: fixed doctor缺模块仍ready/traceback — test_missing_runtime_modules_always_produce_structured_blocked（三模块）RED→GREEN，suite144/144；完整模块名单复用同一RUNTIME_MODULES供构建选源。
- Final: fixed 摘要列表未验证 — test_missing_wrong_duplicate_or_extra_sha256sums_block_before_execution RED→GREEN，suite144/144。
- Final: fixed 人工oracle丢失配对/字段集合 — test_oracle_verifies_exact_pairs_and_full_field_set_not_separate_row_sets RED→GREEN，suite144/144。
- 最终复核：144测试分别在Python3.12.14与普通项目Python3.9.6/openpyxl3.1.5通过；quick_validate通过。最终releases/0.1.0双包为78,679/79,423字节；标准SHA9261bacbfee7e0614d33e15fafc29a59b1c083a7f8d7775fba1db93ab2c8d37f，WorkBuddy SHA86426ae73a0e1f68c768bec5eda4406ecf0316a139f1f96a34012ad737eab637。
- 最终包独立解压Python3.9重跑10任务、inspect和-S CSV降级通过，原始14份字节未变；六客户端12次隔离安装全部重新验证。
- 最终真实Codex CLI：再次使用审查后41份安装资源，原生turn.completed、进程exit0；2匹配对/6字段/11源行、两处非exact的坐标和差额、待确认分区、10份交付文件SHA、Excel惰性文本与原件摘要均由根上下文独立回读。此前forward行为测评仅doctor与最终版本不同，已在证据如实登记；不重写旧日志。
- Task3状态：核心实施与审查已完成，WorkBuddy最终包导入/实际调用仍等待手动解锁。保持Task3与M5未完成，不运行task-done伪造通过；保留本计划工作区供解锁后续验收。最终包、文档和证据先同步feat/m5-distribution分支，待客户端门禁通过后再合入main。
- 解锁后续验收：取消待安装旧候选，选择releases/0.1.0最终WorkBuddy ZIP；等待安全检测完成（低风险），未跳过、未开启全局自动安装。原生UI“技能导入成功”、已安装v0.1.0。
- 最终WorkBuddy真实新任务：显式技能标签，限定workbuddy-project两CSV与技能资源，实际doctor/inspect/run、文件校验和调用记录完成。原生UI“已完成8m29s”、needs_confirmation、真实Excel预览。根上下文对安装副本41资源与最终ZIP逐字节对照；10交付文件SHA、2匹配对/6字段/11源行、两处非exact坐标、前导零/惰性文本、原件摘要全部通过，证据evidence/m5/workbuddy.json。
- 原锁定门禁已解除；其他五宿主/跨系统、SkillHub账号归属和发布仍按既有边界保留M6。没有新增功能或再次独立审查；已审查修复的生产代码与最终包不变。
- Task 3: complete — 实施提交cbe682b..129ace2及本次客户端/资料收尾；task-done全套144/144通过。一次独立整分支审查6项Important均有RED→GREEN证据，最终包与审查后生产代码摘要一致。按既有阶段同步授权合入main并推送；不新建市场提交或改仓库可见性。
