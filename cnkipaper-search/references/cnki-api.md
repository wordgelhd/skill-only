# cnki-deepsearch 接口速查

包版本 `cnki_mcp 0.2.1`；服务配置见 `~/.workbuddy/mcp.json` 的 `cnki-deepsearch`。

## 1. 本技能用到的工具

| 工具 | 入参 | 返回 | 限制 |
| --- | --- | --- | --- |
| `cnki_professional_search` | `expression`（必填）、`max_results`（默认 20） | `expression` / `total_results` / `results[]` / `sidebar` | 单次上限由翻页决定；`>20` 时自动点「下一页」，每页 20 条 |
| `cnki_get_article` | `url`（详情页 URL） | `title` / `authors[]` / `abstract` / `keywords[]` / `doi` / `source` | **无被引、无年份**；URL 带 `v=<hash>`，会过期；本技能已改由 `fetch_abstracts.py` 直连取，不再调用它 |
| `cnki_download` | `url`（详情页 URL） | `{success, path, filename, size}` 或 `{success:false, error}` | 点击详情页 `#pdfDown`，落点固定（见 §6） |
| `cnki_co_open` | — | `{ok, co_mode, headed, user_page_open, tabs[]}` | 会把共享浏览器**重启为有头**，常驻 |
| `cnki_co_status` | — | 同上（不含重启） | 只查状态 |
| `cnki_co_close` | — | `{ok, co_mode:false}` | 只关用户页，登录态保留 |
| `cnki_syntax_guide` | — | 完整语法说明 | 本技能已在本文件固化，不必每轮调用 |

`results[]` 单条字段：`title` / `url` / `authors[]` / `source` / `date` / `database` /
`citation_count`（**字符串，空串表示无**）/ `download_count`。
`total_results` = **本次抓回条数**，不是知网命中总数，报告中不得混用。

`fetch_abstracts.py` **不走 MCP**：直接 `from cnki_mcp.browser import CNKIBrowser`、
`from cnki_mcp.parser import parse_article_detail, parse_search_results`，与 MCP 共用
`Path.home()/.cnki_cookies.json` 登录态，但各自启动浏览器、互不占用连接。必须用
cnki-deepsearch venv 的解释器，default venv 里没有这个包。

## 2. 字段码与运算符（必须配对）

| 字段 | 代码 | 运算符 | 示例 |
| --- | --- | --- | --- |
| 主题 | `SU` | `%=` 模糊 / `=` 精确 | `SU %= '技术识别'` |
| 篇名 | `TI` | `%` 模糊 / `=` 精确 | `TI % '大模型'` |
| 关键词 | `KY` | `=` 精确 | `KY = '技术机会'` |
| 作者 | `AU` | `=` 精确 | `AU = '陈劲'` |
| 作者单位 | `AF` | `%` 模糊 | `AF % '清华大学'` |
| 文献来源 | `LY` | `=` 精确 | `LY = '情报学报'` |
| 年份 | `YE` | `>=` / `<=` / `=` | `YE >= '2021' AND YE <= '2026'` |
| 基金 | `CF` | `=` | `CF = '国家自然科学基金'` |

逻辑：`AND` / `OR` / `NOT`；`OR` 组**必须加括号**，否则优先级出错。
日期：只能写比较式；**`YE BETWEEN` 会被风控拦截**（返回「暂无数据」）。

## 3. 禁用写法

- `YE BETWEEN ('2021','2026')` → 一律改成上下界。
- 把年份写进检索词（`SU %= '2021'`）→ 无效且污染相关度。
- `SU = '长句'` 精确匹配 → 命中为 0，改用 `%=`。
- 运算符与字段错配（如 `TI %= 'x'`）→ 页面挂起到 60 s 超时。

## 4. 返回字段归属（不得串用）

| 字段 | 唯一来源 |
| --- | --- |
| 题名 / 作者列表 / 来源 / 发表时间 / 被引 / URL | 检索结果行 |
| 摘要全文 / 关键词组 | `fetch_abstracts.py`（直连 `parse_article_detail`，字段与 `cnki_get_article` 一致） |
| 引文网络 | `cnki_get_citations`（本技能不用） |

冲突处理：`get_article` 的 `source` 常混入出版社/卷期，**以检索行为准**；
被引只认 `citation_count`，空串归一为 `null`，表格填「未获取」。

## 5. 错误矩阵

| 现象 | 判定 | 处理 |
| --- | --- | --- |
| 返回含「暂无数据，请稍后重试」 | 风控拦截（HTTP 200） | 等 30–60 s，去掉年份或改用单边条件重试 **1 次** |
| `超时（60秒）` | 浏览器无响应/脏状态 | 原样重试 1 次（服务会重建浏览器） |
| `CNKI 需要安全验证…` | headless 遇到验证页 | `cnki_co_open` 开小窗，用户完成后重试当前操作 |
| `no_pdf_download_link` | 无 PDF 权限 / 链接过期 / 非 PDF 源 | 用 `TI` 回查新链接重试 1 次；仍失败记原因 |
| 下载文件非 `%PDF-` 头 | 得到 CAJ/HTML | 判为失败，**不得改名 .pdf** |

## 6. 下载落点（固定）

包内固定写入 `Path.cwd()/downloads`；本项目启动器已 `chdir` 到
`D:\AI proj\paper-search\cnki-deepsearch-data`，故实际落点为：

```
D:\AI proj\paper-search\cnki-deepsearch-data\downloads\
```

下载后必须：校验 `%PDF-` → 大小 >10 KB → **移动**到 `pdf_dir` 并重命名
`{序号:03d}_{第一作者}_{年份}_{题名前12字}.pdf`。只移动本次返回的 `path`，
不扫描、不清空该目录。结果页「下载」给 CAJ/KDH，禁用。

## 7. 小窗（headed）机制

- 默认 `headless=True`；`cnki_co_open` 会把浏览器重启为有头并打开用户页。
- headed 下 `_navigate_and_pass_captcha` 检测到 URL 含 `verify`/`captcha` 时：
  输出提示 → 延长时限 → **等待用户完成** → 自动继续（URL 清除或正文出现即通过）。
- 因此「弹小窗」不需要改环境变量或重启 MCP；`CNKI_HEADED=1` 仅在服务启动前设置才生效。
- 小窗是标准 Chrome 窗口，可自行缩放；批次结束调 `cnki_co_close`。

## 8. `cand_{gid:03d}.json` 结构

```json
{
  "gid": 7,
  "query_id": "Q1",
  "site_rank": 12,
  "title": "……",
  "authors": ["张三", "李四"],
  "source": "情报学报",
  "pub_date": "2024-06-15",
  "cited": 23,
  "abstract": "……（逐字照录）",
  "keywords": ["技术识别", "大模型"],
  "url": "https://kns.cnki.net/kcms2/article/abstract?v=...",
  "score": 0.7312,
  "band": "include",
  "selected": true,
  "sel_rank": 3,
  "exclude_reason": "",
  "conflict": "",
  "fetched_at": "2026-11-16T22:40:00+08:00"
}
```

`band` 取值：`include`（入选，`sel_rank` 为 1..N）/ `reserve`（第 N+1..N+15）/
`exclude`（其余，或议题词命中分低于 `--min-hit` 被门槛挡掉；两类都必须有一句理由）。
`abstract` 由 `fetch_abstracts.py` 写入，取自 `<input id="abstract_text">` 隐藏域，
**长度可超过详情页 503 字上限**，属正常（503 只是 DOM 渲染上限）。
`score_detail` 保留 `hit / cos / cos_norm / cite` 四项，便于复核打分。
`selected=false` 的条目保留，供「筛选记录」页审计。

## 9. 目录与断点

```
{run}/.workbuddy/cnki_run.json          参数卡（复用即续跑）
{run}/.workbuddy/raw/Q1.json            检索结果原样落盘（每式一份）
{run}/.workbuddy/raw/abs_01.jsonl       摘要批次（{gid,abstract,keywords,authors}）
{run}/.workbuddy/basic_info/cand_*.json 每篇一落盘
{run}/.workbuddy/download_queue.json    清单 → 待下载队列
{run}/04_table/文献基本信息表.xlsx
{run}/05_download/下载清单.xlsx          人工回填
{run}/05_download/下载结果.xlsx / _下载校验.md / _download_progress.jsonl
{run}/06_markdown/*.md / manifest.json / _转换校验.md
```
