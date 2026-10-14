"""Arabic text normalization for retrieval (MSA + common Saudi/Gulf dialect).

``normalize`` makes spelling variants compare equal before embedding and
lexical matching:

* hamza/madda forms  أ إ آ ٱ → ا ; ؤ → و ; ئ → ي
* taa marbuta        ة → ه
* alef maqsura       ى → ي
* tashkeel (harakat, tanween, shadda, sukun, superscript alef) and tatweel removed
* Arabic-Indic and Persian digits → ASCII digits
* lower-case Latin, collapse whitespace and repeated letters (ههههه → هه)

``terms`` additionally strips common clitics (ال، و، ب، ف، ل، ك) and maps
dialect words to one canonical form (وش/ايش/شو → ما, ابغى/ابي → اريد ...), so
"وش أوقات دوامكم؟" and "ما هي ساعات العمل لديكم" share terms.
"""

from __future__ import annotations

import re

_TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_CHAR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ي", "ة": "ه", "ى": "ي",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "،": ",", "؛": ";", "؟": "?", "ـ": "",
})
_REPEAT = re.compile(r"(.)\1{2,}")
_TOKEN = re.compile(r"[0-9a-z\u0621-\u064A]+")


def normalize(text: str) -> str:
    t = (text or "").replace(_TATWEEL, "")
    t = _TASHKEEL.sub("", t)
    t = t.translate(_CHAR_MAP).lower()
    t = _REPEAT.sub(r"\1\1", t)
    return re.sub(r"\s+", " ", t).strip()


# Dialect / synonym → canonical (keys and values are already normalized).
DIALECT = {
    # question words
    "وش": "ما", "ايش": "ما", "شو": "ما", "ويش": "ما", "اش": "ما", "شنو": "ما", "وشو": "ما", "ماهو": "ما", "ماهي": "ما",
    "وين": "اين", "فين": "اين", "مكانكم": "موقع", "مكان": "موقع", "لوكيشن": "موقع", "عنوان": "موقع", "عنوانكم": "موقع",
    "موقعكم": "موقع", "location": "موقع", "address": "موقع",
    "امتي": "متي", "متى": "متي", "ايمتى": "متي", "ايمتي": "متي",
    "بكم": "سعر", "بكام": "سعر", "كم": "كم", "قديش": "سعر", "اسعار": "سعر", "اسعاركم": "سعر", "سعره": "سعر",
    "سعرها": "سعر", "تكلفه": "سعر", "تكلف": "سعر", "يكلف": "سعر", "كلفه": "سعر", "price": "سعر", "prices": "سعر",
    "cost": "سعر", "رسوم": "سعر", "فلوس": "سعر", "ثمن": "سعر", "قيمه": "سعر",
    # wanting / having
    "ابغي": "اريد", "ابغا": "اريد", "ابغى": "اريد", "ابي": "اريد", "بغيت": "اريد", "ودي": "اريد", "حاب": "اريد",
    "احب": "اريد", "نبغي": "اريد", "نبي": "اريد", "want": "اريد",
    "عندكم": "يوجد", "فيه": "يوجد", "في": "في", "تتوفر": "يوجد", "متوفر": "يوجد", "يتوفر": "يوجد", "متوفره": "يوجد",
    "موجود": "يوجد", "موجوده": "يوجد", "توفرون": "يوجد", "تقدمون": "يوجد", "لديكم": "يوجد",
    # time / hours
    "دوام": "دوام", "دوامكم": "دوام", "ساعات": "دوام", "اوقات": "دوام", "اوقاتكم": "دوام", "مواعيد": "دوام",
    "مواعيدكم": "دوام", "وقت": "دوام", "اوقات العمل": "دوام", "تفتحون": "تفتح", "تفتحوا": "تفتح", "يفتح": "تفتح", "فاتحين": "تفتح", "مفتوح": "تفتح",
    "تسكرون": "تغلق", "تقفلون": "تغلق", "تسكر": "تغلق", "يسكر": "تغلق", "تقفل": "تغلق", "يقفل": "تغلق", "تغلقون": "تغلق",
    "الحين": "الان", "هالحين": "الان", "اليوم": "اليوم", "hours": "دوام", "open": "تفتح", "close": "تغلق",
    # booking
    "احجز": "حجز", "نحجز": "حجز", "حجوزات": "حجز", "يحجز": "حجز", "اموعد": "موعد", "مواعد": "موعد", "booking": "حجز",
    "book": "حجز", "appointment": "موعد", "reserve": "حجز", "reservation": "حجز", "الغي": "الغاء", "الغاء": "الغاء",
    "كنسل": "الغاء", "اكنسل": "الغاء", "cancel": "الغاء",
    # delivery / payment
    "توصلون": "توصيل", "يوصل": "توصيل", "توصيلكم": "توصيل", "دليفري": "توصيل", "delivery": "توصيل", "توصل": "توصيل",
    "شحن": "توصيل", "الشحن": "توصيل", "تشحنون": "توصيل",
    "ادفع": "دفع", "الدفع": "دفع", "تقبلون": "يوجد", "تقبل": "يوجد", "يقبل": "يوجد", "نقبل": "يوجد", "payment": "دفع", "pay": "دفع", "مدي": "مدى", "كاش": "نقد",
    "نقدا": "نقد", "cash": "نقد", "ابل": "apple", "تابي": "tabby", "تمارا": "tamara",
    "ترجيع": "استرجاع", "ارجاع": "استرجاع", "ارجع": "استرجاع", "رجع": "استرجاع", "استبدال": "استرجاع", "refund": "استرجاع",
    "return": "استرجاع", "بدل": "استرجاع",
    # misc
    "زين": "جيد", "مو": "ليس", "مب": "ليس", "مهوب": "ليس", "شلون": "كيف", "كيفية": "كيف", "طريقه": "كيف",
    "اقدر": "يمكن", "نقدر": "يمكن", "ممكن": "يمكن", "يصير": "يمكن", "ينفع": "يمكن",
    "دكتور": "طبيب", "دكتوره": "طبيب", "الدكتور": "طبيب", "اطباء": "طبيب", "دكاتره": "طبيب",
    "منيو": "قائمه", "المنيو": "قائمه", "menu": "قائمه", "قايمه": "قائمه", "قائمتكم": "قائمه",
    "واتس": "واتساب", "whatsapp": "واتساب", "جوال": "رقم", "تلفون": "رقم", "هاتف": "رقم", "phone": "رقم",
    "اطفال": "طفل", "عيال": "طفل", "بزارين": "طفل", "ولد": "طفل",
    "سيارات": "سياره",
    # "do you do/sell/offer X?" verbs carry no topic
    "تسوون": "يوجد", "تسوي": "يوجد", "تبيعون": "يوجد", "تبيع": "يوجد", "تعالجون": "يوجد", "تعالج": "يوجد",
    "نوفر": "يوجد", "توفر": "يوجد", "نقدم": "يوجد", "تقدم": "يوجد", "تعطون": "يوجد",
    "الاكل": "اكل", "اكلكم": "اكل", "طعام": "اكل", "اطباق": "اكل", "طبق": "اكل", "وجبات": "اكل",
    # more Gulf phrasing
    "تاخذون": "سعر", "تاخذ": "سعر", "ياخذ": "مده", "تاخذه": "مده", "ببلاش": "مجاني", "مجانا": "مجاني", "مجانيه": "مجاني",
    "فاتحين": "تفتح", "لين": "حتي", "تستقبلون": "تستقبل", "يستقبل": "تستقبل", "نستقبل": "تستقبل",
    "عوايل": "عائلات", "عائليه": "عائلات", "عوائل": "عائلات", "ولايم": "ولائم", "عزيمه": "ولائم", "عزايم": "ولائم",
    "وليمه": "ولائم", "مناسبه": "ولائم", "مناسبات": "ولائم", "تستر": "عينه", "عينات": "عينه",
    "تقليد": "اصلي", "اصليه": "اصلي", "اصلية": "اصلي", "original": "اصلي", "genuine": "اصلي",
    "عرايس": "عروس", "عرسي": "عروس", "عرس": "عروس", "زواج": "عروس", "عربون": "عربون",
    "رجال": "رجال", "رجاليه": "رجال", "نسائي": "سيدات", "نساء": "سيدات", "حريم": "سيدات", "بنات": "سيدات",
    "شحنه": "توصيل", "الشحنه": "توصيل", "وصلت": "توصيل",
    # English
    "opening": "تفتح", "vegetarian": "نباتي", "vegan": "نباتي", "perfume": "عطر", "perfumes": "عطور",
    "insurance": "تامين", "cleaning": "تنظيف", "whitening": "تبييض", "haircut": "قص", "family": "عائلات",
    "shipping": "توصيل", "track": "تتبع", "tracking": "تتبع", "sample": "عينه", "samples": "عينه", "باركنق": "مواقف", "parking": "مواقف",
}
# Keys and values are compared after normalize(), so normalize them once (ئ→ي, ة→ه ...).
DIALECT = {normalize(k): normalize(v) for k, v in DIALECT.items()}
_PREFIXES = ("وبال", "فبال", "وال", "بال", "فال", "كال", "لل", "ال", "و", "ب", "ف", "ل")
_SUFFIXES = ("كم", "كن", "ها", "هم", "نا")
STOPWORDS = frozenset(normalize(w) for w in (
    "من على الى إلى عن هل ما ماذا كيف و او أو مع هذا هذه ذلك التي الذي لو يا انا انت احنا نحن هو هي "
    "لو سمحت سمحت الله يعطيك العافيه السلام عليكم مرحبا هلا اهلا شكرا طيب ابغى ابي اريد بس عشان علشان "
    "اذا عندي لكم لي لنا كان يكون ايضا كمان برضو ولا والا ام the a an is are of to in for and or what how do does can i you "
    "your we please hi hello").split())


def _canon(tok: str) -> str:
    if tok in DIALECT:
        return DIALECT[tok]
    for p in _PREFIXES:
        if tok.startswith(p) and len(tok) - len(p) >= 2:
            rest = tok[len(p):]
            if rest in DIALECT:
                return DIALECT[rest]
            if p in ("ال", "وال", "بال", "فال", "كال", "لل", "وبال", "فبال"):
                tok = rest
                break
    for s in _SUFFIXES:
        if tok.endswith(s) and len(tok) - len(s) >= 3 and tok[: -len(s)] in DIALECT:
            return DIALECT[tok[: -len(s)]]
    if tok in DIALECT:
        return DIALECT[tok]
    return tok


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


def terms(text: str) -> list[str]:
    """Canonical content terms (dialect mapped, stopwords dropped), in order."""
    out = []
    for t in tokens(text):
        if t in STOPWORDS:
            continue
        c = _canon(t)
        if c in STOPWORDS or len(c) < 2 and not c.isdigit():
            continue
        out.append(c)
    return out


def light_stem(term: str) -> str:
    """Light suffix strip for fuzzy matching (ية/يه, ات, ين, ون, ها, ه, ي), up to twice."""
    for _ in range(2):
        for s in ("يه", "ات", "ين", "ون", "ها", "ه", "ي"):
            if term.endswith(s) and len(term) - len(s) >= 3:
                term = term[: -len(s)]
                break
        else:
            break
    return term


def canonical_text(text: str) -> str:
    """Normalized + dialect-mapped text used as embedding input."""
    return " ".join(terms(text)) or normalize(text)
