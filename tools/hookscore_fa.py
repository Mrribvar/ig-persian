#!/usr/bin/env python3
"""
hookscore_fa.py — امتیازدهی به جمله‌ی اول (هوک) یک ریلز فارسی، روی پنج ویژگی
هوک‌های قوی، و رتبه‌بندی چند هوک کنار هم.

ایرانی‌سازی از hookscore.py در ریپوی instagram-agent-skill (MIT).
نسخه‌ی اصلی روی هوک‌های انگلیسی تست شده بود: هوکِ عمداً بد را خوب می‌گیرد
(AUC 0.83) ولی بین دو هوکِ خوب نمی‌تواند برنده را انتخاب کند (AUC 0.56).
همین صداقت این‌جا هم برقرار است: این ابزار سلام‌و‌مقدمه و هوکِ بی‌عدد و
هوکِ پنج‌ثانیه‌ای را می‌گیرد؛ پیش‌بینی بازدید نیست و نباید باشد.
نمودار نگه‌داری (retention) همیشه بالاتر از این اسکریپت است.

تغییرات نسخه‌ی فارسی:
- توکن‌سازی فارسی (نیم‌فاصله برای شمارش حذف می‌شود، ی/ک عربی نرمال می‌شود)
- عددها با هر سه رسم‌الخط (۱۲۳، 123، ١٢٣) + عددهای گفتاری («سه»، «پنجاه»)
- نرخ گفتار پیش‌فرض فارسی: ۱۳۰ کلمه در دقیقه (قابل تنظیم با --wpm)
- واژه‌نامه‌های کشش، شروع‌های ضعیف و خط‌قرمزها کاملاً فارسی
- نام‌های تجاری فارسی و لاتین (گوگل، متا، ChatGPT...) مارکر مشخص‌بودن‌اند

استفاده:
  python3 hookscore_fa.py hooks.txt          # هر خط یک هوک، رتبه‌بندی
  python3 hookscore_fa.py --hook "۴ تا ابزار گوگل که ۹۹ درصد آدما نمی‌شناسن"
  python3 hookscore_fa.py hooks.txt --json
"""

import argparse
import json
import re
import statistics
import sys

PERSIAN_WPM = 130.0  # نرخ گفتار پیش‌فرض فارسی؛ با صدای خودت کالیبره‌اش کن
HOOK_SECONDS = 3.0   # پنجره‌ی هوک؛ با آستانه‌ی beats_fa.py یکی است

DIGITS = "0-9۰-۹٠-٩"
NUMBER_RE = re.compile(
    rf"[{DIGITS}][{DIGITS},٬]*(?:\.[{DIGITS}]+)?\s?"
    r"(?:%|درصد|تومان|میلیون|میلیارد|هزار|دلار|ثانیه|دقیقه|ساعت|روز|هفته|ماه|سال|برابر|نفر|تا|k|x)?"
)
HASHTAG_RE = re.compile(r"(?:^|\s)#\S+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿←-⇿️]")
LATIN_PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-zA-Z]{2,}\b")

# عددها در گفتار با حروف هم گفته می‌شوند. «یک» و «یه» عمداً نیستند؛
# مثل نسخه‌ی اصلی که one/first را حذف کرده بود، این‌ها بیشتر پرکننده‌اند.
SPOKEN_NUMBERS = {
    "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده",
    "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده",
    "هجده", "نوزده", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد",
    "هشتاد", "نود", "صد", "هزار", "میلیون", "میلیارد", "نیم", "دوبرابر",
}
MONEY_WORDS = {
    "تومان", "دلار", "پول", "درآمد", "سود", "حقوق", "اجاره", "قیمت",
    "رایگان", "پولی", "هزینه",
}
BRANDS = {
    "گوگل", "متا", "یوتیوب", "تلگرام", "واتساپ", "فیسبوک", "تیکتاک",
    "کپکات", "جمینای", "کلود", "ایجنت", "اپل", "سامسونگ", "مایکروسافت",
}

# کلمه‌هایی که چیزی را سر خط می‌گذارند؛ هوک بدون این‌ها یک جمله‌ی خبری است.
STAKES = {
    "اشتباه", "غلط", "ضرر", "هزینه", "هیچکسی", "هیچکس", "نمیگه", "نمیگن",
    "نمیدونی", "نمیدونن", "نمیشناسن", "نمیشناسی", "بلد", "هرگز", "اصلاً", "اصلا", "راز", "پنهان", "مخفی",
    "حقیقت", "دروغ", "بدترین", "خطر", "هشدار", "فقط", "بدون", "هنوز",
    "دیگه", "باختی", "شکست", "مشکل", "ازدست", "دیره", "جلوشو", "نکن",
    "نذار", "دیگهنکن",
}
STAKES_PHRASES = [
    (re.compile(r"از دست می‌دی|از دستش می‌دی"), "از دست دادن"),
    (re.compile(r"بهت نمی‌گ(?:ه|ن)|هیچ‌کس نمی‌گه"), "حرف ناگفته"),
    (re.compile(r"تقصیر تو نیست"), "تبرئه"),
    (re.compile(r"به جاش"), "جایگزینی"),
    (re.compile(r"نمی‌خوابه|هیچ‌وقت نمی‌خوابه"), "همیشه روشن"),
    (re.compile(r"قبل از اینکه|قبل از این‌که"), "مهلت"),
]

# شروع‌هایی که ثانیه‌ی اول را روی هیچ خرج می‌کنند.
WEAK_OPENERS = [
    "سلام دوستان", "سلام به همه", "سلام بچه‌ها", "سلام بچها", "سلام",
    "خب بچه‌ها", "بچه‌ها", "بچها", "دوستان عزیز", "دوستان",
    "امروز می‌خوام", "امروز میخوام", "امروز قراره", "امروز اومدم",
    "تو این ویدیو", "در این ویدیو", "تو این پست",
    "می‌خوام بهتون بگم", "میخوام بهتون بگم", "می‌خوام در مورد", "میخوام در مورد",
    "اول از همه", "ببینید", "گوش کنید", "یه چیزی می‌خوام بگم",
    "خب", "امروز",
]

# فعل‌های امری که جمله را به بیننده خطاب می‌کنند.
IMPERATIVES = {
    "ببین", "نگاه", "نکن", "نذار", "بردار", "امتحان", "ذخیره", "بفرست",
    "بگیر", "بذار", "بنویس", "بساز", "بخون", "بگرد", "بکن", "بده", "برو",
    "بیا", "کن", "کنید", "دیگه", "بس", "استفاده", "یادت",
}
FIRST_PERSON = {
    "من", "ما", "خودم", "برام", "پولم", "صفحهم",
    "دادم", "گرفتم", "کردم", "شدم", "بودم", "گفتم", "فهمیدم", "دیدم",
}
# ضمیرها و فعل‌های دوم‌شخص گفتاری. بعد از حذف نیم‌فاصله، به‌صورت توکن کامل
# تطبیق داده می‌شوند تا «قیمت» یا «ثبت» اشتباهاً دوم‌شخص حساب نشوند.
SECOND_PERSON = {
    "تو", "شما", "شماها", "خودت", "خودتون", "برات", "بهت", "براتون", "بهتون",
    "داری", "دارید", "می‌خوای", "میخوای", "می‌خواید", "میخواید", "می‌تونی",
    "میتونی", "می‌تونید", "میتونید", "کنی", "کنید", "بدی", "بدید", "بشی",
    "بشید", "بری", "برید", "بگیری", "بذاری", "بنویسی", "بخری", "کپشنت",
    "صفحه‌ت", "صفحهت", "پیجت", "کاربرات", "مشتری‌هات", "مشتریهات",
}

DEALBREAKERS = [
    (re.compile(r"^\s*(?:اسکرول نکن|وایسا اسکرول|رد نشو|اسکرول رو نگه دار)"),
     "شروع با «اسکرول نکن». التماس برای توجه یعنی هنوز به دستش نیاورده‌ای."),
    (re.compile(r"(?:تو|در) این (?:ویدیو|ریلز|پست) (?:می‌خوام|میخوام|قراره|می‌خوایم)"),
     "مقدمه‌ی ویدیو. حذفش کن و از خود نتیجه شروع کن."),
    (re.compile(r"^\s*(?:سلام|درود)\b"),
     "سلام‌واحوال‌پرسی. هیچ‌کس برای سلام‌شنیدن به فید نیامده."),
    (HASHTAG_RE,
     "هشتگ داخل هوک. هشتگ اگر جایی داشته باشد، ته کپشن است."),
    (EMOJI_RE,
     "ایموجی داخل هوک. متن روی تصویر در سایز هوک یا جا برای کلمه دارد یا ایموجی، نه هر دو."),
]


def normalize(text):
    t = text.replace("ي", "ی").replace("ك", "ک")
    t = t.replace("ـ", "")
    return t


def words(text):
    t = normalize(text)
    # نیم‌فاصله را برمی‌داریم تا «نمی‌گه» یک کلمه‌ی گفتاری حساب شود.
    t = t.replace("‌", "")
    toks = re.findall(r"[^\s،؛؟?!.,:«»\"'()\[\]{}…]+", t)
    return [x for x in toks if x.strip()]


def clamp(n):
    return max(0.0, min(100.0, n))


def check_length(text, wpm=PERSIAN_WPM):
    """هوک باید قبل از حرکت شست فرود بیاید؛ حدود سه ثانیه (پنجره‌ی هوک در beats_fa)."""
    w = words(text)
    n = len(w)
    secs = n / (wpm / 60.0)
    chars = len(normalize(text).strip())
    min_words = 3
    max_words = max(4, round(HOOK_SECONDS * wpm / 60.0))
    if min_words <= n <= max_words:
        score = 100.0
    elif n < min_words:
        score = clamp(100 - (min_words - n) * 20)
    else:
        score = clamp(100 - (n - max_words) * 10)
    if chars > 55:  # دو خط متن درشت روی تصویر
        score -= 12
    return clamp(score), (f"{n} کلمه، {chars} کاراکتر، حدود {secs:.1f} ثانیه گفتار "
                          f"(هدف {min_words} تا {max_words} کلمه در پنجره‌ی {HOOK_SECONDS:.0f} ثانیه‌ای)")


def check_specificity(text):
    """یک چیز مشخص، سه چیز انتزاعی را می‌زند."""
    t = normalize(text)
    nums = [x.strip() for x in NUMBER_RE.findall(t) if any(c.isdigit() for c in x)]
    toks = words(t)
    low = [x.lower() for x in toks]
    spoken = [x for x in low if x in SPOKEN_NUMBERS or x in MONEY_WORDS]
    brands = [x for x in low if x in BRANDS]
    propers = set(LATIN_PROPER_RE.findall(text))
    hits = len(nums) + len(spoken) + len(brands) + len(propers)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join((nums[:2] + spoken[:2] + brands[:2] + sorted(propers)[:1]))
    detail = f"{hits} نشانه‌ی مشخص" + (f": {found}" if found else " - نه عددی، نه اسمی، نه چیزی که بشود چک کرد")
    return score, detail


def check_stakes(text):
    """کشش، هزینه، نفی. چیزی که بیننده ممکن است از دست بدهد."""
    t = normalize(text)
    toks = set(words(t))
    hits = sorted(x for x in toks if x in STAKES)
    for pat, name in STAKES_PHRASES:
        if pat.search(t):
            hits.append(name)
    n = len(hits)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detail = f"{n} نشانه‌ی کشش" + (f": {'، '.join(hits[:4])}" if hits else " - هیچ چیزی در این جمله سر خط نیست")
    return clamp(score), detail


def check_frontload(text):
    """کلمه‌ی جالب نمی‌تواند کلمه‌ی نهم باشد."""
    w = words(text)
    if not w:
        return 0.0, "خالی"
    low = [x.lower() for x in w]
    opener = " ".join(low[:3])
    penalty, hit_opener = 0, None
    for weak in WEAK_OPENERS:
        if opener.startswith(weak) or low[0] == weak:
            penalty, hit_opener = 30, weak
            break
    payload = None
    for i, token in enumerate(low):
        if (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
                or token in BRANDS or NUMBER_RE.match(w[i])):
            payload = i
            break
    if payload is None:
        base, where = 30.0, "هیچ کلمه‌ی بار‌داری در کل جمله نیست"
    elif payload <= 2:
        base, where = 100.0, f"بار اصلی روی کلمه‌ی {payload + 1} است"
    elif payload <= 5:
        base, where = 70.0, f"بار اصلی روی کلمه‌ی {payload + 1} است، می‌تواند جلوتر بیاید"
    else:
        base, where = 40.0, f"بار اصلی روی کلمه‌ی {payload + 1} است، خیلی دیر است"
    detail = where + (f"؛ شروع ضعیف: «{hit_opener}»" if hit_opener else "")
    return clamp(base - penalty), detail


def check_address(text):
    """خطاب به یک بیننده، یا شناور در هوا."""
    toks = words(text)
    low = [x.lower() for x in toks]
    if any(x in SECOND_PERSON for x in low):
        return 100.0, "مستقیم با بیننده حرف می‌زند"
    for x in low:
        if x in IMPERATIVES:
            return 90.0, f"فعل امری («{x}»)؛ خطاب به بیننده"
    if any(x in FIRST_PERSON for x in low):
        return 70.0, "اول‌شخص است، بیننده نام برده نشده"
    return 35.0, "سوم‌شخص؛ هیچ‌کس در اتاق نیست"


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]
LABELS = {
    "LENGTH": "طول",
    "SPECIFICITY": "مشخص‌بودن",
    "STAKES": "کشش",
    "FRONTLOAD": "شروع قوی",
    "ADDRESS": "مخاطب",
}
VERDICTS = {"STRONG": "قوی", "OK": "قابل قبول", "WEAK": "ضعیف"}


def run(text, wpm=PERSIAN_WPM):
    results = {
        "LENGTH": check_length(text, wpm),
        "SPECIFICITY": check_specificity(text),
        "STAKES": check_stakes(text),
        "FRONTLOAD": check_frontload(text),
        "ADDRESS": check_address(text),
    }
    flags = [msg for pattern, msg in DEALBREAKERS if pattern.search(normalize(text))]
    scores = [results[c][0] for c in CHECKS]
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout):
    print("\nامتیاز هوک", file=out)
    print("=" * 62, file=out)
    print(f"  «{text.strip()}»\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {LABELS[name]:<12} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<12} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {'امتیاز کل':<12} {bar(overall)} {overall:5.1f}   {VERDICTS[verdict]}", file=out)
    for f in flags:
        print(f"\n  خط قرمز: {f}", file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  ضعیف‌ترین بخش: {LABELS[weakest]}. همان یکی را درست کن و دوباره اجرا کن.", file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    print("\nرتبه‌بندی هوک‌ها\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {VERDICTS[r['verdict']]:<10} {hook}", file=out)
        print(f"        ضعیف‌ترین: {LABELS[r['weakest']]} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        خط قرمز: {f}", file=out)
    print("\nبالایی را فیلم بگیر. اگر بالایی زیر ۵۰ است، هیچ‌کدامشان هوک نیستند.\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="امتیازدهی به هوک فارسی ریلز روی پنج ویژگی.")
    ap.add_argument("input", nargs="?", default="-", help="فایل با هر خط یک هوک، یا -")
    ap.add_argument("--hook", help="یک هوک تنها")
    ap.add_argument("--wpm", type=float, default=PERSIAN_WPM, help="نرخ گفتار (پیش‌فرض ۱۳۰)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    wpm = args.wpm

    if args.hook:
        lines = [args.hook]
    else:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        print("چیزی برای امتیازدهی نیست", file=sys.stderr)
        sys.exit(2)

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line, wpm)
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
        return

    if len(payload) == 1:
        results, overall, verdict, flags = run(lines[0], wpm)
        render_one(lines[0], results, overall, verdict, flags)
    else:
        render_table(sorted(payload, key=lambda r: -r["score"]))

    sys.exit(0 if max(p["score"] for p in payload) >= 70 else 1)


if __name__ == "__main__":
    main()
