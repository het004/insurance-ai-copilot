"""Arabic support for the offline demo agent.

• normalize(): Arabic input → digits converted + English keyword hints appended, so the same intent/slot rules work
  ("أبغى تأمين سيارة" → "... motor car").
• localize(): the agent's short English replies → Saudi-friendly Arabic, sentence by sentence. Anything not in the
  table stays in English (the Gemini agent answers in Arabic natively when it is available).
"""
from __future__ import annotations

import re

from app.config import settings

ARABIC_CHARS = re.compile(r"[؀-ۿ]")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def is_arabic(text: str) -> bool:
    letters = re.findall(r"[A-Za-z؀-ۿ]", text or "")
    return bool(letters) and len(ARABIC_CHARS.findall(text)) >= len(letters) * 0.5


def digits(text: str) -> str:
    return (text or "").translate(DIGITS).replace("٬", ",").replace("،", ",")


# ---------------------------------------------------------------- input: Arabic → keyword hints
PHRASES = [
    (r"أبغى|ابغى|ابغي|أبي|ابي|أريد|اريد|ودي|محتاج", "want"), (r"تأمين|تكافل", "insurance"),
    (r"السلام عليكم|مرحبا|مرحباً|أهلا|اهلا|هلا|صباح الخير|مساء الخير", "hello"),
    (r"عميل حالي|عندي حساب|انا عميل|أنا عميل|مسجل", "existing customer"),
    (r"عميل جديد|أول مرة|اول مرة|تسجيل", "i'm new"),
    (r"تأمين (?:على )?(?:ال)?سيار[ةت]|سيارتي|سيارة|مركبة|مركبات|المركبات|الشامل|ضد الغير", "motor car"),
    (r"تأمين (?:ال)?صحي|صحي|طبي|الصحي", "health"),
    (r"تأمين (?:على )?(?:ال)?حياة|الحياة|حماية", "life insurance"),
    (r"تقاعد|التقاعد|معاش", "retirement"),
    (r"ادخار|الادخار|توفير", "savings"),
    (r"تعليم|الجامعة|أبنائي|ابنائي", "education"),
    (r"شقة|شقتي", "apartment"), (r"فيلا|فلة|فلتي", "villa"), (r"منزل|بيت|بيتي|سكن", "home"),
    (r"اشتري|أشتري|شراء|ابغى اشتري|أبغى أشتري|ادفع|أدفع", "buy"),
    (r"مدى", "mada"), (r"أبل باي|ابل باي", "apple pay"), (r"اس تي سي باي|إس تي سي|اس تي سي", "stc pay"),
    (r"سداد", "sadad"), (r"بطاقة ائتمان|بطاقة", "credit card"),
    (r"حادث|حادثة|صدمت|اصطدام|تصادم", "accident"), (r"مطالبة|مطالبتي", "claim"), (r"حالة", "status"),
    (r"تجديد|جدد|جدّد", "renew"), (r"وثائقي|خططي|بوليصتي|تأميناتي", "what policies do i have"),
    (r"شهرياً|شهريا|شهري|كل شهر", "monthly"), (r"ربع سنوي|كل ثلاث شهور", "quarterly"),
    (r"نصف سنوي|كل ست شهور", "semi-annual"), (r"سنوياً|سنويا|سنوي|كل سنة", "yearly"),
    (r"محافظ|متحفظ|منخفض المخاطر", "conservative"), (r"متوازن", "balanced"), (r"النمو|نمو|عالي المخاطر", "growth"),
    (r"راتب|الراتب|راتبي", "salary"), (r"تجاري|تجارة|بزنس", "business"), (r"استثمار|استثمارات", "investments"),
    (r"اقتراحك|زي ما تشوف|على اقتراحك|اقترح|أقترح|اللي تشوفه", "suggest"),
    (r"لا أدخن|ما أدخن|ما ادخن|لا ادخن|غير مدخن", "non-smoker"), (r"أدخن|ادخن|مدخن|شيشة", "i smoke"),
    (r"سكري|السكر|ضغط|ربو|مزمن", "chronic"),
    (r"ما عندي|لا يوجد|ولا شي|لا شيء|ولا واحد|لا هذا ولا ذاك", "no"),
    (r"أمريكي|امريكي|الجنسية الأمريكية", "us"), (r"معرض سياسيا|معرّض سياسياً|منصب حكومي", "pep"),
    (r"اسمي", "my name is"), (r"عمري", "i am"),
    (r"مليون", "million"), (r"ألف|الف", "thousand"), (r"ريال", "sar"),
]
WORDS = {"نعم": "yes", "ايوه": "yes", "أيوه": "yes", "ايه": "yes", "إيه": "yes", "أكيد": "yes", "اكيد": "yes",
         "تمام": "yes", "موافق": "yes", "صح": "yes", "طيب": "ok", "لا": "no", "لأ": "no", "كلا": "no"}


def normalize(text: str) -> str:
    """Lower-cased text for intent rules: Arabic digits → ASCII, Arabic keywords → English hints appended."""
    t = digits(text)
    if not ARABIC_CHARS.search(t):
        return t.lower().strip()
    hints = [en for rx, en in PHRASES if re.search(rx, t)]
    for tok in re.findall(r"[؀-ۿ]+", t):
        if tok in WORDS:
            hints.append(WORDS[tok])
    return (" ".join(hints) + " " + t).lower().strip()


# ---------------------------------------------------------------- output: English → Arabic
PLAN_AR = {
    "Motor Comprehensive Plus": "الشامل بلس", "Motor Comprehensive": "التأمين الشامل", "Motor TPL": "التأمين ضد الغير",
    "Health Essential": "الصحي الأساسي", "Health Gold": "الصحي الذهبي", "Health Premier": "الصحي المميز",
    "Life Protect Plus": "حماية بلس", "Life Protect": "حماية", "Life Premier": "حماية المميز",
    "Retirement Plan": "خطة التقاعد", "Savings Plan": "خطة الادخار", "Education Plan": "خطة التعليم",
    "Home Basic": "المنزل الأساسي", "Home Plus": "المنزل بلس", "Home Premier": "المنزل المميز",
}
FUND_AR = {"conservative": "المحافظ", "balanced": "المتوازن", "growth": "النمو"}
PORTFOLIOS_AR = "**المركبات**، **الصحي**، **الحماية**، **التقاعد والادخار** أو **العام** (المنزل)"


def _plan(name: str) -> str:
    return PLAN_AR.get(name.strip("* "), name)


RULES: list[tuple[str, object]] = [
    (r"\*\*Health\*\*, \*\*Motor\*\*, \*\*Life\*\*, \*\*Retirement & Savings\*\* or \*\*General\*\* \(home\)", PORTFOLIOS_AR),
    (r"Ahlan wa sahlan! I'm (\w+), your .+? assistant\.", lambda m: f"أهلاً وسهلاً! أنا {settings.ASSISTANT_NAME_AR}، مساعدك في تكافل الراجحي."),
    (r"Ahlan wa sahlan!", "أهلاً وسهلاً!"),
    (r"Happy to have you\.", "سعداء بانضمامك."),
    (r"Which plan are you looking for — (.+?)\?", r"أي خطة تبحث عنها — \1؟"),
    (r"This chat covers individual plans only\.? ?—? ?", "هذه المحادثة للخطط الفردية فقط. "),
    (r"Which would you like —? ?(.*?)\?", r"أيّها تفضّل \1؟"),
    (r"Our online plans are for individuals, so this covers you\.", "خططنا الإلكترونية فردية، لذا ستكون التغطية لك."),
    (r"Let's insure your car\.", "لنؤمّن سيارتك."), (r"Let's find your health plan\.", "لنجد خطتك الصحية."),
    (r"Let's protect your family's future\.", "لنحمِ مستقبل عائلتك."), (r"Let's plan your savings\.", "لنخطط لادخارك."),
    (r"Let's protect your home\.", "لنحمِ منزلك."),
    (r"May I have your full name\?", "ممكن اسمك الكامل؟"),
    (r"Thanks, (.+?)\. Your National ID or Iqama number\? You'll get a Nafath request to approve\.",
     r"شكراً \1. ما رقم الهوية الوطنية أو الإقامة؟ سيصلك طلب على نفاذ للموافقة."),
    (r"And the car's plate number, e\.g\. 7788 BDR\?", "ورقم لوحة السيارة، مثل 7788 BDR؟"),
    (r"What's your plate number, e\.g\. 7788 BDR\? \(Or the Istimara sequence number\.\)",
     "ما رقم لوحة السيارة، مثل 7788 BDR؟ (أو الرقم التسلسلي في الاستمارة)"),
    (r"What's the plate number of the car to insure\?", "ما رقم لوحة السيارة المراد تأمينها؟"),
    (r"Nafath approved, but the name on this ID is different\.", "تمت الموافقة عبر نفاذ، لكن الاسم في هذه الهوية مختلف."),
    (r"Nafath approved\.", "تمت الموافقة عبر نفاذ."),
    (r"Yakeen shows \*\*(.+?)\*\*, born (\d{4}), ([^,.]+?)(?:, and your (.+?))?\. Is that you\?",
     lambda m: f"بيانات يقين: **{m.group(1)}**، مواليد {m.group(2)}، {m.group(3)}"
               + (f"، وسيارتك {m.group(4)}" if m.group(4) else "") + ". هل هذا أنت؟"),
    (r"Shukran, (.+?) — you're registered\.", r"شكراً \1، تم تسجيلك."),
    (r"Ahlan, (.+?) — you're already with us\.", r"أهلاً \1، أنت عميل لدينا مسبقاً."),
    (r"Ahlan, (.+?)! You're verified\.", r"أهلاً \1! تم التحقق من هويتك."),
    (r"Ahlan, (.+?)! You're already with us\.", r"أهلاً \1! أنت عميل لدينا مسبقاً."),
    (r"Ahlan, (.+?)! How can I help you today\?", r"أهلاً \1! كيف أقدر أساعدك اليوم؟"),
    (r"Ahlan, (.+?)!", r"أهلاً \1!"),
    (r"How can I help today\?", "كيف أقدر أساعدك؟"),
    (r"Found your (.+?)\.", r"وجدنا سيارتك \1."),
    (r"Which plan — TPL, Comprehensive or Comprehensive Plus\? I'd suggest \*\*(.+?)\*\*\.",
     lambda m: f"أي خطة — ضد الغير، الشامل أم الشامل بلس؟ أقترح **{_plan(m.group(1))}**."),
    (r"Your \*\*Retirement Plan\*\*: SAR ([\d,]+) a month until (\d+), then about \*\*SAR ([\d,]+) a month for (\d+) years\*\* "
     r"\(projected, not guaranteed\)\. Shall we go ahead\?",
     r"**خطة التقاعد**: \1 ريال شهرياً حتى سن \2، ثم دخل شهري يقارب **\3 ريال لمدة \4 سنة** (تقديري وغير مضمون). هل نكمل؟"),
    (r"Your \*\*(.+?)\*\*: SAR ([\d,]+) a month for (\d+) years — around \*\*SAR ([\d,]+)\*\* at 5% a year \(not guaranteed\)\. "
     r"Shall we go ahead\?",
     lambda m: f"**{_plan(m.group(1))}**: {m.group(2)} ريال شهرياً لمدة {m.group(3)} سنة — قرابة **{m.group(4)} ريال** "
               "بعائد 5% سنوياً (غير مضمون). هل نكمل؟"),
    (r"Your \*\*(.+?)\*\* quote is \*\*SAR ([\d,]+)\*\* a year \((VAT-exempt|incl\. VAT)\)\. Other plans are on the card\. "
     r"Shall we go ahead\?",
     lambda m: f"عرض **{_plan(m.group(1))}**: **{m.group(2)} ريال** سنوياً "
               f"({'معفى من الضريبة' if m.group(3) == 'VAT-exempt' else 'شامل الضريبة'}). باقي الخطط في البطاقة. هل نكمل؟"),
    (r"\*\*(.+?)\*\*, starting today, \*\*SAR ([\d,]+)\*\* a year\.",
     lambda m: f"**{_plan(m.group(1))}** تبدأ اليوم، بمبلغ **{m.group(2)} ريال** سنوياً."),
    (r"How would you like to pay(?: the SAR ([\d,]+))? — mada, Apple Pay, STC Pay, card or SADAD\?",
     lambda m: "كيف تفضّل الدفع" + (f" لمبلغ {m.group(1)} ريال" if m.group(1) else "")
               + " — مدى، Apple Pay، STC Pay، بطاقة ائتمانية أم سداد؟"),
    (r"Shall I take \*\*SAR ([\d,]+)\*\* by (.+?)\?", r"هل أخصم **\1 ريال** عبر \2؟"),
    (r"Mabrook! Your (.+?) is active — certificate \*\*(.+?)\*\*\. It's in your profile with the schedule below\.",
     lambda m: f"مبروك! {_plan(m.group(1))} مفعّلة — رقم الشهادة **{m.group(2)}**. تجدها في ملفك مع الجدول أدناه."),
    (r"Do you have any chronic condition, like diabetes, hypertension or asthma\?", "هل لديك مرض مزمن مثل السكري أو الضغط أو الربو؟"),
    (r"How old are you\?", "كم عمرك؟"),
    (r"Do you smoke or use tobacco, including shisha\?", "هل تدخّن أو تستخدم التبغ، بما فيه الشيشة؟"),
    (r"I'd suggest \*\*SAR ([\d,]+)\*\* sum covered for \*\*(\d+) years\*\*\. Shall I use that\?",
     r"أقترح مبلغ تغطية **\1 ريال** لمدة **\2 سنة**. هل نعتمد ذلك؟"),
    (r"How much cover would you like, and for how many years\?", "كم مبلغ التغطية الذي تريده، ولكم سنة؟"),
    (r"What are you saving for — \*\*retirement\*\*, a \*\*child's education\*\*, or a \*\*general goal\*\*\?",
     "ما هدف ادخارك — **التقاعد**، **تعليم الأبناء**، أم **هدف عام**؟"),
    (r"How much each month\? I'd suggest \*\*SAR ([\d,]+)\*\* for (\d+) years\.", r"كم شهرياً؟ أقترح **\1 ريال** لمدة \2 سنة."),
    (r"At what age would you like to retire — \*\*55\*\*, \*\*60\*\* or \*\*65\*\*\?", "في أي عمر تودّ التقاعد — **55** أو **60** أو **65**؟"),
    (r"How much would you like to contribute each month\? The minimum is SAR 1,000 — I'd suggest \*\*SAR ([\d,]+)\*\*\.",
     r"كم تودّ أن تساهم شهرياً؟ الحد الأدنى 1,000 ريال — أقترح **\1 ريال**."),
    (r"The Retirement Plan starts from SAR 1,000 a month\. How much would you like to contribute\?",
     "تبدأ خطة التقاعد من 1,000 ريال شهرياً. كم تودّ أن تساهم؟"),
    (r"Would you like to pay \*\*monthly\*\*, \*\*quarterly\*\*, \*\*half-yearly\*\* or \*\*yearly\*\*\?",
     "هل تفضّل الدفع **شهرياً** أم **ربع سنوي** أم **نصف سنوي** أم **سنوياً**؟"),
    (r"Which fund suits you — \*\*Conservative\*\*, \*\*Balanced\*\* or \*\*Growth\*\*\? With (\d+) years to go, I'd suggest \*\*(\w+)\*\*\.",
     lambda m: f"أي صندوق يناسبك — **المحافظ** أم **المتوازن** أم **النمو**؟ مع بقاء {m.group(1)} سنة أقترح "
               f"**{FUND_AR.get(m.group(2).lower(), m.group(2))}**."),
    (r"Who should receive the Takaful protection if anything happens to you\? Their name and relationship, please\.",
     "من المستفيد من حماية التكافل لا قدّر الله؟ اسمه وصلة القرابة من فضلك."),
    (r"Two quick declarations: are you a US citizen or US tax resident, or a politically exposed person\?",
     "إقراران سريعان: هل أنت مواطن أمريكي أو مقيم ضريبي في أمريكا، أو شخص معرّض سياسياً؟"),
    (r"Which applies — US person, politically exposed person, or both\?", "أيّها ينطبق — شخص أمريكي، معرّض سياسياً، أم كلاهما؟"),
    (r"Last one — is the money from your \*\*salary\*\*, \*\*business\*\*, \*\*investments\*\* or something else\?",
     "أخيراً — هل مصدر الأموال **الراتب** أم **عمل تجاري** أم **استثمارات** أم غير ذلك؟"),
    (r"Is it an \*\*apartment\*\* or a \*\*villa\*\*\?", "هل هي **شقة** أم **فيلا**؟"),
    (r"Roughly what would it cost to rebuild\? For example SAR 1\.5 million for a villa\.",
     "كم تقريباً تكلفة إعادة البناء؟ مثلاً 1.5 مليون ريال للفيلا."),
    (r"And your belongings — furniture, electronics\? Say \"none\" for building only\.",
     "وما قيمة المحتويات — الأثاث والأجهزة؟ قل \"لا شيء\" لتأمين المبنى فقط."),
    (r"Sorry to hear that — I hope everyone is safe\. ", "سلامتك، أتمنى أن الجميع بخير. "),
    (r"When did it happen\?", "متى حدث ذلك؟"), (r"Where did it happen\?", "أين حدث؟"),
    (r"Briefly, what happened\?", "باختصار، ماذا حدث؟"),
    (r"Which car — (.+?)\?", r"أي سيارة — \1؟"),
    (r"Done — your claim ID is \*\*(.+?)\*\*\. Next steps are on the card\.", r"تم — رقم مطالبتك **\1**. الخطوات التالية في البطاقة."),
    (r"Please get the Najm report\.", "يرجى إحضار تقرير نجم."),
    (r"Claim \*\*(.+?)\*\* is at \*\*(.+?)\*\* — (\d+)% done\.", r"المطالبة **\1** في مرحلة **\2** — الإنجاز \3%."),
    (r"Sure\. Are you already with .+?\? Share your registered mobile number, or your National ID / Iqama\.",
     "بكل سرور. هل أنت عميل لدى تكافل الراجحي؟ شاركنا رقم جوالك المسجّل أو رقم الهوية / الإقامة."),
    (r"Please share your registered mobile number, or your National ID / Iqama\.", "شاركنا رقم جوالك المسجّل أو رقم الهوية / الإقامة."),
    (r"Sure — what's your registered mobile number\?", "بكل سرور — ما رقم جوالك المسجّل؟"),
    (r"I couldn't find that number\. What's your National ID or Iqama number\?", "لم أجد هذا الرقم. ما رقم الهوية الوطنية أو الإقامة؟"),
    (r"I couldn't find that number\. Try another, or share your National ID / Iqama to register\.",
     "لم أجد هذا الرقم. جرّب رقماً آخر أو شاركنا الهوية / الإقامة للتسجيل."),
    (r"You have (\d+) active plans — they're on the card\.", r"لديك \1 خطط سارية — تجدها في البطاقة."),
    (r"Your (.+?) is due for renewal in (\d+) days — renew it\?", r"موعد تجديد \1 بعد \2 يوماً — هل أجدّدها؟"),
    (r"Your (.+?) renews at \*\*SAR ([\d,]+)\*\*\.", r"تجديد \1 بمبلغ **\2 ريال**."),
    (r"Your No Claim Discount goes to (\d+)%\.", r"خصم عدم وجود مطالبات يرتفع إلى \1%."),
    (r"Shall I renew it\?", "هل أجدّدها؟"),
    (r"Mabrook — renewed! Your new certificate is \*\*(.+?)\*\*\.", r"مبروك — تم التجديد! رقم الشهادة الجديدة **\1**."),
    (r"No problem — your quote stays saved for 15 days\.", "لا مشكلة — عرضك محفوظ لمدة 15 يوماً."),
    (r"Your quote stays saved for 15 days\.", "عرضك محفوظ لمدة 15 يوماً."),
    (r"No problem, cleared\. What would you like to do next\?", "لا مشكلة، تم المسح. ماذا تودّ أن تفعل الآن؟"),
    (r"No problem — what should I correct\?.*", "لا مشكلة — ما الذي يحتاج تصحيح؟"),
    (r"Is everything correct now\?", "هل كل شيء صحيح الآن؟"),
    (r"Which plan would you like instead\?", "أي خطة تفضّل بدلاً منها؟"),
    (r"I can help with quotes, claims and renewals\. Which plan interests you — (.+?)\?",
     r"أقدر أساعدك في العروض والمطالبات والتجديد. أي خطة تهمّك — \1؟"),
    (r"I couldn't find a clear answer in our documents\.", "لم أجد إجابة واضحة في مستنداتنا."),
]


def localize(text: str) -> str:
    out = text
    for rx, rep in RULES:
        out = re.sub(rx, rep, out)
    for en, ar in PLAN_AR.items():
        out = out.replace(f"**{en}**", f"**{ar}**")
    return re.sub(r"SAR ([\d,]+(?:\.\d+)?)", r"\1 ريال", out)
