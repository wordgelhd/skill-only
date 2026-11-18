#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按议题卡片给候选文献打相关度分并初选（纯规则，零 token）。

用法：
    python rank_candidates.py --info-dir <basic_info> --card card.json --top-n 50
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
STOP_TERMS = {
    "研究", "技术", "方法", "分析", "基于", "问题", "视角", "应用", "影响",
    "机制", "路径", "体系", "模型", "文献", "综述", "进展", "探索",
}
WEIGHTS = {"hit": 0.55, "cos": 0.35, "cite": 0.10}
PUNCT = r"[\s\u3000·•\-—–_/、，,。.；;：:（）()\[\]【】\"'“”‘’|]+"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(PUNCT, "", text).lower()


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v for v in re.split(r"[；;、,，]", value) if v.strip()]
    return [str(v) for v in value if str(v).strip()]


def terms_of(*values) -> list[str]:
    out, seen = [], set()
    for v in values:
        for t in as_list(v):
            t = re.sub(r"[（(][^）)]*[）)]", "", str(t))   # 去掉括号注释
            n = norm(t)
            if len(n) < 2 or n in STOP_TERMS or n in seen:
                continue
            seen.add(n)
            out.append(n)
    return out


def cover(terms: list[str], text: str) -> float:
    """命中 1 个词 0.7，命中 2 个及以上 1.0。"""
    if not terms:
        return 0.0
    hits = sum(1 for t in terms if t in text)
    if hits == 0:
        return 0.0
    return 1.0 if hits >= 2 else 0.7


def bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)} if len(text) > 1 else set()


def cosine(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) ** 0.5 * len(b) ** 0.5)


def year_of(item: dict) -> str:
    m = re.search(r"(19|20)\d{2}", str(item.get("pub_date") or item.get("date") or ""))
    return m.group(0) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="候选文献相关度打分与初选")
    ap.add_argument("--info-dir", required=True, help="cand_*.json 所在目录")
    ap.add_argument("--card", required=True, help="议题卡片 JSON")
    ap.add_argument("--top-n", type=int, default=50, help="最终入选篇数，默认 50")
    ap.add_argument("--reserve", type=int, default=15, help="备选条数，默认 15")
    ap.add_argument("--boundary", type=int, default=10, help="边界复核范围 N±k，默认 10")
    ap.add_argument("--min-hit", type=float, default=0.2,
                    help="相关度门槛：议题词命中分低于此值直接排除，默认 0.2")
    ap.add_argument("--out-ranking", default="", help="默认 <info-dir>/_ranking.json")
    args = ap.parse_args()

    info_dir = Path(args.info_dir)
    files = sorted(info_dir.glob("cand_*.json"))
    if not files:
        print(f"no cand_*.json in {info_dir}", file=sys.stderr)
        return 1

    card = json.loads(Path(args.card).read_text(encoding="utf-8"))
    obj_terms = terms_of(card.get("object"), card.get("object_synonyms"))
    topic_terms = terms_of(card.get("topic"), card.get("topic_synonyms"))
    card_grams = bigrams("".join(obj_terms + topic_terms))
    journals = [j for j in as_list(card.get("journals")) if j]
    y_from, y_to = str(card.get("year_from") or ""), str(card.get("year_to") or "")

    items = []
    for f in files:
        it = json.loads(f.read_text(encoding="utf-8"))
        title = norm(it.get("title", ""))
        kws = norm(" ".join(as_list(it.get("keywords"))))
        abstract = norm(it.get("abstract", ""))

        obj_title, topic_title = cover(obj_terms, title), cover(topic_terms, title)
        title_hit = 0.6 * obj_title + 0.4 * topic_title
        kw_hit = 0.6 * cover(obj_terms, kws) + 0.4 * cover(topic_terms, kws)
        abs_hit = 0.6 * cover(obj_terms, abstract) + 0.4 * cover(topic_terms, abstract)
        hit = max(title_hit, 0.8 * kw_hit, 0.5 * abs_hit)

        body_grams = bigrams(title + kws + abstract[:1600])
        cos_raw = cosine(card_grams, body_grams)

        it["_hit"] = round(hit, 4)
        it["_cos"] = cos_raw
        items.append(it)

    max_cos = max((x["_cos"] for x in items), default=0.0) or 1.0

    # 被引：按发表年组内归一；缺失给 0.5（中性）
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(year_of(it), []).append(it)
    for _, group in groups.items():
        nums = [it["cited"] for it in group if isinstance(it.get("cited"), int)]
        lo, hi = (min(nums), max(nums)) if nums else (0, 0)
        for it in group:
            cited = it.get("cited")
            if not isinstance(cited, int) or hi <= lo:
                it["_cite"] = 0.5
            else:
                it["_cite"] = round((cited - lo) / (hi - lo), 4)

    for it in items:
        cos_norm = it["_cos"] / max_cos
        it["score"] = round(
            WEIGHTS["hit"] * it["_hit"]
            + WEIGHTS["cos"] * cos_norm
            + WEIGHTS["cite"] * it["_cite"], 4)
        it["score_detail"] = {
            "hit": it["_hit"], "cos": round(it["_cos"], 6),
            "cos_norm": round(cos_norm, 4), "cite": it["_cite"],
        }

    eligible = [it for it in items if it["_hit"] >= args.min_hit]
    ineligible = [it for it in items if it["_hit"] < args.min_hit]
    eligible.sort(key=lambda x: (-x["score"], -(x.get("cited") or -1),
                                 str(x.get("query_id", "")), int(x.get("site_rank") or 0)))
    ineligible.sort(key=lambda x: -x["_hit"])

    top_n = max(1, args.top_n)
    for idx, it in enumerate(eligible, start=1):
        it["_rank"] = idx
        if idx <= top_n:
            it["band"], it["selected"], it["sel_rank"] = "include", True, idx
            it["exclude_reason"] = ""
        elif idx <= top_n + max(0, args.reserve):
            it["band"], it["selected"], it["sel_rank"] = "reserve", False, None
            it["exclude_reason"] = f"备选（第 {idx} 名）"
        else:
            it["band"], it["selected"], it["sel_rank"] = "exclude", False, None
        if not it["selected"] and not it.get("exclude_reason"):
            y = year_of(it)
            if y_from and y_to and y and not (y_from <= y <= y_to):
                it["exclude_reason"] = f"年份超出范围（{y}）"
            elif journals and not any(j in str(it.get("source", "")) for j in journals):
                it["exclude_reason"] = "期刊不在范围"
            else:
                it["exclude_reason"] = f"相关度排名第 {idx}（目标前 {top_n}）"

    for offset, it in enumerate(ineligible, start=len(eligible) + 1):
        it.update(_rank=offset, band="exclude", selected=False, sel_rank=None,
                  exclude_reason=f"未达相关度门槛（议题词命中 {it['_hit']:.2f} < {args.min_hit}）")

    selected_count = sum(1 for it in items if it["selected"])

    # 按 gid 回写（文件名与 gid 一一对应，避免顺序错位）
    by_gid = {int(it["gid"]): it for it in items if it.get("gid") is not None}
    for f in files:
        try:
            gid = int(f.stem.split("_")[-1])
        except ValueError:
            continue
        it = by_gid.get(gid)
        if not it:
            continue
        clean = {k: v for k, v in it.items() if not k.startswith("_")}
        f.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")

    lo, hi = max(1, top_n - args.boundary), top_n + args.boundary
    boundary = [it for it in items if lo <= it["_rank"] <= hi]
    boundary.sort(key=lambda x: x["_rank"])
    payload = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "weights": WEIGHTS,
        "min_hit": args.min_hit,
        "top_n": top_n,
        "total": len(items),
        "eligible": len(eligible),
        "selected": selected_count,
        "reserve": sum(1 for it in items if it["band"] == "reserve"),
        "excluded": sum(1 for it in items if it["band"] == "exclude"),
        "shortage": max(0, top_n - selected_count),
        "boundary": [
            {"rank": it["_rank"], "gid": it.get("gid"), "score": it["score"],
             "band": it["band"], "title": str(it.get("title", ""))[:60]}
            for it in boundary
        ],
    }
    out = Path(args.out_ranking) if args.out_ranking else info_dir / "_ranking.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "boundary"},
                     ensure_ascii=False))
    for row in payload["boundary"]:
        print(f'  {row["rank"]:>3} {row["band"]:<7} {row["score"]:.3f} '
              f'#{row["gid"]} {row["title"]}')
    if payload["shortage"]:
        print(f'shortage: 仅 {selected_count} 篇达到相关度门槛，不足目标 {top_n} 篇', file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
