# 新游戏情报与素材日报项目

这个仓库是一组本地日报工具，用来发现新游戏、沉淀线索、同步新游戏情报到飞书，并抓取可借势的热点素材。

运维/交接说明见 [docs/OPERATIONS.md](D:/GetNewGames/docs/OPERATIONS.md)。这份文档集中说明产品边界、官方命名、日期规则、安全脚本、生成产物策略和禁止事项。

```text
D:\GetNewGames
├── adx                    # 国内 DataEye 新品
├── youtube-newgame-daily  # YouTube 新游线索
├── overseas-casual-newgame-daily  # 海外休闲新品日报
├── meme-hotspot-daily     # 抖音/B站热点素材候选与 LLM 可用性判定
└── feishu-sync            # 新游戏情报飞书同步
```

## 运作模式

当前仓库分成三条线：

1. **新游戏情报主线**
   - `adx` 抓取国内 DataEye 新品，并补充厂商名。
   - `youtube-newgame-daily` 扫描指定 YouTube 频道最近 3 个完整自然日的视频，提取 YouTube 新游线索。
   - `feishu-sync` 把 DataEye 与 YouTube 两个来源同步到飞书多维表格。
2. **海外休闲新品线**
   - **海外休闲新品日报** 从 DataEye/AdXray 海外版抓取 Meta/Facebook 系媒体中新发现的海外休闲游戏。
   - 只保留目标公司名单内的产品，归因依赖开发者账号、域名、DataEye 公司名、FB 主页等映射。
   - 输出 Markdown、XLSX，并可单独发送飞书群，不走 `feishu-sync`。
3. **热点素材线**
   - `meme-hotspot-daily` 抓取抖音热榜与 B 站排行榜。
   - 可选调用兼容 OpenAI Chat Completions 的 LLM，把条目标成 `pass`、`reject`、`review`。
   - 这是素材候选工具，不进入新游戏情报飞书 Base。

## 飞书主线

`feishu-sync` 当前只同步 `adx` 和 `youtube-newgame-daily`：

```text
新游戏情报日报中心
```

飞书里保留：

- `01_概览`：栏目级卡片/看板展示层，一天一个来源栏目一张卡。
- `03_新游戏明细`：统一明细层，用于跟进、补充备注和人工判断。
- `04_DataEye源数据`：DataEye 原始同步数据。
- `05_YouTube源数据`：YouTube 原始同步数据。
- `06_运行记录`：每次同步的执行日志。

## 官方命名词典

| 模块 | 中文展示名 | 英文目录名 | 飞书栏目名 | 输出文件前缀 | 备注 |
|---|---|---|---|---|---|
| DataEye 国内新品 | 国内 DataEye 新品 | `adx` | `国内 DataEye 新品` | `dataeye_new_games_company_` | `adx` 是代码目录名，短期保留 |
| YouTube 新游线索 | YouTube 新游线索 | `youtube-newgame-daily` | `YouTube 新游线索` | `youtube_new_games_` | 进入新游戏情报飞书 Base |
| 海外休闲新品日报 | 海外休闲新品日报 | `overseas-casual-newgame-daily` | 不进入主 Base | `海外休闲新品日报_` | 独立生成 Markdown/XLSX，可单独群发 |
| 热点素材候选 | 热点素材候选 | `meme-hotspot-daily` | 不进入主 Base | `douyin_` / `bilibili_` | 用于素材灵感筛选 |
| 飞书同步 | 新游戏情报飞书同步 | `feishu-sync` | 管理同步表，不是业务栏目 | 无本地日报输出 | 只同步国内 DataEye + YouTube |

## 日期术语词典

| 术语 | 官方定义 | 当前使用模块 |
|---|---|---|
| `run_date` | 程序运行日期，按上海时区解释；不一定等于日报归属日期 | YouTube 主流程 |
| `report_date` | 报告归属日期，也是飞书 `报告日期` 的筛选日期 | `feishu-sync`、海外休闲、汇入飞书的数据 |
| `target_date` | YouTube 当前内部术语，表示扫描窗口结束日，也是 YouTube 日报文件日期 | `youtube-newgame-daily` |
| `stat_date` | DataEye 统计日期/接口查询日期 | `adx`、海外休闲 |
| `snapshot_date` | 素材或榜单快照日期 | `meme-hotspot-daily` |
| `scan_window` | 一次报告覆盖的日期窗口，通常是开始日到结束日 | YouTube、海外休闲 |

## 推荐每日流程

下面命令按模块分组。带有“真实抓取 / 真实发送 / 真实同步”标记的命令会访问外部服务、写入本地数据，或写入远端飞书；只做验收时不要运行这些命令。

国内 DataEye 新品：

```powershell
cd D:\GetNewGames\adx
npm run fetch:new-games
npm run send:feishu -- --test
```

- `npm run fetch:new-games`：真实抓取 DataEye，并写入本地 `data/` 与 `output/`。
- `npm run send:feishu`：真实发送国内 DataEye 新品日报到飞书群。

YouTube 新游线索：

```powershell
cd D:\GetNewGames\youtube-newgame-daily
python main.py
python main.py --date 2026-05-28
python send_feishu_report.py
```

- `python main.py`：真实抓取 YouTube Data API、访问候选页面，并写入 SQLite、`data/` 与 `output/`。
- `python main.py --date YYYY-MM-DD`：按报告日期回放，仍然是真实抓取。
- `python send_feishu_report.py`：真实发送 YouTube 日报到飞书群。

feishu-sync：

```powershell
cd D:\GetNewGames\feishu-sync
python sync_all.py
python sync_all.py --date 2026-05-28
```

- `python sync_all.py`：真实同步国内 DataEye 新品与 YouTube 新游线索到飞书多维表格。
- `python sync_all.py --date YYYY-MM-DD`：按指定 `report_date` 真实同步。

海外休闲新品日报：

```powershell
cd D:\GetNewGames\overseas-casual-newgame-daily
python main.py
python send_feishu_report.py
```

- `python main.py`：真实抓取 DataEye/AdXray 海外版，并写入本地 `data/` 与 `output/`。
- `python send_feishu_report.py`：真实发送海外休闲新品日报到飞书群。

热点素材候选：

```powershell
cd D:\GetNewGames\meme-hotspot-daily
python main.py
python judge_material.py
```

- `python main.py`：真实抓取抖音/B 站热点，并写入本地 `data/` 与 `output/`。
- `python judge_material.py`：真实调用 LLM 接口做素材可用性判定，并写入本地判定结果。

## 安全验证命令

以下命令只检查参数、测试或静态语法，不会触发真实抓取、真实发送或真实同步：

推荐使用批量安全验证入口：

```powershell
cd D:\GetNewGames
powershell -ExecutionPolicy Bypass -File scripts/check-modules.ps1
```

它不会触发真实业务：不会真实抓取、真实发送或真实同步。只想检查旧命名、敏感示例和产物 dirty 时，用 `scripts/check-readonly.ps1`；只想预览单模块运行命令时，用 `scripts/run-module.ps1`。

```powershell
cd D:\GetNewGames\adx
npm test

cd D:\GetNewGames\youtube-newgame-daily
python main.py --help
python send_feishu_report.py --help
python -m unittest discover -s tests

cd D:\GetNewGames\feishu-sync
python sync_all.py --help
python -m compileall .

cd D:\GetNewGames\overseas-casual-newgame-daily
python send_feishu_report.py --help
python -m unittest discover -s tests -p "test_feishu_sender.py"

cd D:\GetNewGames
git diff --check -- README.md feishu-sync\README.md meme-hotspot-daily\README.md
```

## 提交前安全检查

仓库提供一个只读检查入口，用来在 dirty 工作区提交前做安全提示：

```powershell
cd D:\GetNewGames
powershell -ExecutionPolicy Bypass -File scripts/check-readonly.ps1
```

这个脚本只做报告，不会真实抓取、真实发送或真实同步，也不会修改文件、清理文件、stage 或 commit。它会检查旧栏目名、旧目录名、带值 token 示例和已知敏感 token 片段，并输出当前 `git status --short`。

`data/`、`output/`、SQLite、`__pycache__/`、`.pytest_cache/`、`.cache/` 等 dirty 项只作为“需人工确认，不建议纳入常规提交”的提示；它们不会让脚本自动失败，也不会被脚本处理。真正提交时应精确 stage 本次目标文件，避免把历史日报、数据库、抓取结果或缓存误带进提交。

## 统一运行入口

`scripts/run-module.ps1` 是便利入口，不替代各模块原生 bat、npm 或 Python 命令。旧 bat / npm scripts / Python 入口继续保留兼容。

默认只预览将要执行的命令，不会真实抓取、真实发送或真实同步：

```powershell
cd D:\GetNewGames
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module youtube -Action fetch -Date 2026-06-04
```

只有显式传入 `-Execute` 时才执行本地命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module youtube -Action fetch -Date 2026-06-04 -Execute
```

远端写入类动作，例如飞书群发送、飞书同步和历史同步，需要同时传入 `-Execute -AllowRemote`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module feishu-sync -Action sync -Date 2026-06-04 -Execute -AllowRemote
```

这个入口不会自动串联 DataEye + YouTube + feishu-sync，也不会提供一键全量真实运行。需要真实抓取、真实发送或真实同步时，必须明确选择模块、动作和执行开关。

## 日期规则

- `adx`：默认采集上海时区运行日前一天；也可 `npm run fetch:new-games -- --date YYYY-MM-DD`。DataEye 当前入口只返回最近约 14 天。
- `youtube-newgame-daily`：默认运行日是上海当天，扫描运行日前 3 天到前 1 天，日报文件日期是窗口结束日；回放用 `python main.py --run-date YYYY-MM-DD`。
- `feishu-sync`：默认同步上海时区前一天；指定日期用 `python sync_all.py --date YYYY-MM-DD`。
- **海外休闲新品日报**：报告日期默认是上海当天，默认扫描报告日前 3 天到前 1 天。
- `meme-hotspot-daily`：快照日期默认是上海当天；指定日期用 `--date YYYY-MM-DD`。

## P1 统一运行说明

根目录暂不新增统一脚本，避免一个入口同时触发抓取、发送或飞书写入。日常仍按子项目分别运行，根 README 只作为运行顺序和参数语义的统一索引。

配置入口：

- `youtube-newgame-daily`：复制 `youtube-newgame-daily/.env.example` 为 `.env`，配置 `YOUTUBE_API_KEY`、`YOUTUBE_FEISHU_WEBHOOK`、`FEISHU_WEBHOOK`。
- `overseas-casual-newgame-daily`：复制 `.env.example` 为 `.env`。正式群发优先使用 `OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK`，为空时回退 `OVERSEAS_CASUAL_FEISHU_WEBHOOK`；测试群发优先使用 `OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK`，为空时回退 `FEISHU_WEBHOOK`。
- `feishu-sync`：只负责把 `adx` 与 `youtube-newgame-daily` 同步到新游戏情报飞书 Base，配置入口仍是 `feishu-sync/.env`。

日期参数：

- `youtube-newgame-daily --date YYYY-MM-DD` 表示报告日期/日报文件日期，内部换算为 `run_date = date + 1 天`。
- `youtube-newgame-daily --run-date YYYY-MM-DD` 继续表示运行日，保留兼容；`--date` 与 `--run-date` 不能同时传入。
- `feishu-sync --date YYYY-MM-DD` 表示统一 `report_date`，用于飞书 `报告日期` 筛选。
- `overseas-casual-newgame-daily --date YYYY-MM-DD` 表示报告日期；`--stat-date` 表示单个 DataEye 统计日期。

同步来源注册：

- `feishu-sync` 当前通过 `feishu_sync.sources.SOURCE_REGISTRY` 登记 `DataEye` 与 `YouTube` 两个来源。
- registry 只保存来源名、源数据表名、源数据日期字段和 loader；不改变 loader 内部转换逻辑、去重 key 策略或飞书表结构。

## data/output 历史产物策略

`data/`、`output/`、SQLite 数据库、已生成日报和历史 CSV 都属于历史产物或运行产物。默认策略是：

- `.gitignore` 会尽量忽略未来生成的 `data/`、`output/`、SQLite / DB 和 cache。
- 如果某些历史产物已经被 git 跟踪，`.gitignore` 不会自动取消跟踪。
- 不批量改写历史产物。
- 不删除历史产物。
- 不迁移历史产物。
- 不默认提交历史产物。
- 提交时只 stage 本次目标文件，避免把历史日报、数据库或抓取结果误带进提交。

本项目不建议在常规功能提交中纳入 `data/`、`output/`、SQLite / DB、cache 或历史日报。提交或交付前先运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-readonly.ps1
```

如果未来需要整理历史产物，应单独开“历史产物归档/迁移”任务，并先确认保留范围、备份方式和回滚策略，不要和功能或文档改造混在一起。

## 旧脚本兼容

旧 bat、npm scripts 和现有 Python 入口继续保留兼容。当前官方命名主要用于产品展示名、文档口径和飞书栏目语义，不强制改旧入口名。

如果未来要做统一命令入口或更语义化的 wrapper，建议放到 P3 或单独任务，并默认只提供安全验证入口；真实抓取、真实发送、真实同步必须显式命名，避免误操作。

## 主要输出

国内 DataEye 新品：

```text
D:\GetNewGames\adx\data\daily-new-games-company\YYYY-MM-DD.json
D:\GetNewGames\adx\data\daily-new-games-company\YYYY-MM-DD.csv
D:\GetNewGames\adx\output\dataeye_new_games_company_YYYY-MM-DD.txt
```

YouTube：

```text
D:\GetNewGames\youtube-newgame-daily\data\youtube_newgame.db
D:\GetNewGames\youtube-newgame-daily\output\youtube_new_games_YYYY-MM-DD.txt
D:\GetNewGames\youtube-newgame-daily\output\history\youtube_new_games_history_YYYY-MM-DD.csv
```

海外休闲新品：

```text
D:\GetNewGames\overseas-casual-newgame-daily\data\raw\SCAN_DATE.json
D:\GetNewGames\overseas-casual-newgame-daily\data\raw\REPORT_DATE_scan.json
D:\GetNewGames\overseas-casual-newgame-daily\data\processed\YYYY-MM-DD.json
D:\GetNewGames\overseas-casual-newgame-daily\data\unmatched\YYYY-MM-DD.csv
D:\GetNewGames\overseas-casual-newgame-daily\output\海外休闲新品日报_YYYY-MM-DD.md
D:\GetNewGames\overseas-casual-newgame-daily\output\海外休闲新品日报_YYYY-MM-DD.xlsx
```

热点素材：

```text
D:\GetNewGames\meme-hotspot-daily\data\items\YYYY-MM-DD\*_items.json
D:\GetNewGames\meme-hotspot-daily\data\judged\YYYY-MM-DD\*_judged.json
D:\GetNewGames\meme-hotspot-daily\output\YYYY-MM-DD\*.csv
D:\GetNewGames\meme-hotspot-daily\output\YYYY-MM-DD\*.txt
```

## 配置文件

```text
D:\GetNewGames\adx\.env
D:\GetNewGames\youtube-newgame-daily\.env
D:\GetNewGames\overseas-casual-newgame-daily\.env
D:\GetNewGames\meme-hotspot-daily\.env
D:\GetNewGames\feishu-sync\.env
```

这些文件包含账号、密钥或 webhook，已被 `.gitignore` 忽略。已有 `.env.example` 的目录可以直接以示例文件为准；没有示例文件时，按对应子项目 README 中列出的变量配置。

## 验证

```powershell
cd D:\GetNewGames\adx
npm test
npm run typecheck

cd D:\GetNewGames\youtube-newgame-daily
python -m unittest discover -s tests

cd D:\GetNewGames\overseas-casual-newgame-daily
python -m pytest

cd D:\GetNewGames\feishu-sync
python -m compileall .
```
