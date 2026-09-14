# دليل إعداد إعلانات Meta — حملة النرجس التوعوية

> خطوة بخطوة لإعداد حملة إعلانية على Facebook + Instagram
> الميزانية الشهرية: **250 ريال سعودي** (~8.3 ريال/يوم)
> Pixel ID: `1470684118222978`

---

## الخطوة 1: الدخول إلى Meta Ads Manager

1. افتح المتصفح وانتقل إلى: **adsmanager.facebook.com**
2. سجّل الدخول بنفس حساب Facebook الخاص بك
3. إذا لم يكن لديك حساب إعلانات، أنشئ واحداً أولاً من **business.facebook.com**

---

## الخطوة 2: إنشاء حملة جديدة

1. اضغط الزر الأزرق **"+ Create"** في أعلى اليسار
2. اختر **Objective: Traffic** (الزيارات)
   - السبب: هدف الحملة التوعوية هو إرسال الزوار إلى karmaai.online
3. اضغط **Continue**

---

## الخطوة 3: إعداد الحملة (Campaign Level)

- **Campaign Name:** حملة_النرجس_التوعوية_سبتمبر2026
- **Special Ad Categories:** لا شيء (لا إعلانات سياسية أو ائتمانية)
- **Campaign Budget Optimization (CBO):** **مفعّل**
  - الميزانية الشهرية: **250 SAR**
  - سيوزع Meta الميزانية تلقائياً بين Ad Sets الأفضل أداءً

---

## الخطوة 4: إعداد مجموعات الإعلانات (Ad Sets)

أنشئ **2 Ad Sets** كالتالي:

### Ad Set 1: أصحاب الأعمال في الرياض

| الإعداد | القيمة |
|---|---|
| **Ad Set Name** | أصحاب_أعمال_الرياض |
| **Locations** | Saudi Arabia → Riyadh (استهداف مدينة الرياض تحديداً) |
| **Age** | 25 – 45 |
| **Gender** | All |
| **Languages** | Arabic |
| **Detailed Targeting** | Entrepreneurs, Small business owners, Digital marketing, E-commerce |
| **Placements** | Manual Placements (المواضع اليدوية) |
| **Devices** | Mobile + Desktop |

### Ad Set 2: رواد الأعمال في الخليج

| الإعداد | القيمة |
|---|---|
| **Ad Set Name** | رواد_أعمال_الخليج |
| **Locations** | Saudi Arabia + UAE + Kuwait + Bahrain + Oman + Qatar |
| **Age** | 25 – 45 |
| **Gender** | All |
| **Languages** | Arabic |
| **Detailed Targeting** | Entrepreneurship, Startups, Artificial Intelligence, Small and medium-sized enterprises |
| **Placements** | Manual Placements |
| **Devices** | Mobile + Desktop |

---

## الخطوة 5: المواضع الإعلانية (Placements)

فعّل المواضع الإعلانية التالية لكلا الـ Ad Sets:

| الموضع الإعلاني | مفعل/معطّل |
|---|---|
| Facebook Feed | ✅ مفعل |
| Facebook Reels | ❌ معطّل |
| Facebook Stories | ✅ مفعل |
| Instagram Feed | ✅ مفعل |
| Instagram Reels | ✅ مفعل |
| Instagram Stories | ✅ مفعل |
| Instagram Explore | ❌ معطّل |
| Messenger Inbox | ❌ معطّل |
| Audience Network | ❌ معطّل |

> السبب: نركز على Feed و Reels و Stories لأنها أعلى تفاعلاً للجمهور السعودي

---

## الخطوة 6: رفع الإعلان (Ad Level)

لكل Ad Set، أنشئ إعلاناً واحداً على الأقل:

1. اضغط **"+ Create Ad"** داخل الـ Ad Set
2. **Identity:** اختر صفحة Facebook + حساب Instagram الخاص بالمشروع
3. **Ad Format:** اختر من القائمة التالية (حسب الإعلانات الخمسة في `ad-copies.md`):

| الإعلان | الصيغة |
|---|---|
| إعلان 1 (نقطة الألم) | Single Image |
| إعلان 2 (الفضول) | Video / Reels |
| إعلان 3 (FOMO) | Carousel |
| إعلان 4 (النتيجة) | Single Image |
| إعلان 5 (المؤسس) | Video |

4. **Primary Text:** انسخ النص العربي من `ad-copies.md`
5. **Headline:** مثال: "فريق ذكي لتسويق مشروعك"
6. **Description:** "جرّب الآن مع كود NARJIS50 — خصم 50%"
7. **Website URL:** `https://karmaai.online`
8. **CTA Button:** **Learn More**

---

## الخطوة 7: إعداد Facebook Pixel

يجب تفعيل الـ Pixel على موقعك لمتابعة التحويلات:

### تثبيت Pixel على karmaai.online

**الطريقة 1: كود يدوي**
1. اذهب إلى **Events Manager** في Business Manager
2. اختر الـ Pixel الخاص بك
3. اضغط **Settings** → **Install Code Manually**
4. انسخ الكود وألصقه في قسم `<head>` في صفحة الهبوط

```html
<!-- Facebook Pixel Code -->
<script>
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '1470684118222978');
fbq('track', 'PageView');
fbq('track', 'ViewContent');
</script>
<noscript>
<img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id=1470684118222978&ev=PageView&noscript=1"/>
</noscript>
<!-- End Facebook Pixel Code -->
```

**الطريقة 2: عبر Google Tag Manager**
1. اذهب إلى **Events Manager** → **Custom Conversions**
2. أنشئ custom event على رابط karmaai.online
3. استخدم GTM لإضافة الـ Pixel code

**التحقق من التثبيت:**
- نزّل إضافة **Facebook Pixel Helper** من Chrome
- افتح karmaai.online وتأكد أن الـ Pixel يظهر بـID: `1470684118222978`
- يجب أن يظهر **2 fired events**: PageView + ViewContent

---

## الخطوة 8: قراءة النتائج

### المؤشرات الرئيسية

| المؤشر | الوصف | الهدف المقترح |
|---|---|---|
| **Impressions** | عدد مرات عرض الإعلان | 5,000+/شهر |
| **Reach** | عدد الأشخاص الفريدين الذين رأوا الإعلان | 2,000+/شهر |
| **Link Clicks** | عدد النقرات على الرابط إلى karmaai.online | 200+/شهر |
| **CTR (Click-Through Rate)** | نسبة النقرات إلى عدد مرات العرض | 1.5%+ |
| **Cost per Click (CPC)** | تكلفة كل نقرة بالريال | أقل من 1.5 SAR |
| **Conversions** | عدد التسجيلات من الإعلان | 20+/شهر |

### كيفية الوصول إلى البيانات

1. اذهب إلى **Meta Ads Manager**
2. اضغط على اسم الحملة → ثم Ad Set → ثم Ad
3. اضغط **Columns: Performance and Clicks**
4. غيّر الفترة الزمنية إلى **Last 7 Days** أو **Last 30 Days**
5. صدّر البيانات كـ CSV للتحليل

---

## الخطوة 9: التحسين التدريجي (Optimization) أسبوع بأسبوع

### الأسبوع 1 (الأسبوع الأول)
- **الخوارزمية:** لا تُعدّل أي شيء — دع الخوارزمية تجمع بيانات
- **المراقبة:** راقب CTR و CPC فقط
- **الهدف:** جمع 1000+ impression لكل Ad Set
- **ملاحظة:** الإعلانات تحتاج 3–5 أيام للتعلم (Learning Phase)

### الأسبوع 2 (الأسبوع الثاني)
- **تحليل النتائج:** مقارنة CTR بين الإعلانات الخمسة
- **التحسين:**
  - أوقف الإعلانات ذات CTR أقل من 0.8%
  - زد ميزانية الإعلانات الأعلى أداءً (CTR أعلى من 2%)
  - عدّل العناوين إذا كان CTR ضعيفاً
- **الهدف:** خفض CPC أقل من 1.5 SAR

### الأسبوع 3 (الأسبوع الثالث)
- **توسيع الاستهداف:** أضف Ad Set جديد بجمهور أوسع
- **اختبار:** أضف نسخة جديدة من الإعلان مع نص مختلف (A/B Testing)
- **الهدف:** تحسين Conversion Rate
- **ملاحظة:** راجع إذا كان الـ Pixel يلتقط التسجيلات بشكل صحيح

### الأسبوع 4 (الأسبوع الرابع)
- **التقييم الشامل:** قارن النتائج مع KPIs
- **القرار:**
  - إذا النتائج جيدة → استمرار بنفس الخوارزمية
  - إذا النتائج متوسطة → تحسين الخوارزمية والمحتوى
  - إذا النتائج ضعيفة → أعد تصميم الإعلانات واختبار جمهور جديد
- **التخطيط:** ابدأ تحضير حملة الشهر القادم

---

## ملاحظات مهمة

- **لا تُعدّل الخوارزمية خلال Learning Phase** (أول 3–5 أيام) — هذا يُعيد الخوارزمية من الصفر
- **Minimum Budget:** لا تنقص عن 50 SAR لكل Ad Set
- **Frequency:** إذا وصلت تكرار الإعلان أكثر من 3 مرات للشخص الواحد، أوقفه أو غيّر الخوارزمية
- **Creative Fatigue:** إذا انخفض CTR بنسبة 20%+، أظهر مواد إعلانية جديدة
- **Firebase أو أي أداة تحليلات أخرى:** تأكد من تثبيتها لتتبع التحويلات من الإعلان إلى التسجيل في karmaai.online
