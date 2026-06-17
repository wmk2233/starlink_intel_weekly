# Starlink 情报周报自动化运维指南

本指南用于阶段 2G 稳定版的日常维护。当前系统只处理两个官方来源的规则化采集与周报输出，不做大模型总结，不新增来源，不编造事实。

## 1. 每周自动运行机制

GitHub Actions 会按 `.github/workflows/weekly.yml` 定时运行：

```text
cron: "17 0 * * 1"
```

对应时间为每周一 UTC 00:17、北京时间每周一 08:17、日本时间每周一 09:17。任务在 GitHub 云端执行，本地电脑和 Codex 不需要保持打开。

## 2. 每周运行后需要检查什么

优先检查 GitHub Actions Summary：

- workflow 是否为 Success；
- 输出质量检查状态；
- 稳定性与配置审计状态；
- Gitee 同步状态；
- 本周 summary、details、兼容索引路径；
- 来源健康状态、页面变化状态和条目统计；
- 解析质量状态。

## 3. 如何确认邮件是否正常

检查收件箱是否收到主题类似 `Starlink 情报周报自动化测试 - YYYY-WW` 的邮件。邮件应包含总结版和明细版两个附件。

本地测试邮件前先确认 `.env` 已手动配置：

```powershell
cd E:\starlink_intel_weekly
python scripts/validate_env.py
python scripts/run_weekly.py
```

不要在命令行或文档中写入真实授权码。

## 4. 如何确认 GitHub 是否自动更新

在 GitHub 仓库 `main` 分支查看最新提交，自动提交信息通常为：

```text
chore: update weekly Starlink automation output
```

也可以本地同步后查看：

```powershell
cd E:\starlink_intel_weekly
git pull --rebase origin main
git log --oneline -20
```

## 5. 如何确认 Gitee 是否同步

先看 GitHub Actions Summary 中的 Gitee 同步状态：

```text
success / failed / skipped / unknown
```

如果显示 `failed`，说明 Gitee 同步未成功，但 GitHub 主流程仍可能成功。可稍后手动重新运行 workflow，或检查 GitHub Secrets 中的 `GITEE_REMOTE` 是否仍可推送。

## 6. 如何同步本地仓库

每次 GitHub Actions 自动提交后，本地执行：

```powershell
cd E:\starlink_intel_weekly
git pull --rebase origin main
git status --short
```

如果本地有未提交修改，先确认这些修改是否属于自己当前任务，再决定是否提交或暂存。

## 7. 如何检查输出质量

输出质量检查脚本用于确认本周 summary、details、兼容索引、周报总索引和数据文件结构完整：

```powershell
cd E:\starlink_intel_weekly
python scripts/check_outputs.py --strict
```

JSON 输出便于后续自动化解析：

```powershell
python scripts/check_outputs.py --json
```

`--strict` 是质量门禁，失败时应先修复输出结构。

## 8. 如何查看历史周报

历史周报入口是：

```text
weekly/index.md
```

每周通常包含三类文件：

- `weekly/YYYY-WW-summary.md`：总结版；
- `weekly/YYYY-WW-details.md`：明细版；
- `weekly/YYYY-WW.md`：兼容索引。

页面级记录、hash 变化和解析质量字段只表示自动化抽取状态，不代表人工核验后的事实结论。

## 9. 如何处理 GitHub Actions 失败

处理顺序：

1. 打开失败的 workflow run；
2. 先看 Summary；
3. 再看失败步骤日志；
4. 本地运行对应脚本复现。

常用本地命令：

```powershell
cd E:\starlink_intel_weekly
python scripts/validate_env.py
python scripts/self_check.py
python scripts/check_outputs.py --strict
python scripts/audit_project.py --strict
```

## 10. 如何处理 Gitee 408 或同步失败

Gitee 408 常见于认证服务超时或网络波动。当前 workflow 会自动重试 3 次，最终失败也不会让主流程标红。

排查顺序：

- 查看 Summary 中的 Gitee 同步状态；
- 确认 `GITEE_REMOTE` Secret 是否存在；
- 确认 Gitee 仓库仍存在；
- 确认令牌仍有写权限；
- 稍后重新手动运行 workflow。

不要把完整 `GITEE_REMOTE` 输出到日志。

## 11. 如何处理邮件认证失败

常见原因：

- SMTP 服务未开启；
- 授权码失效；
- `SMTP_USER` 与 `MAIL_FROM` 不一致；
- 邮箱服务商限制第三方客户端登录；
- GitHub Secrets 配置缺失。

本地只检查变量存在性和格式：

```powershell
cd E:\starlink_intel_weekly
python scripts/validate_env.py
```

脚本不会打印密码或授权码。

## 12. 如何安全更新 Secrets

在 GitHub 网页中更新 Secrets：

1. 打开仓库 `Settings`；
2. 进入 `Secrets and variables`；
3. 选择 `Actions`；
4. 更新对应 Secret；
5. 手动运行一次 workflow 验证。

本地 `.env` 只用于本机测试，不提交、不截图、不复制到公开文档。

## 13. 后续接入大模型前的注意事项

阶段 3A 才考虑大模型摘要。在接入前需要确认：

- 当前官方来源采集链路稳定；
- `check_outputs.py --strict` 长期通过；
- `audit_project.py --strict` 长期通过；
- 大模型输出必须区分事实、推断和待核验内容；
- 不允许把页面级记录包装成确定事实；
- 不允许把 hash 变化解释成事实变化；
- 新增来源必须先更新 `sources.yml`、审计脚本和安全边界说明。
