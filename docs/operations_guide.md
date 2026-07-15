# Starlink 情报周报自动化运维指南

## 19. 阶段 4D 告警与 run health 运维

完整 replay 使用 `.invalid` 虚构 fixture 且完全离线：

```powershell
$env:PYTHON_DOTENV_DISABLED="1"
$env:LLM_ENABLED="false"
python scripts/replay_lifecycle_events.py --all --fixture-dir tests\fixtures\lifecycle_replay --json --no-write --strict
```

诊断告警与健康时使用 `scripts/diagnose_alerts.py --all --json --no-write` 和 `scripts/diagnose_run_health.py --all --history --json --no-write`。事件型通知只对新 event ID 通知一次；条件型告警会 open、在冷却结束后 update、达到阈值时 escalate，并在采集条件恢复后 resolve。历史 4C 事件在 bootstrap 时只建立 watermark，不重发。

告警等级只表示自动化系统中的人工复查优先级，不代表官方事件重要性。source unreachable 表示采集器未成功访问来源，不代表官方服务中断；fetch failed 不代表官方页面故障；detail fetch recovered 不代表官方服务恢复。LLM disabled、无新增条目、单纯页面 hash changed 和正常 Playwright fallback 都不是故障。

`alert_events.jsonl` 与 `run_health_history.jsonl` 有历史上限并使用原子替换；open alert 状态保存在 `alert_state.json`，不会因历史裁剪丢失。出现 stale run warning 时，先确认 GitHub Actions concurrency，再检查 `last_applied_run_id / last_applied_started_at`，不要手工回退生产状态。

## 18. 阶段 4C 生命周期运维

日常诊断使用只读命令：

```powershell
$env:PYTHON_DOTENV_DISABLED="1"
$env:LLM_ENABLED="false"
python scripts/diagnose_item_lifecycle.py --all --json --no-write
```

`change_status`、`extraction_change_status` 与 `lifecycle_state` 是三条独立轴。new 仅表示本轮首次发现；extraction improved 仅表示字段或证据更完整；`temporarily_missing`/`long_absent` 不代表删除；`fetch_failed` 不代表官方故障；`detail_fetch_recovered` 不代表官方服务恢复；`reappeared` 不代表重新发布。

missing 只在来源索引可达且候选发现完整时累计。候选因 `MAX_SOURCE_ITEMS` 截断、索引渲染失败或索引请求失败时，不得人工递增 missing。连续缺失默认同时满足 4 次与 14 天才进入 `long_absent`。连续详情失败达到 3 次会设置 attention，但主流程继续运行并保留最近一次成功数据。

版本历史每条默认保留 20 个结构化快照，事件历史默认保留 1000 条；event/version ID 去重，unchanged 不追加版本。字段级变化证据仅保留有限 before/after excerpt，不保存完整 HTML。调整阈值后先运行全量离线测试、`check_outputs.py --strict` 和 `audit_project.py --strict`。

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
- 大模型摘要状态；
- Gitee 同步状态；
- 本周 summary、details、兼容索引路径；
- 来源健康状态、页面变化状态和条目统计；
- 解析质量状态。

阶段 3B 支持 DeepSeek provider，但默认不启用 LLM。未配置当前 provider 对应的 API Key 时，LLM 状态显示为 `skipped` 或 `skipped_no_api_key` 是正常现象，主流程仍应成功。

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

## 13. DeepSeek Provider 运维注意事项

阶段 3B 已支持 `deepseek` 与 `openai` provider，但 LLM 默认关闭。只有显式设置 `LLM_ENABLED=true` 或传入 `--enable-llm` 才启用。DeepSeek API Key 需要单独在 DeepSeek 平台获取；ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用。

无 API Key 场景本地测试：

```powershell
cd E:\starlink_intel_weekly
python scripts/llm_summarize.py
python scripts/llm_summarize.py --enabled --provider deepseek
python scripts/run_weekly.py --no-email --output-mode dual --enable-llm --llm-provider deepseek --max-source-items 10 --max-history-records 20 --max-run-history 200
```

后续如需启用 API Key 场景，本地真实值只放入未提交的 `.env`，GitHub Actions 按 GitHub Variables 与 GitHub Secrets 分级配置，不要写入代码：

```text
GitHub Variables:
LLM_ENABLED=true
LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com

GitHub Secrets:
DEEPSEEK_API_KEY=<真实 API Key>
```

本地真实 key 只写入被忽略的 `.env`，GitHub Actions 只写入 GitHub Secrets，API Key 不得提交。DeepSeek 推荐默认模型为 `deepseek-v4-flash`，可选 `deepseek-v4-pro`；旧名称 `deepseek-chat`、`deepseek-reasoner` 不应再作为默认值。

启用前需要确认：

- 当前官方来源采集链路稳定；
- `check_outputs.py --strict` 长期通过；
- `audit_project.py --strict` 长期通过；
- 大模型输出必须区分事实、推断和待核验内容；
- 不允许把页面级记录包装成确定事实；
- 不允许把 hash 变化解释成事实变化；
- 新增来源必须先更新 `sources.yml`、审计脚本和安全边界说明。

阶段 3B 的 LLM 摘要只基于本地结构化来源数据。无来源不写结论，页面级记录不得扩展成具体事实。通过校验的 LLM 输出保存在 `data/llm_summaries.json`，provider、模型、脱敏 base URL 类型与校验结果保存在 `data/llm_audit.json`，两者均不覆盖原始采集数据。本阶段不新增来源、不编造事实。

## 14. 阶段 3C 去重、用量与 Actions 运维

`items.jsonl` 继续保留历史。LLM 输入按 `source_id + normalized_url` 去重并选择每组最新记录；模型输出的 record IDs 和 URLs 再次去重。去重不等于删除来源历史。

页面 changed 只表示页面 hash 或页面内容变化；条目 changed 表示规则抽取出的结构化情报条目发生可确认变化。页面 changed 且新增/变化条目均为 0 时，只能说明页面级变化，不能扩展为事件事实。

`data/llm_usage.jsonl` 最多保留 200 条，只记录 provider、model、状态、输入去重数量、token 数量和调用耗时；不记录 API Key、完整 prompt、完整 response 或费用。token 缺失时显示 `unknown`，这是兼容不同 provider 响应格式的正常状态。

Workflow 使用 `actions/checkout@v5` 与 `actions/setup-python@v6`，对应 Node.js 24 运行时。非敏感配置放 GitHub Variables，API Key 放 GitHub Secrets。创建 Variables 后，旧的 `LLM_ENABLED`、`LLM_PROVIDER`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL` Secrets 需要用户在 GitHub 网页手动删除，代码不能自动代办。

## 15. 阶段 4A 官方条目抽取运维

日常只读诊断：

```powershell
python scripts/diagnose_official_pages.py --all --no-write
python scripts/collect_sources.py --max-source-items 10 --render-mode auto --dry-run
```

`auto` 模式只在静态候选为 0 时启动 Playwright。浏览器不可用、索引候选为空、详情请求失败或详情证据不足时，来源保留 page-level fallback。此状态不表示官方页面没有内容，也不能扩展为具体事件事实。

`data/item_extraction_state.json` 保存每个来源的 bootstrap 状态和已知 stable ID；`data/item_extraction_report.json` 保存本次候选数、详情成功/失败数、baseline/new/changed/unchanged 和 fallback 状态。两者不保存完整 HTML、Secrets 或 API Key。

首次成功 item-level 抽取会把当前条目全部标记为 baseline，防止历史条目误报为本周 new。只有明确需要重建基线时，人工运行：

```powershell
python scripts/collect_sources.py --source-id starlink_official_updates --rebootstrap-source starlink_official_updates
```

该操作会改变变化检测语义，执行前应先备份数据并人工确认。GitHub Actions 永远不传入 `--rebootstrap-source`。

## 16. 阶段 4B 详情诊断与失败恢复运维

无写入诊断使用：

```powershell
$env:PYTHON_DOTENV_DISABLED="1"
$env:LLM_ENABLED="false"
python scripts/diagnose_official_details.py --all --limit 10 --render-mode auto --json --no-write
```

`data/detail_extraction_diagnostics.json` 只记录候选 URL、静态/渲染状态、长度、有限错误类型和是否复用历史成功，不保存完整 HTML、DOM、Cookie、截图、视频、HAR、trace 或完整异常。详情失败不代表官方条目删除；`current_run_data_reused=true` 表示正文来自最近一次成功解析，不代表本轮重新确认。

parser v2 的 `semantic_content_hash` 不包含 parser version、质量、字段证据或提取方法；这些变化通过 `extraction_hash` 和 `extraction_change_status=improved` 观察。事实字段真正变化时才使用 `change_reason=semantic_content_changed`。不得从 URL slug 推断日期、状态或载荷。

LLM 运行统计依次显示原始候选记录、URL 去重后记录和最终核心输入记录。baseline 说明仅在本轮产生 baseline 时出现，LLM 状态说明按当前实际启用状态生成。详情 Playwright 会增加运行时间，排障时先看失败类型，不反复请求追求固定成功率。

## 17. 阶段 4B.1 LLM 引用对齐运维

模型输入边界是 `final_core_records + allowed_reference_pairs`。`monitoring_context` 只用于代码生成页面监测解释，不发送给模型；页面 hash、可达性、条目数量和索引页 URL 不能成为核心摘要引用。

模型 schema 不包含 `source_based_notes`，只生成 `overall_summary` 与 `key_points`。每个 key point 必须包含安全配对的 record ID 和 canonical URL。对齐器可以补齐单侧缺失引用，但不会把属于不同记录的合法 ID/URL 强行配对，也不会改写 claim 文本；修复后无合法来源的要点会删除，严格校验仍失败时保留旧摘要。

排障优先查看 `data/llm_audit.json` 中的 `invalid_record_ids_removed`、`invalid_urls_removed`、`missing_record_ids_repaired`、`missing_urls_repaired`、`key_points_removed_without_sources` 和 `reference_alignment_status`。审计不保存完整 prompt 或完整原始 response。
