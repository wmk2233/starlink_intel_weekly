# Starlink 情报周报总结版：2026-W26

## 1. 本周概览

本周自动化流程已运行。当前系统接入两个官方来源：
- Starlink Official Updates
- SpaceX Official Launches

当前阶段为阶段 3A：引入大模型摘要，但强制来源约束。

## 2. 本周核心结论

- 本周接入来源数量：2
- 可达来源数量：2
- 页面发生变化的来源数量：0
- 新增条目数量：0
- 内容变化条目数量：0
- 未变化条目数量：2
- 当前解析质量总体判断：low（以当前规则解析完整度为准）

说明：本节仅基于规则化网页采集、hash 变化检测和解析质量诊断，不包含大模型事实推理。

## 大模型辅助摘要

当前状态：skipped

说明：
- 本节仅在显式启用 LLM 且通过来源约束校验后生成；
- 未配置 OpenAI API Key 时会自动跳过；
- 大模型摘要只基于 `data/items.jsonl` 等本地结构化来源数据；
- 无来源不写结论；
- 页面级记录不扩展成具体事实。

跳过原因：LLM is disabled.

当前主流程仍会继续生成周报、邮件、GitHub 提交和 Gitee 同步。


## 3. 来源状态概览

| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 | 主导解析层级 | 主导质量 |
|---|---|---|---:|---:|---:|---|---|
| Starlink Official Updates | reachable | unchanged | 0 | 0 | 1 | page_level | low |
| SpaceX Official Launches | reachable | unchanged | 0 | 0 | 1 | page_level | low |

## 4. 本周值得关注的信息

### 4.1 新增或变化条目

本周未检测到新增或内容变化条目。

### 4.2 页面级变化说明

- Starlink Official Updates：页面变化状态为 unchanged。
- SpaceX Official Launches：页面变化状态为 unchanged。
以上仅为页面 hash 或采集状态检测结果，不做事实推断。

## 5. 解析质量概览

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 候选链接数 |
|---|---|---|---:|---:|
| Starlink Official Updates | page_level | low | 0.35 | 0 |
| SpaceX Official Launches | page_level | low | 0.35 | 0 |

说明：解析质量只表示规则化抽取完整度，不表示事实重要性或事实可信度。

## 6. 人工复查建议

- 对 `new` 或 `changed` 条目，建议人工打开来源链接复核；
- 对 `page_level / low` 记录，不应直接当作具体情报事实；
- 当前阶段不编造发布时间、发射时间、任务状态、载荷数量或技术细节；
- LLM 摘要默认关闭，只有显式启用且通过来源约束校验后才展示。

## 7. 本周文档

- 明细版文档：`weekly/2026-W26-details.md`
- 兼容索引文档：`weekly/2026-W26.md`

## 8. 最近一次自动化运行摘要

- 运行时间：2026-06-22 05:29:19 UTC+0000
- ISO 周编号：2026-W26
- 输出模式：dual
- 是否发送邮件：是
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 已接入来源数量：2
- 新增条目数：0
- 内容变化条目数：0
- 未变化条目数：2
- LLM 摘要状态：skipped
