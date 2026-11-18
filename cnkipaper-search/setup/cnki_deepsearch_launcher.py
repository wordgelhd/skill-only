"""cnki-deepsearch MCP 启动器 — 固定工作目录，使 PDF 下载落点可预期。

包内代码把下载存到 Path.cwd()/downloads；Agent 启动 MCP 时 cwd 不可控，
故先 chdir 到固定数据目录。

数据目录优先级：
1. 环境变量 CNKI_DEEPSEARCH_DATA
2. <技能目录>/cnki-deepsearch-data   （默认）
"""
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CNKI_DEEPSEARCH_DATA", SKILL_DIR / "cnki-deepsearch-data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(DATA_DIR)

from cnki_mcp.server import run  # noqa: E402

if __name__ == "__main__":
    run()
