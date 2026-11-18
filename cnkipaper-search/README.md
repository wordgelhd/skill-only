# cnkipaper-search

中国知网文献检索与基本信息提取技能。适用于支持 `SKILL.md` 的 Agent（WorkBuddy、Claude Code、OpenCode 等）。

一条流水线走完：**议题 → 检索式审核 → 检索取摘要 → 规则打分选前 N → 基本信息表 → 人工标注下载 → PDF → Markdown**。

## 能做什么

| 步骤 | 内容 | 是否停下等人 |
| --- | --- | --- |
| 1 | 解析研究议题（提示词或 Markdown），输出议题卡片 | 缺关键项时询问 |
| 2 | 生成 1..N 条知网专业检索式 | **是**，审核通过才检索 |
| 3 | 串行检索、全量取摘要、规则打分，选出前 `top_n`（默认 50） | 否 |
| 4 | 输出 `文献基本信息表.xlsx` + `下载清单.xlsx` | **是**，人工标注「是/否」 |
| 5 | 按清单下载 PDF，校验 `%PDF-`，失败回查重试 1 次 | 验证时弹小窗 |
| 6 | markitdown 批量转 Markdown，附 manifest 与校验报告 | 否 |

## 仓库结构

```
cnkipaper-search/
├── SKILL.md                        # 技能主文件（六步流程）
├── references/
│   └── cnki-api.md                 # cnki-deepsearch 接口速查（工具/字段码/限制/错误矩阵）
├── scripts/                        # 7 个确定性脚本，全部零 token
│   ├── ingest_candidates.py        #   检索/摘要 jsonl → 候选 JSON（映射/清洗/去重）
│   ├── fetch_abstracts.py          #   直连 cnki_mcp 抓摘要（不进上下文，顺带修 503 字截断）
│   ├── rank_candidates.py          #   相关度打分与初选（--min-hit 门槛）
│   ├── build_basic_table.py        #   基本信息表 + 下载清单
│   ├── read_download_list.py       #   读人工清单 → 下载队列
│   ├── write_download_result.py    #   下载进度 → 结果表 + 校验
│   └── convert_pdfs.py             #   PDF → Markdown（markitdown）
├── setup/
│   ├── install.ps1                 # Windows 一键装环境
│   ├── install.sh                  # macOS/Linux 一键装环境
│   ├── verify.py                   # 依赖自检
│   ├── cnki_deepsearch_launcher.py # MCP 启动器（固定下载落点）
│   └── mcp.example.json            # MCP 配置模板
├── requirements.txt
└── .gitignore
```

## 依赖

| 依赖 | 说明 |
| --- | --- |
| Python 3.10+ | 脚本与 MCP 共用技能目录下的 `.venv` |
| `cnki-deepsearch==0.2.1` | **唯一的 MCP 依赖**，PyPI 公开包（MIT），自动随 requirements 安装 |
| `openpyxl` | 读写 xlsx |
| `markitdown[pdf]` | PDF 转 Markdown |
| Microsoft Edge | `CNKIBrowser` 默认 `browser_channel="msedge"`；机器上没有 Edge 时给 `fetch_abstracts.py` 加 `--channel chromium` |
| 知网账号 | PDF 下载权限取决于机构 IP / 个人订阅 |

**本技能不依赖其它技能。** `cnki-deepsearch` 提供浏览器、登录与知网页面能力，已包含在安装脚本里。

## 安装

本仓库含两个技能，各占一个子目录。先克隆，再把 `cnkipaper-search/` 整个子目录复制到 Agent 的技能目录，**目录名保持 `cnkipaper-search`**：

```bash
git clone https://github.com/wordgelhd/skill-only.git
cp -r skill-only/cnkipaper-search <技能目录>/
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
```

**macOS / Linux**

```bash
bash setup/install.sh
```

脚本会：创建 `.venv` → 升级 pip → 安装 `requirements.txt` → 安装 Playwright Chromium。
完成后自检：

```powershell
.venv\Scripts\python.exe setup\verify.py     # Windows
.venv/bin/python setup/verify.py             # macOS / Linux
```

## 配置 MCP

编辑 `setup/mcp.example.json`，把 `<SKILL_DIR>` 替换为技能目录的绝对路径：

```json
{
  "mcpServers": {
    "cnki-deepsearch": {
      "type": "stdio",
      "command": "<SKILL_DIR>/.venv/Scripts/python.exe",
      "args": ["<SKILL_DIR>/setup/cnki_deepsearch_launcher.py"]
    }
  }
}
```

macOS / Linux 把 `command` 换成 `<SKILL_DIR>/.venv/bin/python`。

- **WorkBuddy**：合并进 `~/.workbuddy/mcp.json`（先读后合并，不要整体覆盖），然后在连接器管理页右上角「自定义连接器」点「信任」。
- **Claude Code**：合并进项目或用户的 MCP 配置。
- **OpenCode**：按 OpenCode 的 MCP 配置格式填写。

## 首次使用

1. 确认 MCP `cnki-deepsearch` 已连接。
2. 首次检索会启动浏览器，请在弹出的窗口里登录知网（登录态保存在浏览器 profile，后续复用）。
3. 在提示词里给出：

```text
研究对象：平台企业
研究主题：数字化转型对创新绩效的影响
年份：2021–2026
期刊：（可逐本列出，或留空按学科范围）
数量：50
```

4. 技能会先给出检索式，**等你审核**后再开跑。

## 产物示例

```text
runs/{议题}_{年段}/
├── 04_table/文献基本信息表.xlsx     # 两个 Sheet：基本信息表 + 筛选记录
├── 05_download/下载清单.xlsx        # 人工标注「是/否」
├── 05_download/下载结果.xlsx        # 成功/失败/未执行/非 PDF
├── 05_pdf/*.pdf                     # 下载的 PDF
└── 06_markdown/*.md                 # Markdown + manifest.json + _转换校验.md
```

## 常见问题

**Q：提示「需要安全验证」怎么办？**
技能会调用 `cnki_co_open` 打开有头小窗，你在窗口里完成验证后它会自动继续。

**Q：某些论文下载不到 PDF？**
可能是无机构权限、链接过期或只有 CAJ。技能会如实记「PDF 不可得/无权限」，不会把 CAJ 改名成 PDF 硬凑。

**Q：能按 CSSCI / 北大核心过滤吗？**
不能直接过滤。知网检索字段码只有 `SU/TI/KY/AU/AF/LY/YE/CF` 八个，没有核心期刊标识。需要先准备目标刊名名单，用 `LY = '刊名'` 精确匹配。

**Q：为什么用 `.venv` 而不是系统 Python？**
系统 PATH 里的 `python` 往往缺 `openpyxl` / `markitdown`。技能约定统一用技能目录下 `.venv` 的解释器，换机器只需重跑一次安装脚本。

## 依赖致谢

- [cnki-deepsearch](https://github.com/weileyao2005/cnki-deepsearch)（MIT）：知网深搜 MCP，提供检索、详情、下载与浏览器控制能力。
- [MarkItDown](https://github.com/microsoft/markitdown)（MIT）：PDF 转 Markdown。

## 许可

本仓库的技能文件与脚本可自由使用与修改；第三方依赖遵循其各自许可。
