#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""摘要抓取（零 token）：直连 cnki_mcp 的浏览器，摘要原文不进模型上下文。

用 `{PYC}`（装 cnki_mcp 的那个解释器，见 SKILL.md 解释器约定）跑，default venv 里没有该包：
    {PYC} scripts/fetch_abstracts.py --info-dir <basic_info> --out <raw/abs_all.jsonl>

流程：
  1) 有 URL → get_page_html(url) → parse_article_detail
  2) 立刻从 <input id="abstract_text" value="..."> 取全文（详情页 .abstract 只渲染 503 字）
  3) 抓不到/标题不匹配 → search_simple(field=TI) 拿新 URL 再抓，题名按 ——／： 逐级截短
  4) 逐条 append + flush + fsync，按 gid 断点续跑

输出每行：{gid, title, abstract, keywords, method, char_len}
（`authors` 恒为空数组：详情页作者选择器会抓到 UI 链接与单位，作者一律沿用检索结果行）
可直接喂给现有命令合并（无需改动 ingest_candidates.py）：
    {PY} scripts/ingest_candidates.py abstracts --info-dir <basic_info> --input <raw/abs_all.jsonl>
"""
from __future__ import annotations

import argparse
import asyncio
import html as htmllib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from cnki_mcp.browser import CNKIBrowser, SearchConfig
    from cnki_mcp.parser import parse_article_detail, parse_search_results
except ImportError as exc:  # noqa: BLE001
    print(json.dumps({
        "error": f"import cnki_mcp 失败：{exc}",
        "used_interpreter": sys.executable,
        "hint": "本脚本依赖 cnki-deepsearch 包，请改用 SKILL.md 解释器约定里的 "
                "{PYC}（本机为 cnki-deepsearch venv；便携版为技能目录下的 .venv）",
    }, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(2)

CST = timezone(timedelta(hours=8))
BADGES = re.compile(r"网络首发|免费|增强出版|优先出版")
ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
VERIFY_HINT = ("安全验证", "验证码", "captcha", "/verify")


def norm_title(text: str) -> str:
    s = unicodedata.normalize("NFKC", BADGES.sub("", str(text or "")))
    s = ZERO_WIDTH.sub("", s)
    return re.sub(r"[\s\u3000]+", "", s).lower()


def clean_abstract(raw: str) -> str:
    s = htmllib.unescape(str(raw or ""))
    s = ZERO_WIDTH.sub("", s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    return re.sub(r"^(摘要|摘\s*要)\s*[:：]\s*", "", s).strip()


def full_from_html(html: str, trunc: str) -> str:
    """全文藏在 <input id="abstract_text" value="...">；退路是长 content 属性。"""
    m = re.search(r'id="abstract_text"[^>]*value="([^"]+)"', html)
    if m:
        cand = clean_abstract(m.group(1))
        if len(cand) > len(trunc):
            return cand
    key = norm_title(trunc)[:36]
    best = ""
    for raw in re.findall(r'content="([^"]{180,8000})"', html):
        cand = clean_abstract(raw)
        if key and key in norm_title(cand) and len(cand) > len(best):
            best = cand
    return best


def clean_keywords(raw) -> list[str]:
    """详情页的关键词链接会带尾随分号，也可能混进导航项，这里统一清洗。"""
    out: list[str] = []
    for item in raw or []:
        s = re.sub(r"\s+", " ", str(item).strip().strip(" \t;；,，、"))
        if s and len(s) <= 30 and s not in out:
            out.append(s)
    return out


def title_matches(detail_title: str, target: str) -> bool:
    a, b = norm_title(detail_title), norm_title(target)
    if not a or not b:
        return False
    if b in a or a in b:
        return True
    return b[: max(12, len(b) - 6)] in a


def title_variants(title: str) -> list[str]:
    out = [title]
    main = re.split(r"——|—{1,2}|\s{2,}", title)[0].strip()
    if main and main != title:
        out.append(main)
    colon = re.split(r"[:：]", main)[0].strip()
    if colon and colon not in out:
        out.append(colon)
    return out


def looks_blocked(html: str) -> bool:
    head = str(html or "")[:4000]
    return any(k in head for k in VERIFY_HINT)


def load_done(out_path: Path, force: bool) -> set[int]:
    done: set[int] = set()
    if force or not out_path.exists():
        return done
    for line in out_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(rec.get("abstract") or "").strip():
            try:
                done.add(int(rec.get("gid")))
            except (TypeError, ValueError):
                continue
    return done


def append(out_path: Path, rec: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def log(msg: str) -> None:
    print(f"[{datetime.now(CST).strftime('%H:%M:%S')}] {msg}", flush=True)


async def detail_of(br: CNKIBrowser, url: str, title: str) -> tuple[dict | None, bool]:
    """抓一个详情页，返回 (detail, 是否触发截断修复)。"""
    html = await br.get_page_html(url)
    if looks_blocked(html):
        raise RuntimeError("CNKI 需要安全验证（headless 无法通过），请改用 --headed")
    detail = parse_article_detail(html)
    if not detail.get("abstract"):
        return None, False
    if not title_matches(detail.get("title", ""), title):
        return None, False
    trunc = clean_abstract(detail.get("abstract", ""))
    full = full_from_html(html, trunc)
    if full and len(full) > len(trunc):
        detail["abstract"] = full
        return detail, True
    detail["abstract"] = trunc
    return detail, False


async def fetch_one(br: CNKIBrowser, item: dict, state: dict) -> dict | None:
    title = item["title"]
    url = (item.get("url") or "").strip()
    if state.get("url_broken"):
        url = ""

    if url:
        try:
            detail, fixed = await detail_of(br, url, title)
            if detail:
                return {"detail": detail, "url": url, "method": "url", "trunc_fixed": fixed}
            log(f"  URL 未命中，转篇名检索：{title[:34]}")
        except Exception as exc:  # noqa: BLE001
            if "安全验证" in str(exc):
                raise
            msg = str(exc)
            is_timeout = "Timeout" in type(exc).__name__ or "Timeout" in msg or "超时" in msg
            state["url_fail"] = state.get("url_fail", 0) + 1
            if (is_timeout or state["url_fail"] >= 3) and not state.get("url_broken"):
                state["url_broken"] = True
                log("  ※ 旧链接已失效（验证页/超时），本轮后续直接走篇名检索；"
                    "续跑时加 --skip-url 可省掉这段等待")
            log(f"  URL 异常 {type(exc).__name__}: {msg[:90]}")

    hits: list = []
    for q in title_variants(title):
        try:
            merged, _ = await br.search_simple(query=q, field="TI", max_results=3)
            hits = parse_search_results(merged)
        except Exception as exc:  # noqa: BLE001
            if "安全验证" in str(exc):
                raise
            log(f"  篇名检索失败（{q[:18]}）{type(exc).__name__}: {str(exc)[:80]}")
            continue
        if any(title_matches(h.get("title", ""), title) for h in hits):
            break
    if not hits:
        return None
    best = next((h for h in hits if title_matches(h.get("title", ""), title)), None)
    if not best:
        log(f"  篇名检索无匹配（{len(hits)} 条）")
        return None
    try:
        detail, fixed = await detail_of(br, best["url"], title)
    except Exception as exc:  # noqa: BLE001
        if "安全验证" in str(exc):
            raise
        log(f"  详情页异常 {type(exc).__name__}: {str(exc)[:90]}")
        return None
    if not detail:
        log(f"  详情页无摘要：{title[:34]}")
        return None
    return {"detail": detail, "url": best["url"], "method": "title_search", "trunc_fixed": fixed}


async def run(args) -> int:
    info_dir = Path(args.info_dir)
    cands = []
    for f in sorted(info_dir.glob("cand_*.json")):
        try:
            cands.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            log(f"跳过损坏 JSON：{f.name}")
    if not cands:
        print(json.dumps({"error": f"no cand_*.json in {info_dir}"}, ensure_ascii=False), file=sys.stderr)
        return 1
    cands.sort(key=lambda x: int(x.get("gid") or 0))

    out_path = Path(args.out)
    done = load_done(out_path, args.force)
    if not args.force:
        # 候选里已有摘要的也视为已完成，避免整轮重抓（老数据若被 503 截断，用 --force 重取）
        done |= {int(c.get("gid") or 0) for c in cands if str(c.get("abstract") or "").strip()}
    pending = [c for c in cands if int(c.get("gid") or 0) not in done]
    log(f"候选 {len(cands)} / 已抓 {len(done)} / 待抓 {len(pending)}")
    if args.limit and args.limit > 0:
        pending = pending[: args.limit]
    if not pending:
        print(json.dumps({"ok": 0, "failed": 0, "pending": 0, "note": "无需抓取"}, ensure_ascii=False))
        return 0

    config = SearchConfig(headless=not args.headed)
    if args.channel:
        config.browser_channel = args.channel
    br = CNKIBrowser(config)
    await br.start(headed=args.headed)

    ok = failed = fixed_cnt = suspect = 0
    consec = 0
    state: dict = {"url_broken": bool(args.skip_url)}
    if args.skip_url:
        log("--skip-url：直接走篇名检索，不使用候选里的旧链接")
    try:
        for i, item in enumerate(pending, 1):
            gid = item.get("gid")
            log(f"[{i}/{len(pending)}] gid={gid} {str(item.get('title'))[:46]}")
            res = None
            try:
                res = await fetch_one(br, item, state)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001
                if "安全验证" in str(exc):
                    log("  ✗ 需要安全验证：请停在本步，按提示改用 --headed 重跑")
                    append(out_path, {"gid": gid, "title": item.get("title"), "abstract": "",
                                      "keywords": [], "authors": [], "method": "blocked",
                                      "char_len": 0, "at": datetime.now(CST).isoformat(timespec="seconds")})
                    break
                log(f"  失败 {type(exc).__name__}: {str(exc)[:110]}")

            if res is None:
                for attempt in (1, 2):
                    await asyncio.sleep(10 * attempt)
                    log(f"  退避后重试（第 {attempt} 次）")
                    try:
                        res = await fetch_one(br, item, state)
                    except Exception:  # noqa: BLE001
                        res = None
                    if res:
                        break

            if res:
                detail = res["detail"]
                abs_ = clean_abstract(detail.get("abstract", ""))
                rec = {
                    "gid": gid,
                    "title": item.get("title"),
                    "abstract": abs_,
                    "keywords": clean_keywords(detail.get("keywords")),
                    # 详情页的作者选择器会抓到「作者发文检索」「我是作者，免费下载」等 UI 链接与单位，
                    # 不可信；作者一律沿用检索结果行（硬规则 1），此处留空让 ingest 跳过。
                    "authors": [],
                    "method": res["method"],
                    "char_len": len(abs_),
                }
                append(out_path, rec)
                ok += 1
                consec = 0
                fixed_cnt += 1 if res.get("trunc_fixed") else 0
                if len(abs_) < 120:
                    suspect += 1
                flag = "（超 503 已补全）" if res.get("trunc_fixed") else ""
                log(f"  OK {len(abs_)} 字 / kw {len(rec['keywords'])} / {res['method']} {flag}")
            else:
                append(out_path, {"gid": gid, "title": item.get("title"), "abstract": "",
                                  "keywords": [], "authors": [], "method": "failed", "char_len": 0})
                failed += 1
                consec += 1
                log("  FAIL 未取到摘要")
                if args.max_fail and consec >= args.max_fail:
                    log(f"  ✗ 连续 {consec} 篇失败，停止本轮（检查登录态后重跑，已抓的会跳过）")
                    break

            await asyncio.sleep(args.delay)
            if args.throttle and i % args.throttle[0] == 0:
                log(f"  -- 节流 {args.throttle[1]}s --")
                await asyncio.sleep(args.throttle[1])
    finally:
        await br.stop()

    summary = {"ok": ok, "failed": failed, "skipped_done": len(done), "trunc_fixed": fixed_cnt,
               "suspect_short": suspect, "out": str(out_path)}
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if failed == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="直连 cnki_mcp 抓摘要（零 token，含 503 字截断修复）")
    ap.add_argument("--info-dir", required=True, help="cand_*.json 所在目录")
    ap.add_argument("--out", required=True, help="摘要 jsonl 输出路径（同时作为断点缓存）")
    ap.add_argument("--limit", type=int, default=0, help="本次最多抓多少篇，0=全部")
    ap.add_argument("--force", action="store_true", help="已有摘要也重抓")
    ap.add_argument("--headed", action="store_true", help="有头模式，便于人工过安全验证")
    ap.add_argument("--skip-url", action="store_true",
                    help="跳过候选里的旧链接，直接篇名检索（续跑或链接普遍过期时用，省掉每篇 120s 等待）")
    ap.add_argument("--channel", default="", help="浏览器通道，默认沿用 msedge；可填 chromium")
    ap.add_argument("--delay", type=float, default=1.2, help="每篇间隔秒")
    ap.add_argument("--throttle", default="10:8", help="每 N 篇停 M 秒，格式 N:M，0:0 关闭")
    ap.add_argument("--max-fail", type=int, default=5, help="连续失败多少篇后停止，0=不限制")
    args = ap.parse_args()
    try:
        a, b = str(args.throttle).split(":")
        args.throttle = (int(a), int(b))
    except ValueError:
        args.throttle = (0, 0)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
