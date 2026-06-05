# 热点素材候选

这个子项目用于每天抓取热点素材候选，并可选用 LLM 判断这些热点是否适合改编成游戏广告素材灵感。

它不进入 `feishu-sync` 管理的新游戏情报 Base；输出结果用于本地素材复核。

## 来源

- 抖音热榜：`https://www.douyin.com/hot`
- B 站排行榜：默认抓取全站、鬼畜、生活、娱乐、动画、游戏分区。

默认 B 站分区：

```text
0    全站
119  鬼畜
160  生活
5    娱乐
1    动画
4    游戏
```

## 当前流程

抓取阶段 `python main.py`：

1. 按 `Asia/Shanghai` 计算 `snapshot_date`，默认是当天。
2. 抓取指定来源的原始 JSON。
3. 规范化为统一字段。
4. 按来源分别输出 JSON、CSV、TXT。

判定阶段 `python judge_material.py`：

1. 读取 `data/items/YYYY-MM-DD/<source>_items.json`。
2. 按 `--batch-size` 分批请求兼容 OpenAI Chat Completions 的模型接口。
3. 要求模型只返回 JSON，并将每条热点标记为 `pass`、`reject` 或 `review`。
4. 输出完整 judged JSON，以及按判定结果拆分的 CSV。

判定层不会覆盖原始抓取结果；模型失败、超时或返回缺项时，对应条目会进入 `review`。

## 安装与配置

基础抓取只依赖 Python 标准库。判定阶段需要先把 `.env.example` 复制为 `.env`：

```env
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=
LLM_TIMEOUT_SECONDS=60
```

`LLM_BASE_URL` 可以直接写到 `/v1`，也可以写完整 `/chat/completions` 地址。

## 抓取

```powershell
cd D:\GetNewGames\meme-hotspot-daily
python main.py
```

指定快照日期：

```powershell
python main.py --date 2026-06-02
```

只抓 B 站全站榜：

```powershell
python main.py --sources bilibili --bili-types 0
```

只抓抖音：

```powershell
python main.py --sources douyin
```

也可以双击或定时执行：

```powershell
run_hotspot_crawler.bat --date 2026-06-02
```

## 判定素材可用性

```powershell
python judge_material.py
```

指定日期、来源或批量大小：

```powershell
python judge_material.py --date 2026-06-02
python judge_material.py --sources douyin
python judge_material.py --date 2026-06-02 --sources douyin --batch-size 20
```

也可以双击或定时执行：

```powershell
run_judge_material.bat --date 2026-06-02
```

## 判定口径

- `pass`：有明确可迁移的视频模板、情绪梗、视觉形式、反差结构或挑战形式，且商业素材风险低。
- `reject`：纯新闻、具体游戏宣发、政治/灾难/刑案/严重负面舆情，或难以游戏化改编。
- `review`：信息不足、可能可用但风险或语义不清，或模型调用失败需要人工复核。

风险等级只能是 `low`、`medium`、`high`。标签字段 `materialTags` 最多保留 5 个中文标签。

## 输出

当前新产物以日期目录为准。抓取和判定结果按 `YYYY-MM-DD` 分目录落地，方便按快照日期复核和归档。

抓取输出：

```text
data/raw/YYYY-MM-DD/douyin/hot.json
data/raw/YYYY-MM-DD/bilibili/<type>.json

data/items/YYYY-MM-DD/douyin_items.json
data/items/YYYY-MM-DD/bilibili_items.json

output/YYYY-MM-DD/douyin_items.csv
output/YYYY-MM-DD/douyin_items.txt
output/YYYY-MM-DD/bilibili_items.csv
output/YYYY-MM-DD/bilibili_items.txt
```

判定输出：

```text
data/judged/YYYY-MM-DD/douyin_judged.json
data/judged/YYYY-MM-DD/bilibili_judged.json

output/YYYY-MM-DD/douyin_passed.csv
output/YYYY-MM-DD/douyin_rejected.csv
output/YYYY-MM-DD/douyin_review.csv
output/YYYY-MM-DD/bilibili_passed.csv
output/YYYY-MM-DD/bilibili_rejected.csv
output/YYYY-MM-DD/bilibili_review.csv
```

统一抓取字段：

```text
source, board, rank, id, title, desc, author, hot, timestamp,
url, mobileUrl, cover, capturedAt
```

判定新增字段：

```text
materialVerdict, materialReason, materialTags, riskLevel
```

## 历史产物策略

旧平铺产物 `hotspot_items_YYYY-MM-DD.*` 属于历史产物。它们可能来自早期输出结构或人工复核流程，不建议在常规文档收口中删除、重命名或批量迁移。

默认策略：

- 新产物继续以 `output/YYYY-MM-DD/*.csv` 和 `output/YYYY-MM-DD/*.txt` 为准。
- 原始候选继续以 `data/items/YYYY-MM-DD/*` 为准。
- LLM 判定结果继续以 `data/judged/YYYY-MM-DD/*` 为准。
- 旧平铺产物保留原状，不批量改写。

后续如果需要归档旧平铺产物，应单独做历史产物整理任务，先确认备份、命名规则、迁移范围和回滚方式。
