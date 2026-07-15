# Starlink 情报周报总结版：2026-W29

## 1. 本周概览

本周自动化流程已运行。当前系统接入两个官方来源：
- Starlink Official Updates
- SpaceX Official Launches

当前阶段为阶段 4A：完成两个官方索引页的条目发现、详情解析、稳定 ID、baseline 与页面级 fallback。

## 2. 本周核心结论

- 本周接入来源数量：2
- 可达来源数量：2
- 页面发生变化的来源数量：1
- baseline 条目数量：0
- 新增条目数量：0
- 内容变化条目数量：0
- 未变化条目数量：1
- 当前解析质量总体判断：low（以当前规则解析完整度为准）

说明：本节统计结论由结构化采集结果确定性生成，不依赖大模型；后续“大模型辅助摘要”小节为单独的来源约束型摘要。

## 大模型辅助摘要

LLM Provider：deepseek
模型：deepseek-v4-flash
状态：skipped

说明：
- 本节仅在显式启用 LLM 且通过来源约束校验后生成；
- 未配置当前 provider 对应的 API Key 时会自动跳过；
- 大模型摘要只基于 `data/items.jsonl` 等本地结构化来源数据；
- 无来源不写结论；
- 页面级记录不扩展成具体事实。

### 输入与引用去重

| 指标 | 数量 |
|---|---:|
| 去重前输入记录 | 5 |
| 去重后输入记录 | 3 |
| 删除重复记录 | 2 |
| 唯一来源 URL | 3 |
| 输出 record ID 引用（前 / 后） | 0 / 0 |
| 输出 URL 引用（前 / 后） | 0 / 0 |

### 页面级监测解释

- SpaceX Official Launches：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。

### LLM 调用统计

| 指标 | 数值 |
|---|---:|
| Prompt tokens | unknown |
| Completion tokens | unknown |
| Total tokens | unknown |
| API 调用耗时 | unknown ms |

跳过原因：LLM is disabled.

当前主流程仍会继续生成周报、邮件、GitHub 提交和 Gitee 同步。


## 结构化官方条目

### 抽取概览

| 来源 | 候选 | 详情成功 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| SpaceX Official Launches | 1 | 0 | 0 | 0 | 0 | 0 | page_level | low |
| Starlink Official Updates | 4 | 1 | 0 | 0 | 0 | 1 | item_level | high |

### 本周新增或变化条目

本周未检测到新增或内容变化的结构化官方条目。

### 条目抽取质量

| 来源 | Item-level 数量 | 标题完整度 | 日期完整度 | 证据完整度 | 页面级 fallback |
|---|---:|---:|---:|---:|---|
| SpaceX Official Launches | 0 | unknown | unknown | unknown | 是 |
| Starlink Official Updates | 1 | 1.0 | 1.0 | 1.0 | 否 |

## 3. 来源状态概览

| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 | 主导解析层级 | 主导质量 |
|---|---|---|---:|---:|---:|---|---|
| Starlink Official Updates | reachable | changed | 0 | 0 | 1 | item_level | high |
| SpaceX Official Launches | reachable | unchanged | 0 | 0 | 0 | page_level | low |

## 4. 本周值得关注的信息

### 4.1 新增或变化条目

本周未检测到新增或内容变化的结构化官方条目。

### 4.2 页面级变化说明

- Starlink Official Updates：页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。
- SpaceX Official Launches：页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。
页面变化状态与条目变化状态是两个检测层级，不能相互替代。

## 5. 解析质量概览

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 候选链接数 |
|---|---|---|---:|---:|
| Starlink Official Updates | item_level | high | 0.9 | 0 |
| SpaceX Official Launches | page_level | low | 0.35 | 1 |

说明：解析质量只表示规则化抽取完整度，不表示事实重要性或事实可信度。

## 6. 人工复查建议

- 对 `new` 或 `changed` 条目，建议人工打开来源链接复核；
- 对 `page_level / low` 记录，不应直接当作具体情报事实；
- 当前阶段不编造发布时间、发射时间、任务状态、载荷数量或技术细节；
- LLM 摘要默认关闭，只有显式启用且通过来源约束校验后才展示。

## 7. 本周文档

- 明细版文档：`weekly/2026-W29-details.md`
- 兼容索引文档：`weekly/2026-W29.md`

## 8. 最近一次自动化运行摘要

- 运行时间：2026-07-15 06:12:06 UTC+0000
- ISO 周编号：2026-W29
- 输出模式：dual
- 是否发送邮件：是
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 已接入来源数量：2
- 新增条目数：0
- 内容变化条目数：0
- 未变化条目数：1
- LLM Provider：deepseek
- LLM 摘要状态：skipped
