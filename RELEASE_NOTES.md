# Release Notes

## v0.2G-stable：官方来源自动化周报稳定版

阶段 2G 是进入大模型摘要阶段前的稳定版整理。目标是让当前自动化链路可长期运行、可复查、可交接，并明确安全边界。

### 核心能力

- 每周自动采集已启用官方来源；
- 记录来源健康状态、页面 hash 变化和条目变化状态；
- 生成总结版、明细版和兼容索引三类周报；
- 维护 `weekly/index.md` 历史周报入口；
- 维护 `data/weekly_manifest.json` 和 `data/run_history.jsonl`；
- 发送带 summary 与 details 双附件的邮件；
- GitHub Actions 自动运行、自动质量检查、自动提交；
- Gitee 同步支持 3 次重试，失败不阻断 GitHub 主流程；
- 新增项目稳定性与配置审计。

### 已接入来源

当前只启用两个官方来源：

- `Starlink Official Updates`：Starlink 官方更新页面；
- `SpaceX Official Launches`：SpaceX 官方发射页面。

未接入第三方发射日程网站、微信公众号、arXiv、FCC 或 CelesTrak。

### 自动化输出

- `weekly/YYYY-WW-summary.md`：面向快速阅读的总结版；
- `weekly/YYYY-WW-details.md`：面向复查的明细版；
- `weekly/YYYY-WW.md`：兼容索引；
- `weekly/index.md`：历史周报总索引；
- `docs/starlink_knowledge_base.md`：长期知识库。

### 数据文件

- `data/items.jsonl`：来源记录；
- `data/source_status.json`：来源健康状态与页面变化；
- `data/extraction_quality.json`：解析质量诊断；
- `data/weekly_manifest.json`：周报输出清单；
- `data/run_history.jsonl`：自动化运行历史。

### GitHub Actions

- workflow 名称为 `Starlink Weekly Automation`；
- 支持手动触发；
- 定时规则为每周一 UTC 00:17；
- 对应北京时间每周一 08:17、日本时间每周一 09:17；
- 主流程包括依赖安装、环境检查、周报生成、输出质量检查、项目审计、GitHub 自动提交和 Gitee 同步。

### 邮件发送

- SMTP 配置全部来自环境变量或 GitHub Secrets；
- 邮件正文说明当前为自动化链路测试与官方来源规则化抽取；
- 邮件附件包含总结版和明细版；
- 不发送 `.env`、raw HTML 或 cache 文件。

### Gitee 同步

- `GITEE_REMOTE` 从 GitHub Secrets 读取；
- 未配置时跳过；
- 配置后最多重试 3 次；
- 失败时输出 warning，并记录 Summary 状态；
- 失败不会阻断 GitHub 主流程。

### 质量检查

- `scripts/check_outputs.py --strict` 检查周报与数据文件完整性；
- `scripts/audit_project.py --strict` 检查仓库结构、workflow、sources、数据文件、weekly 输出、邮件附件能力和敏感信息风险；
- GitHub Actions 已将两项检查作为质量门禁。

### 安全边界

- 不提交 `.env`；
- 不提交 `prompts/`；
- 不提交真实 SMTP 授权码；
- 不提交真实 Gitee Token；
- 不在日志中打印完整 `GITEE_REMOTE`；
- 当前不使用大模型；
- 当前不编造 Starlink 或 SpaceX 事实。

### 当前局限性

- 当前两个官方来源多数记录仍为 `page_level / low`，表示静态规则只能稳定生成页面级记录；
- 页面级记录不等于具体情报事实；
- hash 变化不等于事实变化；
- 解析质量只表示抽取完整度，不代表事实可信度；
- 当前不做跨来源事实核验；
- 当前不使用大模型总结。

### 后续计划

- 阶段 3A 才考虑引入大模型摘要；
- 引入大模型前，需要继续保持事实、推断和待核验内容的边界；
- 后续新增来源前，需要先更新来源配置、审计脚本、文档和安全边界。
