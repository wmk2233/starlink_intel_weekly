# Starlink 情报周报自动化项目

本项目用于搭建 Starlink 技术情报周报的自动化基础链路。当前阶段只是验证自动化链路，不包含真实 Starlink 信息采集和大模型总结。

## 当前阶段目标

- 生成每周 Markdown 测试周报；
- 更新长期知识库中的最近一次自动化运行记录；
- 通过 SMTP 发送测试邮件；
- 通过 GitHub Actions 每周自动运行并提交 `docs/` 和 `weekly/` 的变化；
- 预留通过 GitHub Secrets 中的 `GITEE_REMOTE` 同步到 Gitee 的能力。

## 阶段 1B 工程加固

阶段 1B 只加固现有自动化链路，不实现真实 Starlink 数据采集、不接入爬虫、不接入大模型。新增内容包括：

- `validate_env.py` 增加邮箱、端口、Gitee Remote 和双等号误写检查；
- `run_weekly.py` 增加 `--max-history-records`，限制周报自动化测试记录数量；
- `send_email.py` 增加 SMTP 认证、网络连接、附件缺失等中文错误提示；
- GitHub Actions 增加并发控制、环境检查和运行摘要；
- 新增 `outputs/logs/` 目录，当前阶段只提交 `.gitkeep`，真实 `.log` 文件不提交；
- 新增 `scripts/self_check.py`，用于本地基础工程自检。

## 项目结构

```text
E:\starlink_intel_weekly
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── scripts/
│   ├── __init__.py
│   ├── run_weekly.py
│   ├── send_email.py
│   ├── validate_env.py
│   └── self_check.py
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
- 自动提交 `docs/`、`weekly/` 和 `outputs/logs/.gitkeep` 的变化到 GitHub；
- 写入 GitHub Actions 运行摘要，展示分支、触发方式、Python 版本、更新路径和 Gitee 配置状态；
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
- 当前阶段仍不包含真实 Starlink 信息采集和大模型总结。

## 后续扩展计划

- 接入 Starlink 官方网站、SpaceX Launches、FCC、CelesTrak、arXiv、技术博客和微信公众号白名单等信息来源；
- 增加数据去重、来源标注和结构化归档；
- 增加大模型总结、趋势分析和长期知识库自动沉淀；
- 增加失败告警、运行日志归档和更细粒度的测试。
