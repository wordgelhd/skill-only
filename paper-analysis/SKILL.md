---
name: paper-analysis
description: 把一批中英文文献 PDF 转为 Markdown（已有同名 .md 则跳过），提取结构化信息（标题/作者/年份/期刊/研究问题/理论框架/研究方法/数据来源/主要发现/局限性；英文文献概括字段译为中文、标题括注原文、作者与期刊保留原文）汇总为 Excel，再依据用户自备的中文打分说明对每篇打分并输出评分表。用户提出「提取文献结构化信息」「生成文献信息表」「给这批文献打分」「整理综述所需的信息」「PDF 转 Markdown 后提取字段」「extract structured info from papers」「score a batch of papers」等需求时使用。
---

# 文献结构信息提取与分析（中英文）

**解释器约定**：下文所有 `{PY}` 一律指**本技能目录下 `.venv` 里的 Python**：
Windows 为 `<技能目录>\.venv\Scripts\python.exe`，macOS/Linux 为 `<技能目录>/.venv/bin/python`。
首次使用先运行 `setup/install.ps1`（Windows PowerShell）或 `bash setup/install.sh`（macOS/Linux）
创建该 venv 并安装依赖；系统 PATH 里的 `python` 通常缺 openpyxl / markitdown，不要直接用它。
`scripts/...` 一律按技能目录展开为绝对路径再执行。

## 目录约定

```
{run_dir}/
├── pdf/          输入 PDF（只读来源）
├── markdown/     已转换的 md（与 pdf 同级，作为「跳过转换」的依据）
├── reference/    打分说明.md + 可选示例表格（只读，勿改动）
└── note/         产物：文献信息.xlsx、文献评分.xlsx
```

## 第 0 步 参数卡

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `run_dir` | `runs/{议题}/` | 上述四个子目录必须都在 |
| 分批规模 | 约 35 万字符/批 | 第 2 步提取时的单批上限 |

## 第 1 步 PDF → Markdown（已有则跳过）

**`pdf/` 为空则跳过本步**：若 `pdf/` 目录不存在或没有 `.pdf`，打印「无待转换 PDF」并直接进入第 2 步，不要报错。

1. 扫描 `pdf/*.pdf`，逐一检查 `markdown/` 下是否存在同名 `.md`；存在即视为已转换，跳过。
2. 运行 `{PY} scripts/convert_pdfs.py --pdf-dir {run}/pdf --md-dir {run}/markdown`
   （脚本内置「已存在跳过」，只有加 `--overwrite` 才重转）。
3. 前置检查 `{PY} -c "import markitdown"`（已装 0.1.9，通常直接通过）；缺才装：
   `{PY} -m pip install "markitdown[pdf]" -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 第 2 步 提取结构化信息 → note/文献信息.xlsx

1. **先看 reference/ 是否有示例表格**（`*.xlsx`）：读其表头，判定它对应「文献信息表」
   还是「评分表」；若命中「文献信息表」，则列名、列序、格式以其为准；否则用下方默认列。
2. 统计 `markdown/*.md` 总字符数，按约 35 万字符/批切分（通常 8–12 篇/批）。
3. 逐批处理：对每篇先判断语言（中文/英文，判断法见 `references/translation-guide.md`）；
   英文文献的概括性字段（研究问题/理论框架/研究方法/主要发现/局限性）**译为中文**，
   标题按「中文译名（原文）」、作者与期刊保留原文（规则见翻译指南）→
   提取 **10 个字段**（口径见 `references/extraction-guide.md`）→
   把该批的行数据**追加**写入 `note/_extract.jsonl`（每行一篇，带 `filename`）。
4. 全部批完成后，把 `_extract.jsonl` 按标题/年份排序并去重，构造成下述 JSON 结构，
   运行 `{PY} scripts/write_table.py --in note/_info_result.json --out note/文献信息.xlsx`。
5. 完成后停下，汇报总篇数、缺字段统计，等用户检查。

默认列（无示例表格时）：

```
序号、标题、作者、年份、期刊、研究问题、理论框架、研究方法、数据来源、主要发现、局限性
```

## 第 3 步 评分 → note/文献评分.xlsx

1. 读 `reference/打分说明.md`（必读、只读，**始终中文**）。
2. 读 `reference/` 是否存在「评分」示例表格，有则以其列结构为准。
3. 读 `note/文献信息.xlsx` 全部行（**只读表格，不回读原文**；信息不足就标「信息不足」并保守打分，绝不回读原文）。表格字段少、token 小，通常一次读完所有行，不必按字符分批；仅当评分维度很多导致单次输出过大时，按约 50 行/批拆分。
4. 逐篇按打分说明评分；产出 JSON：

```
列 = [序号、标题] + [打分说明定义的各维度分、总分] + [提示词指定的重要信息列]
```

「重要信息列」来自提示词：提示词给出额外字段名（如「研究问题、主要发现」）就按名字追加在评分维度列之后；**未指定则只输出评分维度列**，不额外加列。

5. 运行 `{PY} scripts/write_table.py --in note/_score_result.json --out note/文献评分.xlsx`。
6. 完成后停下，汇报评分分布与分级（若有），等用户检查。

## write_table.py 的输入契约

```json
{
  "sheets": [
    {
      "name": "文献信息",
      "headers": ["序号", "标题", "..."],
      "rows": [["1", "...", "..."], ["2", "...", "..."]],
      "widths": [6, 40, 8],          // 可选：列宽（字符）
      "center_cols": [1, 3, 5]       // 可选：居中的列（从 1 起）
    }
  ]
}
```

可写多个 sheet（如正文表 + 明细表）。脚本负责落盘、表头样式、自动列宽、冻结首行。

## 硬规则

- `reference/` 只读：不改动打分说明与示例表格。
- 元数据（标题/作者/年份/期刊）逐字照录——英文标题按「中文译名（原文）」、作者与期刊保留原文；
  概括性字段（研究问题/理论框架/研究方法/主要发现/局限性）用一句话浓缩，不编造，英文译为中文。
- **两张表一律中文输出**（列名与内容均中文；专有名词按翻译指南保留原文）。
- 缺失字段写「未提及」，不要臆测补全；局限性若为推断，标注「（推断）」。
- 第 2 步读原文的 token 无法避免，但第 3 步必须基于表格、不再回读原文——信息不足就标「信息不足」，绝不回读。
- 分批是断点友好的：已写进 `_extract.jsonl` 的篇不要重复提取，重跑时先读它核对。
- 中间文件：保留 `note/_extract.jsonl`（断点续跑依据）；`_info_result.json`、`_score_result.json`
  在对应 xlsx 写成功后删除（都可由 `_extract.jsonl` 重建）。
