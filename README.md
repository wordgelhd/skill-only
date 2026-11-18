# skill-only

两个面向文献工作流的 Agent Skill，遵循 [SKILL.md 规范](https://code.claude.com/docs/en/skills)（WorkBuddy / Claude Code / OpenCode 通用）。

```
skill-only/
├── cnkipaper-search/    中国知网：检索 → 基本信息表 → 审核下载 → Markdown
└── paper-analysis/      PDF → Markdown → 10 字段信息表 → 按打分说明评分
```

两者可独立使用，也可串成一条完整链路：

```
议题
 └─ cnkipaper-search ──► pdf/ ──► paper-analysis ──► note/文献信息.xlsx
                                    └─► note/文献评分.xlsx
```

## 快速开始

```bash
git clone https://github.com/wordgelhd/skill-only.git
```

把需要的子目录复制到 Agent 的技能目录（目录名不要改）：

| Agent | 用户级 | 项目级 |
| --- | --- | --- |
| WorkBuddy | `~/.workbuddy/skills/` | `<项目>/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` | `<项目>/.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `<项目>/.opencode/skills/` |

然后进入该技能目录跑一次安装脚本（创建 `.venv` 并装依赖）：

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File setup\install.ps1
```

```bash
# macOS / Linux
bash setup/install.sh
```

新装的技能不会在已开的对话里热加载，**重开一次对话**才会出现在技能列表。

## 两个技能各自要什么

| | cnkipaper-search | paper-analysis |
| --- | --- | --- |
| 输入 | 研究议题（对象 / 主题 / 年份 / 期刊，可加同义词与种子文献） | `pdf/` 下的文献 PDF；`reference/打分说明.md` |
| 输出 | `04_table/文献基本信息表.xlsx` + 下载清单 + `markdown/` | `note/文献信息.xlsx` + `note/文献评分.xlsx` |
| MCP | **cnki-deepsearch**（安装脚本自动装好） | 无 |
| 外部依赖 | 知网登录态、PDF 下载权限 | 无 |
| 人工介入 | 检索式审核、下载清单标「是/否」 | 提供打分说明.md |
| 语言 | 中文文献 | 中英文文献（英文译中文输出） |

细节分别见 [cnkipaper-search/README.md](cnkipaper-search/README.md) 与 [paper-analysis/README.md](paper-analysis/README.md)。

## 设计原则

- **模型只做判断，脚本只做搬运。** 检索式设计、选哪篇、字段概括、评分是模型的事；去重、打分排序、xlsx 落盘、格式转换、读回人工标注全是 Python 脚本，确定性、零 token。
- **事实与流程分离。** 接口事实、字段归属、风控黑名单放在 `references/`，按需读取；`SKILL.md` 只留流程，控制在 120 行内。
- **人机交界处必须停。** 检索式、下载清单、打分说明三处强制停下等人工确认，不猜、不自动放行。

## 环境

Python 3.10+。依赖清单见各子目录 `requirements.txt`：

| 技能 | 依赖 |
| --- | --- |
| cnkipaper-search | `cnki-deepsearch==0.2.1`、`openpyxl`、`markitdown[pdf]`、Playwright Chromium |
| paper-analysis | `openpyxl`、`markitdown[pdf]` |

`cnki-deepsearch` 是 MIT 许可的第三方包（PyPI），本仓库不收录其源码，安装脚本直接安装并生成 MCP 配置所需的启动器与示例。

## 已知限制

- **cnkipaper-search 无法按期刊级别（CSSCI / 北大核心）过滤**——知网检索字段码只有 `SU/TI/KY/AU/AF/LY/YE/CF`，没有核心库标识。要限定核心刊只能逐本列出刊名，或检索后人工按「来源期刊」筛。
- **PDF 可得性取决于账号权限。** 无权限时只能拿到 CAJ 或验证页，脚本会如实记「PDF不可得」，不硬凑。
- **英文文献的翻译质量由模型 + 术语表决定**，脚本无法校验；`paper-analysis/references/translation-guide.md` 里是起点词表，可按学科继续追加。
