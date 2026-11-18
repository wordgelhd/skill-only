#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用 JSON → xlsx 写入器。

输入 JSON 结构：
{
  "sheets": [
    {
      "name": "文献信息",
      "headers": ["序号", "标题", "..."],
      "rows": [["1", "...", "..."], ["2", "...", "..."]],
      "widths": [6, 40, 8],          # 可选：列宽（字符）
      "center_cols": [1, 3, 5]       # 可选：居中的列（从 1 起）
    }
  ]
}

用法：
    python write_table.py --in result.json --out note/文献信息.xlsx
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
HEADER_FONT = Font(bold=True)
WRAP = Alignment(vertical="top", wrap_text=True)
CENTER = Alignment(vertical="center", horizontal="center", wrap_text=True)


def _display_width(v: str) -> int:
    """按中文=2、ASCII=1 估算显示宽度，换行取最长行。"""
    if v is None:
        return 0
    return max((sum(2 if ord(ch) > 127 else 1 for ch in line)
                for line in str(v).split("\n")), default=0)


def _autofit(ws, headers: list, rows: list) -> None:
    ncol = max(len(headers), max((len(r) for r in rows), default=0))
    for c in range(1, ncol + 1):
        mx = _display_width(headers[c - 1]) if c <= len(headers) else 0
        for r in rows:
            if c <= len(r):
                mx = max(mx, _display_width(r[c - 1]))
        ws.column_dimensions[get_column_letter(c)].width = min(max(mx + 2, 8), 60)


def main() -> int:
    ap = argparse.ArgumentParser(description="通用 JSON → xlsx")
    ap.add_argument("--in", dest="inp", required=True, help="输入 JSON")
    ap.add_argument("--out", required=True, help="输出 xlsx 路径")
    args = ap.parse_args()

    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    sheets = data.get("sheets") or data.get("data") or []
    if isinstance(sheets, dict):
        sheets = [sheets]
    if not sheets:
        print("输入 JSON 缺少 sheets", file=sys.stderr)
        return 1

    wb = Workbook()
    wb.remove(wb.active)
    for si, sh in enumerate(sheets):
        name = str(sh.get("name") or f"Sheet{si + 1}")
        headers = sh.get("headers") or []
        rows = sh.get("rows") or []
        widths = sh.get("widths") or []
        center_cols = set(sh.get("center_cols") or [])

        ws = wb.create_sheet(title=name[:31])
        for c, h in enumerate(headers, start=1):
            cell = ws.cell(1, c, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
            cell.border = BORDER
        for r, row in enumerate(rows, start=2):
            for c, v in enumerate(row, start=1):
                cell = ws.cell(r, c, value=(v if v is not None else ""))
                cell.alignment = CENTER if c in center_cols else WRAP
                cell.border = BORDER
        if widths:
            for c, w in enumerate(widths, start=1):
                ws.column_dimensions[get_column_letter(c)].width = w
        else:
            _autofit(ws, headers, rows)
        ws.freeze_panes = "A2"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(json.dumps({
        "sheets": len(sheets),
        "rows": [len(s.get("rows") or []) for s in sheets],
        "out": str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
