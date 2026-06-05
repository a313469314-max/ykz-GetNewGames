# 国内 DataEye 新品采集工具

这个子项目的产品展示名是 **国内 DataEye 新品**，代码目录名保留为 `adx`。它负责从 DataEye AdXray 获取每日新品游戏，补充厂商信息，生成本地 JSON、CSV、TXT 日报，并可选通过飞书群机器人发送日报。

## 目录

```text
D:\GetNewGames\adx
```

## 当前流程

`npm run fetch:new-games` 是唯一主采集命令，内部流程是：

1. 复用 `.auth/dataeye-state.json` 登录态访问 DataEye。
2. 调用 DataEye 每日新品列表接口。
3. 按 `Asia/Shanghai` 选择目标日期，默认是运行日前一天。
4. 标准化产品字段，例如产品名、平台名、图标链接、详情页链接。
5. 按 `productId` 批量查询产品详情，补充 `companyName`。
6. 生成包含厂商字段的 JSON、CSV、TXT 日报。

如果登录态失效，脚本会自动打开浏览器要求人工完成验证码和登录，成功后继续执行。

同步到飞书多维表格时，对应栏目名是 `国内 DataEye 新品`。

## 安装

```powershell
cd D:\GetNewGames\adx
npm install
npx playwright install chromium
```

## 配置

复制 `.env.example` 为 `.env`，按需填写：

```env
DATAEYE_ACCOUNT=
DATAEYE_PASSWORD=
ADX_FEISHU_WEBHOOK=
```

说明：

- `DATAEYE_ACCOUNT` / `DATAEYE_PASSWORD`：用于自动填充登录表单，验证码仍需人工处理。
- `ADX_FEISHU_WEBHOOK`：用于把 TXT 日报发送到飞书群。不发送群消息时可以留空；脚本也兼容读取旧的 `FEISHU_WEBHOOK`。

## 首次登录

```powershell
cd D:\GetNewGames\adx
npm run login
```

登录成功后会保存状态到：

```text
D:\GetNewGames\adx\.auth\dataeye-state.json
```

后续采集会优先复用这个登录态。

## 日期规则

`--date` 表示 DataEye `stat_date`，也是后续同步到飞书时使用的 `report_date`。不传 `--date` 时，默认采集上海时区运行日前一天。

## 采集前一天

```powershell
cd D:\GetNewGames\adx
npm run fetch:new-games
```

例如当前上海日期是 `2026-05-29`，不传 `--date` 时默认采集 `2026-05-28`。

## 采集指定日期

```powershell
cd D:\GetNewGames\adx
npm run fetch:new-games -- --date 2026-05-28
```

DataEye 当前接口只返回最近约 14 天每日新品。指定更早日期时，脚本会报错提示选择最近 14 天内日期。

## 输出文件

输出文件：

```text
data/daily-new-games-company/YYYY-MM-DD.json
data/daily-new-games-company/YYYY-MM-DD.csv
output/dataeye_new_games_company_YYYY-MM-DD.txt
```

字段重点：

- `productId`：DataEye 产品 ID，也是 DataEye 侧稳定去重标识。
- `productName`：产品名。
- `companyName`：通过产品详情补充的厂商名；部分产品详情查不到时可能为空。
- `platformName`：平台名，例如 iOS、微信小游戏、抖音小游戏、快手小游戏。
- `detailUrl`：DataEye 产品详情页链接。
- `fetchedAt`：本地采集时间。

CSV 使用 UTF-8 with BOM，方便 Excel 打开中文。

## 发送飞书群日报

配置 `ADX_FEISHU_WEBHOOK` 后运行：

```powershell
cd D:\GetNewGames\adx
npm run send:feishu
```

发送指定日期：

```powershell
npm run send:feishu -- --date 2026-05-28
```

直接指定文件：

```powershell
npm run send:feishu -- --path output/dataeye_new_games_company_2026-05-28.txt
```

自动查找日报时，只匹配：

```text
output/dataeye_new_games_company_YYYY-MM-DD.txt
```

不传 `--date` 或 `--path` 时，会在 `output` 里寻找最近 6 小时内最新的公司版日报。

## 验证

```powershell
cd D:\GetNewGames\adx
npm test
npm run typecheck
```

## 常用命令

```powershell
cd D:\GetNewGames\adx
npm run login
npm run fetch:new-games
npm run fetch:new-games -- --date 2026-05-28
npm run send:feishu
npm run send:feishu -- --date 2026-05-28
npm test
npm run typecheck
```
