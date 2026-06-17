# Starlink 技术情报长期知识库

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
| Starlink Official Updates | 2026-06-17T20:36:26+08:00 | reachable | unchanged | 2026-06-17T17:43:22+08:00 | 正常 |
| SpaceX Official Launches | 2026-06-17T20:36:27+08:00 | reachable | unchanged | 2026-06-17T18:23:48+08:00 | 正常 |

## 来源解析质量诊断

| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 候选链接数 |
|---|---|---|---:|---:|
| Starlink Official Updates | page_level | low | 0.35 | 0 |
| SpaceX Official Launches | page_level | low | 0.35 | 0 |

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

## 最近一次自动化运行记录

- 运行时间：2026-06-17 20:36:26 中国标准时间+0800
- ISO 周编号：2026-W25
- 执行环境：Windows 10
- Python 版本：3.11.9
- 输出模式：dual
- 是否发送邮件：否
- 是否执行真实来源采集：是
- 是否生成解析质量诊断：是
- 总结版文档：weekly/2026-W25-summary.md
- 明细版文档：weekly/2026-W25-details.md
- 兼容索引文档：weekly/2026-W25.md
- 周报总索引：weekly/index.md
- 周报 manifest：data/weekly_manifest.json
- 运行历史：data/run_history.jsonl
- 本次采集来源名称：Starlink Official Updates、SpaceX Official Launches
- 本次采集条目数量：2
- 已接入来源数量：2
- 来源可达性概览：Starlink Official Updates=reachable；SpaceX Official Launches=reachable
- 页面变化状态概览：Starlink Official Updates=unchanged；SpaceX Official Launches=unchanged
- 新增条目数：0
- 内容变化条目数：0
- 未变化条目数：2

