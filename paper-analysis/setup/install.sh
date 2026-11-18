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

echo "[1/3] 创建 venv: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

echo "[2/3] 升级 pip"
"${PY}" -m pip install -U pip

echo "[3/3] 安装依赖（openpyxl / markitdown）"
"${PY}" -m pip install -r "${SKILL_DIR}/requirements.txt"

echo
echo "完成。"
echo "技能目录: ${SKILL_DIR}"
echo "解释器:   ${PY}"
echo "下一步:   用 setup/verify.py 自检，然后按 README 准备运行目录。"
