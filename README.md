# Starlink 情报周报自动化项目

本项目用于搭建 Starlink 技术情报周报的自动化基础链路。当前阶段只是验证自动化链路，不包含真实 Starlink 信息采集和大模型总结。

## 当前阶段目标

- 生成每周 Markdown 测试周报；
- 更新长期知识库中的最近一次自动化运行记录；
- 通过 SMTP 发送测试邮件；
- 通过 GitHub Actions 每周自动运行并提交 `docs/` 和 `weekly/` 的变化；
- 预留通过 GitHub Secrets 中的 `GITEE_REMOTE` 同步到 Gitee 的能力。

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
│   └── validate_env.py
├── docs/
│   └── starlink_knowledge_base.md
├── weekly/
│   └── .gitkeep
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
- 自动提交 `docs/` 和 `weekly/` 的变化到 GitHub。

## 配置 Gitee 同步

准备 Gitee 仓库后，在 GitHub Secrets 中配置：

```text
GITEE_REMOTE=https://用户名:私人令牌@gitee.com/用户名/仓库名.git
```

工作流运行时会添加临时 `gitee` remote 并执行 `git push gitee main`。不要把包含 Token 的 Remote 写入代码或 README 之外的真实配置文件。

## 后续扩展计划

- 接入 Starlink 官方网站、SpaceX Launches、FCC、CelesTrak、arXiv、技术博客和微信公众号白名单等信息来源；
- 增加数据去重、来源标注和结构化归档；
- 增加大模型总结、趋势分析和长期知识库自动沉淀；
- 增加失败告警、运行日志归档和更细粒度的测试。
