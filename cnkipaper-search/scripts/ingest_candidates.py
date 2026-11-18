#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检索结果 / 摘要批次 → cand_{gid:03d}.json（统一字段映射与去重）。

用法：
    python ingest_candidates.py search --info-dir DIR --query-id Q1 --input raw/Q1.json
    python ingest_candidates.py abstracts --info-dir DIR --input raw/abs_01.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
BADGES = re.compile(r"网络首发|免费|增强出版|优先出版")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", BADGES.sub("", str(text or "")))
    return re.sub(r"[\s\u3000]+", "", text).lower()


def parse_cited(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def first_author(authors) -> str:
    if isinstance(authors, list) and authors:
        return str(authors[0]).strip()
    return ""


def year_of(date_str: str) -> str:
    m = re.search(r"(19|20)\d{2}", str(date_str or ""))
    return m.group(0) if m else ""


def load_items(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:            # JSONL
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data["results"] if isinstance(data.get("results"), list) else [data]
    return []


def clean_title(text: str) -> str:
    title = BADGES.sub("", str(text or ""))
    title = re.sub(r"[（(]\s*[）)]", "", title)
    return re.sub(r"\s{2,}", " ", title).strip()


def next_gid(info_dir: Path) -> int:
    gids = []
    for f in info_dir.glob("cand_*.json"):
        try:
            gids.append(int(f.stem.split("_")[-1]))
        except ValueError:
            continue
    return max(gids, default=0) + 1


def cmd_search(args) -> int:
    info_dir = Path(args.info_dir)
    info_dir.mkdir(parents=True, exist_ok=True)
    items = load_items(Path(args.input))
    if not items:
        print("input 为空", file=sys.stderr)
        return 1

    existing = {}
    for f in info_dir.glob("cand_*.json"):
        it = json.loads(f.read_text(encoding="utf-8"))
        key = (norm(it.get("title")), first_author(it.get("authors")), year_of(it.get("pub_date")))
        existing[key] = it.get("gid")

    gid, added, dups = next_gid(info_dir), 0, []
    for idx, it in enumerate(items, start=1):
        title = clean_title(it.get("title"))
        if not title:
            continue
        key = (norm(title), first_author(it.get("authors")), year_of(it.get("date")))
        if key in existing:
            dups.append({"title": title[:50], "gid": existing[key]})
            continue
        rec = {
            "gid": gid, "query_id": args.query_id, "site_rank": idx,
            "title": title, "authors": it.get("authors") or [],
            "source": str(it.get("source") or "").strip(),
            "pub_date": str(it.get("date") or "").strip(),
            "cited": parse_cited(it.get("citation_count")),
            "abstract": "", "keywords": [], "url": str(it.get("url") or "").strip(),
            "fetched_at": datetime.now(CST).isoformat(timespec="seconds"),
        }
        (info_dir / f"cand_{gid:03d}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        existing[key] = gid
        gid += 1
        added += 1

    print(json.dumps({"added": added, "duplicates": len(dups), "next_gid": gid,
                      "dup_titles": [d["title"] for d in dups[:8]]}, ensure_ascii=False))
    return 0


def cmd_abstracts(args) -> int:
    info_dir = Path(args.info_dir)
    items = load_items(Path(args.input))
    updated = missing = 0
    conflicts = []
    for it in items:
        try:
            gid = int(it.get("gid"))
        except (TypeError, ValueError):
            missing += 1
            continue
        f = info_dir / f"cand_{gid:03d}.json"
        if not f.exists():
            missing += 1
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        notes = []
        if it.get("abstract"):
            rec["abstract"] = str(it["abstract"]).strip()
        if it.get("keywords"):
            rec["keywords"] = [str(k).strip() for k in it["keywords"] if str(k).strip()]
        if it.get("authors"):
            authors = [str(a).strip() for a in it["authors"] if str(a).strip()]
            if rec.get("authors") and authors and rec["authors"] != authors:
                notes.append("authors: 检索行与详情页不一致，保留检索行")
            elif authors and not rec.get("authors"):
                rec["authors"] = authors
        if notes:
            rec["conflict"] = "；".join(notes)
            conflicts.append(gid)
        rec["fetched_at"] = datetime.now(CST).isoformat(timespec="seconds")
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        updated += 1

    print(json.dumps({"updated": updated, "missing_gid": missing,
                      "conflicts": conflicts}, ensure_ascii=False))
    return 0 if not missing else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="检索/摘要入库")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("search", help="检索结果 → 新建候选 JSON")
    p1.add_argument("--info-dir", required=True)
    p1.add_argument("--query-id", required=True)
    p1.add_argument("--input", required=True, help="工具返回的 results（JSON 数组或含 results 的对象）")
    p1.set_defaults(func=cmd_search)

    p2 = sub.add_parser("abstracts", help="摘要批次 → 合并进候选 JSON")
    p2.add_argument("--info-dir", required=True)
    p2.add_argument("--input", required=True, help="JSONL/JSON 数组：[{gid,abstract,keywords,authors}]")
    p2.set_defaults(func=cmd_abstracts)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
