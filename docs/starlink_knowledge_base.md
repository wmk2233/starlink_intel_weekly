# Starlink 技术情报长期知识库

## 阶段 4D 回放、告警与运行健康知识

- 生命周期核心可用 `.invalid` 虚构 observation 完全离线 replay，生产数据文件不参与回放。
- 事件型通知按 lifecycle event ID 去重；条件型告警维护 open、冷却、升级与 resolve。
- info/warning/high/critical 仅是自动化人工复查优先级，不是官方事件的重要程度或风险等级。
- source unreachable 不代表官方服务中断，fetch failed 不代表官方页面故障，采集 recovery 不代表官方服务恢复。
- run health 使用 healthy/degraded/unhealthy；LLM disabled、无新增和页面 hash changed 可保持 healthy。
- 告警与健康历史有历史上限并原子更新；重复和乱序运行不得覆盖较新状态。
- 新增 `lifecycle_replay_report.json`、`alert_state.json`、`alert_events.jsonl`、`alert_report.json`、`run_health.json` 和 `run_health_history.jsonl`。

## 阶段 4C 增量变化与生命周期知识

阶段 4C 为 item-level 记录增加确定性生命周期。new 是系统本轮首次发现 canonical URL，不自动等于官方本周发布；semantic changed 需要已有非空事实字段的实质变化；extraction improved 只表示解析字段、证据或 parser 能力提升。

`temporarily_missing` 和 `long_absent` 仅描述在完整索引观测中未发现历史条目，不代表删除。`fetch_failed` 会保留最近一次成功记录，不代表官方故障。`detail_fetch_recovered` 只表示采集链路恢复，不代表官方服务恢复；`reappeared` 不代表重新发布。

结构化状态和历史位于 `data/item_lifecycle_state.json`、`data/item_versions.jsonl`、`data/lifecycle_events.jsonl` 与 `data/lifecycle_report.json`。首次迁移幂等，不产生 new、changed 或新 baseline。字段级变化证据限长，且不保存完整 HTML。

本文件用于记录 Starlink 技术情报的长期更新内容。

当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，并新增双文档周报输出；不包含大模型事实推理。

## 已接入来源

| 来源 | 类型 | 可信度 | 地址 | 状态 |
|---|---|---|---|---|
| Starlink Official Updates | official | S | https://www.starlink.com/updates | 已接入 |
| SpaceX Official Launches | official | S | https://www.spacex.com/launches | 已接入 |

## 来源状态与变化检测

| 来源 | 最近检查时间 | 可达性 | 页面变化状态 | 最近变化时间 | 当前状态 |
|---|---|---|---|---|---|
| Starlink Official Updates | 2026-08-10T02:32:23+00:00 | reachable | changed | 2026-08-10T02:32:23+00:00 | 正常 |
| SpaceX Official Launches | 2026-08-10T02:32:58+00:00 | reachable | unchanged | 2026-06-17T18:23:48+08:00 | 正常 |

## 来源解析质量诊断

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 静态候选 | 渲染候选 | 候选总数 |
|---|---|---|---:|---:|---:|---:|
| Starlink Official Updates | item_level | medium | 0.8 | 0 | 5 | 5 |
| SpaceX Official Launches | item_level | medium | 0.8 | 0 | 1 | 1 |

## 周报输出结构

| 文档 | 用途 |
|---|---|
| `weekly/YYYY-WW-summary.md` | 总结版，适合快速阅读和组会分享 |
| `weekly/YYYY-WW-details.md` | 明细版，适合来源复查、结构化数据核验和知识库维护 |
| `weekly/YYYY-WW.md` | 兼容索引，指向总结版和明细版 |

## 周报归档与历史索引

| 文件 | 用途 |
|---|---|
| `weekly/index.md` | 周报总索引 |
| `data/weekly_manifest.json` | 机器可读的周报输出清单 |
| `data/run_history.jsonl` | 自动化运行历史记录 |
| `scripts/check_outputs.py` | 周报输出质量检查脚本 |

## 阶段 2G 稳定版说明

当前项目已形成官方来源自动化周报稳定版，支持每周自动采集、变化检测、解析质量诊断、双文档周报、邮件发送、GitHub 自动更新、Gitee 非阻塞同步、历史索引与输出质量检查。

阶段 2G 新增发布前稳定性与配置审计，不新增来源，不接入大模型，不编造 Starlink 或 SpaceX 事实。页面级记录不等于具体情报事实，hash 变化不等于事实变化，解析质量只表示规则抽取完整度。

## 运维与部署文档

| 文档 | 用途 |
|---|---|
| `docs/deployment_checklist.md` | 部署检查清单 |
| `docs/operations_guide.md` | 日常运维指南 |
| `RELEASE_NOTES.md` | 稳定版发布说明 |
| `scripts/audit_project.py` | 项目配置与稳定性审计脚本 |

## 阶段 3C LLM 去重、变化分层与用量审计

阶段 3C 保留 `openai` 与 `deepseek` provider，并新增 LLM 输入与输出引用去重、页面级与条目级变化分层解释，以及限长用量记录。LLM 仍默认关闭；缺少当前 provider 对应的 API Key 时会写入跳过审计且不阻断主流程。

| 文件 | 用途 |
|---|---|
| `scripts/llm_summarize.py` | 基于本地结构化数据生成受来源约束的可选 LLM 摘要 |
| `data/llm_audit.json` | 记录 LLM 是否启用、是否跳过、校验状态和 guardrails |
| `data/llm_summaries.json` | 仅在 LLM 启用且校验通过后保存摘要 |
| `data/llm_usage.jsonl` | 仅记录 provider、model、状态、去重计数、token 与调用耗时 |

约束：

- ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用；
- provider、model、base URL 等非敏感配置使用 GitHub Variables；API Key 只使用 GitHub Secrets；
- 不得把任何 API Key 写入代码、文档或提交记录；
- LLM 摘要只基于 `data/items.jsonl` 等本地结构化来源数据；
- 无来源不写结论；
- 页面级记录不扩展成具体事实；
- 页面 changed 仅代表页面 hash 或内容变化，不能等同于条目 changed；
- `items.jsonl` 保留历史，LLM 输入才按 `source_id + normalized_url` 选择每组最新记录；
- 用量记录不保存费用、完整 prompt、完整 response 或 API Key；
- LLM 输出与原始采集数据分离。
- 本阶段不新增来源，不编造 Starlink 或 SpaceX 事实。

## 阶段 4A 官方条目抽取知识

- 两个官方索引页先做静态候选发现，静态候选为 0 时才受控运行 Playwright；
- 允许路径仅为 Starlink `/updates/<slug>` 与 SpaceX `/launches/<slug>`；
- item-level ID 由 `source_id + canonical_url` 生成，内容变化不改变稳定 ID；
- 首次成功 item-level 抽取建立 baseline，历史条目不属于本周新增；
- 页面级 hash 与条目级 baseline/new/changed/unchanged 是不同检测层级；
- 条目缺失于当前索引时不删除历史，只把 `seen_in_current_index` 更新为 false；
- SpaceX 的 Starlink 助推器历史提及属于 incidental，只有 direct 条目进入核心结论；
- `data/item_extraction_state.json` 保存 bootstrap 和 stable ID 状态；
- `data/item_extraction_report.json` 保存候选、详情成功/失败、fallback 和变化计数；
- 浏览器不可用或证据不足时使用 page-level fallback，不编造标题、日期、任务状态或载荷事实。

## 阶段 4B.1 LLM 引用边界知识

- LLM 核心输入只包含 `final_core_records` 与 `allowed_reference_pairs`；
- `monitoring_context`、页面 hash、页面可达性和条目计数由代码确定性生成，不进入模型 prompt；
- 模型不生成 `source_based_notes`，只生成 `overall_summary` 和带安全来源配对的 `key_points`；
- record ID 与 canonical URL 必须属于同一允许记录，合法但错配时不得强行组合；
- 无法安全修复的输出保持 `validation_failed`，不得覆盖最近一次有效摘要；
- 审计只保存引用对齐计数和状态，不保存完整 prompt 或完整原始 response。

## 阶段 4B 动态详情解析与失败恢复知识

- 官方详情先静态请求，JavaScript shell、缺少标题或 evidence 时才受控运行 Playwright；
- `data/detail_extraction_diagnostics.json` 保存逐候选状态、长度和有限 error type，不保存完整 HTML、截图、HAR、视频或 trace；
- 历史成功 item-level 在本轮详情失败时保留，并明确标记为复用历史，不代表本轮重新确认；
- `consecutive_failures` 只用于运维诊断，不用于推断官方条目删除；
- `semantic_content_hash` 排除 parser version、质量、field evidence 和提取方法；parser enrichment 与 semantic change 分开记录；
- baseline 文案仅在本轮 baseline 大于 0 时出现；LLM 当前状态按实际运行动态展示；
- LLM 输入统计分为原始候选、URL 去重后和最终核心输入；复用历史记录受额外提示词约束；
- 不从 slug、HTTP Last-Modified 或采集时间推断官方日期、任务状态或载荷事实；
- Playwright 详情 fallback 会增加运行时间，但详情失败不会阻断周报、邮件、GitHub 提交或 Gitee 同步。

## 阶段 4D.1 最终健康与时间语义知识

- `provisional` 是周报渲染时点快照，只评估已经完成的内部组件；`pending_at_render_time` 不是失败。
- `final health` 在输出检查、项目审计、邮件和主要 Gitee 同步尝试完成后生成，Actions Summary 优先使用 `is_final=true` 的结果。
- `component_status_source` 区分 `internal_result`、`workflow_step_outcome`、`pending_at_render_time`、`not_applicable` 和 `unknown`。
- output validation/project audit 失败属于 critical 系统完整性问题；email/Gitee 失败属于 warning 分发问题，不能写成官方服务故障。
- `run_health_history.jsonl` 以 `run_id` 唯一，只保存 final 记录；同 run final 重试原位更新，不追加重复历史。
- final 阶段才持久化告警 open、update、escalate 或 resolve；provisional 只做内存预览，不推进计数或 watermark。
- 邮件无法报告自身尚未完成的投递结果，主要 Gitee 推送也不包含其后产生的 finalization commit；下一次正常同步可补齐。
- unchanged 是历史条目本轮无语义变化，必须使用历史记录语气；changed 只表示检测到内容变化；new 无明确官方日期证据不得写“本周发布”。

## 阶段 4D.2 最终展示与邮件报告知识

- Actions Summary 的输出检查和审计区域以 final health 为唯一结果来源；final 缺失时显示 unavailable。
- 邮件来源概览使用 `source_name`，并展示页面变化、new/changed/unchanged、解析层级和质量。
- 条目概览来自 `item_extraction_report.json`，详情成功、失败和 fallback 诊断来自 `detail_extraction_diagnostics.json`。
- GitHub Actions 核心步骤的 `--no-email` 表示由后续独立步骤发送，不表示整个 workflow 不发送邮件。
- 报告生成时邮件状态为 `pending_at_render_time`；邮件完成后的真实结果只进入 final health。

## 最近一次自动化运行记录

- 运行时间：2026-08-10 02:32:23 UTC+0000
- ISO 周编号：2026-W33
- 执行环境：Linux 6.17.0-1020-azure
- Python 版本：3.11.15
- 输出模式：dual
- 邮件发送方式：GitHub Actions 后续独立步骤
- 报告生成时邮件状态：pending_at_render_time
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 总结版文档：weekly/2026-W33-summary.md
- 明细版文档：weekly/2026-W33-details.md
- 兼容索引文档：weekly/2026-W33.md
- 周报总索引：weekly/index.md
- 周报 manifest：data/weekly_manifest.json
- 运行历史：data/run_history.jsonl
- 本次采集来源名称：Starlink Official Updates、SpaceX Official Launches
- 本次采集条目数量：6
- 已接入来源数量：2
- 来源可达性概览：Starlink Official Updates=reachable；SpaceX Official Launches=reachable
- 页面变化状态概览：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
- 新增条目数：1
- 内容变化条目数：0
- 未变化条目数：5
- LLM Provider：deepseek
- LLM 模型：deepseek-v4-flash
- LLM 摘要状态：validation_failed
- LLM 输入记录（去重前 / 后）：14 / 12
- LLM 唯一来源 URL：12
- LLM Total tokens：12558
- LLM API 调用耗时：54428.88 ms

