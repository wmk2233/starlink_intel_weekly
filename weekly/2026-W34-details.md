# Starlink 情报周报明细版：2026-W34

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
| `data/item_lifecycle_state.json` | item-level 条目当前生命周期状态 |
| `data/item_versions.jsonl` | 限长的结构化语义与解析版本历史 |
| `data/lifecycle_events.jsonl` | 限长、去重的生命周期事件历史 |
| `data/lifecycle_report.json` | 本轮生命周期统计、事件与版本摘要 |
| `data/lifecycle_replay_report.json` | 完全离线的 `.invalid` 虚构生命周期回放验收摘要 |
| `data/alert_state.json` | 告警 watermark、open conditions、冷却和去重状态 |
| `data/alert_events.jsonl` | 限长的告警 notify/open/update/escalate/resolve 历史 |
| `data/alert_report.json` | 本轮告警摘要 |
| `data/run_health.json` | 当前运行健康状态 |
| `data/run_health_history.jsonl` | 限长、按 run ID 去重的长期趋势历史 |
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
| 输入记录数 | 6 |
| 去重前输入记录 | 15 |
| 去重后输入记录 | 13 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 13 |
| 原始候选记录 | 15 |
| URL 去重后记录 | 13 |
| 最终核心输入记录 | 6 |
| 最终核心唯一 URL | 6 |
| 复用历史记录 | 0 |
| 输出 record ID 去重前数量 | 6 |
| 输出 record ID 去重后数量 | 6 |
| 输出 URL 去重前数量 | 6 |
| 输出 URL 去重后数量 | 6 |
| 移除非法 record ID | 0 |
| 移除非法 URL | 0 |
| 补齐缺失 record ID | 0 |
| 补齐缺失 URL | 0 |
| 删除无来源要点 | 0 |
| 引用对齐状态 | passed |
| Prompt tokens | 5664 |
| Completion tokens | 5872 |
| Total tokens | 11536 |
| API 调用耗时 | 46664.95 ms |
| 校验状态 | failed |
| 严格来源约束 | true |
| 页面级记录禁止事实扩展 | true |
| 审计文件 | data/llm_audit.json |
| 摘要文件 | data/llm_summaries.json |
| 用量记录 | data/llm_usage.jsonl |

### 页面级监测解释

- SpaceX Official Launches：当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。
- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。

- 原因：LLM output failed source-guardrail validation.

### 错误类型

- new 条目缺少明确发布日期证据，不得描述为本周发布。


## 3. 来源状态诊断

| 来源 | 类别 | 类型 | 可信度 | 可达性 | 页面变化状态 | HTTP状态 | 最近检查时间 | page_hash |
|---|---|---|---|---|---|---|---|---|
| Starlink Official Updates | official_updates | official | S | reachable | changed | 200 | 2026-08-17T01:54:10+00:00 | 4abc1083c679244f |
| SpaceX Official Launches | official_launches | official | S | reachable | unchanged | 200 | 2026-08-17T01:54:46+00:00 | afd623b148154a55 |

## 4. 本周变化检测

| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 | 最近变化时间 |
|---|---:|---:|---:|---|---|
| Starlink Official Updates | 0 | 0 | 5 | changed | 2026-08-17T01:54:10+00:00 |
| SpaceX Official Launches | 1 | 0 | 0 | unchanged | 2026-06-17T18:23:48+08:00 |

## 5. 解析质量诊断

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 页面级 | 链接级 | 条目级 | 静态候选 | 渲染候选 | 候选总数 | 解析器版本 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Starlink Official Updates | item_level | medium | 0.8 | 0 | 0 | 5 | 0 | 5 | 5 | starlink_updates_item_v2 |
| SpaceX Official Launches | item_level | medium | 0.8 | 0 | 0 | 1 | 0 | 1 | 1 | spacex_launches_item_v2 |

## 6. 采集条目明细

### 6.1 Starlink Official Updates

| 字段 | 内容 |
|---|---|
| id | ba5555615b6e6fb6 |
| title | Starlink Version 3 Satellites |
| url | https://starlink.com/updates/starlink-version-3-satellites |
| source_id | starlink_official_updates |
| category | starlink_update |
| change_status | unchanged |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | 66117236912f2019 |
| previous_content_hash | 66117236912f2019 |
| first_seen_at | 2026-07-20T04:02:30+00:00 |
| last_seen_at | 2026-08-17T01:54:10+00:00 |
| last_changed_at | 2026-07-20T04:02:30+00:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

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
| content_hash | a4a8dfdee687fbe2 |
| previous_content_hash | a4a8dfdee687fbe2 |
| first_seen_at | 2026-07-14T14:54:30+08:00 |
| last_seen_at | 2026-08-17T01:54:10+00:00 |
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
| content_hash | 782864df0d71359e |
| previous_content_hash | 782864df0d71359e |
| first_seen_at | 2026-07-15T15:30:05+08:00 |
| last_seen_at | 2026-08-17T01:54:10+00:00 |
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
| content_hash | bbda025dc135eb82 |
| previous_content_hash | bbda025dc135eb82 |
| first_seen_at | 2026-07-15T15:30:05+08:00 |
| last_seen_at | 2026-08-17T01:54:10+00:00 |
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
| content_hash | a73aef78a8f128de |
| previous_content_hash | a73aef78a8f128de |
| first_seen_at | 2026-07-15T15:34:13+08:00 |
| last_seen_at | 2026-08-17T01:54:10+00:00 |
| last_changed_at | 2026-07-15T15:34:13+08:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

### 6.2 SpaceX Official Launches

| 字段 | 内容 |
|---|---|
| id | 607f72a4338081b3 |
| title | Starlink Mission |
| url | https://www.spacex.com/launches/sl-17-50 |
| source_id | spacex_official_launches |
| category | spacex_launch |
| change_status | new |
| extracted_level | item_level |
| source_quality | medium |
| extraction_confidence | 0.8 |
| content_hash | 56b3c2f2aa1cb44a |
| previous_content_hash |  |
| first_seen_at | 2026-08-17T01:54:46+00:00 |
| last_seen_at | 2026-08-17T01:54:46+00:00 |
| last_changed_at | 2026-08-17T01:54:46+00:00 |
| matched_keywords | ["starlink"] |
| candidate_links | [] |
| extraction_notes | 条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。 |

## 7. 原始摘要与证据片段

### 7.1 Starlink Version 3 Satellites

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/starlink-version-3-satellites)
- summary：Starlink V3 is our next generation satellite design with meaningful increases in capacity, data density, and power generation.
- evidence：The greater data density and number of beams from the new phased arrays are enabled by our next generation of SpaceX-developed beamformer chips. This ensures that information is routed efficiently and correctly across various beams. Additionally, the V3 satellites phased arrays are fed by upgraded chips that support a ~64x increase in throughput handled per modem chip. This increase enables us to more efficiently serve customers simultaneously in both densely and sparsely populated regions and…

### 7.2 Stargaze: SpaceX’s Space Situational Awareness System

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/stargaze)
- summary：Stargaze: SpaceX’s Space Situational Awareness System that enhances the safety and sustainability of satellite operations in low Earth orbit.
- evidence：SpaceX has developed a novel Space Situational Awareness (SSA) system, called Stargaze

### 7.3 Space Safety Web Interface

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/space-safety-web-interface)
- summary：A new web-based tool that simplifies satellite conjunction screening and ephemeris sharing for operators.
- evidence：To ensure safe spaceflight for everyone, all satellite operators should track their spacecraft with onboard GNSS, accurately predict their future trajectories, and broadcast that information to other satellite operators. Starlink currently publishes its ephemeris to multiple conjunction screening platforms and makes them available on our public website . For the past two years, Starlink has provided free, low-latency conjunction screening to participating satellite operators via our Space Traff…

### 7.4 Starlink Beam Switching

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/starlink-beam-switching)
- summary：Starlink uses beam switching to automatically route around obstacles for reliable high-speed internet.
- evidence：Starlink is built to deliver reliable high-speed internet, even when a customer’s view of the sky isn’t perfect. Trees, buildings, and other obstacles can temporarily block the connection to a given satellite, but the system is designed in such a way that these are generally imperceptible to the user. A given user terminal in the US has 10s of satellites in view, providing diversity to route traffic via a satellite with a stable and unobstructed connection. Starlink terminals automatically swit…

### 7.5 Starlink Network Update

- 来源：Starlink Official Updates
- 链接：[链接](https://starlink.com/updates/network-update)
- summary：Latest updates on Starlink network speeds, latency, resilience, scalability, and capacity.
- evidence：Over the past year, Starlink has expanded to 42 new countries, territories and other markets around the world while growing by 2.7 million+ active customers globally and serving more than 6 million and counting with high-speed, low-latency internet. During that time, the SpaceX team has also launched more than 100 Starlink missions, adding 2,300+ satellites to the constellation, and invested heavily in our ground infrastructure, network backbone, and internal technologies and systems. As a resu…

### 7.6 Starlink Mission

- 来源：SpaceX Official Launches
- 链接：[链接](https://www.spacex.com/launches/sl-17-50)
- summary：SpaceX designs, manufactures and launches advanced rockets and spacecraft. The company was founded in 2002 to revolutionize space technology, with the ultimate goal of enabling people to live on other planets.
- evidence：SpaceX’s Falcon 9 is targeting the launch of 24 Starlink satellites to low-Earth orbit from Space Launch Complex 4 East (SLC-4E) at Vandenberg Space Force Base in California.

## 官方条目解析诊断

| 来源 | 解析器 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| SpaceX Official Launches | spacex_launches_item_v2 | 0 | 1 | 1 | 0 | 1 | 1 | 0 | 100% | 0 | 1 | 0 | 0 | item_level | medium |
| Starlink Official Updates | starlink_updates_item_v2 | 0 | 5 | 5 | 0 | 5 | 5 | 0 | 100% | 0 | 0 | 0 | 5 | item_level | medium |

| 状态 | 来源 | 标题 | 日期文本 | 相关性 | 层级 | 质量 | 字段证据 | 官方链接 |
|---|---|---|---|---|---|---|---|---|
| unchanged | Starlink Official Updates | Starlink Version 3 Satellites | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/starlink-version-3-satellites) |
| unchanged | Starlink Official Updates | Stargaze: SpaceX’s Space Situational Awareness System | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/stargaze) |
| unchanged | Starlink Official Updates | Space Safety Web Interface | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/space-safety-web-interface) |
| unchanged | Starlink Official Updates | Starlink Beam Switching | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/starlink-beam-switching) |
| unchanged | Starlink Official Updates | Starlink Network Update | 未知 | direct | item_level | medium/0.8 | evidence, summary, title | [链接](https://starlink.com/updates/network-update) |
| new | SpaceX Official Launches | Starlink Mission | 未知 | direct | item_level | medium/0.8 | evidence, mission_status, payload_count, summary, title | [链接](https://www.spacex.com/launches/sl-17-50) |

## 官方详情页解析诊断

| 来源 | 详情 URL | 静态状态 | 是否渲染 | 渲染状态 | 最终状态 | 最终方法 | 错误类型 | 是否复用历史记录 |
|---|---|---|---|---|---|---|---|---|
| SpaceX Official Launches | [详情](https://www.spacex.com/launches/sl-17-50) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/starlink-version-3-satellites) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/stargaze) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/space-safety-web-interface) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/starlink-beam-switching) | javascript_shell | 是 | success | success | rendered | none | 否 |
| Starlink Official Updates | [详情](https://starlink.com/updates/network-update) | javascript_shell | 是 | success | success | rendered | none | 否 |

### 详情失败类型

本轮没有详情解析失败。

## 条目生命周期状态

| Record ID | 来源 | 标题 | 当前状态 | Change status | Extraction status | Semantic version | Extraction revision | Missing count | Failure count | Attention | 官方 URL |
|---|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 05610f007056730c | spacex_official_launches | Starlink Mission | long_absent | unchanged | unchanged | 1 | 1 | 4 | 0 | 否 | [链接](https://www.spacex.com/launches/sl-17-39) |
| 55130902f9db129e | spacex_official_launches | Starlink Mission | temporarily_missing | unchanged | unchanged | 1 | 1 | 1 | 0 | 否 | [链接](https://www.spacex.com/launches/sl-10-19) |
| 5bbf6ea4ad2f7fd0 | spacex_official_launches | Starlink Mission | temporarily_missing | unchanged | unchanged | 1 | 1 | 3 | 0 | 否 | [链接](https://www.spacex.com/launches/sl-17-52) |
| 607f72a4338081b3 | spacex_official_launches | Starlink Mission | active | new | unchanged | 1 | 1 | 0 | 0 | 否 | [链接](https://www.spacex.com/launches/sl-17-50) |
| c6060f6415f8c377 | spacex_official_launches | SDA's Third Tranche 1 Mission | long_absent | unchanged | unchanged | 1 | 1 | 5 | 0 | 否 | [链接](https://www.spacex.com/launches/sda-t1tl-e) |
| c8751f4ce5201339 | spacex_official_launches | Starlink Mission | temporarily_missing | unchanged | unchanged | 1 | 1 | 2 | 0 | 否 | [链接](https://www.spacex.com/launches/sl-17-53) |
| 044bafcf1089533d | starlink_official_updates | Space Safety Web Interface | active | unchanged | unchanged | 1 | 2 | 0 | 0 | 否 | [链接](https://starlink.com/updates/space-safety-web-interface) |
| 495a49c7d5c93cbc | starlink_official_updates | Starlink Beam Switching | active | unchanged | unchanged | 1 | 1 | 0 | 0 | 否 | [链接](https://starlink.com/updates/starlink-beam-switching) |
| 95bbf31b3a93d3e6 | starlink_official_updates | Stargaze: SpaceX's Space Situational Awareness System | active | unchanged | unchanged | 1 | 1 | 0 | 0 | 否 | [链接](https://starlink.com/updates/stargaze) |
| ba5555615b6e6fb6 | starlink_official_updates | Starlink Version 3 Satellites | active | unchanged | unchanged | 1 | 1 | 0 | 0 | 否 | [链接](https://starlink.com/updates/starlink-version-3-satellites) |
| d3b89bb9510b1b9a | starlink_official_updates | Starlink Network Update | active | unchanged | unchanged | 1 | 1 | 0 | 0 | 否 | [链接](https://starlink.com/updates/network-update) |

## 本轮生命周期事件

| 事件 | 来源 | 条目 | 前一状态 | 当前状态 | 变化字段 | 发生时间 | 限制说明 |
|---|---|---|---|---|---|---|---|
| long_absence_reached | spacex_official_launches | [05610f007056730c](https://www.spacex.com/launches/sl-17-39) | temporarily_missing | long_absent | 无 | 2026-08-17T01:55:02+00:00 | 长期未见，不代表删除 |
| temporarily_missing | spacex_official_launches | [55130902f9db129e](https://www.spacex.com/launches/sl-10-19) | active | temporarily_missing | 无 | 2026-08-17T01:55:02+00:00 | 未判定删除 |
| item_discovered | spacex_official_launches | [607f72a4338081b3](https://www.spacex.com/launches/sl-17-50) | unobserved | active | 无 | 2026-08-17T01:55:02+00:00 | 本轮首次发现，不等于本周发布 |

## 结构化版本历史

| Record ID | Semantic version | Extraction revision | Version kind | Observed at | Changed fields |
|---|---:|---:|---|---|---|
| 044bafcf1089533d | 1 | 1 | initial_snapshot | 2026-07-15T17:29:14+08:00 | 无 |
| 044bafcf1089533d | 1 | 2 | extraction_improvement | 2026-07-15T09:48:04+00:00 | detail_parse_method |
| 495a49c7d5c93cbc | 1 | 1 | initial_snapshot | 2026-07-15T17:29:14+08:00 | 无 |
| 95bbf31b3a93d3e6 | 1 | 1 | initial_snapshot | 2026-07-15T17:29:14+08:00 | 无 |
| c6060f6415f8c377 | 1 | 1 | initial_snapshot | 2026-07-15T17:29:14+08:00 | 无 |
| d3b89bb9510b1b9a | 1 | 1 | initial_snapshot | 2026-07-15T17:29:14+08:00 | 无 |
| 05610f007056730c | 1 | 1 | new_item | 2026-07-20T04:03:21+00:00 | 无 |
| ba5555615b6e6fb6 | 1 | 1 | new_item | 2026-07-20T04:03:21+00:00 | 无 |
| 5bbf6ea4ad2f7fd0 | 1 | 1 | new_item | 2026-07-27T04:01:08+00:00 | 无 |
| c8751f4ce5201339 | 1 | 1 | new_item | 2026-08-03T03:53:25+00:00 | 无 |
| 55130902f9db129e | 1 | 1 | new_item | 2026-08-10T02:33:14+00:00 | 无 |
| 607f72a4338081b3 | 1 | 1 | new_item | 2026-08-17T01:55:02+00:00 | 无 |


## 运维告警明细

| Alert Type | Kind | Severity | Action | Source | Record ID | Consecutive | First Opened | Last Observed | Status | Message |
|---|---|---|---|---|---|---:|---|---|---|---|
| item_discovered | event | info | notify | spacex_official_launches | 607f72a4338081b3 | 1 |  | 2026-08-17T01:54:10+00:00 | event | item_discovered |
| long_absent | condition | high | open | spacex_official_launches | 05610f007056730c | 4 |  | 2026-08-17T01:54:10+00:00 | event | long_absent |
| temporarily_missing | condition | warning | open | spacex_official_launches | 55130902f9db129e | 1 |  | 2026-08-17T01:54:10+00:00 | event | temporarily_missing |
| temporarily_missing | condition | warning | update | spacex_official_launches | 5bbf6ea4ad2f7fd0 | 3 |  | 2026-08-17T01:54:10+00:00 | event | temporarily_missing |
| long_absent | condition | high | update | spacex_official_launches | c6060f6415f8c377 | 5 |  | 2026-08-17T01:54:10+00:00 | event | long_absent |
| temporarily_missing | condition | warning | update | spacex_official_launches | c8751f4ce5201339 | 2 |  | 2026-08-17T01:54:10+00:00 | event | temporarily_missing |
| llm_validation_failed | condition | high | escalate |  |  | 3 |  | 2026-08-17T01:54:10+00:00 | event | llm_validation_failed |
| temporarily_missing | condition | warning | resolve | spacex_official_launches | 05610f007056730c | 3 |  | 2026-08-17T01:54:10+00:00 | event | temporarily_missing |
| llm_validation_failed | condition | high | current |  |  | 3 | 2026-08-03T03:52:32+00:00 | 2026-08-17T01:54:10+00:00 | open | llm_validation_failed |
| long_absent | condition | high | current | spacex_official_launches | 05610f007056730c | 4 | 2026-08-17T01:54:10+00:00 | 2026-08-17T01:54:10+00:00 | open | long_absent |
| long_absent | condition | high | current | spacex_official_launches | c6060f6415f8c377 | 5 | 2026-08-10T02:32:23+00:00 | 2026-08-17T01:54:10+00:00 | open | long_absent |
| temporarily_missing | condition | warning | current | spacex_official_launches | 55130902f9db129e | 1 | 2026-08-17T01:54:10+00:00 | 2026-08-17T01:54:10+00:00 | open | temporarily_missing |
| temporarily_missing | condition | warning | current | spacex_official_launches | 5bbf6ea4ad2f7fd0 | 3 | 2026-08-03T03:52:32+00:00 | 2026-08-17T01:54:10+00:00 | open | temporarily_missing |
| temporarily_missing | condition | warning | current | spacex_official_launches | c8751f4ce5201339 | 2 | 2026-08-10T02:32:23+00:00 | 2026-08-17T01:54:10+00:00 | open | temporarily_missing |

告警等级只表示自动化系统中的人工复查优先级，不表示 Starlink、SpaceX 或相关事件的战略重要性、影响程度或安全等级。

## 长期运行趋势

本表只展示 final health；旧记录中无法还原的 step outcome 保留为 unknown。

| 运行时间 | Phase | Overall health | 来源可达 | 详情成功率 | 新条目 | 变化条目 | 失败条目 | Open warning | Open high | LLM 状态 | 邮件状态 | Gitee 状态 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 2026-07-15T20:45:02+08:00 | final | healthy | 2/2 | 1.0 | 0 | 0 | 0 | 0 | 0 | skipped_disabled | disabled | skipped |
| 2026-07-15T12:57:08+00:00 | final | healthy | 2/2 | 1.0 | 0 | 0 | 0 | 0 | 0 | skipped_disabled | unknown | unknown |
| 2026-07-15T21:34:26+08:00 | final | healthy | 2/2 | 1.0 | 0 | 0 | 0 | 0 | 0 | generated | success | success |
| 2026-07-15T14:22:02+00:00 | final | healthy | 2/2 | 1.0 | 0 | 0 | 0 | 0 | 0 | skipped_disabled | success | success |
| 2026-07-15T14:25:33+00:00 | final | healthy | 2/2 | 1.0 | 0 | 0 | 0 | 0 | 0 | generated | success | success |
| 2026-07-16T01:08:20+00:00 | final | healthy | 2/2 | 1.0 | 0 | 0 | 0 | 0 | 0 | generated | success | success |
| 2026-07-20T04:03:44+00:00 | final | degraded | 2/2 | 1.0 | 2 | 0 | 0 | 1 | 0 | generated | success | success |
| 2026-07-27T04:01:42+00:00 | final | degraded | 2/2 | 1.0 | 1 | 0 | 0 | 2 | 0 | generated | success | success |
| 2026-08-03T03:54:17+00:00 | final | degraded | 2/2 | 1.0 | 1 | 0 | 0 | 4 | 0 | validation_failed | success | success |
| 2026-08-10T02:34:23+00:00 | final | degraded | 2/2 | 1.0 | 1 | 0 | 0 | 4 | 1 | validation_failed | success | success |

## 离线生命周期回放验收

- 场景数量：13
- 通过数量：13
- 失败数量：0
- 网络访问：False
- 生产文件修改：False

## 8. 局限性

- 当前仅接入两个官方来源；
- 静态候选为 0 时才会按 `auto` 模式尝试受控 Chromium 索引渲染；
- 浏览器不可用、候选为空或详情证据不足时会保留页面级 fallback；
- hash 变化不等于事实变化；
- 解析质量分数不代表事实重要性；
- 不编造发布时间、发射时间、任务状态、载荷数量或 Starlink 技术事实。

## 9. 自动化测试记录

- 运行时间：2026-08-17 01:54:10 UTC+0000
  - ISO 周编号：2026-W34
  - 执行环境：Linux 6.17.0-1022-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 邮件发送方式：GitHub Actions 后续独立步骤
  - 报告生成时邮件状态：pending_at_render_time
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=changed；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
