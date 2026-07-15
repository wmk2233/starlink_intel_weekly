# Starlink 情报周报自动化部署检查清单

## 19. 阶段 4D 回放、告警与健康部署清单

- [ ] 确认 replay fixture 仅使用 `example.invalid`，完全离线且不修改生产数据。
- [ ] 确认 `data/lifecycle_replay_report.json` 为 13/13 passed、`network_accessed=false`、`production_files_modified=false`。
- [ ] 确认首次 bootstrap 仅把已有生命周期事件设为 watermark，不重发历史通知。
- [ ] 确认事件型通知与条件型告警分离，severity 仅表示人工复查优先级。
- [ ] 确认 source unreachable 文案不代表官方服务中断，recovery 不代表官方服务恢复。
- [ ] 确认 run health 允许 LLM disabled 和无新增条目保持 healthy。
- [ ] 在 GitHub Variables 配置告警冷却、趋势阈值和历史上限；这些字段不是 Secrets。
- [ ] 确认 workflow 不运行完整 replay，只运行全量离线单元测试。
- [ ] 确认 Gitee 仍为三次重试、失败非阻塞，邮件仍只有两份 Markdown 附件。
- [ ] 确认 `.env`、`prompts/`、HTML、HAR、trace、截图和视频均未提交。

## 18. 阶段 4C 生命周期部署清单

- [ ] 确认 `data/item_lifecycle_state.json` 的 `phase4c_initialized=true` 且初始化只发生一次。
- [ ] 确认已有 item 未被标为 new、changed 或重新 baseline。
- [ ] 确认 `data/item_versions.jsonl` 与 `data/lifecycle_events.jsonl` 的 ID 唯一，`data/lifecycle_report.json` 与 state 的 `run_id` 一致。
- [ ] 在 GitHub Variables 中按需配置 `LONG_ABSENCE_OBSERVATION_THRESHOLD=4`、`LONG_ABSENCE_MIN_DAYS=14`、`DETAIL_FAILURE_ATTENTION_THRESHOLD=3`、`MAX_ITEM_VERSIONS_PER_RECORD=20`、`MAX_LIFECYCLE_EVENTS=1000`；这些不是 Secret。
- [ ] 先以 `LLM_ENABLED=false` 验证生命周期、双文档、邮件、自动提交和非阻塞 Gitee 同步。
- [ ] 再以 `LLM_ENABLED=true` 验证 new 不等于本周发布、extraction improved 不等于内容变化、missing 不代表删除、recovery 不代表官方服务恢复、reappeared 不代表重新发布。
- [ ] 确认只接入 `sources.yml` 中两个官方来源，Chromium 安装仍为单浏览器，未保存完整 HTML、截图、HAR、视频或 trace。

本清单用于阶段 3C 部署前复查。当前系统仍只使用两个官方来源，可选 LLM 摘要默认关闭；本阶段不新增来源，不编造 Starlink 或 SpaceX 事实。

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

## 4. GitHub Variables 与 GitHub Secrets

在 GitHub 仓库 `Settings` -> `Secrets and variables` -> `Actions` 中分级配置。

GitHub Variables：

```text
LLM_ENABLED=true
LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=
```

GitHub Secrets：

```text
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
MAIL_FROM
MAIL_TO
GITEE_REMOTE
DEEPSEEK_API_KEY
OPENAI_API_KEY
```

`GITEE_REMOTE` 可以暂时不配置。未配置时，workflow 会跳过 Gitee 同步。

Provider、model、base URL 和开关不是秘密，放入 Variables；API Key、SMTP 密码和 `GITEE_REMOTE` 是敏感值，放入 Secrets。非敏感配置迁移完成后，Summary 可正常显示 provider/model。代码不能自动修改仓库配置；创建 Variables 后，应由用户手动删除旧的 `LLM_ENABLED`、`LLM_PROVIDER`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL` Secrets。ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用。

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
- Summary 是否包含输出质量检查、稳定性与配置审计、LLM 摘要状态、Gitee 同步状态；
- 无 API Key 时，LLM 状态应为 `skipped` 或 `skipped_no_api_key`；
- 邮箱是否收到本周周报；
- GitHub 是否生成 `chore: update weekly Starlink automation output` 提交；
- `weekly/YYYY-WW-summary.md`、`weekly/YYYY-WW-details.md`、`weekly/index.md` 是否更新；
- `data/weekly_manifest.json`、`data/run_history.jsonl` 是否更新；
- Gitee 是否同步到最新 `main`。若 Gitee 失败但 workflow 成功，主流程仍可视为可用；
- `data/llm_audit.json` 是否存在且不包含任何 API Key。

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
- 不提交 OpenAI 或 DeepSeek API Key；
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

## 13. 阶段 3B DeepSeek 与 LLM 来源约束确认清单

- LLM 默认关闭；
- GitHub Variables 保存 `LLM_ENABLED`、`LLM_PROVIDER` 和 `DEEPSEEK_MODEL`，GitHub Secrets 只保存对应 API Key；
- 无 `DEEPSEEK_API_KEY` 时不阻断采集、周报、邮件、GitHub 提交和 Gitee 同步；
- DeepSeek 推荐默认模型为 `deepseek-v4-flash`，可选模型为 `deepseek-v4-pro`；
- 不再使用 `deepseek-chat` 或 `deepseek-reasoner` 作为默认模型；
- LLM 摘要只基于本地结构化来源数据；
- 无来源不写结论；
- 页面级记录不扩展成具体事实；
- 不编造发射时间、任务状态、载荷数量或技术细节；
- LLM 输出与原始采集数据分离；
- `data/llm_audit.json` 可以提交；
- `data/llm_summaries.json` 只有生成并通过校验后才提交。

## 14. 阶段 3C 去重、用量与 Actions 确认清单

- `items.jsonl` 保留历史，LLM 输入按 `source_id + normalized_url` 去重并选择每组最新记录；
- 输出 record IDs 和 URLs 再次去重，去重不等于删除来源历史；
- 页面 changed 与条目 changed 分属页面 hash 和结构化条目两个检测层级；
- `data/llm_usage.jsonl` 最多保留 200 条，只记录 provider、model、状态、去重数量、token 与耗时；
- 用量记录不保存 API Key、完整 prompt、完整 response 或费用；
- Workflow 使用 `actions/checkout@v5` 与 `actions/setup-python@v6`，对应 Node.js 24；
- GitHub Variables 与 GitHub Secrets 已按非敏感配置和真实凭据分级。

## 15. 阶段 4A 官方条目抽取部署清单

- `requirements.txt` 包含 `playwright>=1.49.0`；
- Workflow 运行 `python -m playwright install --with-deps chromium`；
- Workflow 在正式周报前运行三个解析/baseline/质量测试模块；
- Workflow 不使用 `--rebootstrap-source`；
- `data/item_extraction_state.json` 与 `data/item_extraction_report.json` 被显式提交；
- 首次成功 item-level 抽取只建立 baseline，不报告为本周新增；
- Playwright 只渲染两个官方索引页，失败时 page-level fallback 且不阻断主流程；
- GitHub Actions 保持 LLM 默认关闭，不需要 DeepSeek/OpenAI API Key；
- `.env`、`prompts/`、`data/raw/` 和 `data/cache/` 仍不提交。

## 16. 阶段 4B 动态详情解析部署清单

- GitHub Variables 可配置 `DETAIL_RENDER_MODE=auto`、`MAX_RENDERED_DETAILS_PER_SOURCE=10`、`DETAIL_TIMEOUT_MS=30000`、`DETAIL_WAIT_MS=1500`、`DETAIL_MAX_SCROLLS=3`、`DETAIL_CONCURRENCY=1`；
- Workflow 仍只安装 Chromium，并在质量检查前运行全部离线单元测试；
- 自动提交清单包含 `data/detail_extraction_diagnostics.json`；
- 确认详情浏览器不保存完整 HTML、截图、视频、HAR 或 trace；
- 确认历史成功记录保留、consecutive failure、semantic change 与 extraction improvement 检查通过；
- baseline=0 时不显示首次建库，LLM 文案按当前运行动态生成；
- Actions Summary 显示原始候选、URL 去重后和最终核心输入；
- Playwright 详情 fallback 会增加 workflow 执行时间。

## 17. 阶段 4B.1 LLM 引用对齐部署清单

- 模型 prompt 只包含 `final_core_records` 和 `allowed_reference_pairs`；
- `monitoring_context`、页面 hash、可达性、条目数量与索引页 URL 不进入模型输入；
- 模型不生成 `source_based_notes`，只生成 `overall_summary` 和 `key_points`；
- 每个 key point 的 record ID 与 canonical URL 必须属于同一允许引用对；
- 输入外 ID/URL 被删除，单侧缺失引用仅在可确定配对时补齐；
- 修复后无来源的要点被删除，无法安全修复时保持 `validation_failed`；
- 校验失败不得覆盖旧摘要，不保存完整 prompt 或完整原始 response；
- 本地测试保持 `PYTHON_DOTENV_DISABLED=1`、`LLM_ENABLED=false`。
