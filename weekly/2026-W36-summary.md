# Starlink 情报周报总结版：2026-W36

## 1. 本周概览

本周自动化流程已运行。当前系统接入两个官方来源：
- Starlink Official Updates
- SpaceX Official Launches

当前阶段为阶段 4D.2：周报统一展示生成时点的 provisional 健康快照与独立邮件步骤，运行结束后的 final 状态以 GitHub Actions Summary 和 `data/run_health.json` 为准；pending_at_render_time 不是失败。这些采集及告警状态不代表官方业务状态或事件重要程度。

## 2. 本周核心结论

- 本周接入来源数量：2
- 可达来源数量：2
- 页面发生变化的来源数量：0
- baseline 条目数量：0
- 新增条目数量：1
- 内容变化条目数量：0
- 未变化条目数量：5
- 当前解析质量总体判断：medium（以当前规则解析完整度为准）

说明：本节统计结论由结构化采集结果确定性生成，不依赖大模型；后续“大模型辅助摘要”小节为单独的来源约束型摘要。

## 大模型辅助摘要

LLM Provider：deepseek
模型：deepseek-v4-flash
状态：generated

说明：
- 代码层面 LLM 默认关闭；当前自动化运行已显式启用 LLM。只有 API 调用成功且通过来源约束校验后，摘要才会展示。
- 本节仅在显式启用 LLM 且通过来源约束校验后生成；
- 未配置当前 provider 对应的 API Key 时会自动跳过；
- 大模型摘要只基于 `data/items.jsonl` 等本地结构化来源数据；
- 无来源不写结论；
- 页面级记录不扩展成具体事实。

### 输入与引用去重

| 指标 | 数量 |
|---|---:|
| 原始候选记录 | 17 |
| URL 去重后记录 | 15 |
| 最终核心输入记录 | 6 |
| 最终核心唯一 URL | 6 |
| 复用历史记录 | 0 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 15 |
| 输出 record ID 引用（前 / 后） | 6 / 6 |
| 输出 URL 引用（前 / 后） | 6 / 6 |
| 移除非法 record ID | 0 |
| 移除非法 URL | 0 |
| 补齐缺失 record ID | 0 |
| 补齐缺失 URL | 0 |
| 删除无来源要点 | 0 |
| 引用对齐状态 | passed |

### 页面级监测解释

- SpaceX Official Launches：当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。
- Starlink Official Updates：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。

### LLM 调用统计

| 指标 | 数值 |
|---|---:|
| Prompt tokens | 5664 |
| Completion tokens | 6123 |
| Total tokens | 11787 |
| API 调用耗时 | 49845.73 ms |

### 总体摘要

本轮共监测到 6 个官方条目：其中 1 个为首次观测到的 SpaceX Starlink 发射条目，5 个为未发生语义变化的现有 Starlink 官方更新条目；本轮未检测到 changed 状态条目。

### 来源约束要点

| 要点 | 来源记录 | 来源链接 | 限制说明 |
|---|---|---|---|
| 当前监测到的 SpaceX 官方发射条目“Starlink Mission”显示，Falcon 9 计划从加州范登堡太空军基地 SLC-4E 发射 27 颗 Starlink 卫星至近地轨道，任务状态为 targeting（瞄准中）。 | 1ce0691a44c65212 | https://www.spacex.com/launches/sl-15-23 | 官方条目未提供具体发射日期。 |
| 现有官方条目介绍 Starlink V3 为下一代卫星设计，容量、数据密度和发电能力显著提升；其相控阵由下一代 SpaceX 波束成形芯片驱动，单个调制解调器芯片处理的吞吐量提升约 64 倍。 | ba5555615b6e6fb6 | https://starlink.com/updates/starlink-version-3-satellites |  |
| 当前监测到的 Starlink 官方条目介绍了用于卫星交会筛选和星历共享的网页界面；Starlink 向多个交会筛选平台公开星历，并通过 Space Traffic Coordination API 为参与运营商提供免费低延迟交会筛选。 | 044bafcf1089533d | https://starlink.com/updates/space-safety-web-interface |  |
| 现有官方条目记录显示，Starlink 过去一年扩展至 42 个新国家、地区或其他市场，全球活跃客户增长 270 万以上，客户总数超过 600 万；同期发射超过 100 次 Starlink 任务，新增 2300 多颗卫星。截至 2025 年 7 月，美国 200 多万活跃客户在高峰时段的中位下载速度接近 200 Mbps。 | d3b89bb9510b1b9a | https://starlink.com/updates/network-update | 该条目中的统计数字均为官方条目给出的历史期间数据。 |
| 现有官方条目说明，Starlink 终端会自动在可见卫星间实时切换，以应对树木、建筑物等遮挡造成的信号降级，并持续构建实时遮挡图以保持稳定连接。 | 495a49c7d5c93cbc | https://starlink.com/updates/starlink-beam-switching |  |
| 现有官方条目介绍 SpaceX 开发了名为 Stargaze 的空间态势感知（SSA）系统，旨在提升低地球轨道卫星运行的安全性和可持续性；该系统利用超过 30,000 个光学传感器跟踪近地点 600 公里以下 50% 的物体，并已开始发布交会数据消息（CDM）。 | 95bbf31b3a93d3e6 | https://starlink.com/updates/stargaze |  |


## 结构化官方条目

### 抽取概览

| 来源 | 候选 | 详情成功 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| SpaceX Official Launches | 1 | 1 | 0 | 1 | 0 | 0 | item_level | medium |
| Starlink Official Updates | 5 | 5 | 0 | 0 | 0 | 5 | item_level | medium |

### 详情解析情况

| 来源 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SpaceX Official Launches | 0 | 1 | 1 | 0 | 1 | 1 | 0 | 100% |
| Starlink Official Updates | 0 | 5 | 5 | 0 | 5 | 5 | 0 | 100% |

### 详情失败概览

本轮没有详情解析失败。

### 本周新增或变化条目

| 标题 | 来源 | 官方日期文本 | 状态 | 解析层级 | 质量 | 官方链接 |
|---|---|---|---|---|---|---|
| Starlink Mission | SpaceX Official Launches | 未知 | new | item_level | medium | [链接](https://www.spacex.com/launches/sl-15-23) |

### 条目抽取质量

| 来源 | Item-level 数量 | 标题完整度 | 日期完整度 | 证据完整度 | 页面级 fallback |
|---|---:|---:|---:|---:|---|
| SpaceX Official Launches | 1 | 1.0 | 0.0 | 1.0 | 否 |
| Starlink Official Updates | 5 | 1.0 | 0.0 | 1.0 | 否 |

## 条目生命周期概览

| 来源 | Active | New | Changed | Extraction Improved | Temporarily Missing | Long Absent | Fetch Failed | Recovered | Reappeared |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SpaceX Official Launches | 1 | 1 | 0 | 0 | 3 | 4 | 0 | 0 | 0 |
| Starlink Official Updates | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### 本轮新增条目

- [1ce0691a44c65212](https://www.spacex.com/launches/sl-15-23)：本轮首次发现，不自动等于官方本周首次发布。

### 本轮内容变化

本轮没有检测到语义内容变化。

### 解析质量提升

以下变化仅表示解析完整度提升，不代表官方内容发生变化。

本轮没有解析质量提升事件。

### 暂时消失与长期未见

未在本轮索引中发现不代表官方删除。

- [4dd339041081b52c](https://www.spacex.com/launches/sl-10-49)：temporarily_missing。
- [c8751f4ce5201339](https://www.spacex.com/launches/sl-17-53)：long_absence_reached。

### 详情抓取失败与恢复

抓取失败或恢复属于采集链路状态，不代表官方业务状态。

本轮没有详情抓取失败或恢复事件。

### 历史版本

- 本轮新建 semantic versions：1
- 本轮新建 extraction revisions：0


## 运行健康与告警

| 指标 | 状态 |
|---|---|
| Health phase | provisional |
| Is final | False |
| 整体运行健康 | degraded |
| 来源采集 | healthy |
| 候选发现 | healthy |
| 详情解析 | healthy |
| 生命周期处理 | healthy |
| LLM | healthy |
| 输出检查 | pending_at_render_time |
| 项目审计 | pending_at_render_time |
| 邮件 | pending_at_render_time |
| Gitee 同步 | pending_at_render_time |
| Workflow 核心流程 | pending_at_render_time |

本表是周报生成时点的 provisional 快照；pending_at_render_time 不是失败。运行结束后的最终状态以 GitHub Actions Summary 和 data/run_health.json 为准。

### 本轮告警摘要

- Info：1
- Warning：4
- High：5
- Critical：0
- Open conditions：7
- Resolved：2

告警等级只表示自动化系统中的人工复查优先级，不表示 Starlink、SpaceX 或相关事件的战略重要性、影响程度或安全等级。

## 3. 来源状态概览

| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 | 主导解析层级 | 主导质量 |
|---|---|---|---:|---:|---:|---|---|
| Starlink Official Updates | reachable | unchanged | 0 | 0 | 5 | item_level | medium |
| SpaceX Official Launches | reachable | unchanged | 1 | 0 | 0 | item_level | medium |

## 4. 本周值得关注的信息

### 4.1 新增或变化条目

| 标题 | 来源 | 官方日期文本 | 状态 | 解析层级 | 质量 | 官方链接 |
|---|---|---|---|---|---|---|
| Starlink Mission | SpaceX Official Launches | 未知 | new | item_level | medium | [链接](https://www.spacex.com/launches/sl-15-23) |

### 4.2 页面级变化说明

- Starlink Official Updates：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
- SpaceX Official Launches：当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。
页面变化状态与条目变化状态是两个检测层级，不能相互替代。

## 5. 解析质量概览

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 静态候选 | 渲染候选 | 候选总数 |
|---|---|---|---:|---:|---:|---:|
| Starlink Official Updates | item_level | medium | 0.8 | 0 | 5 | 5 |
| SpaceX Official Launches | item_level | medium | 0.8 | 0 | 1 | 1 |

说明：解析质量只表示规则化抽取完整度，不表示事实重要性或事实可信度。

## 6. 人工复查建议

- 对 `new` 或 `changed` 条目，建议人工打开来源链接复核；
- 对 `page_level / low` 记录，不应直接当作具体情报事实；
- 当前阶段不编造发布时间、发射时间、任务状态、载荷数量或技术细节；
- 代码层面 LLM 默认关闭；当前自动化运行已显式启用 LLM。只有 API 调用成功且通过来源约束校验后，摘要才会展示。

## 7. 本周文档

- 明细版文档：`weekly/2026-W36-details.md`
- 兼容索引文档：`weekly/2026-W36.md`

## 8. 最近一次自动化运行摘要

- 运行时间：2026-08-31 05:30:09 UTC+0000
- ISO 周编号：2026-W36
- 输出模式：dual
- 邮件发送方式：GitHub Actions 后续独立步骤
- 报告生成时邮件状态：pending_at_render_time
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 已接入来源数量：2
- 新增条目数：1
- 内容变化条目数：0
- 未变化条目数：5
- LLM Provider：deepseek
- LLM 摘要状态：generated
