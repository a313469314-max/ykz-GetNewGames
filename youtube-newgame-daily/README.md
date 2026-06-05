# YouTube 新游线索日报工具

这个子项目的产品展示名是 **YouTube 新游线索**。它负责扫描指定 YouTube 频道的视频，从标题、描述和商店链接中提取新游戏线索，生成日报，保存 SQLite 历史台账，并可选通过飞书群机器人发送日报。

它和 `D:\GetNewGames\adx` 相互独立：YouTube 项目不依赖 DataEye；两个来源只在 `D:\GetNewGames\feishu-sync` 同步到飞书多维表格时汇合。

同步到飞书多维表格时，对应栏目名是 `YouTube 新游线索`。

## 目录

```text
D:\GetNewGames\youtube-newgame-daily
```

## 当前流程

`python main.py` 会执行完整流水线：

1. 读取 `channels.yaml` 和 `channels.csv`。
2. 使用 YouTube Data API v3 解析频道和 uploads playlist。
3. 按 `Asia/Shanghai` 计算日期窗口。
4. 扫描最近 3 个完整自然日内发布的视频。
5. 从视频描述和标题中提取 Google Play、App Store、Steam、TapTap、官网、落地页等候选链接。
6. 访问页面标题补全游戏名；Google Play / App Store 链接必须优先使用商店页标题作为最终游戏名。
7. 给候选打 `high`、`medium`、`low`、`rejected` 置信度。
8. 保存视频、候选、运行记录和已输出记录到 SQLite。
9. 根据历史输出记录去重，只把未发过的高质量条目写入日报。

抓取频道时通过频道的 `uploads playlist` 分页翻取，直到视频发布时间早于窗口起始时间；不是只抓最近固定 N 条视频，因此高频频道在目标窗口内较早发布的视频也能被覆盖。

## 安装

```powershell
cd D:\GetNewGames\youtube-newgame-daily
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 配置

推荐复制 `.env.example` 为 `.env`，或直接通过系统环境变量配置。示例文件只保留空值，不要写入真实 key 或 webhook。

```env
YOUTUBE_API_KEY=
YOUTUBE_FEISHU_WEBHOOK=
FEISHU_WEBHOOK=
```

核心配置文件：

```text
channels.yaml
channels.csv
```

`channels.csv` 至少包含：

```text
name
channel_url
enabled
channel_id
```

`channel_id` 可以为空。为空时程序会尝试从 `channel_url` 解析 `@handle`，再通过 YouTube API 解析频道 ID。为了稳定，建议补齐 `channel_id`。

## 日期规则

项目全部按 `Asia/Shanghai` 计算日期。

当前规则是：运行日向前扫描 3 个完整自然日，日报文件名使用窗口结束日。

例如运行日是 `2026-05-29`：

```text
run_date = 2026-05-29
window_start_date = 2026-05-26
window_end_date = 2026-05-28
```

内部字段名说明：

- `previous_date`：窗口起始日期。
- `target_date`：窗口结束日期，也是日报文件名中的日期。
- `report_date`：汇入飞书时使用的统一报告日期，当前等于 `target_date`。

推荐按报告日期回放：

```powershell
python main.py --date 2026-05-28
```

`--date` 表示报告日期/日报文件日期，会在内部换算为 `run_date = date + 1 天`。例如 `--date 2026-05-28` 会扫描 `2026-05-26` 至 `2026-05-28`，并生成 `output/youtube_new_games_2026-05-28.txt`。

兼容入口 `--run-date` 继续表示运行日：

```powershell
python main.py --run-date 2026-05-29
```

这同样会扫描 `2026-05-26` 至 `2026-05-28`。`--date` 与 `--run-date` 不能同时传入。

## 手动运行

只抓取并生成日报：

```powershell
cd D:\GetNewGames\youtube-newgame-daily
python main.py
```

按指定报告日期回放：

```powershell
python main.py --date 2026-05-28
```

按指定运行日回放：

```powershell
python main.py --run-date 2026-05-29
```

导出某天历史台账：

```powershell
python export_daily_history.py --date 2026-05-28
```

抓取、导出台账并发送飞书：

```powershell
run_and_send_feishu.bat
```

单独发送最近日报：

```powershell
python send_feishu_report.py
```

发送到测试机器人：

```powershell
python send_feishu_report.py --test
```

抓取、导出台账并发送到测试机器人：

```powershell
run_and_send_feishu_test.bat
```

## 输出文件

日报：

```text
output/youtube_new_games_YYYY-MM-DD.txt
```

这里的 `YYYY-MM-DD` 是 `target_date`，也就是运行日前一天。

历史 CSV：

```text
output/history/youtube_new_games_history_YYYY-MM-DD.csv
```

SQLite 数据库：

```text
data/youtube_newgame.db
```

关键表：

- `videos`：已扫描视频。
- `games`：所有候选游戏，包括低置信和被拒绝候选。
- `game_catalog`：按去重键沉淀的游戏目录。
- `report_runs`：每次日报运行记录。
- `report_output_items`：每次日报实际输出过的条目，用于历史去重。
- `store_title_cache`：商店页标题缓存。

## 日报筛选规则

进入日报的候选必须满足：

- 有可展示链接。
- `confidence` 是 `high` 或 `medium`。
- `link_type` 不是 `rejected`。
- 没有在历史日报中输出过。

Google Play、App Store、APKPure、TapTap、QooApp、Steam、区域商店等明确商店链接会访问页面并优先使用页面标题作为游戏名，避免把 YouTube 标题里的试玩前缀、介绍语或营销语误识别成游戏名。页面标题读取成功后，该候选会升为 `high`；如果标题读取失败且只有视频标题兜底名，该候选会被拒绝，不进入日报；如果描述链接附近已经有可信游戏名，则作为 `medium` 兜底保留召回。

页面标题会做商店专项清洗，例如：

- `‎心跳陷落 App - App Store` -> `心跳陷落`
- `灵魂潮汐2 - 安卓官方预约 - TapTap` -> `灵魂潮汐2`
- `Anime TCG Merge Battle APK for Android Download` -> `Anime TCG Merge Battle`
- `幻獸之旅：新紀元 Old Versions APK Download` -> `幻獸之旅：新紀元`

描述里的元信息不会作为游戏名进入日报，例如 `Size: 714 MB`、`PC`、`IOS`、`Android`、`Version: 1.0`。

同一游戏有多个链接时，日报只展示优先级最高的一条：

```text
Google Play > App Store > Steam > 第三方/区域商店 > 官网/落地页 > 其他
```

Steam、TapTap、第三方商店、官网、预约页等非商店链接在上下文可信时也可以进入日报。

## 去重规则

优先级：

```text
package_id
apple_app_id
normalized_store_url
normalized_game_name
```

没有商店唯一 ID 的非商店链接，会结合 `normalized_store_url` 去重，避免不同官网首页互相污染。

## 常见问题

`YOUTUBE_API_KEY` 缺失：

- 启用频道抓取时会报错，先配置 API key。

YouTube API 配额不足：

- YouTube Data API v3 返回 403 或配额错误时，当次频道可能失败，但不会中断全局流程。

频道解析失败：

- 常见原因是 `channel_url` 格式不标准。建议直接补齐 `channel_id`。

网络超时：

- 请求已配置 timeout 和 retry；单个频道失败不会中断其他频道。
