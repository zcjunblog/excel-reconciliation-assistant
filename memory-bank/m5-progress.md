# SDD ledger — plan: memory-bank/m5-plan.md

范围：用户授权“继续M5”，沿用当前会话原生执行与阶段GitHub同步。基线d8e0d7b，分支feat/m5-distribution；不进入市场发布/账号实名。

- Pre-flight: Task1生成自包含Skill目录与单一VERSION，Task2 snapshot消费相同目录，Task3只消费解压包；引用路径不能退回仓库根。接口已对齐。
- Pre-flight: Task1仅附加交付版本，M4 CLI授权/预算/状态不变；Task2安装与构建沿用可信源和身份清理，Task3对其SHA逐项回读。
- Ruling: 沿用M2–M4同目录独立分支方式，不重试曾无响应的原生worktree；用户本轮授权是既定M5的继续执行，无须重新询问产品/实施方式。代价是同目录分支弱于独立worktree隔离。
- 基线行为：无专用Skill的新上下文已正确完成指定虚构CSV核对，11源行、2匹配对、6字段比较，重复/空键与0007/7未任意合并，文本公式惰性。没有纪律失败，不据此声称Skill能修复通用Agent的业务错误；本Skill价值是复用已测引擎、统一版本/文件交付与跨客户端资源定位。5次措辞强化微测对纯工具/参考入口不适用。
- 官方资料：已实时核对Agent Skills、Codex、Claude Code、Cursor、Copilot、Gemini CLI、OpenCode和WorkBuddy；WorkBuddy抓取工具超时后直接读取其官方HTML正文。SkillHub官网跳转skillhub.cn，公开教程已核对其独立发布、实名、全局唯一slug与许可证要求；没有登录、创建凭证或发布。
