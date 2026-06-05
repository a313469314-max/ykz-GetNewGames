# GetNewGames 运维与交接说明

这份文档用于交接当前项目结构、产品边界、命名、日期规则、安全脚本和禁止事项。这里不记录任何真实 token、webhook、账号或密钥。

## 当前产品线

| 产品线 | 目录 | 定位 |
|---|---|---|
| 国内 DataEye 新品 | `adx` | 抓取国内 DataEye 新品，补充厂商信息，生成本地日报，可单独群发。 |
| YouTube 新游线索 | `youtube-newgame-daily` | 扫描 YouTube 频道视频，提取新游戏线索，沉淀 SQLite 台账，生成本地日报，可单独群发。 |
| 海外休闲新品日报 | `overseas-casual-newgame-daily` | 从 DataEye/AdXray 海外版抓取 Meta/Facebook 系媒体中新发现的海外休闲游戏，按目标公司与归因规则输出日报。 |
| 热点素材候选 | `meme-hotspot-daily` | 抓取抖音/B 站热点，并可用 LLM 判断是否适合作为游戏广告素材灵感。 |

## 飞书同步边界

`feishu-sync` 当前只同步两类来源到新游戏情报主 Base：

- 国内 DataEye 新品
- YouTube 新游线索

当前不进入主 Base：

- 海外休闲新品日报：只生成本地 Markdown/XLSX，并可独立发送飞书群。
- 热点素材候选：只用于本地素材复核和 LLM 判定，不进入新游戏情报主 Base。

不要把海外休闲或热点素材直接加入 `feishu-sync`。如果未来要接入，必须先做独立 PRD、飞书表结构设计、同步边界确认和历史数据迁移策略评审。

## 官方命名

| 模块 | 中文展示名 | 英文目录名 | 飞书栏目名 | 输出前缀 | 兼容说明 |
|---|---|---|---|---|---|
| DataEye 国内新品 | 国内 DataEye 新品 | `adx` | `国内 DataEye 新品` | `dataeye_new_games_company_` | `adx`、旧 npm scripts、`ADX_FEISHU_WEBHOOK` 等继续保留兼容。 |
| YouTube 新游线索 | YouTube 新游线索 | `youtube-newgame-daily` | `YouTube 新游线索` | `youtube_new_games_` | `--run-date` 保留兼容，新增 `--date` 作为报告日期别名。 |
| 海外休闲新品日报 | 海外休闲新品日报 | `overseas-casual-newgame-daily` | 不进入主 Base | `海外休闲新品日报_` | 旧 webhook 变量 fallback 保留。 |
| 热点素材候选 | 热点素材候选 | `meme-hotspot-daily` | 不进入主 Base | `douyin_` / `bilibili_` | 旧平铺热点产物保留为历史产物。 |
| 飞书同步 | 新游戏情报飞书同步 | `feishu-sync` | 管理同步表，不是业务栏目 | 无本地日报输出 | `SOURCE_REGISTRY` 当前只含 DataEye / YouTube。 |

## 日期规则

| 术语 | 含义 |
|---|---|
| `run_date` | 程序运行日期，按上海时区解释；不一定等于日报归属日期。 |
| `report_date` | 报告归属日期，也是飞书 `报告日期` 的筛选日期。 |
| `target_date` | YouTube 内部术语，表示扫描窗口结束日，也是 YouTube 日报文件日期。 |
| `stat_date` | DataEye 统计日期或接口查询日期。 |
| `snapshot_date` | 热点素材或榜单快照日期。 |
| `scan_window` | 一次报告覆盖的日期窗口，通常是开始日到结束日。 |

当前模块规则：

- `adx`：默认采集上海运行日前一天；`--date` 表示 DataEye `stat_date` / 报告日期。
- `youtube-newgame-daily`：默认 `run_date=上海当天`，扫描 `run_date-3` 到 `run_date-1`；`--date` 表示报告日期，内部换算为 `run_date = date + 1 天`；`--run-date` 保留兼容。
- `feishu-sync`：默认同步上海前一天；`--date` 表示统一 `report_date`。
- `overseas-casual-newgame-daily`：默认 `report_date=上海当天`，默认扫描报告日前 3 天到前 1 天；`--stat-date` 只扫单个 DataEye 日期。
- `meme-hotspot-daily`：默认 `snapshot_date=上海当天`；`--date` 表示快照日期。

## 配置入口

配置时优先看各模块 README 与 `.env.example`。不要读取、输出或提交真实 `.env` / `.env.*`。

| 模块 | 配置入口 |
|---|---|
| `adx` | `adx/.env.example`、`adx/README.md` |
| `youtube-newgame-daily` | `youtube-newgame-daily/.env.example`、`youtube-newgame-daily/channels.yaml`、`youtube-newgame-daily/channels.csv`、`youtube-newgame-daily/README.md` |
| `feishu-sync` | `feishu-sync/.env.example`、`feishu-sync/README.md` |
| `overseas-casual-newgame-daily` | `overseas-casual-newgame-daily/.env.example`、`overseas-casual-newgame-daily/config/`、`overseas-casual-newgame-daily/README.md` |
| `meme-hotspot-daily` | `meme-hotspot-daily/.env.example`、`meme-hotspot-daily/README.md` |

## 安全脚本

| 脚本 | 场景 | 安全边界 |
|---|---|---|
| `scripts/check-readonly.ps1` | 提交前或改造前安全检查。 | 查旧命名、敏感示例、生成产物 dirty；不抓取、不发送、不同步、不改文件、不 stage、不 commit。 |
| `scripts/run-module.ps1` | 单模块运行入口。 | 默认只预览；`-Execute` 才执行；远端写入类动作必须同时传 `-AllowRemote`。 |
| `scripts/check-modules.ps1` | 批量安全验证入口。 | 只跑不会触发真实业务的验证命令；不安装依赖、不清理缓存、不 stage、不 commit。 |

## 生成产物策略

`data/`、`output/`、SQLite / DB、cache、历史日报和历史 CSV 都视为生成产物或本地状态。

默认策略：

- 不默认提交。
- 不批量改写。
- 不删除。
- 不迁移。
- 提交时只 stage 本次目标文件。

`.gitignore` 会尽量忽略未来生成的 data/output/db/cache，但如果某些历史产物已经被 git 跟踪，`.gitignore` 不会自动取消跟踪。不要在普通功能或文档改造中顺手处理这些历史产物。

## 禁止事项

- 不要提交 `.env` / `.env.*`。
- 不要提交真实 token、webhook、API key、账号或密码。
- 不要默认运行真实发送、真实飞书同步或历史同步。
- 不要把海外休闲新品日报接入 `feishu-sync`，除非已有单独 PRD 和表结构设计。
- 不要删除、迁移、重命名历史产物。
- 不要回退用户已有变更。
- 不要用安全脚本清理文件、stage 或 commit。

## 后续可能的 P8/P9

- 做真正的提交分组和版本管理，明确哪些文件进入同一批提交。
- 单独做历史产物治理，包括备份、归档、取消跟踪策略和回滚方案。
- 独立评估海外休闲新品日报是否进入主 Base。
- 建立 CI 或本地 preflight，把 `check-readonly` / `check-modules` 纳入标准交付流程。
