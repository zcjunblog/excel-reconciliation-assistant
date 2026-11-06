# M5 技能封装与分发验证

日期：2026-11-06。版本：0.1.0。**M5完成：标准分发、真实Codex CLI与WorkBuddy本地导入/调用均通过。** 本记录不表示已经提审、发布市场或公开仓库。

## 安装包与运行证据

- [标准Skill ZIP](../../releases/0.1.0/excel-reconciliation-assistant-0.1.0.zip)：78,679字节。
- [WorkBuddy ZIP](../../releases/0.1.0/excel-reconciliation-assistant-workbuddy-0.1.0.zip)：79,423字节。
- [SHA256SUMS](../../releases/0.1.0/SHA256SUMS)及[逐资源清单](../../releases/0.1.0/manifest.json)：每包41份资源，只有入口展示frontmatter不同，单一VERSION。不含人工答案、评估结果、真实业务资料、凭证或缓存。
- [归档验证](archive-verification.json)：两个包均在仓库外独立路径执行，Python3.9.6/openpyxl3.1.5，共四行业×两包、10个任务；每个匹配对、非键字段集合、坐标、数量和异常同独立人工答案一致。inspect和禁用site-packages的CSV降级另验，降级没有Excel且明确partial。
- [目录安装矩阵](installation-matrix.json)：六客户端×project/user共12次隔离安装，41资源逐字节回读与dry-run无写入通过。这些目录是临时模拟项目/用户根，未写入真实客户端用户设置，不是12次宿主运行。
- [行为与实际Codex证据](behavior.json)、[宿主状态](clients.json)：已安装Skill的全新上下文、真实Codex CLI及[WorkBuddy](workbuddy.json)分别执行；11条虚构源行，2匹配对、6字段比较（4精确、1容差内、1不同）。重复/空键隔离，0007与7不同，=1+1为惰性文本，清单内10文件SHA及原件均核验。`needs_confirmation`不是“核对通过”。原始会话日志仅存忽略目录，仓库仅记录摘要和校验结果。
- [代码与测试记录](verification.json)：Python3.12.14和普通项目Python3.9.6环境完整144测试通过；原始14份M1文件字节不变，通用入口quick_validate通过。

## 真正验证到哪一层

| 层级 | 实际状态 |
| --- | --- |
| 标准入口、引用和资源 | 自包含；quick_validate通过 |
| 通用/WorkBuddy归档 | 构建、集合/摘要/大小/安全路径、独立运行通过 |
| 六客户端目录 | 官方本地surface说明核对、隔离复制/字节回读通过 |
| Codex CLI真实宿主 | 已发现安装后的Skill，doctor/inspect/run与文件交付通过 |
| WorkBuddy V5.9.3 | 解锁后取消旧候选，最终ZIP经低风险检测后导入成功，v0.1.0；新任务显式选中Skill，doctor/inspect/run完成，实际Excel预览和原行结果通过独立回读 |
| Claude Code / Cursor / Copilot CLI / Gemini CLI / OpenCode | 未做真实宿主端到端调用；不把Claude桌面版存在当作Claude Code验收 |
| SkillHub | 只读公开发布教程；未登录实名、验证账号归属/slug、创建凭证、上传或发布 |
| 市场提审/公开/跨系统办公视觉 | 未执行，留待后续阶段 |

## 行为评估与负面环境记录

无专用Skill的独立基线也完成了同一虚构案例的正确配对和字段统计，不能据此宣称安装Skill提升了通用准确率。基线自行构造比较器，报告对未给币种作了同单位假设；有Skill的记录明确为数值比较、不推定币种。本项目可证实的价值是复用确定性工具、规范交付与源定位，而非未经证明的普遍准确率提升。

首轮真实Codex测试的启动器误将venv路径resolve到系统Python，丢失openpyxl：工具正确交付MD/JSON且明确无Excel，外层会话240秒超时。该记录保留作环境诊断，不计正向通过。最终使用虚拟环境可执行入口及审查后的41份资源重新验收，原生Codex进程exit0/turn.completed、交付回读通过。全新上下文行为评估发生于审查前，其引擎/入口与最终版相同、doctor后续补强，behavior.json明确登记这一文件差别。

## 审查与修复

一次全分支独立只读审查发现6项Important，无Critical。先复现失败，再修复：深层链接目标拒绝及祖先身份检查、安装全目录集合核验并保留外来对象、只允许归档成员的相对链接、doctor完整运行模块缺失结构化阻断、执行前验证SHA256SUMS、人工oracle逐对逐字段集合核验。最终144测试通过；不以重复审查替代失败回归。

保留一项Minor：安装器最后发布的SKILL.md为0600，当前用户可读；跨系统用户/服务账号共享项目时需明确授予读权限。ZIP内入口为0644，不受此限制。审查时尚未存在的证据链接已在原定文档收尾中补齐，WorkBuddy状态在本页与安装指南按最终实际结果更新。

## 重现

```sh
python3 -m pip install -r tools/requirements-m5.txt  # 使用自己的项目虚拟环境
python3 -m unittest discover -s tests -q
python3 tools/build_release.py --out "<新的构建目录>"
python3 tools/smoke_archive.py --release "<构建目录>" --output "<新的验收目录>" --python "<项目venv的Python入口>"
```

构建/安装/交付目录均拒绝已有目标；重跑须用新目录。人工答案只被仓库验证器读取，不进入包内或提供给行为Agent。真实客户端调用不能靠以上脚本重现，须在对应客户端重新打开任务、发现技能并检查实际工具与交付。

M5已关闭；下一步M6准备正式README/白蓝封面/Logo/展示样张、跨环境与真人复核，以及许可证/公开范围和渠道决策。安装说明见[安装指南](../../docs/installation.md)，渠道边界见[分发说明](../../docs/distribution.md)。

WorkBuddy验收在用户手动解锁后继续：未跳过安全检测，也未开启全局自动安装。安装副本的41资源与最终WorkBuddy ZIP逐字节相同；原生任务显示“已完成8m29s”，结论needs_confirmation，实际预览核对结果.xlsx。根上下文再按保留的人工预期检查2匹配对/6字段/11源行、分类与坐标、所有清单文件及原表SHA。仅此本机版本和此合成任务通过，不扩展为所有宿主或业务场景的兼容承诺。
