# YouTube 新游日报工具

这是一个独立的本地 Python 项目，用于按固定规则抓取指定 YouTube 频道的视频，提取其中的新游条目，生成日报、保存历史台账，并可选发送到飞书群 webhook。

本项目位于 `D:\GetNewGames\youtube-newgame-daily`，与 `D:\GetNewGames\adx` 完全无关，不会读取、修改或依赖 `D:\GetNewGames\adx`。

## 功能概览

- 使用 YouTube Data API v3 抓取频道视频
- 通过频道 `uploads playlist` 分页翻取，不依赖固定 N 条视频
- 从标题、描述、Google Play、App Store、Steam、第三方商店、官网、落地页等链接提取候选条目
- 使用 SQLite 保存视频、游戏候选、日报运行记录、历史输出记录、页面标题缓存
- 生成日报文本和历史 CSV
- 支持将日报通过飞书 webhook 发送到群聊

## 安装依赖

```powershell
cd D:\GetNewGames\youtube-newgame-daily
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 配置 YouTube API Key

推荐通过环境变量配置：

```powershell
$env:YOUTUBE_API_KEY = "你的 YouTube Data API v3 Key"
```

也可以放到 `.env` 文件中：

```env
YOUTUBE_API_KEY=你的 YouTube Data API v3 Key
FEISHU_WEBHOOK=你的飞书 webhook
```

核心配置在 [channels.yaml](D:/GetNewGames/youtube-newgame-daily/channels.yaml)：

- `channels_file`
- `output_dir`
- `database_path`
- `timezone_name`
- `youtube_api_key_env`
- `feishu_webhook_env`
- `request_timeout_seconds`
- `request_retry_count`

## 配置 channels.csv

[channels.csv](D:/GetNewGames/youtube-newgame-daily/channels.csv) 至少需要以下列：

- `name`
- `channel_url`
- `enabled`
- `channel_id`

说明：

- `channel_id` 可以为空
- 如果为空，程序会尝试从 `channel_url` 解析 `@handle`，再通过 YouTube API 解析 `channelId`
- 未来建议补齐 `channel_id`，提高稳定性
- CSV 读取兼容 `utf-8-sig`、`utf-8`、`gbk`、`cp936`

## 手动运行

只抓取并生成日报：

```powershell
cd D:\GetNewGames\youtube-newgame-daily
python main.py
```

抓取并导出台账：

```powershell
python main.py
python export_daily_history.py --date 2026-05-18
```

抓取、导出台账并发送飞书：

```powershell
run_and_send_feishu.bat
```

## 飞书 webhook 配置

推荐使用环境变量：

```powershell
$env:FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

发送脚本：

```powershell
python send_feishu_report.py
```

如果预期日报文件不存在，脚本会尝试寻找最近 6 小时内最新的日报文件并发送。

## 日期规则说明

项目全部日期都按 `Asia/Shanghai` 计算。

当前规则是：运行日向前抓取 3 个完整自然日的数据，再结合历史日报输出记录做排重。

例如运行日是 `2026-05-19`：

- `run_date = 2026-05-19`
- `window_start_date = 2026-05-16`
- `window_end_date = 2026-05-18`
- 实际抓取窗口为 `2026-05-16`、`2026-05-17`、`2026-05-18`

程序内部仍沿用原有字段名：

- `previous_date` 表示窗口起始日
- `target_date` 表示窗口结束日

## 输出规则说明

日报不是只比较相邻两天，而是：

1. 扫描本次 3 天窗口内识别到的条目
2. 用数据库中已经落地的“历史已输出记录”做排重
3. 只输出此前从未在历史日报中发过的条目
4. 同一次运行内部也会继续去重，避免同一条内容在同一份日报里重复出现

“历史已输出过”的依据是 SQLite 中的 `report_output_items` 表。这个表会记录每次日报实际输出过的条目，后续运行会优先拿它来判断是否已经发过。

## 历史去重主键

优先复用当前项目已有去重键：

- `package_id` 优先，对应 `pkg:<package_id>`
- `apple_app_id` 次之，对应 `ios:<apple_app_id>`
- 否则退回 `normalized_game_name`
- 对没有商店唯一 ID 的非商店链接，会附加 `normalized_store_url` 参与去重，避免不同官网首页互相污染

## 日报候选过滤与置信度规则

为尽量减少脏数据，项目会把候选分成 `high`、`medium`、`low`、`rejected` 四种置信度。

### 日报展示原则

- 日报优先展示 Google Play / App Store 链接
- 非商店链接不会一刀切丢弃
- 非商店链接如果像游戏官网、预约页、下载页、第三方商店页，且名称有效，可以进入日报
- 条款、隐私、客服、帮助、政策类链接不会进入日报
- `high` 和 `medium` 进入日报
- `low` 和 `rejected` 不进入日报，但会保存在数据库和历史 CSV 中，便于复盘

### 链接分类

- `google_play`
- `app_store`
- `non_store`
- `rejected`

### 典型拒绝场景

以下内容会被压到 `rejected` 或 `low`，不会进入日报：

- Terms / Privacy / Policy / Support / Help / FAQ / Contact / Customer Service 链接
- `support.google.com/googleplay`
- `terms.withhive.com`
- `superboxgo.com/termsofservice_en.php`
- `superboxgo.com/privacypolicy_en.php`
- `cdn.endlessfrontier.io/.../policy/privacy...`
- 名称只是“官网 / 官方網站 / 服务条款 / 隐私政策 / 官方網站”
- 只有下划线、横线、分隔线、说明句的文本

### 视频标题兜底规则

视频标题只作为最后兜底来源，并且会清洗：

- 去掉 hashtag，例如 `#shorts`
- 去掉 emoji
- 去掉明显营销尾巴
- 去掉过长说明句和无效符号

例如：

- `Vehicle Masters #shorts #vehicles #vehicle 🚗🚓🚕`

不会原样进入日报。若商店页标题可用，会优先用商店页标题；若商店页不可用，至少会清洗成 `Vehicle Masters`；若仍不可靠，则只做审计，不进日报。

## 审计与历史导出

`games` 表和历史 CSV 会保留这些审计字段：

- `link_type`
- `confidence`
- `reject_reason`
- `normalized_store_url`

这意味着：

- 被过滤的链接并不代表视频没有抓到
- 只是该候选不满足进入日报的质量要求
- 后续可以通过历史 CSV 或数据库回看低置信 / 被拒绝候选

## 为什么必须按日期翻页，而不是固定抓 N 条

高频频道一天可能发布很多条视频。若只抓最近固定 N 条，容易把目标窗口内稍早一点的视频漏掉。

因此本项目固定采用：

- 先解析频道的 `uploads playlist`
- 再用 `playlistItems` 分页翻取
- 一直翻到视频发布时间早于窗口起始时间

这样才能保证日期窗口内的数据尽量完整。

## 输出说明

日报输出路径：

- `output/youtube_new_games_YYYY-MM-DD.txt`

其中 `YYYY-MM-DD` 使用本次窗口结束日，也就是 `target_date`。

历史 CSV 输出路径：

- `output/history/youtube_new_games_history_YYYY-MM-DD.csv`

历史 CSV 使用 `UTF-8 with BOM`，避免 Excel 中文乱码。

## 常见错误

`YOUTUBE_API_KEY` 缺失：

- 为启用频道抓取时会报错，请先配置 API key

YouTube API 配额不足：

- YouTube Data API v3 返回 403 或配额相关错误时，当次频道可能失败

频道解析失败：

- 多见于 `channel_url` 格式不标准，建议直接补齐 `channel_id`

网络超时：

- 请求已配置 timeout 和 retry
- 单个频道失败不会中断全局流程

## 运行结果

运行完成后，日志会明确输出：

- `run_date`
- `window_start_date`
- `window_end_date`
- 成功频道数
- 失败频道数
- 扫描到的游戏条目数
- 日报路径
