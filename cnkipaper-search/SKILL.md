---
name: cnkipaper-search
description: 中国知网文献检索与基本信息提取全流程：解析研究议题（提示词或 Markdown 文档）、生成须人工审核的专业检索式、按指定篇数（默认 50）选出最相关文献、提取题名/作者/来源/发表时间/被引/摘要/关键词并汇总 Excel、按人工标注的清单下载 PDF、再用 markitdown 批量转为 Markdown。用户提出「按议题检索知网文献」「找 50 篇最相关的」「导出文献基本信息表」「批量下载知网 PDF」「把下载的 PDF 转成 Markdown」等需求时使用。
---

# 知网文献检索与基本信息

**解释器约定**：下文 `{PY}` 与 `{PYC}` 都指**本技能目录下 `.venv` 里的 Python**：
Windows 为 `<技能目录>\.venv\Scripts\python.exe`，macOS/Linux 为 `<技能目录>/.venv/bin/python`。
`requirements.txt` 已同时包含 openpyxl、markitdown 与 cnki-deepsearch，一个环境够用。
首次使用先运行 `setup/install.ps1`（Windows PowerShell）或 `bash setup/install.sh`（macOS/Linux）；
系统 PATH 里的 `python` 通常缺依赖，不要直接用它。
`scripts/...` 一律按技能目录展开为绝对路径再执行。

依赖 `cnki-deepsearch` 提供浏览器、登录与知网页面能力。不套用 deepsearch 的「三层渐进发现」。
`references/cnki-api.md` **不预读**：只在工具报错（§5）、字段归属不确定（§4）、
下载落点异常（§6）、候选 JSON 结构（§8）时按节查；不要每轮调 `cnki_syntax_guide`。

## 第 0 步 参数卡（缺省即默认，须向用户明示）

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| 议题来源 | — | 提示词正文，或用户给的 Markdown 路径（两者同权） |
| `top_n` | 50 | 指**最终入选篇数**，不是单条检索式返回数；合法范围 5–120 |
| `pdf_dir` | `{run}/05_pdf/` | 用户可指定任意绝对路径 |
| `md_dir` | `{run}/06_markdown/` | 同上 |
| `run_dir` | `runs/{议题}_{年段}/` | 产物根目录 |

写入 `{run}/.workbuddy/cnki_run.json`；已存在则复用（续跑），不重问。

## 第 1 步 议题卡片（双来源同构）

输出 JSON：`object` / `object_synonyms[]` / `topic` / `topic_synonyms[]` /
`year_from` / `year_to` / `journals[]` / `journal_scope`。

- 来源为 Markdown 时先 Read 文件再抽取；两种来源结果同构，后续不再区分。
- 缺失回填并明示：年份→近 5 年；期刊→学术期刊（不含学位论文）。**禁止静默假设**。

## 第 2 步 检索式（可多条）→ 审核闸门

- 渲染规则：对象 `SU %= 'A'`；主题 `SU %= 'B'`；同义 `(A OR B)`；
  年份 `AND YE >= '2021' AND YE <= '2026'`；期刊 `AND (LY = '刊1' OR LY = '刊2')`。
- 生成 1..N 条，每条列：编号、完整表达式、意图一句话、`max_results`。
- 候选池 `pool = 2 × top_n`（上限 120）；每条 `max_results = min(60, max(20, ceil(pool/条数)))`。
- **【审核闸门】列完必须停下**，等用户确认或修改；改动后重生成再审。
  **未确认前禁止调用任何检索工具。**

## 第 3 步 检索 → 全量取摘要 → 打分 → 取前 N

1. 串行执行已确认检索式；把工具返回的 `results` 原样写入 `{run}/.workbuddy/raw/{query_id}.json`，
   记抓回条数（≠命中总数）。
2. `{PY} scripts/ingest_candidates.py search --info-dir {run}/.workbuddy/basic_info --query-id Q1 --input {run}/.workbuddy/raw/Q1.json`
   由脚本完成字段映射（`citation_count`→`cited`）、题名清洗与去重。
3. **摘要由脚本抓取（原文不进上下文）**：
   `{PYC} scripts/fetch_abstracts.py --info-dir {run}/.workbuddy/basic_info --out {run}/.workbuddy/raw/abs_all.jsonl`
   - 首次先加 `--limit 5` 验证登录态与字段，再全量（`--limit 0`）。
   - 撞「需要安全验证」→ 停下，改用 `--headed` 让用户在小窗完成验证后重跑；脚本按 gid 跳过已抓。
   - 单篇 <120 字会记 `suspect`，可在汇总里看数量。
   抓完合并（复用现有命令，无需模型参与）：
   `{PY} scripts/ingest_candidates.py abstracts --info-dir {run}/.workbuddy/basic_info --input {run}/.workbuddy/raw/abs_all.jsonl`
   **模型不调用 `cnki_get_article`、不读摘要原文**。
4. 打分（脚本，零 token）：
   `0.55×标题命中 + 0.35×摘要字符二元组余弦 + 0.10×被引同年归一`；
   运行 `{PY} scripts/rank_candidates.py --info-dir <dir> --card <card.json> --top-n <N>`。
   议题词命中分低于 `--min-hit`（默认 0.2）直接排除，**不用离题文献凑数**。
5. 取前 `top_n`；只复核第 N±10 名（标题/年份/期刊/被引/`score_detail`）；边界确有争议时
   才读该篇摘要前 200 字（单篇，不批量），调整须写一句理由。
6. 落盘 `{run}/.workbuddy/basic_info/cand_{gid:03d}.json`，字段见 `references/cnki-api.md`。
7. 入选不足 `top_n`：如实报「实际 X / 目标 N」，**不降标准凑数**。
8. 报错：`暂无数据/请稍后重试` → 等 30–60 s 用简化式重试一次；`超时` → 原样重试一次；
   `需要安全验证` → 摘要阶段改用 `--headed` 重跑；检索/下载阶段按「运行时策略」开小窗后重试。

## 第 4 步 汇总 xlsx → 停下等人工审核

运行 `{PY} scripts/build_basic_table.py --info-dir <dir> --out-xlsx <path> --download-list <path>`，产出：

**A. `04_table/文献基本信息表.xlsx`**（两个 Sheet；检索式已在第 2 步审核通过，不再单列记录页）

- Sheet1「基本信息表」：序号（=相关度排名 1..N）、题名、作者（全列表）、来源期刊、
  发表时间、被引次数（空写「未获取」）、摘要全文（由脚本抓取，已修 503 字截断）、
  关键词组（`；`）、URL
- Sheet2「筛选记录」：候选号、站内序、检索式、题名、来源、年份、被引、相关度分、判定、排除理由

**B. `05_download/下载清单.xlsx`**

- 列：序号、题名、第一作者、年份、期刊、被引、相关度分、**摘要**、**是否下载**
  （下拉 是/否，默认全部「是」）、备注

生成后**停下**，提示用户把不要的改成「否」并回传文件路径。

## 第 5 步 按清单下载 PDF

1. `{PY} scripts/read_download_list.py --list <文件> --info-dir {run}/.workbuddy/basic_info --out {run}/.workbuddy/download_queue.json`
   仅 `是/下载/yes/Y/1/true` 才下载；**缺失行视为否**；序号对不上报错，不猜。
2. 每篇 `cnki_download(url)` → 校验 `success` → 读文件头 `%PDF-` → 大小 >10 KB →
   从固定落点移入 `pdf_dir` → 命名 `{序号:03d}_{第一作者}_{年份}_{题名前12字}.pdf`
   （过滤 `\/:*?"<>|`）→ 记录状态。**只移动本次返回的 path，不扫描目录。**
3. 失败（`no_pdf_download_link` 或落到验证页）：用 `TI = '标题'` 回查新链接重试 **1 次**
   （长题名按 `——`/`：` 截断）；仍失败记「PDF不可得/无权限/链接过期」，继续下一项。
4. 节奏：3–5 s/篇，每 10 篇停 20 s；每篇处理完向 `05_download/_download_progress.jsonl`
   追加一行 `{sel_rank, status, file, size, error, at}`（status=ok/failed/skipped），可按序号续跑。
5. 收尾：`{PY} scripts/write_download_result.py --queue <queue> --progress <jsonl> --out-xlsx <path>`
   产出 `下载结果.xlsx` + `_下载校验.md`（成功/失败/未执行/非 PDF）。完成后停下。

## 第 6 步 markitdown 转 Markdown

1. 前置检查 `{PY} -c "import markitdown"`（已装 0.1.9，通常直接通过）；缺才装：
   `{PY} -m pip install "markitdown[pdf]" -i https://pypi.tuna.tsinghua.edu.cn/simple`
2. `{PY} scripts/convert_pdfs.py --pdf-dir <pdf_dir> --md-dir <md_dir>`
   逐个 `convert_local()`，写同名 `.md`，已存在跳过（`--overwrite` 才覆盖）。
3. 产物：`06_markdown/*.md` + `manifest.json` + `_转换校验.md`
   （成功数、字符数 min/median/max、<2000 字告警、失败原因）。完成后停下等审核。

## 阶段化运行（跨会话续跑，省 token）

- 四个天然断点：第 2 步审核后 / 第 4 步建表后 / 第 5 步下载后 / 第 6 步转换后。
- 每阶段产物都已落盘，可随时中断：`{run}/.workbuddy/cnki_run.json`（参数卡）、`raw/`（检索与摘要原样）、
  `basic_info/cand_*.json`（候选）、`download_queue.json`、`05_download/_download_progress.jsonl`。
- 续跑：先读 `cnki_run.json`，再按产物是否存在判断从哪一步接；**已完成的不重跑**
  （脚本本身也做了跳过：已抓摘要、已有 md、已下载进度）。
- 建议在断点处**开新会话**继续下一阶段：十几万 token 的上下文每轮都要重发，换会话可把成本降一个量级。

## 运行时策略

- 所有 cnki 工具**串行**调用，同一时刻只发一个。
- `fetch_abstracts.py` 不占 MCP 锁，但**同一时间不要与 MCP 调用并行**，以免触发知网风控。
- **小窗**：默认 headless；捕获「需要安全验证」→ `cnki_co_open` 开有头窗口 → 告知用户
  「请在小窗完成验证，完成后我会自动继续」→ 重试当前操作；批次结束 `cnki_co_close`
  （只关页面，登录态保留）。
- 登录/验证码由用户在可见窗口完成；不规避风控、不导出 cookie、不保存凭据。

## 硬规则

1. 元数据只取检索结果行；摘要/关键词取详情页；冲突时保留检索行值并记 `conflict`。
2. 不改写、不增删、不推断；缺失「未提取/证据不足」；被引空「未获取」（≠0）。
3. 摘要与关键词由脚本写入，**不在对话中读取或复述**；仅边界复核时读单篇前 200 字。
4. 只用详情页 `#pdfDown` 取 PDF；结果页「下载」给 CAJ，禁用；绝不把 CAJ/HTML 改名 `.pdf`。
5. 不修改 `markdown/`、`papers/`、`reference/` 下已有文件；不动 Zotero。
