# DataEye AdXray 每日新游戏采集工具

使用 Node.js + TypeScript + Playwright 实现 DataEye AdXray 每日新品采集，并支持生成日报文本、发送到飞书群 webhook。

## 项目目录

当前项目目录：

```text
D:\GetNewGames\adx
```

后续命令都在这个目录下执行。

## 功能概览

- 首次登录后保存登录态到 `.auth/dataeye-state.json`
- 后续采集复用登录态，浏览器不需要保持打开
- 默认采集上海时区前一日新品
- 支持采集指定日期新品
- 输出 UTF-8 JSON 和 UTF-8 with BOM CSV
- 额外生成一份日报文本，适合直接发飞书
- 支持通过飞书 webhook 发送日报
- 不在控制台输出 token、cookie、sign

## 安装依赖

```bash
cd D:\GetNewGames\adx
npm install
npx playwright install chromium
```

## 配置 `.env`

复制 `.env.example` 为 `.env`，按需填写：

```env
DATAEYE_ACCOUNT=
DATAEYE_PASSWORD=
FEISHU_WEBHOOK=
```

说明：

- `DATAEYE_ACCOUNT` / `DATAEYE_PASSWORD`：用于自动填充登录表单，验证码仍需人工输入
- `FEISHU_WEBHOOK`：用于发送日报到飞书群；不发送飞书时可留空

## 首次登录

```bash
cd D:\GetNewGames\adx
npm run login
```

流程说明：

1. 程序打开 `https://adxray.dataeye.com/index/home`
2. 若 `.env` 中配置了 `DATAEYE_ACCOUNT` / `DATAEYE_PASSWORD`，会尝试自动填充
3. 验证码必须人工输入
4. 登录成功后程序校验：
   - `window.App?.isLogin === "1"`
   - `window.App?.userKey` 存在
5. 校验成功后保存登录态到 `.auth/dataeye-state.json`

浏览器不需要保持打开，保存完状态后会自动关闭。

## 采集前一日

```bash
cd D:\GetNewGames\adx
npm run fetch:new-games
```

默认会按 `Asia/Shanghai` 计算当前日期，并读取前一日数据。

例如：如果当前上海日期是 `2026-05-19`，不传 `--date` 时默认读取 `2026-05-18`。

DataEye 当前入口仍然只返回最近 14 天每日新品；如果前一日不在接口返回范围内，程序会保持现有报错提示。

## 采集指定日期

```bash
cd D:\GetNewGames\adx
npm run fetch:new-games -- --date 2026-05-18
```

如果指定日期不在接口返回范围内，程序会提示：

`DataEye 当前入口仅返回最近 14 天每日新品，请选择最近 14 天内的日期。`

## 输出文件

采集时会生成三类文件：

```text
data/daily-new-games/YYYY-MM-DD.json
data/daily-new-games/YYYY-MM-DD.csv
output/dataeye_new_games_YYYY-MM-DD.txt
```

说明：

- JSON 为 UTF-8，保留中文
- CSV 为 UTF-8 with BOM，方便 Excel 打开中文不乱码
- TXT 为日报文本，格式参考旁边 YouTube 新游日报项目，适合直接发飞书

## 发送飞书日报

先在 `.env` 或环境变量中配置：

```env
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

发送最近 6 小时内最新的一份日报：

```bash
cd D:\GetNewGames\adx
npm run send:feishu
```

发送指定日期的日报：

```bash
cd D:\GetNewGames\adx
npm run send:feishu -- --date 2026-05-18
```

也可以直接指定文件路径：

```bash
cd D:\GetNewGames\adx
npm run send:feishu -- --path output/dataeye_new_games_2026-05-18.txt
```

## 登录态过期处理

如果登录态失效、状态文件缺失，或接口返回未登录相关响应，请重新执行：

```bash
cd D:\GetNewGames\adx
npm run login
```

## 当前入口限制

DataEye 当前入口仅返回最近 14 天每日新品，不支持通过这个入口直接获取更早日期的数据。

## 常用命令

```bash
cd D:\GetNewGames\adx
npm run login
npm run fetch:new-games
npm run fetch:new-games -- --date 2026-05-18
npm run send:feishu
npm run send:feishu -- --date 2026-05-18
npm test
```
