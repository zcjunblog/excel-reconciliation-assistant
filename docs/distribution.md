# 分发与渠道边界

## 单一来源

`skills/excel-reconciliation-assistant/VERSION`是唯一版本源。`tools/build_release.py`从同一个明确资源集合生成通用包与WorkBuddy包，后者只改变SKILL.md的展示frontmatter。root `distribution/workbuddy.json`不允许覆盖name或version；中英文示例必须为等长、非空字符串数组。

包内包括完整工具、模板、Schema、参考和四行业原始合成样例，不含人工expected答案、用户资料、测试输出、凭证或Python缓存。每个版本目录包含两个ZIP、SHA256SUMS及逐资源manifest.json；不覆盖既有版本目录。

```sh
python3 tools/build_release.py --out "<新的构建目录>"
python3 tools/smoke_archive.py --release "<构建目录>" --output "<新的验证目录>" --python "<具备Excel依赖的Python>"
```

解压验证先校验两个完整ZIP的集合、路径、类型、大小与摘要，再在独立目录执行其中的CLI和资源。四行业5任务在每个包中与仓库外部人工oracle核对，CSV缺依赖降级及inspect分别验证；执行进程清除PYTHONPATH，不从仓库导入生产模块。校验器本身在仓库中读取原始人工答案，答案不进入技能包。

## WorkBuddy

构建成功、客户端导入、实际调用、开放平台解析、提交审核和审核上线是不同状态。M5已分别完成WorkBuddy本地导入/实际执行与Codex CLI实际调用，证据见evidence/m5。M6另行准备品牌展示、提审和发布。本地ZIP不能证明市场已接受，客户端通过也不等于全Agent客户端已实跑。

## SkillHub是独立渠道

已于2026-11-06读取官方[使用/发布指南](https://skillhub.cn/tutorials#publish-via-cli)，从旧域名skillhub.tencent.com进入后跳转skillhub.cn。公开教程说明网页、CLI和Agent均有发布入口；发布前需注册/实名认证，CLI还需本人创建的凭证。

SkillHub使用自己的slug、displayName、version、summary、license元数据，slug要求全网唯一，账号身份/实际归属需登录后核验。**WorkBuddy发布不会自动证明SkillHub已有本项目条目或归属。** 当前技能标识excel-reconciliation-assistant与GitHub作者zcjunblog已记录，但没有为该SkillHub账号预留或验证slug。

后续若选择该渠道，可以考虑带作者前缀的slug，如zcjunblog-excel-reconciliation-assistant，仍需当时检查冲突与账号归属。项目许可证尚未确定，不照抄官方示例的MIT，也不把平台专属字段直接塞进通用入口。本阶段不生成SkillHub发布包、不登录实名、不创建凭证、不上传或发布。

发布决策保留M6：确定公开范围、许可证、市场展示、真实用户验收后，再按用户授权执行各渠道提审，并记录提交/审核/上线的真实状态。
