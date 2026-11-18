# paper-analysis

文献结构信息提取与评分技能，**中英文文献通用**。适用于支持 `SKILL.md` 的 Agent（WorkBuddy、Claude Code、OpenCode 等）。

三步走完：**PDF → Markdown → 文献信息表 → 文献评分表**。提取、翻译、评分由模型完成；转换与写表由脚本完成。

## 能做什么

| 步骤 | 内容 | 产物 |
| --- | --- | --- |
| 1 | `pdf/` 批量转 Markdown（已有同名 `.md` 自动跳过） | `markdown/*.md` + manifest |
| 2 | 提取 10 个字段：标题、作者、年份、期刊、研究问题、理论框架、研究方法、数据来源、主要发现、局限性 | `note/文献信息.xlsx` |
| 3 | 按 `reference/打分说明.md`（只读、中文）逐篇评分 | `note/文献评分.xlsx` |

**双语规则**：中文文献直接提取；英文文献的概括字段译为中文，标题写成「中文译名（English Original Title）」，作者与期刊保留原文；两张表一律中文输出。术语对照表在 `references/translation-guide.md`，可自行追加。

## 仓库结构

```
paper-analysis/
├── SKILL.md                        # 技能主文件（三步流程 + 输入契约 + 硬规则）
├── references/
│   ├── extraction-guide.md         # 10 字段口径、理论框架 vs 研究方法、打分说明格式
│   └── translation-guide.md        # 语言识别、翻译原则、经管术语对照表 30+ 词条
├── scripts/
│   ├── convert_pdfs.py             # PDF → Markdown（markitdown，幂等跳过）
│   └── write_table.py              # 通用 JSON → xlsx（多 Sheet/列宽/居中/冻结）
├── setup/
│   ├── install.ps1                 # Windows 一键装环境
│   ├── install.sh                  # macOS/Linux 一键装环境
│   └── verify.py                   # 依赖自检
├── requirements.txt
└── .gitignore
```

## 依赖

| 依赖 | 说明 |
| --- | --- |
| Python 3.10+ | 脚本使用技能目录下的 `.venv` |
| `openpyxl>=3.1` | 读写 xlsx |
| `markitdown[pdf]>=0.1.9` | PDF 转 Markdown |

**无 MCP 依赖，无其它技能依赖。**

## 安装

本仓库含两个技能，各占一个子目录。先克隆，再把 `paper-analysis/` 整个子目录复制到 Agent 的技能目录，**目录名保持 `paper-analysis`**：

```bash
git clone https://github.com/wordgelhd/skill-only.git
cp -r skill-only/paper-analysis <技能目录>/
```

| Agent | 用户级 | 项目级 |
| --- | --- | --- |
| WorkBuddy | `~/.workbuddy/skills/` | `<项目>/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` | `<项目>/.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `<项目>/.opencode/skills/` |

然后在技能目录执行安装脚本：

**Windows（PowerShell）**

```powershell
powershell -ExecutionPolicy Bypass -File setup\install.ps1
.venv\Scripts\python.exe setup\verify.py
```

**macOS / Linux**

```bash
bash setup/install.sh
.venv/bin/python setup/verify.py
```

## 准备运行目录

技能不写死路径，运行时按「议题」建一个目录（`run_dir`）：

```text
runs/{议题}/
├── pdf/          放待分析的 PDF（可空）
├── markdown/     自动生成（已有同名 .md 则跳过转换）
├── reference/
│   ├── 打分说明.md      ← 必填、只读
│   └── *.xlsx           ← 可选：示例表格，决定输出列结构
└── note/         产物：文献信息.xlsx、文献评分.xlsx
```

### 打分说明.md 怎么写

至少包含三部分：

1. **评分维度**：每个维度的名称 + 含义 + 分值范围或权重。
2. **总分公式**：加权求和或直接加总。
3. **打分锚点**：什么情况给高分/低分，保证评分一致。

若文件不存在或没有任何可量化维度，技能会**停下提醒你补充**，不会自己发明一套规则。

## 运行

在对话里直接说：

```text
用 paper-analysis 分析 runs/技术识别_2021-2026 下的文献
```

或更口语化：

- 「提取这批文献的结构化信息」
- 「生成文献信息表」
- 「给这批文献打分」
- 「把 pdf 里的文献转成 markdown 并整理成表」

第 2 步完成会停下等你检查提取质量；第 3 步完成会停下汇报评分分布。

## 设计要点

- **评分只读表格，不回读原文**——这是省 token 的关键；信息不足标「信息不足」并保守打分，不臆造。
- **逐字照录 vs 概括浓缩**：前四列（标题/作者/年份/期刊）不改写；后六列一句话浓缩，不编造。
- **断点友好**：已提取的篇目写入 `_extract.jsonl`，重跑不重复提取。
- **示例表格优先**：`reference/*.xlsx` 的表头决定输出列名与列序（只作格式模板，不复制示例数据）。

## 产物

| 文件 | 内容 |
| --- | --- |
| `note/文献信息.xlsx` | 序号 + 10 字段 |
| `note/文献评分.xlsx` | 序号、标题 + 打分说明定义的各维度分与总分 + 提示词指定的重要信息列 |

## 常见问题

**Q：英文文献标题会翻译吗？**
会。格式为「中文译名（English Original Title）」，既方便中文速览，也能回溯原文。

**Q：作者和期刊名为什么不译？**
专有名词翻译容易不一致。作者保留原文姓名，期刊保留英文全称，方便检索与引用。

**Q：能自定义术语译名吗？**
可以。直接编辑 `references/translation-guide.md` 的对照表，追加你所在领域的惯用译名；技能会优先采用。

**Q：为什么用 `.venv` 而不是系统 Python？**
系统 PATH 里的 `python` 往往缺 `openpyxl` / `markitdown`。技能约定统一用技能目录下 `.venv` 的解释器。

## 依赖致谢

- [MarkItDown](https://github.com/microsoft/markitdown)（MIT）：PDF 转 Markdown。

## 许可

本仓库的技能文件与脚本可自由使用与修改；第三方依赖遵循其各自许可。
