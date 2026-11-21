# ما يفعله المالك لتفعيل المتاجر وواتساب والنموذج

هذا الملف يصف إعدادات بيئة Render وتطبيقات الشركاء. لا تُكتب الأسرار في المستودع ولا في المحادثة. القيم تُلصق في لوحة Render فقط.

## موجز الرئيس التنفيذي

المسار يعمل بدون مفتاح نموذج: العميل على `/brief` يصف الفكرة، يُسأل عما ينقص، يعتمد الموجز، وتُحفظ مسودة تصرّح أنها لم تُستدعَ من نموذج.

ليكتب المختصون نصاً من النموذج:

1. ضع `GEMINI_API_KEY` في بيئة Render (موجود أصلاً في الإعدادات إن كان الموقع يرد اليوم).
2. لا متغير جديد. إن غاب المفتاح أو فشل المزود تبقى المسودة التوضيحية، ويظهر للمالك في `/acquisition` مصدر `ceo_brief` ومرحلة الموجز.

الجدول `customer_engagements` يُنشأ عند إقلاع التطبيق. ترحيل Alembic `0020` نسخة مطابقة لمن يشغّل `alembic upgrade`.

## واتساب

الكود يفتح سجل CRM بمصدر `whatsapp` للمرسل غير المعروف، ويحوّل الرسالة غير المطابقة أو ذات نية الشراء إلى متابعة بشرية (مهمة للمالك، بدون رد آلي).

لا سر جديد. تأكد في Render أن هذه الأسماء مضبوطة على حساب واتساب التجاري الذي ينتهي رقمه بـ 8753:

- `WHATSAPP_TOKEN`
- `WHATSAPP_PHONE_ID`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN`

في لوحة ميتا، عنوان الإشعار هو `https://alnarjisai.com/webhooks/whatsapp` (وليس مساراً بلا `webhooks`). الرقم `0552978753` ظاهر على الرئيسية وصفحة التواصل وصفحة الصوت.

## سلة وزد

الكود موجود ويبقى مغلقاً حتى تكتمل البنود التالية. لا يُعرض الربط كجزء من الباقة العامة قبل ذلك. بعد الربط يُفتح سجل في CRM بمصدر `salla` أو `zid` ومتابعة على المالك ووكيل إدارة المتجر.

### قيم Render (لا تُرسل هنا)

- `STORE_INTEGRATIONS_ENABLED=true`
- `STORE_TOKEN_ENC_KEY` مفتاح Fernet مستقل. لا يُشتق من `SECRET_KEY`. يُولَّد محلياً ويُلصق في Render.
- `STORE_TOKEN_ENC_KEY_ID=1`
- `SALLA_CLIENT_ID`
- `SALLA_CLIENT_SECRET`
- `SALLA_WEBHOOK_SECRET`
- `SALLA_REDIRECT_URI=https://alnarjisai.com/webhooks/stores/salla/callback`
- `ZID_CLIENT_ID`
- `ZID_CLIENT_SECRET`
- `ZID_WEBHOOK_SECRET`
- `ZID_REDIRECT_URI=https://alnarjisai.com/webhooks/stores/zid/callback`
- `ZID_WEBHOOK_ALLOW_UNSIGNED` اتركه `false` إلا إذا كان تطبيق زد يرسل ترويسة ثابتة بلا توقيع جسم الرسالة.
- `STORE_WEBHOOK_MAX_AGE_SECONDS` اختياري، الافتراضي 900.

### تطبيق سلة (Salla Partners)

1. أنشئ تطبيقاً بصلاحيات القراءة فقط: `offline_access` و`orders.read` و`products.read` و`settings.read`. الكود يطلب هذه الصلاحيات ولا يطلب الكتابة.
2. عنوان إعادة التوجيه: `https://alnarjisai.com/webhooks/stores/salla/callback`
3. عنوان الإشعار: `https://alnarjisai.com/webhooks/stores/salla`
4. سر الإشعار هو قيمة `SALLA_WEBHOOK_SECRET` (توقيع `X-Salla-Signature`).
5. انسخ معرّف العميل وسرّه إلى `SALLA_CLIENT_ID` و`SALLA_CLIENT_SECRET`.
6. التطبيق يحتاج أن يكون قابلاً للتثبيت على متجر تجريبي. مسودة خاصة لا يركّبها تاجر لن تظهر كربط ناجح.

### تطبيق زد (Zid Partners)

1. الصلاحيات تُختار في لوحة الشريك لا في رابط التفويض: `orders.read` و`products.read` و`third_store_details_read`.
2. عنوان إعادة التوجيه: `https://alnarjisai.com/webhooks/stores/zid/callback`
3. عنوان الإشعار: `https://alnarjisai.com/webhooks/stores/zid`
4. مصادقة الإشعار: Basic بالمستخدم `narjis` وكلمة السر هي `ZID_WEBHOOK_SECRET`، أو ترويسة `X-Zid-Signature` بتوقيع HMAC لجسم الطلب.
5. انسخ معرّف العميل وسرّه إلى `ZID_CLIENT_ID` و`ZID_CLIENT_SECRET`.

### بعد الحفظ

1. أعد نشر خدمة Render حتى تُقرأ المتغيرات.
2. من بوابة عميل اشتراكه `active` يظهر صندوق الربط (يختفي ما دام العلم مغلقاً).
3. ثبّت التطبيق على متجر تجريبي، لا على متجر عميل حقيقي في أول تجربة.
4. في `/acquisition` يظهر السجل بالمصدر `salla` أو `zid` وبمتابعة مستحقة للمالك.

فحص الصحة الحالي للموقع يبقى `GET /webhooks/telegram/health`. مسار المتاجر يرجع 404 ما دام `STORE_INTEGRATIONS_ENABLED` مغلقاً أو `STORE_TOKEN_ENC_KEY` فارغاً.
