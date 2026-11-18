#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""下载进度 jsonl + 下载队列 → 下载结果.xlsx + 校验报告。

用法：
    python write_download_result.py --queue download_queue.json \
        --progress 05_download/_download_progress.jsonl \
        --out-xlsx 05_download/下载结果.xlsx
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

CST = timezone(timedelta(hours=8))
HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
HEAD_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="center")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
STATUS_CN = {"ok": "成功", "failed": "失败", "skipped": "跳过（已存在）"}


def main() -> int:
    ap = argparse.ArgumentParser(description="下载进度 → 下载结果.xlsx")
    ap.add_argument("--queue", required=True, help="read_download_list.py 产出的队列")
    ap.add_argument("--progress", required=True, help="_download_progress.jsonl")
    ap.add_argument("--out-xlsx", required=True, help="下载结果.xlsx 输出路径")
    ap.add_argument("--report", default="", help="校验报告，默认与 xlsx 同目录")
    args = ap.parse_args()

    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    items = queue.get("items", [])
    if not items:
        print("下载队列为空", file=sys.stderr)
        return 1

    latest: dict[int, dict] = {}
    p = Path(args.progress)
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                latest[int(rec["sel_rank"])] = rec
            except (ValueError, KeyError, TypeError):
                continue

    rows, counts = [], {"成功": 0, "失败": 0, "跳过（已存在）": 0, "未执行": 0}
    total_bytes = 0
    for item in items:
        rid = int(item["sel_rank"])
        rec = latest.get(rid, {})
        status = STATUS_CN.get(str(rec.get("status", "")).lower(), "未执行")
        counts[status] = counts.get(status, 0) + 1
        size = rec.get("size")
        if isinstance(size, (int, float)) and size > 0:
            total_bytes += int(size)
        rows.append([
            rid,
            item.get("title", ""),
            status,
            rec.get("file") or item.get("filename", ""),
            round(size / 1024, 1) if isinstance(size, (int, float)) and size > 0 else "",
            rec.get("error", "") or "",
            rec.get("at", "") or "",
        ])

    wb = Workbook()
    ws = wb.active
    ws.title = "下载结果"
    ws.append(["序号", "题名", "状态", "文件名", "大小(KB)", "失败原因", "完成时间"])
    for row in rows:
        ws.append(row)
    for idx, width in enumerate([6, 42, 14, 34, 10, 30, 20], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for cell in ws[1]:
        cell.fill, cell.font, cell.alignment, cell.border = HEAD_FILL, HEAD_FONT, CENTER, BORDER
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=7):
        for cell in row:
            cell.font, cell.border = BODY_FONT, BORDER
            cell.alignment = CENTER if cell.column in (1, 3, 5, 7) else WRAP
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{ws.max_row}"

    out = Path(args.out_xlsx)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)

    failures = [r for r in rows if r[2] in ("失败", "未执行")]
    report_path = Path(args.report) if args.report else out.parent / "_下载校验.md"
    lines = [
        "# PDF 下载校验", "",
        f"- 生成时间：{datetime.now(CST).isoformat(timespec='seconds')}",
        f"- 清单请求：{len(items)} 篇；成功 {counts['成功']}；跳过 {counts['跳过（已存在）']}；"
        f"失败 {counts['失败']}；未执行 {counts['未执行']}",
        f"- 已下载总量：{total_bytes / 1024 / 1024:.1f} MB",
        "", "## 异常明细", "",
    ]
    lines += [f"- {r[0]}｜{r[1][:40]}｜{r[2]}｜{r[5]}" for r in failures] or ["- 无"]
    lines += ["", "> 失败原因常见值：no_pdf_download_link（无 PDF 权限）、链接过期、"
                  "not_pdf（拿到 CAJ/HTML）、超时。未自动改名，也未把 CAJ 当 PDF。"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "requested": len(items), "ok": counts["成功"], "skipped": counts["跳过（已存在）"],
        "failed": counts["失败"], "not_run": counts["未执行"],
        "mb": round(total_bytes / 1024 / 1024, 2),
        "xlsx": str(out), "report": str(report_path),
    }, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
