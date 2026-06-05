# 新游戏情报飞书同步工具

这个目录负责把本地 **国内 DataEye 新品** 和 **YouTube 新游线索** 同步到固定的飞书多维表格 Base。

当前不负责同步 **海外休闲新品日报**，也不负责同步 `meme-hotspot-daily` 的热点素材结果；这两个模块各自输出本地文件或单独发送飞书群。

Base：
```text
新游戏情报日报中心
```

app token 在 `.env` 中配置：
```text
FEISHU_BITABLE_APP_TOKEN=
```

## 数据来源

国内 DataEye 新品：
```text
D:\GetNewGames\adx\data\daily-new-games-company\YYYY-MM-DD.json
D:\GetNewGames\adx\output\dataeye_new_games_company_YYYY-MM-DD.txt
```

历史 DataEye 数据如果没有 `daily-new-games-company` 文件，脚本会回退读取 `daily-new-games` 里的旧 JSON；旧数据没有厂商字段时，`companyName` / `厂商名` 会留空。

YouTube 新游线索：
```text
D:\GetNewGames\youtube-newgame-daily\data\youtube_newgame.db
D:\GetNewGames\youtube-newgame-daily\output\youtube_new_games_YYYY-MM-DD.txt
```

## 飞书表结构

脚本管理 5 张表：
```text
01_概览
03_新游戏明细
04_DataEye源数据
05_YouTube源数据
06_运行记录
```

`01_概览` 是给人看的栏目级展示层，适合画册/看板视图。它不是“一款产品一张卡”，而是“一天一个栏目一张卡”。卡片内用 `产品列表` 紧凑展示当天产品，方便扫读。

当前栏目：
- `国内 DataEye 新品`
- `YouTube 新游线索`

后续新增其他来源或栏目时，只需要按同样结构新增栏目记录。所有栏目统一用 `报告日期` 做日期筛选。

`03_新游戏明细` 是统一明细层，保留更多可跟进字段。`04_DataEye源数据` 和 `05_YouTube源数据` 保留源数据，方便排查和审计。

## 初始化结构和视图

```powershell
cd D:\GetNewGames\feishu-sync
python setup_overview.py
```

这个命令会：
- 创建/补齐 5 张表和字段。
- 在 `01_概览` 创建 `栏目卡片` 画册视图。
- 在 `01_概览` 创建 `栏目看板` 看板视图。

如只需要基础表结构，也可以运行：
```powershell
python setup_bitable.py
```

如果飞书应用权限不足，无法由脚本自动建表或建字段，可以先打印手工清单：

```powershell
python setup_bitable.py --print-manual-tables
python setup_bitable.py --print-manual-fields
```

## 同步某天数据

```powershell
cd D:\GetNewGames\feishu-sync
python sync_all.py --date 2026-05-28
```

不传 `--date` 时，默认同步上海时区的前一天。

同步行为：
1. 读取国内 DataEye JSON。
2. 读取 YouTube SQLite 中对应日期最新一次日报运行的实际输出条目；如果没有运行记录，则回退读取当天 `games` 表中的高/中置信候选。
3. 写入 `04_DataEye源数据` 和 `05_YouTube源数据`。
4. 转换并写入 `01_概览`。
5. 转换并写入 `03_新游戏明细`。
6. 写入 `06_运行记录`。

同步是幂等的：同一天重复运行会根据 `去重Key` / `dedupeKey` 跳过已写入记录。

某天缺少本地数据时，默认会写入失败运行记录并返回非零退出码。只想跳过缺失来源时：

```powershell
python sync_all.py --date 2026-05-28 --allow-missing-sources
```

## 同步所有历史数据

```powershell
cd D:\GetNewGames\feishu-sync
python sync_history.py
```

这个命令会自动发现本地 DataEye 文件、git 历史中的 DataEye 文件，以及 YouTube SQLite 中已有的日期，然后逐天同步。某天缺少某个来源时会跳过该来源，不会记为失败。

## 重建某天概览

如果只想重建 `01_概览`，不动源数据和明细表：

```powershell
cd D:\GetNewGames\feishu-sync
python rebuild_overview.py --date 2026-05-28
```

## 清空某天同步数据

```powershell
cd D:\GetNewGames\feishu-sync
python clear_report_date.py --date 2026-05-28
```

它会删除这一天在 `01_概览`、`03_新游戏明细`、`04_DataEye源数据`、`05_YouTube源数据`、`06_运行记录` 中的记录，不删除表结构。

## 清理重复记录

```powershell
cd D:\GetNewGames\feishu-sync
python cleanup_duplicates.py --date 2026-05-28
```

## 配置

填写 `D:\GetNewGames\feishu-sync\.env`：
```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_BITABLE_APP_TOKEN=
FEISHU_WEBHOOK=
```

`FEISHU_WEBHOOK` 可选。

## 来源注册

`sync_all.py` 通过 `feishu_sync.sources.SOURCE_REGISTRY` 管理当前同步来源。SOURCE_REGISTRY 当前只包含 DataEye / YouTube：

```text
DataEye  -> 04_DataEye源数据 -> statDate    -> load_dataeye
YouTube  -> 05_YouTube源数据 -> report_date -> load_youtube
```

registry 只登记 source 名、raw 表、日期字段、loader；不改变 `load_dataeye` / `load_youtube` 的内部转换逻辑、去重 key 策略和飞书表结构。

当前 **海外休闲新品日报** 和 **热点素材候选** 不进入主 Base，也不在 `SOURCE_REGISTRY` 中注册：

- 海外休闲新品日报只生成本地 Markdown/XLSX，并可单独真实发送到飞书群。
- 热点素材候选只用于素材复核和 LLM 判定，不进入新游戏情报飞书 Base。

未来如果要把海外休闲新品日报接入主 Base，必须单独做 PRD、飞书表结构设计、同步边界确认和历史数据迁移策略评审；不能只往 `SOURCE_REGISTRY` 加 loader。
