# Starlink 情报周报总结版：2026-W30

## 1. 本周概览

本周自动化流程已运行。当前系统接入两个官方来源：
- Starlink Official Updates
- SpaceX Official Launches

当前阶段为阶段 4D.2：周报统一展示生成时点的 provisional 健康快照与独立邮件步骤，运行结束后的 final 状态以 GitHub Actions Summary 和 `data/run_health.json` 为准；pending_at_render_time 不是失败。这些采集及告警状态不代表官方业务状态或事件重要程度。

## 2. 本周核心结论

- 本周接入来源数量：2
- 可达来源数量：2
- 页面发生变化的来源数量：1
- baseline 条目数量：0
- 新增条目数量：2
- 内容变化条目数量：0
- 未变化条目数量：4
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
| 原始候选记录 | 11 |
| URL 去重后记录 | 9 |
| 最终核心输入记录 | 6 |
| 最终核心唯一 URL | 6 |
| 复用历史记录 | 0 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 9 |
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
- Starlink Official Updates：当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。

### LLM 调用统计

| 指标 | 数值 |
|---|---:|
| Prompt tokens | 5588 |
| Completion tokens | 1037 |
| Total tokens | 6625 |
| API 调用耗时 | 10382.79 ms |

### 总体摘要

本周系统首次检测到两项新的官方条目：一项计划中的Starlink发射任务和Starlink V3卫星的官方介绍；其他已有官方条目（空间安全界面、网络更新、光束切换、Stargaze）内容未发生变化。

### 来源约束要点

| 要点 | 来源记录 | 来源链接 | 限制说明 |
|---|---|---|---|
| 系统首次发现一项计划中的Starlink任务，目标发射24颗Starlink卫星至近地轨道，当前状态为“targeting”。 | 05610f007056730c | https://www.spacex.com/launches/sl-17-39 |  |
| 系统首次发现Starlink V3卫星的官方介绍文档，该文档描述了下一代卫星设计在容量、数据密度和发电能力上的提升，并提及新型波束成形芯片实现了每调制解调器芯片吞吐量约64倍的增长。 | ba5555615b6e6fb6 | https://starlink.com/updates/starlink-version-3-satellites |  |
| 现有官方条目介绍了空间安全网络界面，该工具用于简化卫星交会筛查和星历共享。 | 044bafcf1089533d | https://starlink.com/updates/space-safety-web-interface |  |
| 现有官方条目发布了Starlink网络更新，涵盖速度、延迟、弹性和容量方面的最新进展。 | d3b89bb9510b1b9a | https://starlink.com/updates/network-update |  |
| 现有官方条目介绍了Starlink光束切换技术，利用实时障碍物地图自动切换卫星以保持可靠连接。 | 495a49c7d5c93cbc | https://starlink.com/updates/starlink-beam-switching |  |
| 现有官方条目介绍了Stargaze系统，即SpaceX开发的新型空间态势感知（SSA）系统，用于增强低地球轨道的卫星运行安全与可持续性。 | 95bbf31b3a93d3e6 | https://starlink.com/updates/stargaze |  |


## 结构化官方条目

### 抽取概览

| 来源 | 候选 | 详情成功 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| SpaceX Official Launches | 1 | 1 | 0 | 1 | 0 | 0 | item_level | medium |
| Starlink Official Updates | 5 | 5 | 0 | 1 | 0 | 4 | item_level | medium |

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
| Starlink Version 3 Satellites | Starlink Official Updates | 未知 | new | item_level | medium | [链接](https://starlink.com/updates/starlink-version-3-satellites) |
| Starlink Mission | SpaceX Official Launches | 未知 | new | item_level | medium | [链接](https://www.spacex.com/launches/sl-17-39) |

### 条目抽取质量

| 来源 | Item-level 数量 | 标题完整度 | 日期完整度 | 证据完整度 | 页面级 fallback |
|---|---:|---:|---:|---:|---|
| SpaceX Official Launches | 1 | 1.0 | 0.0 | 1.0 | 否 |
| Starlink Official Updates | 5 | 1.0 | 0.0 | 1.0 | 否 |

## 条目生命周期概览

| 来源 | Active | New | Changed | Extraction Improved | Temporarily Missing | Long Absent | Fetch Failed | Recovered | Reappeared |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SpaceX Official Launches | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| Starlink Official Updates | 5 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### 本轮新增条目

- [05610f007056730c](https://www.spacex.com/launches/sl-17-39)：本轮首次发现，不自动等于官方本周首次发布。
- [ba5555615b6e6fb6](https://starlink.com/updates/starlink-version-3-satellites)：本轮首次发现，不自动等于官方本周首次发布。

### 本轮内容变化

本轮没有检测到语义内容变化。

### 解析质量提升

以下变化仅表示解析完整度提升，不代表官方内容发生变化。

本轮没有解析质量提升事件。

### 暂时消失与长期未见

未在本轮索引中发现不代表官方删除。

- [c6060f6415f8c377](https://www.spacex.com/launches/sda-t1tl-e)：temporarily_missing。

### 详情抓取失败与恢复

抓取失败或恢复属于采集链路状态，不代表官方业务状态。

本轮没有详情抓取失败或恢复事件。

### 历史版本

- 本轮新建 semantic versions：2
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

- Info：2
- Warning：1
- High：0
- Critical：0
- Open conditions：1
- Resolved：0

告警等级只表示自动化系统中的人工复查优先级，不表示 Starlink、SpaceX 或相关事件的战略重要性、影响程度或安全等级。

## 3. 来源状态概览

| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 | 主导解析层级 | 主导质量 |
|---|---|---|---:|---:|---:|---|---|
| Starlink Official Updates | reachable | changed | 1 | 0 | 4 | item_level | medium |
| SpaceX Official Launches | reachable | unchanged | 1 | 0 | 0 | item_level | medium |

## 4. 本周值得关注的信息

### 4.1 新增或变化条目

| 标题 | 来源 | 官方日期文本 | 状态 | 解析层级 | 质量 | 官方链接 |
|---|---|---|---|---|---|---|
| Starlink Version 3 Satellites | Starlink Official Updates | 未知 | new | item_level | medium | [链接](https://starlink.com/updates/starlink-version-3-satellites) |
| Starlink Mission | SpaceX Official Launches | 未知 | new | item_level | medium | [链接](https://www.spacex.com/launches/sl-17-39) |

### 4.2 页面级变化说明

- Starlink Official Updates：当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。
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

- 明细版文档：`weekly/2026-W30-details.md`
- 兼容索引文档：`weekly/2026-W30.md`

## 8. 最近一次自动化运行摘要

- 运行时间：2026-07-20 04:02:30 UTC+0000
- ISO 周编号：2026-W30
- 输出模式：dual
- 邮件发送方式：GitHub Actions 后续独立步骤
- 报告生成时邮件状态：pending_at_render_time
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 已接入来源数量：2
- 新增条目数：2
- 内容变化条目数：0
- 未变化条目数：4
- LLM Provider：deepseek
- LLM 摘要状态：generated
