#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""读取人工回填的《下载清单.xlsx》，生成待下载队列（不回显整表）。

用法：
    python read_download_list.py --list 05_download/下载清单.xlsx \
        --info-dir .workbuddy/basic_info --out .workbuddy/download_queue.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import load_workbook

CST = timezone(timedelta(hours=8))
YES = {"是", "下载", "y", "yes", "true", "1", "1.0", "√", "✓"}


def cell_text(v) -> str:
    return "" if v is None else str(v).strip()


def parse_id(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    s = cell_text(v)
    return int(s) if s.isdigit() else None


def year_of(item: dict) -> str:
    m = re.search(r"(19|20)\d{2}", str(item.get("pub_date") or ""))
    return m.group(0) if m else ""


def first_author(item: dict) -> str:
    authors = item.get("authors")
    if isinstance(authors, list) and authors:
        return str(authors[0]).strip() or "未知作者"
    return "未知作者"


def clean_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]', "", str(text))
    return re.sub(r"\s+", " ", text).strip(" .")


def find_header(ws) -> tuple[int, dict[str, int]]:
    for r in range(1, 6):
        names = {cell_text(ws.cell(r, c).value): c for c in range(1, ws.max_column + 1)}
        if "序号" in names and "是否下载" in names:
            return r, names
    raise ValueError("未找到表头（需含「序号」「是否下载」），请确认是技能生成的下载清单")


def main() -> int:
    ap = argparse.ArgumentParser(description="下载清单 → 待下载队列")
    ap.add_argument("--list", required=True, help="人工回填后的下载清单.xlsx")
    ap.add_argument("--info-dir", required=True, help="cand_*.json 所在目录")
    ap.add_argument("--out", default=".workbuddy/download_queue.json", help="队列输出路径")
    ap.add_argument("--pdf-dir", default="", help="PDF 目标目录（可选，写入队列）")
    args = ap.parse_args()

    wb = load_workbook(args.list, data_only=True)
    ws = wb.active
    try:
        head_row, cols = find_header(ws)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    info_dir = Path(args.info_dir)
    by_rank = {}
    for f in sorted(info_dir.glob("cand_*.json")):
        it = json.loads(f.read_text(encoding="utf-8"))
        if it.get("selected") and it.get("sel_rank"):
            by_rank[int(it["sel_rank"])] = it

    wanted, missing_ids, duplicate_ids, blank = [], [], [], 0
    seen = set()
    for r in range(head_row + 1, ws.max_row + 1):
        rid = parse_id(ws.cell(r, cols["序号"]).value)
        flag = cell_text(ws.cell(r, cols["是否下载"]).value).lower()
        if rid is None:
            continue
        if flag not in YES:
            if not flag:
                blank += 1
            continue
        if rid in seen:
            duplicate_ids.append(rid)
            continue
        seen.add(rid)
        it = by_rank.get(rid)
        if not it:
            missing_ids.append(rid)
            continue
        title = str(it.get("title") or "").strip()
        fname = f"{rid:03d}_{first_author(it)}_{year_of(it) or '未知年'}_{clean_filename(title)[:12] or '无题名'}.pdf"
        wanted.append({
            "sel_rank": rid,
            "gid": it.get("gid"),
            "title": title,
            "first_author": first_author(it),
            "year": year_of(it),
            "source": str(it.get("source") or ""),
            "url": str(it.get("url") or ""),
            "filename": fname,
        })

    used, no_url = {}, []
    for item in wanted:
        if not item["url"]:
            no_url.append(item["sel_rank"])
        base = item["filename"]
        if base in used:
            used[base] += 1
            item["filename"] = base[:-4] + f"_{used[base]}.pdf"
        else:
            used[base] = 1

    payload = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "source_list": str(Path(args.list).resolve()),
        "pdf_dir": args.pdf_dir,
        "total_selected": len(wanted),
        "items": wanted,
        "missing_ids": missing_ids,
        "duplicate_ids": duplicate_ids,
        "no_url": no_url,
        "skipped_rows": blank,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({
        "selected": len(wanted),
        "skipped_rows": blank,
        "duplicate_ids": duplicate_ids,
        "missing_ids": missing_ids,
        "no_url": no_url,
        "out": str(out),
    }, ensure_ascii=False))
    if missing_ids or no_url:
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
