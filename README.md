# Starlink 情报周报自动化项目

本项目用于搭建 Starlink 技术情报周报的自动化链路。当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches，并将每周周报拆分为总结版与明细版；仍不包含大模型总结，也不接入第三方发射日程网站。

## 当前阶段目标

- 生成每周 Markdown 测试周报；
- 更新长期知识库中的最近一次自动化运行记录；
- 通过 SMTP 发送测试邮件；
- 通过 GitHub Actions 每周自动运行并提交 `docs/` 和 `weekly/` 的变化；
- 预留通过 GitHub Secrets 中的 `GITEE_REMOTE` 同步到 Gitee 的能力。
- 阶段 2E 已将每周输出优化为总结版、明细版和兼容索引三份 Markdown。

## 阶段 1B 工程加固

阶段 1B 只加固现有自动化链路，不实现真实 Starlink 数据采集、不接入爬虫、不接入大模型。新增内容包括：

- `validate_env.py` 增加邮箱、端口、Gitee Remote 和双等号误写检查；
- `run_weekly.py` 增加 `--max-history-records`，限制周报自动化测试记录数量；
- `send_email.py` 增加 SMTP 认证、网络连接、附件缺失等中文错误提示；
- GitHub Actions 增加并发控制、环境检查和运行摘要；
- 新增 `outputs/logs/` 目录，当前阶段只提交 `.gitkeep`，真实 `.log` 文件不提交；
- 新增 `scripts/self_check.py`，用于本地基础工程自检。

## 阶段 2A 第一个真实来源

阶段 2A 只接入一个真实来源：`https://www.starlink.com/updates`。当前阶段仍不接入大模型、不接入微信公众号、不接入 arXiv、FCC、CelesTrak 或其他来源。

采集策略是规则化网页抽取：

- 读取 `sources.yml` 中启用的来源；
- 使用 `requests` 获取 Starlink 官方 Updates 页面；
- 使用 BeautifulSoup 提取页面标题、与 `/updates` 相关的链接和页面正文片段；
- 将结构化记录 upsert 到 `data/items.jsonl`；
- 周报展示最近一次采集或数据文件中的最新记录；
- 不编造发布时间，无法确定时 `published_at` 保持为 `null`；
- 不使用大模型进行事实判断。

## 阶段 2B 变化检测

阶段 2B 在第一个真实来源基础上增加来源健康状态与 hash 变化检测。当前仍只监测 `Starlink Official Updates`，不接入大模型、不接入多个来源，也不编造 Starlink 技术事实。

变化检测分为两层：

- `page_hash`：基于页面主要文本或规范化 HTML 计算，用于判断来源页面相对上次采集是否变化；
- `content_hash`：基于条目的 `title + url + summary + evidence` 计算，用于判断单条记录内容是否变化。

`change_status` 含义：

- `new`：首次采集到；
- `changed`：记录内容 hash 或页面 hash 相比上次发生变化；
- `unchanged`：记录内容 hash 或页面 hash 未变化；
- `failed`：来源访问或采集失败。

`data/source_status.json` 记录来源最近一次健康状态和页面变化状态，核心结构包括：

```json
{
  "generated_at": "...",
  "sources": {
    "starlink_official_updates": {
      "source_id": "starlink_official_updates",
      "source_name": "Starlink Official Updates",
      "url": "https://www.starlink.com/updates",
      "health_status": "reachable",
      "change_status": "unchanged",
      "current_page_hash": "...",
      "previous_page_hash": "...",
      "items_collected": 1,
      "new_items": 0,
      "changed_items": 0,
      "unchanged_items": 1
    }
  }
}
```

## 阶段 2C SpaceX Launches 官方来源

阶段 2C 新增第二个官方来源：`https://www.spacex.com/launches`。当前 enabled sources 只有两个官方来源：

- Starlink Official Updates
- SpaceX Official Launches

采集器会默认采集 `sources.yml` 中所有 `enabled: true` 的来源，也可以通过 `--source-id` 只采集一个来源。SpaceX Launches 解析逻辑只做规则化网页抽取：

- 提取页面标题；
- 提取官方域名内与 `launch`、`mission`、`starlink` 相关的链接；
- 标准化 URL 并去重；
- 从链接文本、附近标题或 slug 生成标题；
- 无法提取具体任务条目时，生成页面级记录；
- 不编造发射时间、任务状态、载荷数量；
- 不使用第三方发射日程 API，不使用大模型。

## 阶段 2D 官方来源解析质量增强

阶段 2D 不新增来源，只增强现有两个官方来源的规则化解析质量诊断。采集器版本升级为 `rule_based_html_v4`，每条记录新增以下解析字段：

- `extracted_level`：解析层级，取值为 `page_level`、`link_level` 或 `item_level`；
- `source_quality`：解析质量，取值为 `high`、`medium` 或 `low`，只表示解析完整度；
- `extraction_confidence`：解析置信度，范围为 0 到 1，但不会输出 1.0；
- `matched_keywords`：命中的来源相关关键词；
- `candidate_links`：最多 5 个当前官方来源域名内的候选链接；
- `extraction_notes`：中文解析说明，不包含密钥，也不补写事实；
- `parser_version`：当前为 `rule_based_html_v4`。

阶段 2D 会维护 `data/extraction_quality.json`，并把每个来源的主导解析层级、主导解析质量、平均置信度、候选链接数同步写入 `data/source_status.json`。这些质量指标只描述当前规则解析结果，不代表事实可信度、任务重要性或技术结论。

## 阶段 2E 周报双文档输出

阶段 2E 不新增来源、不接入大模型，只优化每周 Markdown 输出结构。默认运行会生成三份文档：

- `weekly/YYYY-WW-summary.md`：总结版，适合老师、同学和组会快速阅读；
- `weekly/YYYY-WW-details.md`：明细版，适合来源复查、结构化数据核验和知识库维护；
- `weekly/YYYY-WW.md`：兼容索引，指向总结版和明细版，避免旧路径失效。

总结版不会展示完整 hash、过长 evidence 或完整 candidate_links。明细版会保留 record id、hash、解析层级、解析质量、候选链接和截断后的证据片段。兼容索引不再无限追加完整周报内容。

## 项目结构

```text
E:\starlink_intel_weekly
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── sources.yml
├── scripts/
│   ├── __init__.py
│   ├── collect_sources.py
│   ├── run_weekly.py
│   ├── send_email.py
│   ├── validate_env.py
│   └── self_check.py
├── data/
│   ├── items.jsonl
│   ├── source_status.json
│   ├── extraction_quality.json
│   ├── raw/
│   └── cache/
├── docs/
│   └── starlink_knowledge_base.md
├── weekly/
│   ├── YYYY-WW-summary.md
│   ├── YYYY-WW-details.md
│   ├── YYYY-WW.md
│   └── .gitkeep
├── outputs/
│   └── logs/
│       └── .gitkeep
└── .github/
    └── workflows/
        └── weekly.yml
```

## 本地运行方式

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

只生成 Markdown 和更新知识库，不发送邮件：

```powershell
python scripts/run_weekly.py --no-email
```

演练执行流程，不写文件、不发送邮件：

```powershell
python scripts/run_weekly.py --dry-run
```

检查环境变量配置：

```powershell
python scripts/validate_env.py
```

执行基础工程自检：

```powershell
python scripts/self_check.py
```

限制本周周报最多保留 20 条自动化测试记录：

```powershell
python scripts/run_weekly.py --no-email --max-history-records 20
```

阶段 1B 推荐本地测试命令：

```powershell
python scripts/validate_env.py
python scripts/run_weekly.py --dry-run
python scripts/run_weekly.py --no-email --max-history-records 20
python scripts/self_check.py
python -m py_compile scripts\run_weekly.py scripts\send_email.py scripts\validate_env.py scripts\self_check.py
```

阶段 2A 采集 Starlink 官方 Updates 页面：

```powershell
python scripts/collect_sources.py --source-id starlink_official_updates --limit 10
```

采集 dry-run，不写入 `data/items.jsonl`：

```powershell
python scripts/collect_sources.py --source-id starlink_official_updates --dry-run
```

运行完整流程但不发送邮件：

```powershell
python scripts/run_weekly.py --no-email --max-source-items 10
```

阶段 2B 推荐变化检测命令：

```powershell
python scripts/collect_sources.py --source-id starlink_official_updates --limit 10
python scripts/collect_sources.py --source-id starlink_official_updates --dry-run --limit 10
python scripts/run_weekly.py --no-email --max-source-items 10 --max-history-records 20
```

阶段 2C 推荐命令：

```powershell
python scripts/collect_sources.py --limit 10
python scripts/collect_sources.py --source-id spacex_official_launches --limit 10
python scripts/collect_sources.py --source-id spacex_official_launches --dry-run --limit 10
python scripts/run_weekly.py --no-email --max-source-items 10 --max-history-records 20
```

阶段 2D 推荐解析质量测试命令：

```powershell
python scripts/collect_sources.py --source-id starlink_official_updates --dry-run --limit 10
python scripts/collect_sources.py --source-id spacex_official_launches --dry-run --limit 10
python scripts/collect_sources.py --limit 10
python scripts/run_weekly.py --no-email --max-source-items 10 --max-history-records 20
python scripts/print_action_summary.py
```

阶段 2E 推荐双文档输出命令：

```powershell
python scripts/run_weekly.py --no-email --max-source-items 10 --max-history-records 20
```

指定输出模式：

```powershell
python scripts/run_weekly.py --no-email --output-mode dual
python scripts/run_weekly.py --no-email --output-mode legacy
python scripts/run_weekly.py --no-email --output-mode both
```

`--output-mode` 说明：

- `dual`：默认模式，生成总结版、明细版和兼容索引；
- `legacy`：仅更新旧版 `weekly/YYYY-WW.md`，不会删除已有总结版和明细版；
- `both`：生成总结版、明细版和兼容索引，并在兼容索引中附带较完整摘要。

## 配置 `.env`

本项目不会提交真实 `.env`。本地测试邮件发送前，可以参考 `.env.example` 手动创建 `.env`：

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_email_authorization_code
MAIL_FROM=your_email@example.com
MAIL_TO=target_email@example.com
GITEE_REMOTE=https://username:token@gitee.com/username/starlink_intel_weekly.git
```

`.env` 已加入 `.gitignore`，不要把邮箱授权码、Token 或密码提交到仓库。

注意 `.env` 中每一行只能有一个等号，例如：

```env
SMTP_USER=your_email@example.com
```

不要误写成：

```env
SMTP_USER==your_email@example.com
```

## 测试邮件发送

配置 `.env` 后运行：

```powershell
python scripts/run_weekly.py
```

脚本会生成或追加本周周报，更新长期知识库，并把 Markdown 正文和附件通过 SMTP 发送到 `MAIL_TO`。

邮件正文会包含阶段 2E 说明、本次是否执行真实来源采集、已接入来源数量、解析质量概览，以及两个来源的可达性、页面变化状态和条目统计。邮件会同时附带：

- `YYYY-WW-summary.md`
- `YYYY-WW-details.md`

兼容索引 `YYYY-WW.md` 默认不作为邮件附件发送。

## 来源配置

`sources.yml` 是后续扩展来源的统一入口。当前仅启用两个官方来源：

```yaml
sources:
  - id: starlink_official_updates
    name: Starlink Official Updates
    source_type: official
    reliability_tier: S
    language: en
    category: official_updates
    url: https://www.starlink.com/updates
    enabled: true
  - id: spacex_official_launches
    name: SpaceX Official Launches
    source_type: official
    reliability_tier: S
    language: en
    category: official_launches
    url: https://www.spacex.com/launches
    enabled: true
```

阶段 2C 不应在 `sources.yml` 中启用第三方来源、中文来源、arXiv、FCC、CelesTrak 或其他来源。

## 数据结构

`data/items.jsonl` 使用 JSON Lines 格式，每行一条来源记录，支持多个来源混合存储。核心字段包括：

```json
{
  "id": "稳定哈希ID",
  "source_id": "starlink_official_updates",
  "source_name": "Starlink Official Updates",
  "source_type": "official",
  "reliability_tier": "S",
  "category": "official_updates",
  "language": "en",
  "title": "...",
  "url": "...",
  "published_at": null,
  "fetched_at": "...",
  "http_status": 200,
  "tags": ["starlink", "official", "updates"],
  "summary": "...",
  "evidence": "...",
  "extracted_level": "page_level",
  "source_quality": "low",
  "extraction_confidence": 0.35,
  "matched_keywords": ["starlink"],
  "candidate_links": [],
  "extraction_notes": "页面可达，但当前静态规则未识别到稳定的独立条目；保留页面级记录，不补写发布时间或技术事实。",
  "parser_version": "rule_based_html_v4",
  "content_hash": "...",
  "first_seen_at": "...",
  "last_seen_at": "...",
  "last_changed_at": "...",
  "change_status": "new",
  "previous_content_hash": null,
  "collector": "rule_based_html_v4"
}
```

`id` 由 URL 和标题生成 SHA256 前 16 位；重复采集时按 `id` upsert。阶段 2D 起，`collector` 和 `parser_version` 使用 `rule_based_html_v4`。

`data/source_status.json` 中的 `sources` 会同时维护两个来源的状态，例如 `starlink_official_updates` 和 `spacex_official_launches`，每个来源独立记录页面 hash、健康状态、变化状态、条目统计和解析质量摘要。

`data/extraction_quality.json` 记录每个来源的解析质量诊断，核心字段包括：

```json
{
  "parser_version": "rule_based_html_v4",
  "sources": {
    "starlink_official_updates": {
      "dominant_extracted_level": "page_level",
      "dominant_source_quality": "low",
      "average_confidence": 0.35,
      "candidate_links_total": 0,
      "items_collected": 1
    }
  }
}
```

## 配置 GitHub Secrets

在 GitHub 仓库的 `Settings` → `Secrets and variables` → `Actions` 中添加：

```text
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
MAIL_FROM
MAIL_TO
GITEE_REMOTE
```

其中 `GITEE_REMOTE` 可以暂时不配置。未配置时，GitHub Actions 会跳过 Gitee 同步。

## 配置 GitHub Actions

工作流文件位于 `.github/workflows/weekly.yml`，支持：

- 手动触发：`workflow_dispatch`；
- 每周自动触发：每周一 00:17 UTC，对应北京时间 08:17、日本时间 09:17；
- 使用 Python 3.11 安装依赖并运行 `python scripts/run_weekly.py`；
- 运行 `python scripts/validate_env.py` 做 Secrets 格式检查；
- 运行 `python scripts/run_weekly.py --output-mode dual --max-source-items 10 --max-history-records 20` 执行真实来源采集和双文档输出；
- 自动提交 `docs/`、`weekly/`、`data/items.jsonl`、`data/source_status.json`、`data/extraction_quality.json` 和 `outputs/logs/.gitkeep` 的变化到 GitHub；
- 写入 GitHub Actions 运行摘要，展示分支、触发方式、Python 版本、更新路径和 Gitee 配置状态；
- Summary 中展示阶段 2E、三个周报输出路径、所有来源的健康状态、页面变化状态、新增/变化/未变化条目数和解析质量表；
- 使用 `concurrency` 避免同一分支上多个 weekly workflow 同时运行。

## GitHub Actions 手动运行

1. 打开 GitHub 仓库页面；
2. 进入 `Actions`；
3. 选择 `Starlink Weekly Automation`；
4. 点击 `Run workflow`；
5. 选择 `main` 分支并运行；
6. 运行结束后检查 Summary、邮件收件箱、GitHub 自动提交和 Gitee 同步结果。

## 配置 Gitee 同步

准备 Gitee 仓库后，在 GitHub Secrets 中配置：

```text
GITEE_REMOTE=https://用户名:私人令牌@gitee.com/用户名/仓库名.git
```

工作流运行时会添加临时 `gitee` remote 并执行 `git push gitee main`。不要把包含 Token 的 Remote 写入代码或 README 之外的真实配置文件。

如果 Gitee 私人令牌中包含 `@`、`:`、`/`、`#`、`?`、`&` 等特殊字符，需要先做 URL 编码，再写入 GitHub Secrets 的 `GITEE_REMOTE`。

## 部署成功验证清单

- GitHub Actions 手动运行成功；
- 邮件已发送到 `MAIL_TO`；
- `weekly/YYYY-WW-summary.md` 与 `weekly/YYYY-WW-details.md` 已生成；
- `weekly/YYYY-WW.md` 已作为兼容索引或 legacy 输出保留；
- `docs/starlink_knowledge_base.md` 已更新最近一次自动化运行记录；
- GitHub 自动生成 `chore: update weekly Starlink automation output` 提交；
- Gitee 仓库同步到最新 `main`；
- 本地执行 `git pull --rebase origin main` 后保持同步。

## 日志目录

`outputs/logs/` 用于后续保存本地运行日志。当前阶段暂不主动写入日志文件，只提交 `outputs/logs/.gitkeep` 以保留目录。`.gitignore` 已忽略 `outputs/logs/*.log`，真实日志文件不应提交。

`data/raw/` 和 `data/cache/` 用于本地原始网页和缓存，已被 `.gitignore` 忽略。默认采集不保存原始 HTML；如需本地调试可使用 `--save-raw`，但 raw 文件不提交。

## 常见问题排查

### SMTP 535 authentication failed

通常是授权码错误、SMTP 服务未开启、发件账号错误或邮箱服务商拦截。请重新生成邮箱 SMTP 授权码，确认 `SMTP_USER` 是发件邮箱账号，并运行：

```powershell
python scripts/validate_env.py
```

### `.env` 中误写双等号

如果写成 `SMTP_USER==xxx@example.com`，程序会读到以 `=` 开头的值。请改为单等号写法，并重新运行 `validate_env.py`。

### GitHub push 认证失败

GitHub HTTPS 不支持账号密码推送。请使用 Git Credential Manager 完成浏览器认证，或使用 GitHub 官方推荐的凭据方式。不要把 Token 写进 remote URL 或命令行。

### GitHub 走代理问题

如果 push 或 Actions 拉取依赖失败，先检查本机代理、Git 代理配置和网络连通性。不要为了排查网络问题在命令里拼接任何密码或 Token。

### Actions 自动 commit 权限不足

确认工作流包含：

```yaml
permissions:
  contents: write
```

同时检查仓库 Settings 中 Actions 的 workflow permissions 是否允许写入。

### Gitee 同步失败

确认 `GITEE_REMOTE` Secret 使用可推送的 HTTPS Remote 或 SSH Remote，并且 Gitee 仓库存在、令牌具备写权限。日志中不要输出完整 Remote。

### GITEE_REMOTE Token 特殊字符

HTTPS Remote 中的 Token 如果包含特殊字符，需要 URL 编码。例如 `@` 应编码为 `%40`。

## 安全边界

- `.env` 不得提交；
- `prompts/` 不提交；
- SMTP 授权码和 Gitee Token 只放在本地 `.env` 或 GitHub Secrets；
- 不要在命令行、日志、README 或代码中写入真实密钥；
- 当前阶段只包含两个官方来源：Starlink Official Updates 与 SpaceX Official Launches；
- 当前阶段不包含大模型总结，不编造 Starlink 或 SpaceX 发射事实；
- 当前阶段不使用第三方发射日程 API。

## 阶段 2A 局限性

- 不使用大模型；
- 不编造发布时间；
- 不保证动态渲染页面能完全解析；
- 只接入一个官方来源；
- 后续阶段再接入 SpaceX Launches、FCC、CelesTrak、arXiv 和中文来源。

## 阶段 2B 局限性

- hash 变化不等于事实变化；
- 页面由 JavaScript 动态渲染时仍可能只能生成页面级记录；
- 当前不使用大模型；
- 当前不做跨来源事实核验；
- 当前仍只接入一个官方来源。

## 阶段 2C 局限性

- 不使用大模型；
- 不编造发射时间、任务状态、载荷数量；
- 不使用第三方发射日程 API；
- 动态渲染页面可能只能生成页面级记录；
- hash 变化不等于事实变化；
- 当前只接入两个官方来源。

## 阶段 2D 局限性

- 不使用大模型；
- 不新增来源；
- 不编造发射事实、技术事实或发布时间；
- 解析质量只描述规则解析完整度，不代表事实可信度；
- 动态渲染页面仍可能只能生成页面级或链接级记录；
- 当前只处理 Starlink Official Updates 与 SpaceX Official Launches。

## 阶段 2E 局限性

- 总结版不等于人工研判报告；
- 明细版中的 hash 变化不等于事实变化；
- 页面级记录不应直接当作具体情报事实；
- 当前不使用大模型；
- 当前不编造事实；
- 当前不新增来源，不接入第三方发射日程网站。

## 后续扩展计划

- 接入 Starlink 官方网站、SpaceX Launches、FCC、CelesTrak、arXiv、技术博客和微信公众号白名单等信息来源；
- 增加数据去重、来源标注和结构化归档；
- 增加大模型总结、趋势分析和长期知识库自动沉淀；
- 增加失败告警、运行日志归档和更细粒度的测试。
