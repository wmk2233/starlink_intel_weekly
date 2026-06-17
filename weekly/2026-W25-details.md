# Starlink 情报周报明细版：2026-W25

## 1. 文档说明

本明细版用于来源复查、结构化数据核验和知识库维护。内容来自规则化网页采集、hash 变化检测和解析质量诊断，不包含大模型事实推理。

## 2. 数据文件

| 文件 | 说明 |
|---|---|
| `data/items.jsonl` | 结构化采集条目 |
| `data/source_status.json` | 来源状态与变化检测 |
| `data/extraction_quality.json` | 解析质量诊断 |

## 3. 来源状态诊断

| 来源 | 类别 | 类型 | 可信度 | 可达性 | 页面变化状态 | HTTP状态 | 最近检查时间 | page_hash |
|---|---|---|---|---|---|---|---|---|
| Starlink Official Updates | official_updates | official | S | reachable | unchanged | 200 | 2026-06-17T12:23:21+00:00 | 34d4db5ebd0e1223 |
| SpaceX Official Launches | official_launches | official | S | reachable | unchanged | 200 | 2026-06-17T12:23:21+00:00 | afd623b148154a55 |

## 4. 本周变化检测

| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 | 最近变化时间 |
|---|---:|---:|---:|---|---|
| Starlink Official Updates | 0 | 0 | 1 | unchanged | 2026-06-17T17:43:22+08:00 |
| SpaceX Official Launches | 0 | 0 | 1 | unchanged | 2026-06-17T18:23:48+08:00 |

## 5. 解析质量诊断

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 页面级 | 链接级 | 条目级 | 候选链接数 | 解析器版本 |
|---|---|---|---:|---:|---:|---:|---:|---|
| Starlink Official Updates | page_level | low | 0.35 | 1 | 0 | 0 | 0 | rule_based_html_v4 |
| SpaceX Official Launches | page_level | low | 0.35 | 1 | 0 | 0 | 0 | rule_based_html_v4 |

## 6. 采集条目明细

### 6.1 Starlink Official Updates

| 字段 | 内容 |
|---|---|
| id | 42a0ea622e13944d |
| title | Starlink |
| url | https://www.starlink.com/updates |
| source_id | starlink_official_updates |
| category | official_updates |
| change_status | unchanged |
| extracted_level | page_level |
| source_quality | low |
| extraction_confidence | 0.35 |
| content_hash | cfd6a771f245409c |
| previous_content_hash | cfd6a771f245409c |
| first_seen_at | 2026-06-17T09:31:46+00:00 |
| last_seen_at | 2026-06-17T12:23:21+00:00 |
| last_changed_at | 2026-06-17T17:43:22+08:00 |
| matched_keywords | ["starlink", "update", "updates"] |
| candidate_links | [] |
| extraction_notes | 页面可达，但当前静态规则未识别到稳定的独立条目；保留页面级记录，不补写发布时间或技术事实。 |

### 6.2 SpaceX Official Launches

| 字段 | 内容 |
|---|---|
| id | e7e9456a75b0c4db |
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
| first_seen_at | 2026-06-17T18:23:48+08:00 |
| last_seen_at | 2026-06-17T12:23:21+00:00 |
| last_changed_at | 2026-06-17T18:23:48+08:00 |
| matched_keywords | ["launch", "launches"] |
| candidate_links | [] |
| extraction_notes | 页面可达，但当前静态规则未识别到稳定的独立条目；保留页面级记录，不补写发布时间或技术事实。 |

## 7. 原始摘要与证据片段

### 7.1 Starlink

- 来源：Starlink Official Updates
- 链接：[链接](https://www.starlink.com/updates)
- summary：规则化采集生成 Starlink Official Updates 页面级记录。未编造发布时间或具体技术事实。
- evidence：Starlink

### 7.2 SpaceX

- 来源：SpaceX Official Launches
- 链接：[链接](https://www.spacex.com/launches)
- summary：规则化采集生成 SpaceX Official Launches 页面级记录。未编造发射时间、任务状态或载荷数量。
- evidence：SpaceX

## 8. 局限性

- 当前仅接入两个官方来源；
- 当前仅进行规则化静态 HTML 解析；
- 动态渲染页面可能只能形成页面级记录；
- hash 变化不等于事实变化；
- 解析质量分数不代表事实重要性；
- 不编造发布时间、发射时间、任务状态、载荷数量或 Starlink 技术事实。

## 9. 自动化测试记录

- 运行时间：2026-06-17 08:56:20 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：未知
  - 是否生成解析质量诊断：未知
  - 页面变化状态：未知
  - 已接入来源数量：未知
- 运行时间：2026-06-17 17:08:32 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：未知
  - 是否生成解析质量诊断：未知
  - 页面变化状态：未知
  - 已接入来源数量：未知
- 运行时间：2026-06-17 09:12:58 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：未知
  - 是否生成解析质量诊断：未知
  - 页面变化状态：未知
  - 已接入来源数量：未知
- 运行时间：2026-06-17 17:27:39 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：未知
  - 已接入来源数量：未知
- 运行时间：2026-06-17 17:29:06 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：未知
  - 已接入来源数量：未知
- 运行时间：2026-06-17 09:31:46 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：未知
  - 已接入来源数量：未知
- 运行时间：2026-06-17 17:43:55 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：unchanged
  - 已接入来源数量：未知
- 运行时间：2026-06-17 10:01:31 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：unchanged
  - 已接入来源数量：未知
- 运行时间：2026-06-17 10:08:27 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：unchanged
  - 已接入来源数量：未知
- 运行时间：2026-06-17 18:29:33 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 18:30:05 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 10:42:18 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：未知
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 19:11:41 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：未知
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 11:16:00 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：未知
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 19:32:27 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 19:32:56 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：both
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 19:33:19 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 11:38:20 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 20:19:20 中国标准时间+0800
  - ISO 周编号：2026-W25
  - 执行环境：Windows 10
  - Python 版本：3.11.9
  - 输出模式：dual
  - 是否发送邮件：否
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
- 运行时间：2026-06-17 12:23:21 UTC+0000
  - ISO 周编号：2026-W25
  - 执行环境：Linux 6.17.0-1018-azure
  - Python 版本：3.11.15
  - 输出模式：dual
  - 是否发送邮件：是
  - 是否执行真实来源采集：是
  - 是否生成解析质量诊断：是
  - 页面变化状态：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
  - 已接入来源数量：2
