# دليل إعداد بيانات التطبيقات — X (Twitter) و LinkedIn

> دليل عملي خطوة بخطوة لإنشاء بيانات الاعتماد (Credentials) الخاصة بالحسابات الرسمية
> لمنصة **النرجس للذكاء الاصطناعي | Karma AI** حتى نتمكن من نشر المنشورات تلقائياً
> عبر خدمة `src/services/social_publisher.py`.
>
> بعد إكمال كل قسم، ستحتاج إلى لصق القيم في **Render** عبر
> `Dashboard → Service → Environment → Add Environment Variable` أو تحديث `render.yaml`.

---

## جدول المراجع السريع

| المنصة | المتغيّرات في Render | الحالة |
|---|---|---|
| X (Twitter) | `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` | تطبيق Free |
| LinkedIn | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_ORG_ID` | تطبيق شركة + Marketing Developer Platform |

---

# الجزء الأول: حساب X (Twitter) — تطبيق API

> التوكنات هنا من نوع **OAuth 1.0a** (User Context): النشر يتم على حسابك الخاص مباشرة
> بدون الحاجة لـ OAuth 2.0 أو استدعاءات مصادقة متجددة.

## الخطوة 1: الدخول إلى منصة المطورين

1. افتح المتصفح وانتقل إلى: **developer.x.com**
2. اضغط **Sign in** وسجّل الدخول بحساب X الخاص بالمشروع.
   - يُنصح بأن يكون الحساب هو **الحساب الرسمي** لـ Karma AI (@KarmaAI_SA) وليس حسابه الشخصي.

## الخطوة 2: التقدّم بطلب حساب مطوّر (Developer Account)

1. من لوحة التحكم اضغط **Sign up for Free Account**.
2. اختر **Free tier** (الباقة المجانية):
   - تسمح بـ **1,500 تغريدة شهرياً** وقراءة محدودة.
3. املأ الغرض من الاستخدام (مثال بالعربية أو الإنجليزية):
   - *"أنشر المنشورات التسويقية لصفحة النرجس للذكاء الاصطناعي تلقائياً."*
4. اضغط **Submit** وانتظر البريد الإلكتروني من X للموافقة على الحساب.
   > الموافقة عادةً **فورية أو خلال 24 ساعة** للباقة المجانية.

## الخطوة 3: إنشاء المشروع والتطبيق (Project + App)

1. من لوحة المطورين اضغط **Projects & Apps**.
2. اضغط **+ New Project** ثم **+ New App**.
3. أدخل اسم التطبيق (مثال: `narjis-social-publisher`).
4. بعد إنشاء التطبيق، ادخل على صفحة التطبيق وانتقل إلى تبويبة **Keys and Tokens**.

## الخطوة 4: إنشاء المفاتيح (Keys & Tokens)

في تبويبة **Keys and Tokens** ستجد 4 قيم:

| القيمة | زر الإنشاء | المتغيّر في Render |
|---|---|---|
| **API Key** (Consumer Key) | موجودة مسبقاً | `X_CONSUMER_KEY` |
| **API Secret** (Consumer Secret) | موجودة مسبقاً | `X_CONSUMER_SECRET` |
| **Access Token** | اضغط **Generate** | `X_ACCESS_TOKEN` |
| **Access Token Secret** | اضغط **Generate** (يظهر مع الـ Access Token) | `X_ACCESS_TOKEN_SECRET` |

> ⚠️ **الـ API Secret و Access Token Secret يظهران مرة واحدة فقط.**
> انسخهما فوراً وخزّنهما في مكان آمن (مثل مدير كلمات المرور) ولا تشاركهما أبداً.

## الخطوة 5: ضبط صلاحيات التطبيق

1. في نفس الصفحة، انتقل إلى **User authentication settings → Edit**.
2. فعّل **Read and Write** (هذا ضروري جداً للنشر؛ بدونها ستفشل التغريدات برمز خطأ 403).
3. أعد توليد الـ Access Token بعد تغيير الصلاحيات إن طُلب منك.

## الخطوة 6: لصق القيم في Render

أضف المتغيّرات الأربعة إلى بيئة الخدمة على Render:

```
X_CONSUMER_KEY=<API Key>
X_CONSUMER_SECRET=<API Secret>
X_ACCESS_TOKEN=<Access Token>
X_ACCESS_TOKEN_SECRET=<Access Token Secret>
```

في `render.yaml` يمكن إضافتها بصيغة:

```yaml
      - key: X_CONSUMER_KEY
        sync: false
      - key: X_CONSUMER_SECRET
        sync: false
      - key: X_ACCESS_TOKEN
        sync: false
      - key: X_ACCESS_TOKEN_SECRET
        sync: false
```

> ✅ **تحقق:** بعد اللصق، شغّل من داخل بيئة المشروع:
> `python -m src.services.social_publisher`
> وابحث عن `"twitter": {"configured": true}`.

---

# الجزء الثاني: تطبيق LinkedIn Developer

> هنـا نستخدم **LinkedIn Marketing API** (OAuth 2.0) لنشر المنشورات
> على صفحة الشركة (Company Page) الخاصة بـ Karma AI.

## الخطوة 1: الدخول إلى منصة مطوّري LinkedIn

1. افتح المتصفح وانتقل إلى: **linkedin.com/developers**
2. اضغط **Sign in** بحساب LinkedIn الخاص بمدير صفحة الشركة.
   - يجب أن يكون الحساب **أدمن (Admin)** على صفحة الشركة حتى يتمكن التطبيق من النشر عليها.

## الخطوة 2: إنشاء تطبيق جديد

1. اضغط **Create App**.
2. املأ البيانات:

| الحقل | القيمة |
|---|---|
| **App Name** | Karma AI Social Publisher |
| **LinkedIn Page** | النرجس للذكاء الاصطناعي \| Karma AI |
| **Company** | النرجس للذكاء الاصطناعي \| Karma AI |
| **Privacy policy URL** | `https://karmaai.online/privacy` |
| **App Logo** | شعار النرجس |

3. اضغط **Create App** ووافق على **Terms of Service**.

## الخطوة 3: طلب صلاحية Marketing Developer Platform

1. افتح التطبيق وانتقل إلى تبويبة **Products**.
2. من القائمة، اضغط **Request access** بجانب:
   - **Marketing Developer Platform** (إلزامي للنشر على صفحات الشركة).
3. املأ نموذج الطلب: اشرح الغرض (مثال):
   - *"نشر المحتوى التسويقي تلقائياً على صفحة شركتنا النرجس للذكاء الاصطناعي."*
4. اضغط **Submit**.

> ⏳ **الانتظار:** تتم الموافقة خلال **1 – 3 أيام عمل**.
> البريد يأتي على بريد الحساب المطوّر. لا يمكن إكمال بقية الخطوات قبل الموافقة.

## الخطوة 4: نسخ Client ID و Client Secret

بعد الموافقة، انتقل إلى تبويبة **Auth**:

| القيمة | متغيّر Render (للمرجعية فقط) |
|---|---|
| **Client ID** | غير مطلوب في النشر التلقائي (يُستخدم للحصول على التوكن) |
| **Client Secret** | غير مطلوب في النشر التلقائي |

> في نظامنا، `LINKEDIN_ACCESS_TOKEN` فقط هو المطلوب عند التشغيل،
> لأن التوكن يُولَّد مسبقاً (انظر الخطوة التالية) بمدة صلاحية تصل لشهر.

## الخطوة 5: توليد Access Token (OAuth 2.0)

نحتاج توكن نطاق (scope):

```
w_member_social w_organization_social
```
(وقد يُضاف `r_liteprofile r_emailaddress` أثناء التفويض إن طلبه أدوات التفويض).

**الطريقة الأسهل — OAuth Playground:**
1. افتح **developer.linkedin.com → Tools → OAuth Playground**.
2. اختر تطبيق **Karma AI Social Publisher**.
3. اضغط **Request access token** وحدّد النطاقات:
   - `w_member_social` + `w_organization_social`
4. سجّل الدخول بحساب المدير وفوّض التطبيق.
5. انسخ **Access Token** الناتج.

> ⚠️ **صلاحية التوكن:** توكنات LinkedIn تدوم عادةً **60 يوماً** (شهر +).
> ضع تذكيراً في التقويم لتوليد توكن جديد قبل انتهاء الصلاحية، أو أضف عملية تجديد لاحقاً.

**الطريقة البرمجية (للتوثيق):** استبدال كود التفويض بالتوكن عبر:

```bash
curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
  -d grant_type=authorization_code \
  -d code=<CODE> \
  -d redirect_uri=<YOUR_REDIRECT_URI> \
  -d client_id=<CLIENT_ID> \
  -d client_secret=<CLIENT_SECRET>
```

## الخطوة 6: الحصول على معرف صفحة الشركة (Org URN)

1. افتح **linkedin.com/company/النرجس-لِلذكاء-الاصطناعي** أو حسابك → **Your Page**.
2. من شريط العنوان أو من إعدادات الصفحة احصل على **Company/Organization ID** الرقمي.
3. القيمة المطلوبة في المتغيّر `LINKEDIN_ORG_ID` هي **الرقم** فقط (مثال: `1234567890`).
   - خدمة النشر تدمجه تلقائياً بصيغة: `urn:li:organization:<رقم>`.

### طريقة بديلة للعثور على الرقم:
```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" \
  "https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee"
```
ابحث في النتيجة عن `organization` الرقمية ضمن قائمة الصفحات التي يديرها حسابك.

## الخطوة 7: لصق القيم في Render

```
LINKEDIN_ACCESS_TOKEN=<توكن OAuth 2.0>
LINKEDIN_ORG_ID=<معرّف صفحة الشركة الرقمي>
```

في `render.yaml`:

```yaml
      - key: LINKEDIN_ACCESS_TOKEN
        sync: false
      - key: LINKEDIN_ORG_ID
        sync: false
```

> ✅ **تحقق:** شغّل:
> `python -m src.services.social_publisher`
> وابحث عن `"linkedin": {"configured": true}` ليشير إلى جاهزية النشر.

---

# الجزء الثالث: بيئة Render كاملة

عند تجهيز كل ما سبق سيكون لديك في **Environment** على Render:

| المنصة | المتغيّر | مثال |
|---|---|---|
| X | `X_CONSUMER_KEY` | `AbCdEf123456...` |
| X | `X_CONSUMER_SECRET` | `xYz890...` |
| X | `X_ACCESS_TOKEN` | `1234567890-AbCd...` |
| X | `X_ACCESS_TOKEN_SECRET` | `QrStUv...` |
| LinkedIn | `LINKEDIN_ACCESS_TOKEN` | `AQVf...long-string...` |
| LinkedIn | `LINKEDIN_ORG_ID` | `4242424242` |

**ملاحظات عامة:**
- لا تضع القيم داخل كود المصدر أو تحفظها في `requirements.txt` أو تُرفع إلى Git.
- استخدم `sync: false` في `render.yaml` للقيم السرية حتى تبقى مخزّنة في Render فقط.
- بعد إعادة النشر، جرّب إرسال منشور تجريبي لصفحاتك قبل تشغيل الجدولة التلقائية.

---

# فحص جاهزية التشغيل

يمكنك من داخل سطر الأوامر التحقق من اكتمال الإعداد:

```bash
python -m src.services.social_publisher
```

النتيجة المتوقعة عند اكتمال كل شيء:

```json
{
  "linkedin": { "configured": true, "missing": [] },
  "twitter": { "configured": true, "missing": [] },
  "ready": true
}
```

وبذلك يصبح النظام قادراً على تنفيذ `publish_to_all()` لنشر المنشورات
على الحسابين في آنٍ واحد تلقائياً.