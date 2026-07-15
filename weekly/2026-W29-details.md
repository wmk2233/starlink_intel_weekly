# Starlink 情报周报明细版：2026-W29

## 1. 文档说明

本明细版用于来源复查、结构化数据核验和知识库维护。页面级 hash 变化与条目级结构化变化分别展示；大模型辅助摘要独立受来源约束，不能替代确定性统计。

## 2. 数据文件

| 文件 | 说明 |
|---|---|
| `data/items.jsonl` | 结构化采集条目 |
| `data/source_status.json` | 来源状态与变化检测 |
| `data/extraction_quality.json` | 解析质量诊断 |
| `data/item_extraction_state.json` | 条目 stable ID、baseline 与历史状态 |
| `data/item_extraction_report.json` | 本次官方条目发现与详情解析报告 |
| `data/llm_audit.json` | 可选 LLM 摘要审计 |
| `data/llm_summaries.json` | 可选 LLM 摘要输出 |
| `data/llm_usage.jsonl` | 限长的 LLM 状态、token 与耗时记录 |

## 大模型摘要审计

| 字段 | 内容 |
|---|---|
| LLM 是否启用 | true |
| LLM Provider | deepseek |
| LLM 状态 | generated |
| 模型 | deepseek-v4-flash |
| Base URL 类型 | deepseek_default |
| 输入记录数 | 2 |
| 去重前输入记录 | 5 |
| 去重后输入记录 | 3 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 3 |
| 输出 record ID 去重前数量 | 4 |
| 输出 record ID 去重后数量 | 4 |
| 输出 URL 去重前数量 | 4 |
| 输出 URL 去重后数量 | 4 |
| Prompt tokens | 5085 |
| Completion tokens | 1243 |
| Total tokens | 6328 |
| API 调用耗时 | 12381.06 ms |
| 校验状态 | passed |
| 严格来源约束 | true |
| 页面级记录禁止事实扩展 | true |
| 审计文件 | data/llm_audit.json |
| 摘要文件 | data/llm_summaries.json |
| 用量记录 | data/llm_usage.jsonl |

### 页面级监测解释

- SpaceX Official Launches：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。

- 原因：LLM summary generated and validated.


## 3. 来源状态诊断

| 来源 | 类别 | 类型 | 可信度 | 可达性 | 页面变化状态 | HTTP状态 | 最近检查时间 | page_hash |
|---|---|---|---|---|---|---|---|---|
| Starlink Official Updates | official_updates | official | S | reachable | changed | 200 | 2026-07-15T06:21:20+00:00 | e861179ab4dc0b7c |
| SpaceX Official Launches | official_launches | official | S | reachable | unchanged | 200 | 2026-07-15T06:21:34+00:00 | afd623b148154a55 |

## 4. 本周变化检测

| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 | 最近变化时间 |
|---|---:|---:|---:|---|---|
| Starlink Official Updates | 0 | 0 | 1 | changed | 2026-07-15T06:21:20+00:00 |
| SpaceX Official Launches | 0 | 0 | 0 | unchanged | 2026-06-17T18:23:48+08:00 |

## 5. 解析质量诊断

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 页面级 | 链接级 | 条目级 | 候选链接数 | 解析器版本 |
|---|---|---|---:|---:|---:|---:|---:|---|
| Starlink Official Updates | item_level | high | 0.9 | 0 | 0 | 1 | 0 | starlink_updates_item_v1 |
| SpaceX Official Launches | page_level | low | 0.35 | 1 | 0 | 0 | 1 | spacex_launches_item_v1 |

## 6. 采集条目明细

### 6.1 Starlink Official Updates

| 字段 | 内容 |
|---|---|
| id | 95bbf31b3a93d3e6 |
| title | Stargaze |
| url | https://starlink.com/updates/stargaze |
| source_id | starlink_official_updates |
| category | starlink_update |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | high |
| extraction_confidence | 0.9 |
| content_hash | 14d1326f8705072b |
| previous_content_hash | 14d1326f8705072b |
| first_seen_at | 2026-07-14T14:54:30+08:00 |
| last_seen_at | 2026-07-15T06:21:20+00:00 |
| last_changed_at | 2026-07-14T14:54:30+08:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

### 6.2 SpaceX Official Launches

| 字段 | 内容 |
|---|---|
| id | 85aab698bd64b7d5 |
| title | SpaceX |
| url | https://www.spacex.com/launches |
| source_id | spacex_official_launches |
| category | official_launches |
| change_status | unchanged |
| extracted_level | page_level |
| source_quality | low |
| extraction_confidence | 0.35 |
| content_hash | 48928194391143dc |
| previous_content_hash | 48928194391143dc |
| first_seen_at | 2026-07-14T14:54:51+08:00 |
| last_seen_at | 2026-07-15T06:21:34+00:00 |
| last_changed_at | 2026-07-14T14:54:51+08:00 |
| matched_keywords | ["launch", "launches"] |
| candidate_links | [{"title": "", "url": "https://www.spacex.com/launches/sda-t1tl-e", "matched_keywords": []}] |
| extraction_notes | 页面可达，但当前静态规则未识别到稳定的独立条目；保留页面级记录，不补写发布时间或技术事实。 |

## 7. 原始摘要与证据片段

### 7.1 Stargaze

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/stargaze)
- summary：May 21, 2026 To ensure safe spaceflight for everyone, all satellite operators should track their spacecraft with onboard GNSS, accurately predict their future trajectories, and broadcast that information to other satellite operators. Starlink currently publishes its ephemeris to multiple conjunction screening platforms and makes them available on our public website. For the past two years, Starlink has provided free, low-latency conjunction screening to participating satellite operators via our
- evidence：May 21, 2026 To ensure safe spaceflight for everyone, all satellite operators should track their spacecraft with onboard GNSS, accurately predict their future trajectories, and broadcast that information to other satellite operators. Starlink currently publishes its ephemeris to multiple conjunction screening platforms and makes them available on our public website. For the past two years, Starlink has provided free, low-latency conjunction screening to participating satellite operators via our…

### 7.2 SpaceX

- 来源：SpaceX Official Launches
- 链接：[链接](https://www.spacex.com/launches)
- summary：规则化采集生成 SpaceX Official Launches 页面级记录。未编造发射时间、任务状态或载荷数量。
- evidence：SpaceX

## 官方条目解析诊断

| 来源 | 解析器 | 静态候选 | 浏览器候选 | 选中候选 | 详情成功/失败 | baseline/new/changed/unchanged | item/page | 层级 | 质量 | 渲染 fallback | warning |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| SpaceX Official Launches | spacex_launches_item_v1 | 0 | 1 | 1 | 0/1 | 0/0/0/0 | 0/1 | page_level | low | 是 / success | detail_parse_insufficient_evidence |
| Starlink Official Updates | starlink_updates_item_v1 | 0 | 4 | 4 | 1/3 | 0/0/0/1 | 1/0 | item_level | high | 是 / success | detail_parse_insufficient_evidence |

| 状态 | 来源 | 标题 | 日期文本 | 相关性 | 层级 | 质量 | 字段证据 | 官方链接 |
|---|---|---|---|---|---|---|---|---|
| unchanged | Starlink Official Updates | Stargaze | May 21, 2026 | direct | item_level | high/0.9 | evidence, published_at, summary, title | [链接](https://starlink.com/updates/stargaze) |

## 8. 局限性

- 当前仅接入两个官方来源；
- 静态候选为 0 时才会按 `auto` 模式尝试受控 Chromium 索引渲染；
- 浏览器不可用、候选为空或详情证据不足时会保留页面级 fallback；
- hash 变化不等于事实变化；
- 解析质量分数不代表事实重要性；
- 不编造发布时间、发射时间、任务状态、载荷数量或 Starlink 技术事实。

## 9. 自动化测试记录

- 运行时间：2026-07-13 03:57:41 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 10:58:24 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 10:58:27 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 12:26:25 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 04:42:57 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 13:13:55 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 13:17:17 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：否
  - 是否生成解析质量诊断：是
  - 页面变化状态：SpaceX Official Launches=unchanged；Starlink Official Updates=changed
  - 已接入来源数量：2
- 运行时间：2026-07-14 05:59:08 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 14:54:30 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-14 15:04:13 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：否
  - 是否生成解析质量诊断：是
  - 页面变化状态：SpaceX Official Launches=unchanged；Starlink Official Updates=changed
  - 已接入来源数量：2
- 运行时间：2026-07-14 15:04:29 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-15 06:12:06 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-15 06:21:20 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
