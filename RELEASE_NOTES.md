# Release Notes

## v0.4B：动态详情解析与失败恢复

- 新增官方详情静态预检、稳定错误类型和同域 Playwright fallback；
- 新增 `data/detail_extraction_diagnostics.json` 与逐候选脱敏诊断 CLI；
- Starlink/SpaceX 解析器升级为 v2，并分离 published/modified 日期语义；
- 历史成功 item-level 在本轮详情失败时保留，不把临时失败解释为删除；
- 区分 semantic change、parser enrichment 和 extraction failure，避免 parser 升级制造虚假 changed；
- 修复 baseline=0、LLM 当前启用状态和三层最终核心输入统计文案；
- 不新增来源，不保存完整 HTML、截图、视频、HAR 或 trace。

## v0.4A：官方条目级抽取

- 为两个既有官方索引页增加静态候选发现、详情解析和受控 Playwright fallback；
- 新增 `starlink_updates_item_v1` 与 `spacex_launches_item_v1` 模块化解析器；
- 条目 ID 只基于 `source_id + canonical_url`，内容变化不改变 ID；
- 新增 `data/item_extraction_state.json` 与 `data/item_extraction_report.json`；
- 首次成功抽取建立 baseline，历史条目不会误报为本周 new；
- 保留历史条目并使用 `seen_in_current_index` 标记当前索引可见性；
- 浏览器或详情解析失败时回退到 page-level，不阻断周报主流程；
- 周报、邮件与 Actions Summary 增加官方条目抽取诊断；
- LLM 默认关闭，item-level 优先，SpaceX 核心内容只接受 direct Starlink 相关条目；
- 未新增来源，未接入搜索引擎或第三方发射日程网站。

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

## v0.3A-llm-guarded：可选 LLM 来源约束摘要

阶段 3A 在稳定版自动化链路上增加可选 LLM 摘要模块，但默认关闭。

### 核心能力

- 新增 `scripts/llm_summarize.py`；
- 新增 `data/llm_audit.json` 记录 LLM 状态和 guardrails；
- LLM 摘要生成成功并通过校验后，输出到 `data/llm_summaries.json`；
- 周报总结版增加“大模型辅助摘要”；
- 周报明细版增加“大模型摘要审计”；
- 邮件正文和 GitHub Actions Summary 增加 LLM 状态。

### 启用边界

- LLM 默认关闭；
- 未配置 `OPENAI_API_KEY` 时自动跳过，不阻断主流程；
- ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用；
- GitHub Actions 自动调用大模型需要单独配置 OpenAI API Key。

### 来源约束

- 只基于本地结构化来源数据生成摘要；
- 无来源不写结论；
- 页面级记录不扩展成具体事实；
- 不编造发射时间、任务状态、载荷数量、技术细节或商业服务状态；
- LLM 输出与原始采集数据分离，不覆盖 `data/items.jsonl`。

### 当前局限性

- 当前仍只接入两个官方来源；
- 当前不新增第三方发射日程网站；
- 没有 API Key 时不会生成 `data/llm_summaries.json`；
- 即使启用 LLM，输出仍需通过来源约束校验后才展示。

## v0.3B-deepseek-provider：DeepSeek Provider 与受控 LLM 验证

阶段 3B 在保持 LLM 默认关闭和来源约束护栏不变的前提下，新增 DeepSeek OpenAI-compatible provider，并保留 OpenAI provider。

### 核心能力

- 默认 provider 为 `deepseek`，推荐默认模型为 `deepseek-v4-flash`，可选模型为 `deepseek-v4-pro`；
- 只有显式启用 LLM 才调用 API，启用但缺少 provider API Key 时记录 `skipped_no_api_key` 且不阻断主流程；
- `data/llm_audit.json` 增加 provider、模型和脱敏 base URL 类型；
- 周报 summary/details、邮件正文和 GitHub Actions Summary 显示 provider 与状态；
- `check_outputs.py` 与 `audit_project.py` 检查 DeepSeek 配置、输出字段和敏感信息风险。

### 安全与事实边界

- DeepSeek API Key 需要单独在 DeepSeek 平台获取；本地只写入 `.env`，GitHub Actions 只写入 GitHub Secrets；
- API Key 不得提交，也不得写入代码、文档、JSON 或日志；
- 不再使用 `deepseek-chat` 或 `deepseek-reasoner` 作为默认模型；
- LLM 摘要只基于本地结构化来源数据，无来源不写结论，页面级记录不得扩展成具体事实；
- 校验失败不覆盖旧 `data/llm_summaries.json`；
- 本阶段不新增来源，不编造 Starlink 或 SpaceX 事实。

## v0.3C-llm-dedup-actions24：LLM 去重与 Actions 现代化

阶段 3C 聚焦输入质量、变化语义、配置分级和可观测性，不新增来源，也不改变事实边界。

### 核心能力

- LLM 输入按 `source_id + normalized_url` 去重并选择每组最新记录，原始 `items.jsonl` 历史保持不变；
- 模型输出的 record IDs 与 URLs 再次稳定去重，未知引用继续由来源护栏拒绝；
- 页面 changed 与条目 changed 分开解释，页面 hash 变化不再被表述为可确认事件变化；
- 新增 `data/llm_usage.jsonl`，最多保留 200 条 provider、model、状态、去重计数、token 与耗时记录；
- 用量与审计不保存费用、API Key、完整 prompt、完整 response 或异常堆栈；
- 非敏感 LLM 配置迁移到 GitHub Variables，API Key 继续只从 GitHub Secrets 读取；
- Workflow 升级为 `actions/checkout@v5` 与 `actions/setup-python@v6`，使用 Node.js 24 对应 action 版本；
- 新增标准库 `unittest` 覆盖 URL 规范化、输入/引用去重、来源护栏和不覆盖旧摘要行为。

### 兼容与安全

- LLM 默认关闭，无 API Key 时记录 `skipped_no_api_key` 且不阻断主流程；
- 不调用真实 API 也可完成默认关闭、无 Key、dry-run 和完整周报测试；
- 不新增 Starlink 或 SpaceX 来源，不编造发射、服务或技术事实；
- 用户需在创建 Variables 后手动删除旧的非敏感 Secrets，代码不会自动修改 GitHub 仓库设置。
