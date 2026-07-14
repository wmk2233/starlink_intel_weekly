# 官方页面解析侦察记录

## 范围与边界

本记录只针对 `sources.yml` 中两个既有官方索引页，不使用搜索引擎、第三方发射日程网站或外部事实。诊断不保存完整 HTML、截图、视频、HAR、Cookie 或 Secrets。

## 2026-07-14 侦察结果

| 来源 | 静态 HTTP | 静态 HTML 规模 | 静态候选 | 受控渲染观察 | 当前策略 |
|---|---:|---:|---:|---|---|
| Starlink Official Updates | 200 | 约 32 KB | 0 | 最终 baseline 运行发现 4 个允许路径候选，1 个达到条目级证据门槛 | item-level 优先 |
| SpaceX Official Launches | 200 | 约 3 KB | 0 | 最终 baseline 运行发现 1 个允许路径候选，但详情证据不足 | page-level fallback |

两个静态响应都未发现可直接使用的索引锚点、JSON-LD 或 `__NEXT_DATA__` 条目。由此采用 `render-mode=auto`：只有静态候选为 0 时才尝试 Playwright；最多滚动 5 次、每个来源总等待不超过约 30 秒，并阻止图片、媒体和字体请求。

## 解析规则

- Starlink 只接受同域 `/updates/<slug>`；
- SpaceX 只接受同域 `/launches/<slug>`；
- URL slug 只用于定位详情页，不用于推断标题、日期、任务状态或载荷事实；
- 详情页必须提供标题和可追溯 evidence 才建立 item-level 记录；
- 页面、浏览器或详情失败均不完成 bootstrap，也不删除历史条目；
- 首次成功 item-level 抽取建立 baseline，历史条目不属于本周新增；
- page-level fallback 置信度固定为 0.35；item-level 质量按日期和字段证据完整度确定；
- SpaceX 助推器历史中的 Starlink 提及属于 `incidental`，不能进入 Starlink 核心结论。

## 复现命令

```powershell
python scripts/diagnose_official_pages.py --all --no-write
python scripts/collect_sources.py --max-source-items 10 --render-mode auto --dry-run
```
