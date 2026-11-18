#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""候选 JSON → 文献基本信息表.xlsx + 下载清单.xlsx + 校验报告。

用法：
    python build_basic_table.py --info-dir <basic_info> \
        --out-xlsx 04_table/文献基本信息表.xlsx \
        --download-list 05_download/下载清单.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

CST = timezone(timedelta(hours=8))
MISS = "未提取/证据不足"
HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
HEAD_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="center")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def txt(value, default: str = MISS) -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def authors_str(value) -> str:
    if isinstance(value, list):
        names = [str(v).strip() for v in value if str(v).strip()]
        return "，".join(names) if names else MISS
    return txt(value)


def keywords_str(value) -> str:
    if isinstance(value, list):
        kws = [str(v).strip() for v in value if str(v).strip()]
        return "；".join(kws) if kws else MISS
    return txt(value)


def year_of(item: dict) -> str:
    m = re.search(r"(19|20)\d{2}", str(item.get("pub_date") or ""))
    return m.group(0) if m else ""


def first_author(item: dict) -> str:
    authors = item.get("authors")
    if isinstance(authors, list) and authors:
        return str(authors[0]).strip() or "未知作者"
    if isinstance(authors, str) and authors.strip():
        return authors.split("，")[0].split(";")[0].strip()
    return "未知作者"


def clean_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]', "", str(text))
    return re.sub(r"\s+", " ", text).strip(" .")


def style_sheet(ws, widths: list[int], center_cols: set[int]) -> None:
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for cell in ws[1]:
        cell.fill, cell.font, cell.alignment, cell.border = HEAD_FILL, HEAD_FONT, CENTER, BORDER
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=len(widths)):
        for cell in row:
            cell.font, cell.border = BODY_FONT, BORDER
            cell.alignment = CENTER if cell.column in center_cols else WRAP
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(widths))}{ws.max_row}"


def fit_rows(ws, col: int, chars_per_line: int, cap: int) -> None:
    """按摘要长度给行高一个可读的预览高度（不设则换行文本只显示一行）。"""
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=col, max_col=col):
        cell = row[0]
        lines = len(str(cell.value or "")) // max(1, chars_per_line) + 1
        ws.row_dimensions[cell.row].height = min(cap, max(30, lines * 15))


def main() -> int:
    ap = argparse.ArgumentParser(description="候选 JSON 汇总为基本信息表与下载清单")
    ap.add_argument("--info-dir", required=True, help="cand_*.json 所在目录")
    ap.add_argument("--out-xlsx", required=True, help="文献基本信息表.xlsx 输出路径")
    ap.add_argument("--download-list", required=True, help="下载清单.xlsx 输出路径")
    ap.add_argument("--report", default="", help="校验报告，默认与 out-xlsx 同目录")
    args = ap.parse_args()

    info_dir = Path(args.info_dir)
    files = sorted(info_dir.glob("cand_*.json"))
    if not files:
        print(f"no cand_*.json in {info_dir}", file=sys.stderr)
        return 1

    cands = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    selected = sorted([c for c in cands if c.get("selected")], key=lambda x: x.get("sel_rank") or 10 ** 6)
    if not selected:
        print("没有 selected=true 的候选，请先运行 rank_candidates.py", file=sys.stderr)
        return 1

    ranking = {}
    rk = info_dir / "_ranking.json"
    if rk.exists():
        ranking = json.loads(rk.read_text(encoding="utf-8"))
    top_n = int(ranking.get("top_n") or len(selected))

    now = datetime.now(CST)
    out_xlsx = Path(args.out_xlsx)
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    dl_path = Path(args.download_list)
    dl_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    # ---------- Sheet1 基本信息表 ----------
    ws1 = wb.active
    ws1.title = "基本信息表"
    head1 = ["序号", "题名", "作者", "来源期刊", "发表时间",
             "被引次数", "摘要全文", "关键词组", "URL"]
    ws1.append(head1)
    for c in selected:
        ws1.append([
            c.get("sel_rank"),
            txt(c.get("title")),
            authors_str(c.get("authors")),
            txt(c.get("source")),
            txt(c.get("pub_date")),
            c["cited"] if isinstance(c.get("cited"), int) else "未获取",
            txt(c.get("abstract")),
            keywords_str(c.get("keywords")),
            txt(c.get("url")),
        ])
    style_sheet(ws1, [6, 42, 16, 18, 14, 10, 80, 30, 46], {1, 6})
    fit_rows(ws1, 7, 40, 240)
    ws1.sheet_properties.tabColor = "1F4E79"

    # ---------- Sheet2 筛选记录 ----------
    ws2 = wb.create_sheet("筛选记录")
    head2 = ["候选号", "站内序", "检索式", "题名", "来源", "年份",
             "被引", "相关度分", "判定", "排除理由"]
    ws2.append(head2)
    band_cn = {"include": "入选", "reserve": "备选", "exclude": "排除"}
    for c in sorted(cands, key=lambda x: int(x.get("gid") or 0)):
        ws2.append([
            c.get("gid"),
            c.get("site_rank"),
            txt(c.get("query_id"), ""),
            txt(c.get("title")),
            txt(c.get("source")),
            year_of(c),
            c["cited"] if isinstance(c.get("cited"), int) else "未获取",
            c.get("score"),
            band_cn.get(c.get("band"), txt(c.get("band"), "")),
            txt(c.get("exclude_reason"), ""),
        ])
    style_sheet(ws2, [8, 8, 10, 42, 18, 8, 8, 10, 8, 30], {1, 2, 3, 6, 7, 8, 9})
    ws2.sheet_properties.tabColor = "808080"

    # ---------- 下载清单（人工回填） ----------
    wb2 = Workbook()
    ws3 = wb2.active
    ws3.title = "下载清单"
    head3 = ["序号", "题名", "第一作者", "年份", "期刊", "被引",
             "相关度分", "摘要", "是否下载", "备注"]
    ws3.append(head3)
    for c in selected:
        ws3.append([
            c.get("sel_rank"),
            txt(c.get("title")),
            first_author(c),
            year_of(c),
            txt(c.get("source")),
            c["cited"] if isinstance(c.get("cited"), int) else "未获取",
            c.get("score"),
            txt(c.get("abstract")),
            "是",
            "",
        ])
    style_sheet(ws3, [6, 40, 12, 8, 18, 8, 10, 60, 10, 20], {1, 3, 4, 6, 7, 9})
    fit_rows(ws3, 8, 30, 180)
    ws3.sheet_properties.tabColor = "C55A11"
    dv = DataValidation(type="list", formula1='"是,否"', allow_blank=False,
                        showErrorMessage=True, errorTitle="只能填 是/否",
                        error="请选择 是 或 否")
    dv.showDropDown = False  # OOXML 语义：False 才显示下拉箭头
    ws3.add_data_validation(dv)
    dv.add(f"I2:I{ws3.max_row}")

    # ---------- 校验 ----------
    missing = {k: [] for k in ("摘要", "关键词", "作者", "发表时间", "被引")}
    for c in selected:
        if not str(c.get("abstract") or "").strip():
            missing["摘要"].append(c.get("sel_rank"))
        if not c.get("keywords"):
            missing["关键词"].append(c.get("sel_rank"))
        if not c.get("authors"):
            missing["作者"].append(c.get("sel_rank"))
        if not str(c.get("pub_date") or "").strip():
            missing["发表时间"].append(c.get("sel_rank"))
        if not isinstance(c.get("cited"), int):
            missing["被引"].append(c.get("sel_rank"))

    ranks = [c.get("sel_rank") for c in selected]
    seq_ok = ranks == list(range(1, len(selected) + 1))
    dup = len(set(ranks)) != len(ranks)
    conflicts = [c.get("sel_rank") for c in selected if str(c.get("conflict") or "").strip()]
    shortage = top_n - len(selected)

    wb.save(out_xlsx)
    wb2.save(dl_path)

    report_path = Path(args.report) if args.report else out_xlsx.parent / "_基本信息表校验.md"
    lines = [
        "# 文献基本信息表校验", "",
        f"- 生成时间：{now.isoformat(timespec='seconds')}",
        f"- 候选总数：{len(cands)}（入选 {len(selected)} / 备选 "
        f"{sum(1 for c in cands if c.get('band') == 'reserve')} / 排除 "
        f"{sum(1 for c in cands if c.get('band') == 'exclude')}）",
        f"- 目标篇数：{top_n}；实际入选：{len(selected)}"
        + (f"（**缺 {shortage} 篇，未降标准凑数**）" if shortage > 0 else ""),
        f"- 序号 1..N 连续：{'是' if seq_ok else '否'}；重复：{'有' if dup else '无'}",
        f"- 元数据冲突（conflict 非空）：{len(conflicts)}"
        + (f" —— {', '.join(map(str, conflicts))}" if conflicts else ""),
        "", "## 缺失统计（序号）", "",
    ]
    for k, v in missing.items():
        lines.append(f"- {k}：{len(v)}" + (f" —— {', '.join(map(str, v))}" if v else ""))
    lines += [
        "", "## 说明", "",
        "- 被引为空填「未获取」，表示未获取到，**不等于 0 次被引**。",
        "- 摘要与关键词由脚本逐字写入（摘要取详情页隐藏域全文，可超 503 字），未做压缩或改写。",
        "- 下载清单默认全部「是」，人工把不要的改成「否」后回传即可。",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "candidates": len(cands), "selected": len(selected), "target": top_n,
        "shortage": max(0, shortage), "xlsx": str(out_xlsx),
        "download_list": str(dl_path), "report": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
