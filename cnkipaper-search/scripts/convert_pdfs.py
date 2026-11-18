#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用 markitdown 批量把 PDF 转为 Markdown（同名 .md），附 manifest 与校验报告。

用法：
    python convert_pdfs.py --pdf-dir 05_pdf --md-dir 06_markdown
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))


def main() -> int:
    ap = argparse.ArgumentParser(description="markitdown 批量 PDF → Markdown")
    ap.add_argument("--pdf-dir", required=True, help="PDF 目录")
    ap.add_argument("--md-dir", required=True, help="Markdown 输出目录")
    ap.add_argument("--overwrite", action="store_true", help="覆盖已存在的 .md")
    ap.add_argument("--manifest", default="", help="默认 <md-dir>/manifest.json")
    ap.add_argument("--min-chars", type=int, default=2000, help="低于此字符数告警，默认 2000")
    args = ap.parse_args()

    pdf_dir, md_dir = Path(args.pdf_dir), Path(args.md_dir)
    if not pdf_dir.is_dir():
        print(f"pdf dir not found: {pdf_dir}", file=sys.stderr)
        return 1
    md_dir.mkdir(parents=True, exist_ok=True)

    try:
        from markitdown import MarkItDown
    except ImportError:
        print("markitdown 未安装。请先执行：\n"
              '  pip install "markitdown[pdf]" -i https://pypi.tuna.tsinghua.edu.cn/simple',
              file=sys.stderr)
        return 2

    pdfs = sorted(p for p in pdf_dir.iterdir()
                  if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"no pdf in {pdf_dir}", file=sys.stderr)
        return 1

    conv = MarkItDown()
    records, failures, short = [], [], []
    done = skipped = 0

    for pdf in pdfs:
        out = md_dir / f"{pdf.stem}.md"
        rec = {"source": str(pdf), "output": str(out), "chars": 0,
               "seconds": 0.0, "status": "ok", "error": ""}
        if out.exists() and not args.overwrite:
            rec["status"] = "skipped"
            rec["chars"] = len(out.read_text(encoding="utf-8", errors="ignore"))
            if rec["chars"] < args.min_chars:
                short.append({"file": pdf.name, "chars": rec["chars"]})
            records.append(rec)
            skipped += 1
            continue

        with open(pdf, "rb") as fh:
            if fh.read(4) != b"%PDF":
                rec.update(status="failed", error="not_pdf")
                failures.append(rec)
                records.append(rec)
                continue

        started = time.monotonic()
        try:
            try:
                result = conv.convert_local(pdf)
            except AttributeError:          # 兼容 0.0.x
                result = conv.convert(str(pdf))
            text = getattr(result, "markdown", None) or getattr(result, "text_content", "") or ""
            out.write_text(text, encoding="utf-8")
            rec.update(chars=len(text), seconds=round(time.monotonic() - started, 2))
            if rec["chars"] < args.min_chars:
                short.append({"file": pdf.name, "chars": rec["chars"]})
            done += 1
        except Exception as exc:            # noqa: BLE001 - 逐篇隔离失败
            rec.update(status="failed", error=f"{type(exc).__name__}: {exc}",
                       seconds=round(time.monotonic() - started, 2))
            failures.append(rec)
        records.append(rec)

    chars = [r["chars"] for r in records if r["status"] in ("ok", "skipped") and r["chars"]]
    manifest_path = Path(args.manifest) if args.manifest else md_dir / "manifest.json"
    manifest = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "engine": "markitdown",
        "pdf_dir": str(pdf_dir),
        "md_dir": str(md_dir),
        "total": len(pdfs), "converted": done, "skipped": skipped,
        "failed": len(failures), "short": len(short),
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [
        "# Markdown 转换校验", "",
        f"- 生成时间：{manifest['generated_at']}",
        f"- 引擎：markitdown",
        f"- PDF 总数：{len(pdfs)}；新转换：{done}；跳过已存在：{skipped}；失败：{len(failures)}",
        f"- 字符数：min {min(chars) if chars else 0} / median "
        f"{int(statistics.median(chars)) if chars else 0} / max {max(chars) if chars else 0}",
        f"- 低于 {args.min_chars} 字符：{len(short)}",
        "", "## 短文本告警", "",
    ]
    lines += [f"- {x['file']}（{x['chars']} 字）" for x in short] or ["- 无"]
    lines += ["", "## 失败明细", ""]
    lines += [f"- {Path(x['source']).name}：{x['error']}" for x in failures] or ["- 无"]
    lines += ["", "> 短文本通常意味扫描版或双栏解析不佳；不自动回退其他解析器，必要时改用 PyMuPDF 重转。"]
    (md_dir / "_转换校验.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "total": len(pdfs), "converted": done, "skipped": skipped,
        "failed": len(failures), "short": len(short),
        "md_dir": str(md_dir), "manifest": str(manifest_path),
    }, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
