# Starlink 情报周报总结版：2026-W29

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
- 新增条目数量：0
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
| 原始候选记录 | 9 |
| URL 去重后记录 | 7 |
| 最终核心输入记录 | 4 |
| 最终核心唯一 URL | 4 |
| 复用历史记录 | 0 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 7 |
| 输出 record ID 引用（前 / 后） | 4 / 4 |
| 输出 URL 引用（前 / 后） | 4 / 4 |
| 移除非法 record ID | 0 |
| 移除非法 URL | 0 |
| 补齐缺失 record ID | 0 |
| 补齐缺失 URL | 0 |
| 删除无来源要点 | 0 |
| 引用对齐状态 | passed |

### 页面级监测解释

- SpaceX Official Launches：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。

### LLM 调用统计

| 指标 | 数值 |
|---|---:|
| Prompt tokens | 4043 |
| Completion tokens | 584 |
| Total tokens | 4627 |
| API 调用耗时 | 6895.81 ms |

### 总体摘要

本周未检测到新增或内容变化条目。现有的官方 Starlink 更新条目包括：空间安全网络界面、网络更新、波束切换和 Stargaze 空间态势感知系统。

### 来源约束要点

| 要点 | 来源记录 | 来源链接 | 限制说明 |
|---|---|---|---|
| 现有官方条目介绍了一个新的基于网络的工具，用于简化卫星交会筛查和星历共享。 | 044bafcf1089533d | https://starlink.com/updates/space-safety-web-interface | 该条目内容在本轮监测中未发生变化。 |
| 现有官方条目介绍了 Starlink 网络速度、延迟、弹性、可扩展性和容量的最新更新。 | d3b89bb9510b1b9a | https://starlink.com/updates/network-update | 该条目内容在本轮监测中未发生变化。 |
| 现有官方条目说明 Starlink 使用波束切换自动绕开障碍物，以提供可靠的高速互联网。 | 495a49c7d5c93cbc | https://starlink.com/updates/starlink-beam-switching | 该条目内容在本轮监测中未发生变化。 |
| 现有官方条目介绍了 Stargaze，即 SpaceX 的空间态势感知系统，旨在提高低地球轨道卫星操作的安全性和可持续性。 | 95bbf31b3a93d3e6 | https://starlink.com/updates/stargaze | 该条目内容在本轮监测中未发生变化。 |


## 结构化官方条目

### 抽取概览

| 来源 | 候选 | 详情成功 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| SpaceX Official Launches | 1 | 1 | 0 | 0 | 0 | 1 | item_level | medium |
| Starlink Official Updates | 4 | 4 | 0 | 0 | 0 | 4 | item_level | medium |

### 详情解析情况

| 来源 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SpaceX Official Launches | 0 | 1 | 1 | 0 | 1 | 1 | 0 | 100% |
| Starlink Official Updates | 0 | 4 | 4 | 0 | 4 | 4 | 0 | 100% |

### 详情失败概览

本轮没有详情解析失败。

### 本周新增或变化条目

本周未检测到新增或内容变化的结构化官方条目。

### 条目抽取质量

| 来源 | Item-level 数量 | 标题完整度 | 日期完整度 | 证据完整度 | 页面级 fallback |
|---|---:|---:|---:|---:|---|
| SpaceX Official Launches | 1 | 1.0 | 0.0 | 1.0 | 否 |
| Starlink Official Updates | 4 | 1.0 | 0.0 | 1.0 | 否 |

## 条目生命周期概览

| 来源 | Active | New | Changed | Extraction Improved | Temporarily Missing | Long Absent | Fetch Failed | Recovered | Reappeared |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SpaceX Official Launches | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Starlink Official Updates | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

本轮未产生新增、语义变化、暂时消失、连续失败或恢复事件。

### 本轮新增条目

本轮没有首次发现的新条目。

### 本轮内容变化

本轮没有检测到语义内容变化。

### 解析质量提升

以下变化仅表示解析完整度提升，不代表官方内容发生变化。

本轮没有解析质量提升事件。

### 暂时消失与长期未见

未在本轮索引中发现不代表官方删除。

本轮没有暂时消失、长期未见或重新出现事件。

### 详情抓取失败与恢复

抓取失败或恢复属于采集链路状态，不代表官方业务状态。

本轮没有详情抓取失败或恢复事件。

### 历史版本

- 本轮新建 semantic versions：0
- 本轮新建 extraction revisions：0


## 运行健康与告警

| 指标 | 状态 |
|---|---|
| Health phase | provisional |
| Is final | False |
| 整体运行健康 | healthy |
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

- Info：0
- Warning：0
- High：0
- Critical：0
- Open conditions：0
- Resolved：0
本轮未产生需要人工处理的运维告警。

告警等级只表示自动化系统中的人工复查优先级，不表示 Starlink、SpaceX 或相关事件的战略重要性、影响程度或安全等级。

## 3. 来源状态概览

| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 | 主导解析层级 | 主导质量 |
|---|---|---|---:|---:|---:|---|---|
| Starlink Official Updates | reachable | changed | 0 | 0 | 4 | item_level | medium |
| SpaceX Official Launches | reachable | unchanged | 0 | 0 | 1 | item_level | medium |

## 4. 本周值得关注的信息

### 4.1 新增或变化条目

本周未检测到新增或内容变化的结构化官方条目。

### 4.2 页面级变化说明

- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。
- SpaceX Official Launches：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
页面变化状态与条目变化状态是两个检测层级，不能相互替代。

## 5. 解析质量概览

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 静态候选 | 渲染候选 | 候选总数 |
|---|---|---|---:|---:|---:|---:|
| Starlink Official Updates | item_level | medium | 0.8 | 0 | 4 | 4 |
| SpaceX Official Launches | item_level | medium | 0.8 | 0 | 1 | 1 |

说明：解析质量只表示规则化抽取完整度，不表示事实重要性或事实可信度。

## 6. 人工复查建议

- 对 `new` 或 `changed` 条目，建议人工打开来源链接复核；
- 对 `page_level / low` 记录，不应直接当作具体情报事实；
- 当前阶段不编造发布时间、发射时间、任务状态、载荷数量或技术细节；
- 代码层面 LLM 默认关闭；当前自动化运行已显式启用 LLM。只有 API 调用成功且通过来源约束校验后，摘要才会展示。

## 7. 本周文档

- 明细版文档：`weekly/2026-W29-details.md`
- 兼容索引文档：`weekly/2026-W29.md`

## 8. 最近一次自动化运行摘要

- 运行时间：2026-07-15 14:24:19 UTC+0000
- ISO 周编号：2026-W29
- 输出模式：dual
- 邮件发送方式：GitHub Actions 后续独立步骤
- 报告生成时邮件状态：pending_at_render_time
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 已接入来源数量：2
- 新增条目数：0
- 内容变化条目数：0
- 未变化条目数：5
- LLM Provider：deepseek
- LLM 摘要状态：generated
