# 安装与客户端验证

标准技能遵循[Agent Skills规范](https://agentskills.io/specification)。同一目录包含SKILL.md、Python工具、模板、Schema、四行业合成输入/规则与VERSION；无需模型API密钥。能否执行文件取决于宿主能力，安装成功不等于客户端全流程通过。

## 下载与手动安装

通用包：`releases/0.1.4/excel-reconciliation-assistant-0.1.4.zip`。先按同目录SHA256SUMS核对摘要，再解压，将其中**整个excel-reconciliation-assistant目录**放到所选技能根目录。结果应是`<技能根>/excel-reconciliation-assistant/SKILL.md`，不要只复制入口文件或额外多套一层文件夹。

下表于2026-11-06按各官方说明核对；只列本工具选择的本地目录，不代表所有远程/云端surface都会同步本机个人技能。

| 客户端/本地surface | 项目技能根 | 用户技能根 | 官方依据 |
| --- | --- | --- | --- |
| Codex | `.agents/skills` | `~/.agents/skills` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code本地会话 | `.claude/skills` | `~/.claude/skills` | [Claude Code skills](https://code.claude.com/docs/en/skills) |
| Cursor本地Agent | `.cursor/skills` | `~/.cursor/skills` | [Cursor skills](https://cursor.com/docs/skills) |
| GitHub Copilot CLI | `.github/skills` | `~/.copilot/skills` | [Copilot CLI skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| Gemini CLI | `.gemini/skills` | `~/.gemini/skills` | [Gemini skills](https://geminicli.com/docs/cli/skills/) |
| OpenCode | `.opencode/skills` | `~/.config/opencode/skills` | [OpenCode skills](https://opencode.ai/docs/skills/) |

部分客户端也认`.agents/skills`别名；本工具按表中明确目录安装，不同时复制多个同名副本。Claude云会话/Cowork、Cursor Cloud、Copilot cloud等有各自同步/加载范围，应按对应官方surface设置，不推断本地个人目录已在云端生效。

## 项目内安装工具

克隆本仓库后，可先看目标位置，再安装：

```sh
python3 tools/install.py --client codex --scope project --project "<项目目录>" --dry-run
python3 tools/install.py --client codex --scope project --project "<项目目录>"
```

客户端参数：`codex`、`claude`、`cursor`、`copilot`、`gemini`、`opencode`；`generic`选择`.agents/skills`。用户范围用`--scope user`，不传`--project`。自定义技能根用`--dest "<技能根目录>"`，工具会追加技能名；不能与client/project/user范围混用。`--source`可指定已解压的通用技能目录。

工具先验证资源与引用、复制并核对摘要，最后独占发布完整SKILL.md；已有同名目录（即使为空）拒绝覆盖。需升级时先保留现有版本并明确处理安装位置，本工具不自动删除或覆盖。客户端根目录含链接时请明确选择预期的真实位置；不支持独占入口发布的文件系统会明确失败，可按官方方式完整复制技能目录。工具不改模型、账号、权限或客户端设置。

## WorkBuddy

使用`excel-reconciliation-assistant-workbuddy-0.1.4.zip`。本机V5.9.3入口为“专家·技能·连接器 → 技能 → 添加技能 → 上传技能 → 选择 ZIP 文件”。当前本机V5.9.3已完成最终0.1.0包导入和真实任务验收，证据见M5记录。检查导入结果和技能名/版本，再在新任务中通过`/`技能菜单或明确名称调用。

此包注入[WorkBuddy官方元数据](https://open.workbuddy.cn/docs/skill)：中文/英文展示名、介绍、作者、版本及等长非空中英示例。为满足市场两级目录限制，行业样例平铺到references/，四份规则相对文件名与样例索引链接同步调整；核对引擎、Skill正文、原始表格字节和业务规则不变。客户端本地导入、市场解析、提交审核与上线分别记录；当前已获市场提审授权，实际进度见[发布记录](release-readiness.md)。

## 运行环境

安装后先用实际解释器运行技能目录下`scripts/doctor.py`；需要Excel时加`--require-xlsx`。Python3.9+可执行CSV核对和完整MD/JSON交付；XLSX需要该解释器中的`openpyxl>=3.1,<4`。选择虚拟环境时保留其可执行入口路径，不能因解析可执行文件链接而误用基础系统解释器。

依赖缺失时先复用工作区已有环境，必要时按授权在项目虚拟环境安装`requirements.txt`。不改全局Python，不把开发机运行时路径写进Skill。没有文件执行能力的客户端只能解释已提供样本，不能声称已核对全部文件或交付Excel。

重新打开任务并查看技能列表，再做一次实际文件调用。六客户端目录布局的隔离安装验证、独立ZIP脚本验证及真实宿主验证分别记录在[M5证据](../evidence/m5/README.md)，以该记录中的实际状态为准。

当前0.1.4包含MIT许可证并更新VERSION，标准包核对引擎和Skill正文与0.1.0逐字节一致；WorkBuddy包另将样例平铺到references/，同步调整样例索引及规则相对文件名以满足市场两级目录限制，业务规则和原表不变。旧版客户端实跑证据保留原版本；新版安装包单独验包，不把平台解析或旧版宿主测试冒充新版实际调用。
