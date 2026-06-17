# Starlink 情报周报自动化部署检查清单

本清单用于阶段 2G 稳定版部署前复查。当前系统只验证官方来源自动化周报链路，不包含大模型总结，不新增来源，不编造 Starlink 或 SpaceX 事实。

## 1. 部署目标

- GitHub Actions 每周自动运行周报流程；
- 生成总结版、明细版、兼容索引和周报总索引；
- 发送包含总结版与明细版附件的邮件；
- 自动提交生成文件到 GitHub；
- 在配置 `GITEE_REMOTE` 时同步到 Gitee，失败时不阻断主流程；
- 通过 `check_outputs.py --strict` 和 `audit_project.py --strict` 做发布前质量门禁。

## 2. 本地环境要求

- Windows 11 PowerShell 可用；
- Git 可用，当前分支为 `main`；
- Python 3.11 或以上版本可用；
- 已安装 `requirements.txt` 中依赖；
- `.env` 已被 `.gitignore` 忽略；
- `prompts/` 已被 `.gitignore` 忽略。

本地安装依赖：

```powershell
cd E:\starlink_intel_weekly
python -m pip install -r requirements.txt
```

## 3. GitHub 仓库要求

- 仓库默认分支为 `main`；
- `.github/workflows/weekly.yml` 已提交到 GitHub；
- Actions workflow permissions 允许写入仓库内容；
- 本地不要把 `.env`、`prompts/`、`data/raw/`、`data/cache/` 或真实日志提交到仓库。

自动运行后，如 GitHub 生成了自动提交，本地需要同步：

```powershell
git pull --rebase origin main
```

## 4. GitHub Actions Secrets

在 GitHub 仓库 `Settings` -> `Secrets and variables` -> `Actions` 中配置：

```text
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
MAIL_FROM
MAIL_TO
GITEE_REMOTE
```

`GITEE_REMOTE` 可以暂时不配置。未配置时，workflow 会跳过 Gitee 同步。

## 5. 邮件 SMTP 配置

本地只使用 `.env` 保存 SMTP 测试配置，GitHub Actions 只从 Secrets 读取配置。示例占位符：

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_email_authorization_code
MAIL_FROM=your_email@example.com
MAIL_TO=target_email@example.com
```

不要把真实邮箱授权码写入 README、脚本、workflow 或提交历史。

## 6. Gitee 同步配置

GitHub Secrets 中的占位格式：

```text
GITEE_REMOTE=https://username:token@gitee.com/username/starlink_intel_weekly.git
```

注意事项：

- 不要在 workflow 日志中打印完整 `GITEE_REMOTE`；
- Gitee 同步失败不会阻断 GitHub 主流程；
- 若令牌包含特殊字符，需要先进行 URL 编码；
- 本地不要执行 Gitee push，Gitee 同步只由 GitHub Actions 云端执行。

## 7. 定时运行说明

GitHub Actions 定时规则为：

- 每周一 UTC 00:17 自动运行；
- 北京时间每周一 08:17；
- 日本时间每周一 09:17。

该任务由 GitHub 云端执行，本地电脑无需开机，本地 Codex 也不需要打开。

## 8. 手动运行流程

1. 打开 GitHub 仓库；
2. 进入 `Actions`；
3. 选择 `Starlink Weekly Automation`；
4. 点击 `Run workflow`；
5. 选择 `main` 分支运行；
6. 运行结束后先查看 GitHub Actions Summary。

## 9. 自动运行后的检查项

- workflow 是否为 Success；
- Summary 是否包含输出质量检查、稳定性与配置审计、Gitee 同步状态；
- 邮箱是否收到本周周报；
- GitHub 是否生成 `chore: update weekly Starlink automation output` 提交；
- `weekly/YYYY-WW-summary.md`、`weekly/YYYY-WW-details.md`、`weekly/index.md` 是否更新；
- `data/weekly_manifest.json`、`data/run_history.jsonl` 是否更新；
- Gitee 是否同步到最新 `main`。若 Gitee 失败但 workflow 成功，主流程仍可视为可用。

## 10. 常见故障与处理

- 邮件认证失败：检查 SMTP 服务是否开启、授权码是否正确、Secrets 是否配置；
- Gitee 408 或同步失败：优先查看 Summary 中的 Gitee 同步状态，稍后手动重新运行 workflow；
- 输出质量检查失败：本地运行 `python scripts/check_outputs.py --strict`；
- 项目审计失败：本地运行 `python scripts/audit_project.py --strict`；
- GitHub 自动提交失败：检查 `permissions: contents: write` 和仓库 Actions 写权限；
- 本地落后于 GitHub：执行 `git pull --rebase origin main`。

## 11. 安全注意事项

- 不提交 `.env`；
- 不提交 `prompts/`；
- 不提交真实 SMTP 授权码；
- 不提交真实 Gitee Token；
- 不在日志中打印完整远程地址；
- 不读取或展示 `.env` 内容；
- 不把页面级记录直接解释为具体情报事实；
- 不把 hash 变化解释为事实变化。

## 12. 阶段 2G 稳定版确认清单

- 已接入来源仍只有 `Starlink Official Updates` 和 `SpaceX Official Launches`；
- 当前不使用大模型；
- 当前不新增第三方来源；
- 当前不编造 Starlink 或 SpaceX 事实；
- `python scripts/check_outputs.py --strict` 通过；
- `python scripts/audit_project.py --strict` 通过；
- GitHub Actions 已包含项目审计门禁；
- Summary 已展示稳定性与配置审计状态；
- 部署检查清单、运维指南和发布说明已提交。
