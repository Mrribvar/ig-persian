#!/usr/bin/env python3
"""
caption_fa.py — لینت کپشن فارسی و نمایش دقیق همان تیکه‌ای که فید قبل از
«... بیشتر» نشان می‌دهد.

ایرانی‌سازی از caption.py در ریپوی instagram-agent-skill (MIT).
پلتفرم به کپشن حدود ۱۲۵ کاراکتر در فید فضا می‌دهد و بقیه را پشت یک ضربه
پنهان می‌کند؛ بیشتر کپشن‌های ناموفق همان‌جا می‌بازند. این ابزار آن پنجره را
چاپ می‌کند و بعد چک‌های لازم را انجام می‌دهد.

چک‌های مخصوص این نسخه (سیستم خود ریبوار):
- کلمات ممنوعه‌ی قطعی او (ثبت ۲۰۲۶-۱۰-۰۹): پیج، اینستاگرام، ادمین، فالو،
  لایک، کامنت ← خطای قطعی با پیشنهاد جایگزین.
- کلمات پرریسک پژوهشی: مسابقه، قیمت، رایگان، فیک، هک، فالوئر، فروش، تقلب
  ← هشدار. استثنای خودش: «دایرکت» آزاد است.
- فراخوان عددی/کلیدواژه‌ای به سبک خودش («عدد X رو بفرست»، «کلمه‌ی ...»).
- سقف هشتگ ۵ تا (از دسامبر ۲۰۲۵).
- رسم‌الخط و نیم‌فاصله کار این ابزار نیست؛ برای آن زنجیره‌ی persian-writing
  (persian_cleanup.py + fa_lint.py) را اجرا کن.

استفاده:
  python3 caption_fa.py caption.txt
  python3 caption_fa.py caption.txt --keywords "هوش مصنوعی,مشاوره کسب‌وکار"
  python3 caption_fa.py caption.txt --json
"""

import argparse
import json
import re
import sys

LIMIT = 2200
TRUNCATE = 125
HASHTAG_LIMIT = 5

DIGITS = "0-9۰-۹٠-٩"
HASHTAG_RE = re.compile(r"(?:^|\s)(#\S+)")
MENTION_RE = re.compile(r"(?:^|\s)(@[A-Za-z0-9_.]+)")
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+", re.IGNORECASE)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿←-⇿️]")
CONCRETE_RE = re.compile(
    rf"[{DIGITS}]|گوگل|متا|یوتیوب|تلگرام|کپکات|جمینای|\b[A-Z][a-zA-Z]{{2,}}\b"
)

# کلمات ممنوعه‌ی قطعی ریبوار + جایگزین امن
BANNED = {
    "پیج": "صفحه",
    "اینستاگرام": "(حذفش کن؛ اسم پلتفرم را نیاور)",
    "ادمین": "مدیر صفحه / دستیار (جز در عنوان‌های برندشده‌ی خودش)",
    "فالو": "دنبال‌کردن",
    "لایک": "پسند",
    "کامنت": "نظر",
}
# پرریسک از تحقیق (ریپلایو، آذر ۱۴۰۴)
RISKY = {
    "مسابقه": None,
    "قیمت": None,
    "رایگان": "بدون پول",
    "فیک": None,
    "هک": None,
    "فالوئر": "دنبال‌کننده",
    "فروش": "مشتری (در ساختار جمله)",
    "تقلب": None,
}
FILLER_TAGS = {"#اکسپلور", "#وایرال", "#ترند", "#پست", "#جدید", "#explore",
               "#viral", "#fyp", "#foryou", "#trending", "#reels"}

ASKS = [
    (re.compile(rf"عدد\s*[{DIGITS}]+\s*(?:رو|را)?\s*(?:بفرست|بنویس|ارسال کن)"), "عدد در نظر/دایرکت"),
    (re.compile(r"کلمه(?:‌ی|ی)?\s*«[^»]+»\s*(?:رو|را)?\s*(?:بفرست|بنویس)"), "کلیدواژه در نظر/دایرکت"),
    (re.compile(r"دایرکت\s*(?:بده|بفرست|پیام بده|کن)"), "دایرکت"),
    (re.compile(r"ذخیره(?:‌اش|ش)?\s*کن|سیو(?:ش)?\s*کن"), "ذخیره‌کردن"),
    (re.compile(r"بفرست(?:ش|اش)?\s*برای|برای\s+\S+\s*بفرست|به اشتراک بذار"), "فرستادن برای بقیه"),
    (re.compile(r"نظرت(?:و|ون)?\s*(?:بگو|بنویس|چیه|بگید)|تو\s*(?:چی|چه)\s*فکر می‌کنی|سؤالم اینه"), "جواب به سؤال"),
    (re.compile(r"لینک\s*(?:توی|در)?\s*بایو"), "لینک بایو"),
]


def normalize(text):
    return text.replace("ي", "ی").replace("ك", "ک").replace("ـ", "")


SUFFIXES = r"(?:‌?(?:ها|های|ی|ام|ات|اش|مان|تان|شان|م|ت|ش))?"

def find_words(text, table):
    """پیداکردن کلمات ممنوعه به‌صورت کلمه‌ی مستقل (با پسوندهای چسبیده مثل
    «فالوئرها» و «پیجم»)، نه جزئی از کلمه‌ی دیگر مثل «فروشگاه» یا «هکتار»."""
    hits = []
    for w in table:
        pat = re.compile(r"(?<![آ-یA-Za-z])" + re.escape(w) + SUFFIXES + r"(?![آ-یA-Za-z])")
        if pat.search(text):
            hits.append(w)
    return hits


def analyse(text, cut=TRUNCATE, keywords=None):
    text = normalize(text.rstrip())
    stripped = text.strip()
    chars = len(stripped)
    # خط اول را از متن خام می‌گیریم (نه از نسخه‌ی strip‌شده) تا کپشنی که با
    # خط خالی شروع می‌شود هم درست گرفته شود.
    lines = text.split("\n")
    first_line = lines[0].strip() if lines else ""
    tags = HASHTAG_RE.findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = LINK_RE.findall(stripped)
    emoji = EMOJI_RE.findall(text)
    window = stripped[:cut]
    truncated = chars > cut
    asks = [name for pattern, name in ASKS if pattern.search(stripped)]
    filler = [t for t in tags if t.lower() in FILLER_TAGS]
    banned_hits = find_words(stripped, BANNED)
    risky_hits = find_words(stripped, RISKY)
    keywords = [k.strip() for k in (keywords or []) if k.strip()]

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("طول", "FAIL" if chars > LIMIT else "PASS",
        f"{chars} از {LIMIT} کاراکتر" + (f"؛ {chars - LIMIT} تا بالای سقف" if chars > LIMIT else ""))

    if banned_hits:
        sug = "؛ ".join(f"«{w}» ← {BANNED[w]}" for w in banned_hits)
        add("کلمات ممنوعه", "FAIL", f"کلمه‌ی ممنوعه‌ی قطعی در متن است: {sug}")
    else:
        add("کلمات ممنوعه", "PASS", "هیچ‌کدام از کلمات ممنوعه‌ی قطعی نیست")

    if risky_hits:
        sug = "؛ ".join(f"«{w}»" + (f" ← {RISKY[w]}" if RISKY[w] else "") for w in risky_hits)
        add("کلمات پرریسک", "WARN", f"این‌ها ریسک محدودشدن دارند: {sug}")
    else:
        add("کلمات پرریسک", "PASS", "کلمه‌ی پرریسکی نیست")

    if not first_line:
        add("خط اول", "FAIL", "کپشن با خط خالی شروع می‌شود")
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("خط اول", "FAIL", "با هشتگ یا منشن شروع می‌شود؛ باارزش‌ترین جای کپشن مال یک جمله است")
    elif len(first_line) > cut:
        add("خط اول", "WARN",
            f"{len(first_line)} کاراکتر است و در {cut} وسط فکر بریده می‌شود. اگر برش تعلیق است خوب است، اگر جمله‌ی فرعی است بد است")
    else:
        add("خط اول", "PASS", f"{len(first_line)} کاراکتر؛ کامل می‌نشیند")

    add("مشخص‌بودن هوک", "PASS" if CONCRETE_RE.search(window) else "WARN",
        f"{len(CONCRETE_RE.findall(window))} عدد یا اسم در پنجره‌ی قابل مشاهده"
        + ("" if CONCRETE_RE.search(window) else "؛ قبل از ضربه‌زدن هیچ چیز قابل چکی نیست"))

    if len(tags) > HASHTAG_LIMIT:
        add("هشتگ", "FAIL", f"{len(tags)} هشتگ؛ سقف پلتفرم {HASHTAG_LIMIT} تاست. بقیه حساب نمی‌شوند و بلوک هشتگ قدیمی به نظر می‌رسد")
    elif filler:
        add("هشتگ", "WARN", f"{len(tags)} هشتگ که {len(filler)} تایش کلیشه‌ای است ({' '.join(filler[:3])})؛ این‌ها هیچ موضوعی را توصیف نمی‌کنند")
    else:
        add("هشتگ", "PASS", f"{len(tags)} هشتگ" + (f": {' '.join(tags)}" if tags else ""))

    if tags and any(t in window for t in tags):
        add("جای هشتگ", "WARN", "یک هشتگ داخل پنجره‌ی قابل مشاهده است و فضای فید را خرج یک برچسب می‌کند")
    else:
        add("جای هشتگ", "PASS", "هشتگ‌ها زیر برش‌اند" if tags else "هشتگی نیست")

    add("لینک", "WARN" if links else "PASS",
        f"{len(links)} لینک در متن است و لینک در کپشن کلیک‌پذیر نیست؛ ببرش به بایو یا دایرکت" if links else "لینک مرده‌ای در متن نیست")

    # سؤال تعامل (مثل «تو اولین کاری که می‌سپری چیه؟») خواسته‌ی رقیب نیست؛
    # الگوی خود ریبوار سؤال + یک فراخوان عملی است. دو فراخوان عملی یعنی هیچ‌کدام.
    action_asks = [a for a in asks if a != "جواب به سؤال"]
    has_question = "جواب به سؤال" in asks
    if len(action_asks) == 1:
        add("یک خواسته", "PASS", f"یک فراخوان عملی: {action_asks[0]}" + (" + سؤال تعامل" if has_question else ""))
    elif not action_asks and has_question:
        add("یک خواسته", "WARN", "فقط سؤال تعامل است؛ فراخوان عملی ندارد. اگر هدف فقط گفت‌وگوست، اشکالی ندارد")
    elif not asks:
        add("یک خواسته", "WARN", "هیچ فراخوانی نیست. معلوم کن این محتوا برای چیست")
    else:
        add("یک خواسته", "WARN", f"{len(action_asks)} فراخوان عملی ({'، '.join(action_asks)}). دو خواسته یعنی هیچ خواسته")

    density = len(emoji) * 100 / max(chars, 1)
    add("ایموجی", "WARN" if density > 4 else "PASS",
        f"{len(emoji)} ایموجی، {density:.1f} در هر ۱۰۰ کاراکتر" + ("؛ تزئینی خوانده می‌شود" if density > 4 else ""))

    if keywords:
        low = stripped.lower()
        found = [k for k in keywords if k.lower() in low]
        missing = [k for k in keywords if k.lower() not in low]
        in_window = [k for k in found if k.lower() in window.lower()]
        status = "PASS" if not missing else ("WARN" if found else "FAIL")
        add("واژه‌های جست‌وجو", status,
            f"{len(found)} از {len(keywords)} حاضر است"
            + (f"، {len(in_window)} تا در پنجره‌ی قابل مشاهده" if found else "")
            + (f". غایب: {'، '.join(missing)}" if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")
    verdict_fa = {"FIX": "اصلاح لازم", "REVIEW": "بازبینی", "READY": "آماده"}

    return {
        "characters": chars, "limit": LIMIT, "truncate_at": cut,
        "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line),
        "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks,
        "banned": banned_hits, "risky": risky_hits,
        "checks": checks, "verdict": verdict, "verdict_fa": verdict_fa[verdict],
    }


def render(a, out=sys.stdout):
    head = (f"لینت کپشن · {a['characters']} از {a['limit']} کاراکتر · "
            f"{len(a['hashtags'])} هشتگ · {len(a['asks'])} خواسته")
    print("\n" + head, file=out)
    print("=" * 62, file=out)
    print("\n  چیزی که فید نشان می‌دهد (قبل از «... بیشتر»):", file=out)
    print("  " + a["visible"].replace("\n", "\n  "), file=out)
    if a["truncated"]:
        print("  ... بیشتر", file=out)
    else:
        print("  (کل کپشن جا می‌شود)", file=out)
    print("", file=out)
    status_fa = {"PASS": "اوکی", "WARN": "هشدار", "FAIL": "خطا"}
    for c in a["checks"]:
        print(f"  {status_fa[c['status']]:<6} {c['check']:<16} {c['detail']}", file=out)
    print("-" * 62, file=out)
    print(f"  حکم: {a['verdict_fa']}\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="لینت کپشن فارسی.")
    ap.add_argument("input", nargs="?", default="-", help="فایل کپشن، یا -")
    ap.add_argument("--truncate", type=int, default=TRUNCATE)
    ap.add_argument("--keywords", default="", help="واژه‌های جست‌وجو، جداشده با کاما")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    a = analyse(raw, cut=args.truncate, keywords=args.keywords.split(","))
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0 if a["verdict"] == "READY" else 1)


if __name__ == "__main__":
    main()
