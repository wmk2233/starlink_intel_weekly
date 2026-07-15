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
| `data/detail_extraction_diagnostics.json` | 逐候选静态/渲染详情解析状态与有限错误类型 |
| `data/llm_audit.json` | 可选 LLM 摘要审计 |
| `data/llm_summaries.json` | 可选 LLM 摘要输出 |
| `data/llm_usage.jsonl` | 限长的 LLM 状态、token 与耗时记录 |

## 大模型摘要审计

| 字段 | 内容 |
|---|---|
| LLM 是否启用 | true |
| LLM Provider | deepseek |
| LLM 状态 | validation_failed |
| 模型 | deepseek-v4-flash |
| Base URL 类型 | deepseek_default |
| 输入记录数 | 4 |
| 去重前输入记录 | 9 |
| 去重后输入记录 | 7 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 7 |
| 原始候选记录 | 9 |
| URL 去重后记录 | 7 |
| 最终核心输入记录 | 4 |
| 最终核心唯一 URL | 4 |
| 复用历史记录 | 0 |
| 输出 record ID 去重前数量 | 4 |
| 输出 record ID 去重后数量 | 4 |
| 输出 URL 去重前数量 | 5 |
| 输出 URL 去重后数量 | 5 |
| Prompt tokens | 6909 |
| Completion tokens | 883 |
| Total tokens | 7792 |
| API 调用耗时 | 8623.08 ms |
| 校验状态 | failed |
| 严格来源约束 | true |
| 页面级记录禁止事实扩展 | true |
| 审计文件 | data/llm_audit.json |
| 摘要文件 | data/llm_summaries.json |
| 用量记录 | data/llm_usage.jsonl |

### 页面级监测解释

- SpaceX Official Launches：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。

- 原因：LLM output failed source-guardrail validation.

### 错误类型

- source_based_notes[1] 缺少来源记录或 URL。；source_based_notes[1] 出现输入外 URL。；LLM 输出包含输入记录之外的 URL。


## 3. 来源状态诊断

| 来源 | 类别 | 类型 | 可信度 | 可达性 | 页面变化状态 | HTTP状态 | 最近检查时间 | page_hash |
|---|---|---|---|---|---|---|---|---|
| Starlink Official Updates | official_updates | official | S | reachable | changed | 200 | 2026-07-15T07:54:27+00:00 | f5de55de511ccacf |
| SpaceX Official Launches | official_launches | official | S | reachable | unchanged | 200 | 2026-07-15T07:55:01+00:00 | afd623b148154a55 |

## 4. 本周变化检测

| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 | 最近变化时间 |
|---|---:|---:|---:|---|---|
| Starlink Official Updates | 0 | 0 | 4 | changed | 2026-07-15T07:54:27+00:00 |
| SpaceX Official Launches | 0 | 0 | 1 | unchanged | 2026-06-17T18:23:48+08:00 |

## 5. 解析质量诊断

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 页面级 | 链接级 | 条目级 | 静态候选 | 渲染候选 | 候选总数 | 解析器版本 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Starlink Official Updates | item_level | medium | 0.8 | 0 | 0 | 4 | 0 | 4 | 4 | starlink_updates_item_v2 |
| SpaceX Official Launches | item_level | medium | 0.8 | 0 | 0 | 1 | 0 | 1 | 1 | spacex_launches_item_v2 |

## 6. 采集条目明细

### 6.1 Starlink Official Updates

| 字段 | 内容 |
|---|---|
| id | 95bbf31b3a93d3e6 |
| title | Stargaze: SpaceX’s Space Situational Awareness System |
| url | https://starlink.com/updates/stargaze |
| source_id | starlink_official_updates |
| category | starlink_update |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | a2acff504bb0169a |
| previous_content_hash | a2acff504bb0169a |
| first_seen_at | 2026-07-14T14:54:30+08:00 |
| last_seen_at | 2026-07-15T07:54:27+00:00 |
| last_changed_at | 2026-07-15T15:30:05+08:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

| 字段 | 内容 |
|---|---|
| id | 044bafcf1089533d |
| title | Space Safety Web Interface |
| url | https://starlink.com/updates/space-safety-web-interface |
| source_id | starlink_official_updates |
| category | starlink_update |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | 15031e9924949a65 |
| previous_content_hash | 15031e9924949a65 |
| first_seen_at | 2026-07-15T15:30:05+08:00 |
| last_seen_at | 2026-07-15T07:54:27+00:00 |
| last_changed_at | 2026-07-15T15:30:05+08:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

| 字段 | 内容 |
|---|---|
| id | 495a49c7d5c93cbc |
| title | Starlink Beam Switching |
| url | https://starlink.com/updates/starlink-beam-switching |
| source_id | starlink_official_updates |
| category | starlink_update |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | 26342c05c89cd954 |
| previous_content_hash | 26342c05c89cd954 |
| first_seen_at | 2026-07-15T15:30:05+08:00 |
| last_seen_at | 2026-07-15T07:54:27+00:00 |
| last_changed_at | 2026-07-15T15:30:05+08:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

| 字段 | 内容 |
|---|---|
| id | d3b89bb9510b1b9a |
| title | Starlink Network Update |
| url | https://starlink.com/updates/network-update |
| source_id | starlink_official_updates |
| category | starlink_update |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | 2f7b8c18c91fe9b2 |
| previous_content_hash | 2f7b8c18c91fe9b2 |
| first_seen_at | 2026-07-15T15:34:13+08:00 |
| last_seen_at | 2026-07-15T07:54:27+00:00 |
| last_changed_at | 2026-07-15T15:34:13+08:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

### 6.2 SpaceX Official Launches

| 字段 | 内容 |
|---|---|
| id | c6060f6415f8c377 |
| title | SDA’s Third Tranche 1 Mission |
| url | https://www.spacex.com/launches/sda-t1tl-e |
| source_id | spacex_official_launches |
| category | spacex_launch |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | 85a78959c0b1f6e2 |
| previous_content_hash | 85a78959c0b1f6e2 |
| first_seen_at | 2026-07-15T15:31:12+08:00 |
| last_seen_at | 2026-07-15T07:55:01+00:00 |
| last_changed_at | 2026-07-15T15:31:12+08:00 |
| matched_keywords | [] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

## 7. 原始摘要与证据片段

### 7.1 Stargaze: SpaceX’s Space Situational Awareness System

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/stargaze)
- summary：Stargaze: SpaceX’s Space Situational Awareness System that enhances the safety and sustainability of satellite operations in low Earth orbit.
- evidence：SpaceX has developed a novel Space Situational Awareness (SSA) system, called Stargaze

### 7.2 Space Safety Web Interface

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/space-safety-web-interface)
- summary：A new web-based tool that simplifies satellite conjunction screening and ephemeris sharing for operators.
- evidence：To ensure safe spaceflight for everyone, all satellite operators should track their spacecraft with onboard GNSS, accurately predict their future trajectories, and broadcast that information to other satellite operators. Starlink currently publishes its ephemeris to multiple conjunction screening platforms and makes them available on our public website . For the past two years, Starlink has provided free, low-latency conjunction screening to participating satellite operators via our Space Traff…

### 7.3 Starlink Beam Switching

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/starlink-beam-switching)
- summary：Starlink uses beam switching to automatically route around obstacles for reliable high-speed internet.
- evidence：Starlink is built to deliver reliable high-speed internet, even when a customer’s view of the sky isn’t perfect. Trees, buildings, and other obstacles can temporarily block the connection to a given satellite, but the system is designed in such a way that these are generally imperceptible to the user. A given user terminal in the US has 10s of satellites in view, providing diversity to route traffic via a satellite with a stable and unobstructed connection. Starlink terminals automatically swit…

### 7.4 Starlink Network Update

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/network-update)
- summary：Latest updates on Starlink network speeds, latency, resilience, scalability, and capacity.
- evidence：Over the past year, Starlink has expanded to 42 new countries, territories and other markets around the world while growing by 2.7 million+ active customers globally and serving more than 6 million and counting with high-speed, low-latency internet. During that time, the SpaceX team has also launched more than 100 Starlink missions, adding 2,300+ satellites to the constellation, and invested heavily in our ground infrastructure, network backbone, and internal technologies and systems. As a resu…

### 7.5 SDA’s Third Tranche 1 Mission

- 来源：SpaceX Official Launches
- 链接：[链接](https://www.spacex.com/launches/sda-t1tl-e)
- summary：SpaceX designs, manufactures and launches advanced rockets and spacecraft. The company was founded in 2002 to revolutionize space technology, with the ultimate goal of enabling people to live on other planets.
- evidence：SpaceX is targeting Thursday, July 16 at 1:32 p.m. PT for a Falcon 9 launch of the Space Development Agency’s (SDA) third Tranche 1 data transport mission to low-Earth orbit from Space Launch Complex 4 East (SLC-4E) at Vandenberg Space Force Base in California. If needed, a backup opportunity is available on Friday, July 17 at 1:24 p.m. PT. This is the third of nine Tranche 1 missions Falcon 9 will launch on behalf of the SDA.

## 官方条目解析诊断

| 来源 | 解析器 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| SpaceX Official Launches | spacex_launches_item_v2 | 0 | 1 | 1 | 0 | 1 | 1 | 0 | 100% | 0 | 0 | 0 | 1 | item_level | medium |
| Starlink Official Updates | starlink_updates_item_v2 | 0 | 4 | 4 | 0 | 4 | 4 | 0 | 100% | 0 | 0 | 0 | 4 | item_level | medium |

| 状态 | 来源 | 标题 | 日期文本 | 相关性 | 层级 | 质量 | 字段证据 | 官方链接 |
|---|---|---|---|---|---|---|---|---|
| unchanged | Starlink Official Updates | Stargaze: SpaceX’s Space Situational Awareness System | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/stargaze) |
| unchanged | Starlink Official Updates | Space Safety Web Interface | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/space-safety-web-interface) |
| unchanged | Starlink Official Updates | Starlink Beam Switching | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/starlink-beam-switching) |
| unchanged | Starlink Official Updates | Starlink Network Update | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/network-update) |
| unchanged | SpaceX Official Launches | SDA’s Third Tranche 1 Mission | 未知 | incidental | item_level | medium/0.8 | evidence, mission_status, summary, title | [链接](https://www.spacex.com/launches/sda-t1tl-e) |

## 官方详情页解析诊断

| 来源 | 详情 URL | 静态状态 | 是否渲染 | 渲染状态 | 最终状态 | 最终方法 | 错误类型 | 是否复用历史记录 |
|---|---|---|---|---|---|---|---|---|
| SpaceX Official Launches | [详情](https://www.spacex.com/launches/sda-t1tl-e) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/stargaze) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/space-safety-web-interface) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/starlink-beam-switching) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/network-update) | javascript_shell | 是 | success | success | rendered | none | 否 |

### 详情失败类型

本轮没有详情解析失败。

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
- 运行时间：2026-07-15 15:30:05 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-15 15:34:13 中国标准时间+0800
  - ISO 周编号：2026-W29
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-15 07:49:56 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-07-15 07:54:27 UTC+0000
  - ISO 周编号：2026-W29
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
