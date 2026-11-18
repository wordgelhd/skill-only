#!/usr/bin/env bash
# 在技能目录下创建 .venv 并安装全部依赖（macOS / Linux）
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${SKILL_DIR}/.venv"
PY="${VENV_DIR}/bin/python"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3，请先安装 Python 3.10+" >&2
  exit 1
fi

echo "[1/4] 创建 venv: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

echo "[2/4] 升级 pip"
"${PY}" -m pip install -U pip

echo "[3/4] 安装依赖（cnki-deepsearch / openpyxl / markitdown）"
"${PY}" -m pip install -r "${SKILL_DIR}/requirements.txt"

echo "[4/4] 安装 Playwright Chromium（cnki-deepsearch 需要）"
"${PY}" -m playwright install chromium

echo
echo "完成。"
echo "技能目录: ${SKILL_DIR}"
echo "解释器:   ${PY}"
echo "下一步:   把 setup/mcp.example.json 里的 <SKILL_DIR> 替换为上面的技能目录，合并进 MCP 配置。"
