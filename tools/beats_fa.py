#!/usr/bin/env python3
"""
beats_fa.py — تبدیل اسکریپت فارسی ریلز به بیت‌شیت زمان‌دار، قبل از فیلم‌برداری.

ایرانی‌سازی از beats.py در ریپوی instagram-agent-skill (MIT).
تخمین می‌زند هر خط چقدر طول می‌کشد گفته شود، تایم‌کد می‌سازد و چهار چیزی را
که ریلز را در تدوین می‌کشد علامت می‌زند: هوکی که از سه ثانیه رد شود، بیتی
آن‌قدر طولانی که بیننده برود، چند خط پشت سر هم بدون هیچ چیز مشخص، و لوپ‌نداشتن
خط آخر به خط اول.

نرخ پیش‌فرض فارسی ۱۳۰ کلمه در دقیقه است؛ تخمین است، نه جای ضبط واقعی.
یک بار اسکریپت را با صدای بلند بخوان و زمان بگیر، بعد با --wpm نرخ خودت را بده.

استفاده:
  python3 beats_fa.py script.txt
  python3 beats_fa.py script.txt --target 15
  python3 beats_fa.py script.txt --wpm 145 --target 30
  python3 beats_fa.py script.txt --json
"""

import argparse
import json
import re
import sys

DIGITS = "0-9۰-۹٠-٩"
CONCRETE_RE = re.compile(
    rf"[{DIGITS}]|درصد|تومان|میلیون|هزار|\b[A-Z][a-zA-Z]{{2,}}\b|"
    r"گوگل|متا|یوتیوب|تلگرام|کپکات|جمینای|"
    r"\b(?:دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|پانزده|بیست|سی|پنجاه|صد)\b"
)
SENT_RE = re.compile(r"[^.!؟?]+[.!؟?]*")
STOPWORDS = {
    "و", "یا", "که", "از", "به", "در", "این", "اون", "رو", "را", "با",
    "برای", "تا", "هم", "یه", "است", "هست", "من", "تو", "او", "ما",
    "شما", "یه", "چی", "چه",
}

HOOK_WINDOW = 3.0   # ثانیه؛ بعد از این شست تصمیمش را گرفته است.
MAX_BEAT = 4.0      # ثانیه روی یک ایده بدون تغییر روی تصویر.
ABSTRACT_RUN = 3    # بیت پشت سر هم بدون هیچ چیز قابل چک.


def normalize(text):
    return text.replace("ي", "ی").replace("ك", "ک").replace("ـ", "")


def words(text):
    t = normalize(text).replace("‌", "")
    toks = re.findall(r"[^\s،؛؟?!.,:«»\"'()\[\]{}…]+", t)
    return [x for x in toks if x.strip()]


def tc(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def split_beats(raw, wps):
    """هر خط یک بیت است، مگر خطی آن‌قدر طولانی باشد که یک بیت نباشد."""
    beats = []
    for line in [l.strip() for l in raw.splitlines()]:
        if not line:
            continue
        if len(words(line)) / wps <= MAX_BEAT * 1.5:
            beats.append(line)
            continue
        parts = [p.strip() for p in SENT_RE.findall(line) if p.strip()]
        buf = ""
        for part in parts:
            candidate = (buf + " " + part).strip()
            if buf and len(words(candidate)) / wps > MAX_BEAT:
                beats.append(buf)
                buf = part
            else:
                buf = candidate
        if buf:
            beats.append(buf)
    return beats


def analyse(raw, wpm=130, target=None):
    wps = wpm / 60.0
    beats = split_beats(raw, wps)
    if not beats:
        return None

    rows, clock = [], 0.0
    for i, text in enumerate(beats):
        n = len(words(text))
        dur = n / wps
        rows.append({
            "n": i + 1,
            "start": round(clock, 2),
            "dur": round(dur, 2),
            "words": n,
            "text": text,
            "concrete": len(CONCRETE_RE.findall(normalize(text))),
            "label": "",
            "flags": [],
        })
        clock += dur
    total = clock

    for r in rows:
        if r["n"] == 1 or r["start"] + r["dur"] <= HOOK_WINDOW:
            r["label"] = "HOOK"
    rows[-1]["label"] = "CTA" if rows[-1]["label"] != "HOOK" else "HOOK/CTA"
    half = total / 2
    for r in rows:
        if not r["label"] and r["start"] <= half < r["start"] + r["dur"]:
            r["label"] = "MID"

    notes = []
    if rows[0]["dur"] > HOOK_WINDOW:
        rows[0]["flags"].append(f"هوک {rows[0]['dur']:.1f} ثانیه طول می‌کشد، از مرز {HOOK_WINDOW:.0f} ثانیه رد شده")
        notes.append(f"بیت ۱ {rows[0]['dur']:.1f} ثانیه طول می‌کشد. به {int(HOOK_WINDOW * wps)} کلمه یا کمتر برسانش،"
                     " وگرنه هوک بعد از تصمیم بیننده فرود می‌آید.")
    if rows[0]["concrete"] == 0:
        notes.append("بیت ۱ نه عدد دارد نه اسم. هوک‌های بدون چیز قابل چک همان‌هایی‌اند که رد می‌شوند.")

    for r in rows:
        if r["dur"] > MAX_BEAT:
            r["flags"].append(f"{r['dur']:.1f} ثانیه روی یک بیت")
    long_beats = [r["n"] for r in rows if r["dur"] > MAX_BEAT]
    if long_beats:
        notes.append(f"بیت(های) {', '.join(map(str, long_beats))} از {MAX_BEAT:.0f} ثانیه رد می‌شوند."
                     " یا خط را بشکن یا وسطش تصویر را عوض کن. قاب ثابت همان‌جایی است که آدم‌ها می‌روند.")

    run, start = 0, None
    for r in rows:
        if r["concrete"] == 0:
            run += 1
            start = start if start is not None else r["n"]
            if run == ABSTRACT_RUN:
                notes.append(f"بیت‌های {start} تا {r['n']} هیچ چیز مشخصی ندارند. در یکی‌شان یک عدد یا اسم بگذار.")
        else:
            run, start = 0, None

    first = {w for w in words(rows[0]["text"]) if w not in STOPWORDS}
    last = {w for w in words(rows[-1]["text"]) if w not in STOPWORDS}
    loop = sorted(first & last)
    if loop:
        notes.append(f"لوپ دارد: بیت آخر «{'، '.join(loop[:3])}» را از هوک تکرار می‌کند. بازپخش، دسترسیِ بدون پول است.")
    else:
        notes.append("لوپ ندارد: بیت آخر هیچ کلمه‌ای از هوک را تکرار نمی‌کند و ویدیو صاف تمام می‌شود."
                     " تکرار یک کلمه از بیت ۱ ارزان‌ترین بازپخش است.")

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"طول روی هدف است ({total:.1f} ثانیه در برابر هدف {target} ثانیه).")
        elif delta > 0:
            notes.append(f"{delta:.1f} ثانیه بالای هدف. حدود {int(delta * wps)} کلمه کم کن.")
        else:
            notes.append(f"{-delta:.1f} ثانیه زیر هدف. یا {int(-delta * wps)} کلمه اضافه کن یا کوتاه فیلم بگیر؛ کوتاه معمولاً درست‌تر است.")

    return {
        "wpm": wpm, "target": target,
        "total_seconds": round(total, 2),
        "total_words": sum(r["words"] for r in rows),
        "beats": rows,
        "notes": notes,
    }


def render(a, out=sys.stdout):
    head = (f"بیت‌شیت · {a['total_words']} کلمه · حدود {a['total_seconds']:.1f} ثانیه با نرخ {a['wpm']} کلمه در دقیقه"
            + (f" · هدف {a['target']} ثانیه" if a["target"] else ""))
    print("\n" + head, file=out)
    print("=" * 72, file=out)
    for r in a["beats"]:
        label = f"{r['label']:<8}" if r["label"] else " " * 8
        print(f"  {tc(r['start'])}  {r['dur']:4.1f}s  {label}{r['text']}", file=out)
        for f in r["flags"]:
            print(f"  {'':>6}  {'':>5}  {'':<8}^ {f}", file=out)
    print("-" * 72, file=out)
    for n in a["notes"]:
        print(f"  - {n}", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="زمان‌بندی اسکریپت فارسی ریلز به بیت‌شیت.")
    ap.add_argument("input", nargs="?", default="-", help="فایل اسکریپت، یا -")
    ap.add_argument("--wpm", type=float, default=130, help="نرخ گفتار (پیش‌فرض ۱۳۰)")
    ap.add_argument("--target", type=float, help="طول هدف به ثانیه")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    a = analyse(raw, wpm=args.wpm, target=args.target)
    if not a:
        print("اسکریپت خالی است", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0)


if __name__ == "__main__":
    main()
