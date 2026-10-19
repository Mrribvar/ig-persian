# ig-persian — پک فارسی اینستاگرام

ایرانی‌سازی از [instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill)
ساخته‌ی Jake Schincariol (لایسنس MIT). فرمول‌ها و منطق ابزارها از اصلش است؛
همه‌ی متن‌ها، مثال‌ها، واژه‌نامه‌ها و خط‌قرمزها برای فارسی از نو نوشته
شده‌اند. فایل پروفایل صدا به‌صورت قالب است تا هر سازنده‌ای با اطلاعات خودش
پرش کند و سیستم را مال خودش کند.

## اجزا

| فایل | کارش |
|---|---|
| `SKILL.md` | راهنمای گردش‌کار کامل |
| `voice-profile.md` | قالب پروفایل صدا و قوانین سازنده؛ اول با اطلاعات خودت پر و خوانده می‌شود |
| `hooks-fa.json` | ۲۶ فرمول هوک فارسی با مثال در حوزه‌ی هوش مصنوعی و رشد کسب‌وکار |
| `tools/hookscore_fa.py` | امتیازدهی هوک فارسی (پنج ویژگی) |
| `tools/beats_fa.py` | بیت‌شیت زمان‌دار اسکریپت با نرخ گفتار فارسی |
| `tools/caption_fa.py` | لینتر کپشن: پنجره‌ی ۱۲۵ کاراکتری فید، کلمات ممنوعه، سقف ۵ هشتگ |
| `tools/swipe_fa.py` | رتبه‌بندی ریلز رقیب بر اساس ضرب نسبت به میانه‌ی خود صفحه |

## استفاده

```bash
cd tools
python3 hookscore_fa.py --hook "۴ تا ابزار گوگل که ۹۹ درصد آدما نمی‌شناسن"
python3 beats_fa.py script.txt --target 15
python3 caption_fa.py caption.txt
python3 swipe_fa.py captured.tsv
```

نرخ گفتار پیش‌فرض ۱۳۰ کلمه در دقیقه است؛ با `--wpm` (هر دو ابزار بالای خط) قابل
تنظیم. پنجره‌ی هوک ۳ ثانیه است و `hookscore_fa.py` و `beats_fa.py` از یک آستانه
استفاده می‌کنند.

## نصب به‌عنوان اسکیل opencode

```bash
mkdir -p ~/.config/opencode/skill
ln -s "$PWD" ~/.config/opencode/skill/ig-persian
```

بعد از ذخیره، opencode را ببند و دوباره باز کن تا اسکیل بارگذاری شود.

## تغییرات

فهرست کامل تغییرات در [`CHANGELOG.md`](./CHANGELOG.md). نسخه‌ی فعلی: `1.1.0`.

## مجوز

MIT — متن کامل در [`LICENSE`](./LICENSE). حق اصل متعلق به Jake Schincariol است
و اقتباس فارسی به Mrribvar.
