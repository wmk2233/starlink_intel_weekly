# Starlink 情报周报自动化项目

本项目用于搭建 Starlink 技术情报周报的自动化链路。当前阶段已接入第一个真实来源：Starlink 官方 Updates 页面；仍不包含大模型总结，也不做多来源扩展。

## 当前阶段目标

- 生成每周 Markdown 测试周报；
- 更新长期知识库中的最近一次自动化运行记录；
- 通过 SMTP 发送测试邮件；
- 通过 GitHub Actions 每周自动运行并提交 `docs/` 和 `weekly/` 的变化；
- 预留通过 GitHub Secrets 中的 `GITEE_REMOTE` 同步到 Gitee 的能力。
- 阶段 2A 已接入第一个真实来源：Starlink 官方 Updates 页面。

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
│   ├── raw/
│   └── cache/
├── docs/
│   └── starlink_knowledge_base.md
├── weekly/
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

邮件正文会包含阶段 2A 说明、本次是否执行真实来源采集、采集来源名称和采集条目数量。

## 来源配置

`sources.yml` 是后续扩展来源的统一入口。当前仅启用一个来源：

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
```

阶段 2A 不应在 `sources.yml` 中启用多个来源。

## 数据结构

`data/items.jsonl` 使用 JSON Lines 格式，每行一条来源记录。核心字段包括：

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
  "content_hash": "...",
  "first_seen_at": "...",
  "last_seen_at": "...",
  "last_changed_at": "...",
  "change_status": "new",
  "previous_content_hash": null,
  "collector": "rule_based_html_v2"
}
```

`id` 由 URL 和标题生成 SHA256 前 16 位；重复采集时按 `id` upsert。阶段 2B 起，`collector` 使用 `rule_based_html_v2`。

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
- 运行 `python scripts/run_weekly.py --max-source-items 10 --max-history-records 20` 执行真实来源采集；
- 自动提交 `docs/`、`weekly/`、`data/items.jsonl`、`data/source_status.json` 和 `outputs/logs/.gitkeep` 的变化到 GitHub；
- 写入 GitHub Actions 运行摘要，展示分支、触发方式、Python 版本、更新路径和 Gitee 配置状态；
- Summary 中展示阶段 2B、来源健康状态、页面变化状态、新增/变化/未变化条目数；
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
- `weekly/YYYY-WW.md` 已生成或追加记录；
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
- 当前阶段只包含 Starlink 官方 Updates 页面这一个真实来源；
- 当前阶段不包含大模型总结，不编造 Starlink 技术事实。

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

## 后续扩展计划

- 接入 Starlink 官方网站、SpaceX Launches、FCC、CelesTrak、arXiv、技术博客和微信公众号白名单等信息来源；
- 增加数据去重、来源标注和结构化归档；
- 增加大模型总结、趋势分析和长期知识库自动沉淀；
- 增加失败告警、运行日志归档和更细粒度的测试。
