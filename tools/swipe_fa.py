#!/usr/bin/env python3
"""
swipe_fa.py — رتبه‌بندی ریلزهای جمع‌شده بر اساس اینکه هر کدام چقدر از
میانه‌ی خود همان صفحه جلو زده، نام‌گذاری فرمول هوک هر کدام، و ساخت فایل سوایپ.

ایرانی‌سازی از swipe.py در ریپوی instagram-agent-skill (MIT).
نکته‌ی اصلی ابزار یک اصلاح است: بازدید خام مدرک نیست. صفحه‌ی ۲ میلیونی با
۴۰۰ هزار بازدید یک روز معمولی داشته؛ صفحه‌ی ۴ هزارتایی با همان بازدید چیزی
پیدا کرده. رتبه‌بندی روی «ضربِ» معیار نسبت به خط مبنای خود صفحه است.

ورودی یک فایل TSV است که هنگام مرور ریلزها پرش می‌کنی؛ هر سطر یک ریلز:
    account   followers   median   views    hook
median یعنی بازدید معمول اخیر همان صفحه؛ مبنای بهتر. اگر فقط followers
داری، median را خالی بگذار و ابزار می‌گوید مبنا چیست. ستون views می‌تواند
بازدید باشد یا — چون پلتفرم بازدید عمومی نمی‌دهد — پسند؛ فقط در کل فایل
یک معیار را نگه دار و در خروجی همان خوانده می‌شود.

استفاده:
  python3 swipe_fa.py captured.tsv
  python3 swipe_fa.py captured.tsv --out swipe.md
  python3 swipe_fa.py captured.tsv --json
"""

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS_FA = os.path.join(HERE, "..", "hooks-fa.json")
sys.path.insert(0, HERE)
try:
    from hookscore_fa import run as score_hook, words as fa_words
except Exception:
    score_hook, fa_words = None, None


def load_formulas(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    by_id = {h["id"]: h for h in d["hooks"]}
    order = d.get("classify_order") or sorted(by_id)
    return [(by_id[i]["id"], by_id[i]["name_fa"],
             re.compile(by_id[i]["match_fa"])) for i in order if i in by_id]


def classify(hook, formulas):
    if not formulas:
        return None, "نامشخص"
    for fid, name, pattern in formulas:
        if pattern.search(hook):
            return fid, name
    return None, "نامشخص"


def read_rows(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    lines = [l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    head = [c.strip().lower() for c in lines[0].split("\t")]
    if "views" in head and "hook" in head:
        cols, body = head, lines[1:]
    else:
        # بدون هدر: ستون‌ها را از تعداد سلول‌های سطر اول حدس بزن تا فایل
        # پنج‌ستونی (account followers median views hook) با داکیومنت بخواند.
        ncols = len(lines[0].split("\t"))
        cols = (["account", "followers", "median", "views", "hook"] if ncols >= 5
                else ["account", "followers", "views", "hook"])
        body = lines
    rows = []
    for line in body:
        cells = line.split("\t")
        if len(cells) < len(cols):
            cells += [""] * (len(cols) - len(cells))
        r = dict(zip(cols, [c.strip() for c in cells]))
        try:
            r["views"] = int(re.sub(r"[^\d]", "", r.get("views", "")) or 0)
        except ValueError:
            continue
        for k in ("followers", "median"):
            digits = re.sub(r"[^\d]", "", r.get(k, "") or "")
            r[k] = int(digits) if digits else None
        if r["views"] and r.get("hook"):
            rows.append(r)
    return rows


def analyse(rows, formulas):
    used_median = any(r.get("median") for r in rows)
    for r in rows:
        base = r.get("median") or r.get("followers") or 0
        r["baseline"] = base
        r["outlier"] = round(r["views"] / base, 2) if base else None
        r["formula_id"], r["formula"] = classify(r["hook"], formulas)
        r["words"] = len(fa_words(r["hook"])) if fa_words else 0
        if score_hook:
            _, overall, verdict, _ = score_hook(r["hook"])
            r["hook_score"], r["hook_verdict"] = round(overall, 1), verdict
        else:
            r["hook_score"], r["hook_verdict"] = None, None
    ranked = sorted(rows, key=lambda r: -(r["outlier"] or 0))
    third = max(1, len(ranked) // 3)
    top, bottom = ranked[:third], ranked[-third:]

    def med(items, key):
        vals = [i[key] for i in items if i.get(key) is not None]
        return round(statistics.median(vals), 1) if vals else None

    counts = {}
    for r in top:
        counts[r["formula"]] = counts.get(r["formula"], 0) + 1
    return {
        "baseline": "میانه‌ی خود صفحه" if used_median else "تعداد دنبال‌کننده",
        "n": len(ranked),
        "accounts": len({r.get("account", "") for r in ranked}),
        "reels": ranked,
        "top_formulas": sorted(counts.items(), key=lambda kv: -kv[1]),
        "top_hook_score": med(top, "hook_score"),
        "bottom_hook_score": med(bottom, "hook_score"),
        "top_words": med(top, "words"),
        "bottom_words": med(bottom, "words"),
        "unclassified": sum(1 for r in ranked if r["formula"] == "نامشخص"),
    }


def render(a, out=sys.stdout):
    head = (f"فایل سوایپ · {a['n']} ریلز · {a['accounts']} صفحه · مبنا: {a['baseline']}")
    print("\n" + head, file=out)
    print("=" * 78, file=out)
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "   ?"
        score = f"{r['hook_score']:.0f}" if r["hook_score"] is not None else " -"
        fid = f"#{r['formula_id']:<2}" if r["formula_id"] else "-  "
        print(f"  {mult:>7}  هوک {score:>3}  {fid} {r['formula'][:22]:<22} "
              f"{r.get('account', '')[:16]:<16} {r['views']:>9,}", file=out)
        print(f"           «{r['hook'][:96]}»", file=out)
    print("-" * 78, file=out)
    print("در این دسته چه چیزی جواب داده:", file=out)
    if a["top_formulas"]:
        print("  یک‌سوم بالایی بر اساس ضرب:  "
              + "، ".join(f"{n} ×{c}" for n, c in a["top_formulas"][:4]), file=out)
    if a["top_hook_score"] is not None:
        print(f"  میانه‌ی امتیاز هوک:      بالا {a['top_hook_score']:.0f} در برابر پایین {a['bottom_hook_score']:.0f}", file=out)
    print(f"  میانه‌ی طول هوک:         بالا {a['top_words']} کلمه در برابر پایین {a['bottom_words']} کلمه", file=out)
    print(f"  نامشخص:                  {a['unclassified']} از {a['n']}؛ همان‌ها را دستی بخوان، فرمولی که هنوز نداری همان‌جا پنهان است.", file=out)
    print("\n  دسته‌ی دستی مدرک است نه اثبات. ۱۲ ریلز چیزی نشان نمی‌دهد؛"
          "\n  ۴۰ ریلز از ۶ صفحه چیزی نشان می‌دهد. قبل از باورکردن، بیشتر جمع کن.\n", file=out)


def to_markdown(a):
    lines = ["# فایل سوایپ", "",
             f"{a['n']} ریلز از {a['accounts']} صفحه؛ رتبه‌بندی بر اساس ضرب نسبت به {a['baseline']}.", ""]
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "?"
        lines += [f"## {mult} — {r['formula']} ({r.get('account', '')})",
                  f"- معیار: {r['views']:,} · مبنا: {r['baseline']:,}",
                  f"- امتیاز هوک: {r['hook_score']} · کلمه: {r['words']}",
                  f"- هوک: «{r['hook']}»", ""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="رتبه‌بندی ریلزهای جمع‌شده بر اساس ضرب خروجی.")
    ap.add_argument("input", nargs="?", default="-", help="فایل TSV، یا -")
    ap.add_argument("--hooks", default=HOOKS_FA, help="مسیر hooks-fa.json")
    ap.add_argument("--out", help="فایل سوایپ را هم به‌صورت مارک‌داون این‌جا بنویس")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = read_rows(args.input)
    if not rows:
        print("سطر قابل استفاده‌ای نیست. فایل TSV با حداقل ستون‌های views و hook لازم است.", file=sys.stderr)
        sys.exit(2)
    formulas = load_formulas(args.hooks)
    a = analyse(rows, formulas)
    if not formulas:
        print("نکته: hooks-fa.json پیدا نشد؛ فرمول‌ها نام‌گذاری نمی‌شوند.", file=sys.stderr)

    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    if args.out:
        path = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        open(path, "w", encoding="utf-8").write(to_markdown(a))
        print(f"نوشته شد: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
