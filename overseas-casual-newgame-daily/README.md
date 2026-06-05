# 海外休闲新品日报

从 DataEye/AdXray 海外版抓取 Meta/Facebook 系媒体中新发现的海外休闲游戏，并按目标公司名单和归因映射输出日报。

当前项目名是 **海外休闲新品日报**，代码目录使用英文路径：`D:\GetNewGames\overseas-casual-newgame-daily`。

这个模块不进入 `feishu-sync` 管理的新游戏情报 Base；它只生成本地 Markdown/XLSX 日报，并可单独发送飞书群机器人。

## 口径

- 报告日期默认是今天，按 `Asia/Shanghai` 计算。
- 默认扫描报告日期前 3 天到前 1 天。例如 2026-06-04 运行，会扫描 2026-06-01 到 2026-06-03。
- `--stat-date` 会只扫描一个 DataEye 统计日期；`--start-date` 和 `--end-date` 必须成对使用。
- 输出前会参考 `data/processed` 里的历史结果，去掉已经在过往报告中出现过的产品。
- 媒体口径指广告监测里命中 Meta/Facebook 系媒体：`Facebook`、`Instagram`、`Messenger`、`FacebookAudience`。
- 不限制游戏类型，只保留 `config/target_companies.yaml` 内的目标公司；开发者账号归属冲突但历史模板出现过的账号会进入 `未知` 分组。
- 公司字段输出 `canonical_company`，由 `config/company_mapping.csv` 的开发者账号级归因规则决定。包名和 App ID 主要用于抓取商店信息，不作为批量主映射。

## 当前流程

`python main.py` 会执行完整流水线：

1. 解析报告日期与扫描窗口。
2. 优先复用 `.auth/dataeye-state.json`，登录态失效时打开可见浏览器人工完成验证。
3. 先尝试用 DataEye 海外版接口抓新品列表和产品详情；接口没有结果时回退到浏览器页面提取。
4. 按扫描日期逐天落地 raw JSON，并额外写入本次报告的聚合 scan JSON。
5. 只保留首见日期在扫描窗口内、且媒体列表或详情文本命中 Meta/Facebook 系媒体的产品。
6. 可选访问 Google Play / App Store 补充开发者、卖家、隐私域名等归因信号。
7. 用 `config/company_mapping.csv` 和 `config/target_companies.yaml` 做公司归因，只输出目标公司。
8. 先做本次扫描窗口内去重，再对历史 `data/processed` 去重。
9. 写入 processed JSON、unmatched CSV、Markdown 日报和 XLSX 明细。

## 初始化

```powershell
cd D:\GetNewGames\overseas-casual-newgame-daily
python -m pip install -r requirements.txt
python -m playwright install chromium
```

把 `.env.example` 复制为 `.env`，填入本地账号密码：

```env
DATAEYE_EMAIL=
DATAEYE_PASSWORD=
DATAEYE_HOME_URL=https://oversea-v2.dataeye.com/dashboard/home
DATAEYE_STORAGE_STATE=.auth/dataeye-state.json
OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK=
OVERSEAS_CASUAL_FEISHU_WEBHOOK=
OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK=
FEISHU_WEBHOOK=
FEISHU_REQUEST_TIMEOUT_SECONDS=20
```

`.env` 和 `.auth/` 已加入 `.gitignore`，不要提交。

飞书群发送变量读取顺序：

- 正式发送优先读取 `OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK`，为空时回退 `OVERSEAS_CASUAL_FEISHU_WEBHOOK`。
- 测试发送优先读取 `OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK`，为空时回退 `FEISHU_WEBHOOK`。

## 运行

```powershell
python main.py
```

指定报告日期：

```powershell
python main.py --date 2026-06-04
```

只扫描某一天，用于调试或回放：

```powershell
python main.py --stat-date 2026-06-02
```

指定扫描窗口：

```powershell
python main.py --date 2026-06-04 --start-date 2026-06-01 --end-date 2026-06-03
```

调试时限制数量并显示浏览器：

```powershell
python main.py --date 2026-06-04 --headed --max-products 20
```

用已有 raw JSON 回放，不打开 DataEye：

```powershell
python main.py --from-raw data\raw\2026-06-02.json --skip-store-enrich
```

跳过历史去重，仅看本次扫描命中：

```powershell
python main.py --no-history-dedupe
```

也可以双击或定时执行：

```powershell
run_overseas_casual_daily.bat --date 2026-06-04
```

抓取并发送飞书：

```powershell
run_and_send_feishu.bat
```

单独发送最近生成的日报：

```powershell
python send_feishu_report.py
```

发送指定日报文件：

```powershell
python send_feishu_report.py --path output\海外休闲新品日报_2026-06-04.md
```

发送到测试机器人：

```powershell
python send_feishu_report.py --test
```

## 登录态

启动时会优先复用 `.auth/dataeye-state.json`。如果登录态失效，会自动打开可见浏览器，填入 `.env` 里的账号密码。遇到验证码、滑块、短信等人工步骤时，在打开的浏览器中完成即可；登录成功后脚本会覆盖保存新的 storage state。

## 输出

```text
data/raw/SCAN_DATE.json
data/raw/REPORT_DATE_scan.json
data/processed/YYYY-MM-DD.json
data/unmatched/YYYY-MM-DD.csv
output/海外休闲新品日报_YYYY-MM-DD.md
output/海外休闲新品日报_YYYY-MM-DD.xlsx
```

`data/unmatched` 里会保留未匹配或被过滤的产品，便于继续补 `company_mapping.csv`。

`data/processed/YYYY-MM-DD.json` 里的 `scan_dates`、`scan_start_date`、`scan_end_date` 记录本次报告实际扫描窗口；`scan_duplicate_count` 和 `history_duplicate_count` 分别表示窗口内重复与历史重复数量。

## 归因与去重

归因优先级按代码中的信号组执行：

```text
developer_id / google_developer_id / apple_artist_id / developer_name / seller_name
domain / privacy_domain / developer_domain / seller_domain
dataeye_company_id / company_id
dataeye_company_name / company_name / manual
fb_page / facebook_page
package / package_name / app_id
```

如果没有命中映射，但开发者名、卖家名、DataEye 公司名或 FB 主页与目标公司名完全一致，会作为 `direct_*` 中等置信命中。

去重键优先使用包名、Apple App ID、DataEye 产品 ID、标准化商店链接，最后回退到产品名或“公司 + 产品名”。历史去重读取报告日期之前的 `data/processed/*.json`。

## 验证

```powershell
cd D:\GetNewGames\overseas-casual-newgame-daily
python -m pytest
```
