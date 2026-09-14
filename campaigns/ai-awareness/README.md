# حملة التوعية — النرجس (karmaai.online)

حملة توعوية عن الذكاء الاصطناعي لأعمال الخليج → السعودية → **الرياض**،
باسم المؤسس **محمد الهاشمي** وإشارة **karmaai.online**، تُنتج ببساطة

## التوليد

```bash
python campaigns/ai-awareness/generate_week.py [week] [model]
# مثال: الباقة الأسبوع 1 بالموديل الافتراضي gemini-3.6-flash
python campaigns/ai-awareness/generate_week.py 1
```

الناتج يُحفظ في `packs/week-NN/`:

| الملف | المحتوى |
|---|---|
| `linkedin_post.md` | منشور لينكدإن عربي طويل |
| `twitter_posts.md` | 5 تغريدات قصيرة |
| `email_newsletter.md` | نشرة أسبوعية |
| `video_script_60s.md` | سكربت ريلز 60 ثانية كامل |
| `carousel_outline.md` | كاروزيل تعليمي 5 شرائح |
| `manifest.json` | بيانات الباقة |

## المصادر

- الـ config: `config.json` (الجمهور، الأماكن، الركائز، 8 قوائم أسابيع).
- الاستراتيجية الكاملة: `STRATEGY.md`.
- الإيجنتس المستخدمة هي نفس إيجنتس المنصة: `agents/base/content_writer.yaml`,
  `social_media.yaml`, `marketing_agent.yaml`, `localization.yaml`
  والموديل `gemini-3.6-flash` (المفترض من `.env` = `GEMINI_API_KEY`).

## ملاحظات

- راجع كل منشور قبل النشر (دقة، هوية، هاشتاجات).
- النشر يدوي في القنوات الآن؛ النشرة عبر Brevo عندما تتوفر القائمة البريدية.