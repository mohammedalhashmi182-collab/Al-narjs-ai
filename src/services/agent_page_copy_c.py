"""Public agent pages, third group."""

from __future__ import annotations


def register(put, faq) -> None:
    put(
        "content_writer",
        (
            "كاتب المحتوى يصيغ نصًا واحدًا لغرض واحد: منشور، أو صفحة خدمة، أو نبذة قصيرة. قبل الكتابة نحدد المنصة، والقارئ، والفعل بعد القراءة، والحقائق التي يجب أن تظهر كما هي. النص الذي يحاول أن يبيع ويعرّف ويعتذر في الفقرة نفسها يُقسَّم أو يُعاد.",
            "الحقائق مصدرها ما كتبه صاحب النشاط. لا نضيف شهادة، ولا عدد عملاء، ولا سنة خبرة لم تُذكر. إذا كانت اللهجة مطلوبة، نكتب بها من غير أن نكسر المعنى. إذا طُلبت الفصحى، نبقى عليها حتى في المثال. الخلط بين الاثنين في النص نفسه يربك القارئ.",
            "الطول يناسب المكان. منشور ليس مقالًا، وصف خدمة ليس إعلان خصم. نسلم مسودة وعنوانًا داخليًا يشرح الغرض حتى يعرف المراجع ماذا يقرأ. الملاحظات على الهامش تذكر أي جملة حُذفت ولماذا، لا مدحًا للنص.",
            "النشر ليس من هذه الصفحة. بعد الموافقة ينتقل النص إلى مدير الحسابات إن كان منشورًا، أو يبقى عند صاحب النشاط إن كان صفحة. كاتب المقالات يتولى النص الطويل الذي يحتاج هيكلًا ومصادرًا. هنا النص أقصر ومهمته أوضح.",
        ),
        (
            "The content writer drafts one text for one purpose: a post, a service page, or a short profile. Before writing, we name the place it will sit, the reader, the action after reading, and the facts that must appear unchanged. A text that tries to sell, explain, and apologise in the same paragraph is split or rewritten.",
            "Facts come from what the owner wrote. We do not add a testimonial, a customer count, or years of experience that were not stated. If dialect is requested, we write in it without breaking the meaning. If formal Arabic is requested, we stay there, including in the example. Mixing the two inside one text confuses the reader.",
            "Length matches the place. A post is not an article, and a service description is not a discount ad. We deliver a draft and an internal label that states the purpose, so the reviewer knows what they are reading. Margin notes say which sentence was cut and why. They do not praise the draft.",
            "Publishing is not done from this page. After approval, a post can move to the account manager. A page stays with the owner. The article writer handles a long piece that needs a structure and sources. Here the text is shorter and the job is plainer.",
        ),
        "لنفترض صفحة قصيرة لخدمة صيانة مكيفات في الدمام. صاحب النشاط يكتب: الزيارة داخل الدمام، والمعاينة قبل أي قطعة، ولا ضمان مكتوب بعد. المسودة تشرح ترتيب الزيارة والمعاينة، وتذكر أن الضمان غير مذكور فلا يُكتب. لا جملة عن أرخص سعر، ولا عن عدد عملاء. الطول يكفي لقراءة هاتف لا لمقال.",
        "Suppose a short page for air-conditioner maintenance in Dammam. The owner writes: visits are inside Dammam, inspection comes before any part, and no written warranty exists yet. The draft explains the visit order and the inspection, and it says a warranty is not on file so none is written. There is no line about the cheapest price or a customer count. The length fits a phone screen, not an article.",
        faq(
            ("هل تنشرون النص؟", "لا. المسودة تُراجع أولًا. النشر قرار صاحب النشاط."),
            ("هل تضيفون أرقامًا؟", "لا. ما لم يكتبه صاحب النشاط لا يدخل النص."),
            ("ما الفرق عن كاتب المقالات؟", "هنا نص قصير لغرض واحد. المقال أطول ويحتاج هيكلًا."),
        ),
        faq(
            ("Do you publish the text?", "No. The draft is reviewed first. Publishing is the owner's decision."),
            ("Do you add figures?", "No. What the owner did not write does not enter the text."),
            ("How is this different from the article writer?", "Here the text is short and has one job. An article is longer and needs a structure."),
        ),
    )
    put(
        "article_writer",
        (
            "كاتب المقالات يبني نصًا طويلًا يمكن قراءته من غير أن يضيع القارئ. الهيكل يُقترح قبل الكتابة: ما السؤال الذي يجيب عنه المقال، وما الذي لن يجيب عنه، وأي فقرة تحتاج مصدرًا من صاحب النشاط. مقال من غير سؤال واضح يصبح صفحة عامة عن المجال.",
            "كل ادّعاء عام يُعلَّم. إذا لم يملك صاحب النشاط مصدرًا، تُحذف العبارة أو تُكتب بوصفها رأيًا له إن أراد ذلك صراحة. لا ننسب جملة إلى جهة، ولا نذكر دراسة، ولا نضع سنة تأسيس لم تُذكر. الأمثلة داخل المقال تُوسم بأنها توضيح للطريقة، لا تجارب عملاء.",
            "العربية تُراجع من حيث التركيب والربط. العنوان يعد بما في المتن، لا بأكثر منه. الخاتمة تطلب خطوة واحدة يستطيع القارئ فعلها، أو تلخص الحد الذي لا يتجاوزه المقال. لا خاتمة تحث على الشراء إن كان المقال شرحًا.",
            "المقال لا يُنشر من هنا على المدونة تلقائيًا. صاحب النشاط يراجع الأسماء والأرقام. إن طُلب تحسين الظهور في البحث، تُحال الكلمات إلى خبير البحث بعد أن يثبت المتن، حتى لا تُحشى الفقرة بعبارات لا تخدم الشرح.",
        ),
        (
            "The article writer builds a long text a reader can finish without getting lost. The structure is proposed before the draft: which question the article answers, which question it will not answer, and which paragraph needs a source from the owner. An article with no clear question becomes a generic page about the field.",
            "Every broad claim is marked. If the owner has no source, the sentence is cut or written as their own view only when they ask for that explicitly. We do not attribute a line to an organisation, cite a study, or insert a founding year that was not given. Examples inside the article are labelled as illustrations of the method, not as client stories.",
            "The Arabic is checked for structure and connection. The title promises what the body contains, and no more. The ending asks for one step the reader can take, or it states the limit the article will not cross. An explanatory article does not end with a push to buy.",
            "The article is not published to the blog automatically from here. The owner reviews names and figures. If search visibility is requested, keywords go to the SEO expert after the body is stable, so the paragraph is not stuffed with phrases that do not help the explanation.",
        ),
        "لنفترض مقالًا لصاحب مغسلة عن كيف يجهّز العميل الملابس قبل التسليم. السؤال: ماذا يحضّر العميل حتى لا تتوقف المغسلة. المقال يشرح فرز الألوان، وإفراغ الجيوب، وذكر البقعة. لا يذكر نسبة عملاء راضين، ولا يقارن بمغسلة أخرى. الخاتمة تطلب من القارئ إرسال ملاحظة واحدة مع الطلب، لا الاشتراك في باقة.",
        "Suppose an article for a laundry owner about how a customer prepares clothes before drop-off. The question is what the customer should prepare so the laundry does not stop. The article explains sorting colours, emptying pockets, and naming a stain. It cites no satisfaction rate and compares no other laundry. The ending asks the reader to send one note with the order, not to subscribe to a plan.",
        faq(
            ("هل تنشرون المقال على المدونة؟", "لا تلقائيًا. المسودة تُراجع ثم يقرر صاحب النشاط أين تُنشر."),
            ("هل تستشهدون بدراسات؟", "لا ننسب جملة إلى جهة ولم يقدّم صاحب النشاط مصدرها."),
            ("هل المقال إعلان؟", "لا، إلا إذا كان المطلوب إعلانًا صريحًا. الشرح لا يتحول إلى حث على الشراء في الخاتمة."),
        ),
        faq(
            ("Do you publish the article on the blog?", "Not automatically. The draft is reviewed, then the owner decides where it goes."),
            ("Do you cite studies?", "We do not attribute a sentence to an organisation when the owner did not supply the source."),
            ("Is the article an ad?", "No, unless an ad was explicitly requested. An explanation does not turn into a sales push at the end."),
        ),
    )
    put(
        "content_manager",
        (
            "مدير المحتوى يجمع ما سيُنشر في فترة محددة ويرتبه، لا يكتب كل النصوص بنفسه. المدخل: القنوات، وعدد القطع التي يستطيع الفريق مراجعتها فعلًا، والمناسبات المعروفة في هذه الفترة، وما الذي مُنع. التقويم الناتج يسمي لكل خانة الغرض والمالك والمادة الناقصة.",
            "الخانة الفارغة أفضل من خانة بوعد لا مادة له. إذا كان الأسبوع بلا صور، نقلل العدد ولا نخترع موضوعات تحتاج تصويرًا. إذا تداخلت مناسبة عامة مع عرض المتجر، نفصل بينهما حتى لا يبتلع العرض المناسبة أو العكس.",
            "التقويم لا يعتمد النشر. هو أداة للمراجعة الأسبوعية: ما اكتمل، وما تأخر، وما يُلغى لأن العرض تغيّر. الإلغاء يُكتب سببه حتى لا يعود البند في الأسبوع التالي بالخطأ.",
            "الكتابة تُحال إلى كاتب المحتوى أو كاتب المقالات، والرزنامة اليومية إلى مدير الحسابات إن كانت القناة حسابًا. مدير المحتوى يراقب ألا يعدّ تقويم البريد بما يعدّ به تقويم المنصة. التعارض يُرفع لصاحب النشاط قبل الاعتماد.",
        ),
        (
            "The content manager gathers what will be published in a set period and orders it. The manager does not write every text. The input is the channels, how many pieces the team can actually review, the known occasions in that period, and what is banned. The calendar names, for each slot, the purpose, the owner, and the missing material.",
            "An empty slot is better than a slot with a promise and no material. If the week has no photos, the count goes down. We do not invent topics that need a shoot. If a public occasion overlaps a shop offer, they are separated so the offer does not swallow the occasion, or the reverse.",
            "The calendar does not approve publishing. It is a tool for a weekly review: what is done, what is late, and what is cancelled because the offer changed. A cancellation records its reason so the item does not return next week by mistake.",
            "Writing goes to the content writer or the article writer. A daily social calendar goes to the account manager when the channel is an account. The content manager watches that the email calendar does not promise what the social calendar promises differently. A clash goes to the owner before approval.",
        ),
        "لنفترض عيادة تريد تقويم أسبوعين: تذكير بمواعيد، وشرح خدمة واحدة، ومنع لأي نص عن نتائج علاج. الطاقة مراجعتان في الأسبوع. التقويم يضع أربع خانات فقط، كل خانة بمالك ومادة. أسبوع العيد يُترك أخف، ولا تُنسخ خانات أسبوع عادي إليه. لا خانة عن خصم لأن الخصم غير مذكور.",
        "Suppose a clinic wants a two-week calendar: appointment reminders, an explanation of one service, and a ban on any text about treatment results. The team can review two pieces a week. The calendar places only four slots, each with an owner and the material. The holiday week stays lighter. Ordinary-week slots are not copied into it. There is no discount slot, because no discount was stated.",
        faq(
            ("هل التقويم يعني أن النشر تم؟", "لا. هو خطة مراجعة. النشر بعد اعتماد كل قطعة."),
            ("من يكتب النصوص؟", "كاتب المحتوى أو كاتب المقالات حسب الطول. هنا ترتيب لا صياغة."),
            ("ماذا لو تغيّر العرض؟", "تُلغى الخانات المتأثرة ويُكتب سبب الإلغاء."),
        ),
        faq(
            ("Does a calendar mean the posts went out?", "No. It is a review plan. Publishing follows approval of each piece."),
            ("Who writes the texts?", "The content writer or the article writer, depending on length. This role orders, it does not draft everything."),
            ("What if the offer changes?", "Affected slots are cancelled and the reason is written down."),
        ),
    )
    put(
        "market_analyst",
        (
            "محلل السوق يرتب ما نعرفه عن نشاط وقطاعه مما يقدّمه صاحب النشاط، ويفصل ذلك عما لا نعرفه. لا تقرير بسعة سوق ولا بنسبة نمو من غير مصدر يلصقه صاحب النشاط أو يوافق على أنه تقديره هو. التقدير يُوسم بكلمة تقدير، والحقيقة تُوسم بكلمة وارد في المصدر.",
            "الأسئلة التي تُطلب: من المشتري، وما البديل الذي يقارن به، وما القيد في المدينة أو في التنظيم إن كان صاحب النشاط يعرفه. الإجابة المجهولة تبقى مجهولة. ملء الفراغ برقم مستدير يجعل التقرير أسوأ لا أكمل.",
            "المخرج ملاحظات مرتبة: ما الذي يدعم العرض الحالي، وما الذي يهدده إن تغيّر سعر أو توفر، وما السؤال الذي يستحق أن يُسأل قبل قرار. لا توصية بأن يتوسع النشاط إلى مدينة لأن مدينة أخرى نجحت في حكاية لا مصدر لها.",
            "هذا التحليل ليس دراسة جدوى بنكية، ولا يغني عن محلل منافسين إذا كان السؤال عن متجر بعينه. الأرقام الحسابية للسعر والتكلفة تذهب إلى محلل المالية. هنا السياق، لا معادلة الهامش.",
        ),
        (
            "The market analyst orders what is known about a business and its field from what the owner supplies, and separates that from what is not known. There is no market-size figure and no growth rate without a source the owner pastes, or without labelling the figure as the owner's own estimate. An estimate is marked as an estimate. A fact is marked as stated in the source.",
            "The questions we ask: who buys, what alternative they compare with, and what constraint in the city or the rules the owner already knows. An unknown answer stays unknown. Filling the gap with a round number makes the note worse, not more complete.",
            "The output is ordered notes: what supports the current offer, what threatens it if a price or availability changes, and which question is worth asking before a decision. There is no recommendation to expand into a city because some other city succeeded in a story with no source.",
            "This is not a bank feasibility study, and it does not replace the competitor analyst when the question is about one named shop. Price and cost arithmetic goes to the finance analyst. Here the subject is context, not a margin formula.",
        ),
        "لنفترض مخبزًا يريد أن يعرف إن كان يفتح فرعًا ثانيًا في الحي نفسه. هو يكتب أن الفرع الحالي يزدحم عصر الخميس، وأن الإيجار المقترح يعرفه، ولا يملك عدد السكان. الملاحظة تقول إن الزحام في هذه العينة ملاحظة تشغيل لا دليل طلب دائم، وإن عدد السكان غير معروف فلا يُستخدم، وإن القرار يحتاج تكلفة الإيجار من محلل المالية لا من هذا التقرير.",
        "Suppose a bakery wants to know whether to open a second branch in the same district. The owner writes that the current branch is crowded on Thursday afternoons, that they know the proposed rent, and that they do not have a population figure. The note says the crowd in this sample is an operating observation, not proof of lasting demand, that population is unknown and will not be used, and that the rent decision needs the finance analyst, not this note.",
        faq(
            ("هل تذكرون حجم السوق؟", "فقط إذا لصق صاحب النشاط مصدرًا أو سمى الرقم كتقديره. وإلا يبقى الحقل فارغًا."),
            ("هل هذا دراسة جدوى؟", "لا. ملاحظات مرتبة عما نعرف وما لا نعرف. ليست ملفًا بنكيًا."),
            ("من يحسب الربح؟", "محلل المالية والتسعير. هنا لا تُحسب الهوامش."),
        ),
        faq(
            ("Do you state a market size?", "Only if the owner pastes a source or names the figure as their own estimate. Otherwise the field stays empty."),
            ("Is this a feasibility study?", "No. It is ordered notes on what is known and unknown. It is not a bank file."),
            ("Who calculates profit?", "The finance and pricing analyst. Margins are not calculated here."),
        ),
    )
    put(
        "competitor_analyst",
        (
            "محلل المنافسين يقارن ما يمكن لصاحب النشاط أن يراه في عرض منافس سمّاه، لا سمعة السوق كلها. المدخل قائمة قصيرة: من المنافس، وما الصفحة أو العرض الذي ننظر إليه، وما الذي يريد صاحب النشاط فهمه: السعر الظاهر، أو الوعد، أو ما ينقص في الشرح. من غير هذه الحدود يصبح التقرير انطباعًا.",
            "كل ملاحظة تُربط بما شاهده صاحب النشاط أو لصقه. لا ننقل تقييمات النجوم، ولا نختلق شكوى عميل، ولا نقول إن المنافس الأضعف. إن غاب السعر نكتب أن السعر غير ظاهر. المقارنة جدول صغير: بند، ما عندكم، ما ظهر عندهم، وما لا نعرف.",
            "التوصية التالية عملية: وضّحوا بندًا غامضًا عندكم، أو لا تنافسوا على جملة لا تستطيعون الوفاء بها. لا توصية بنسخ عرض المنافس. النسخ ينقل مشكلته أيضًا.",
            "هذا ليس تجسسًا ولا دخولًا إلى حسابات. المعلومات العلنية التي يلصقها صاحب النشاط فقط. أي رقم داخلي عن مبيعات المنافس لا مكان له لأنه لا يصل إلينا بطريقة مشروعة من هذه الصفحة.",
        ),
        (
            "The competitor analyst compares what the owner can see in an offer from a competitor they named, not the reputation of the whole market. The input is a short list: who the competitor is, which page or offer we are looking at, and what the owner wants to understand: the visible price, the promise, or a gap in the explanation. Without those limits the note becomes an impression.",
            "Each observation is tied to what the owner saw or pasted. We do not import star ratings, invent a customer complaint, or say the competitor is weaker. If the price is missing, we write that the price is not visible. The comparison is a small table: the item, what you have, what appeared on their side, and what we do not know.",
            "The next suggestion is practical: clarify a vague item on your side, or do not compete on a sentence you cannot keep. There is no suggestion to copy the competitor's offer. Copying carries their problem too.",
            "This is not spying and not access to accounts. Only public information the owner pastes. An internal figure about a competitor's sales has no place here, because this page has no proper way to receive it.",
        ),
        "لنفترض متجر عبايات يقارن صفحتين لمنافس سمّاه. هو يلصق أن المنافس يظهر مدة التفصيل بينما صفحته لا تظهرها، وأن السعر عند المنافس غير ظاهر. الجدول يذكر هذه النقطتين فقط. التوصية: أضيفوا مدة التفصيل عندكم إن كانت ثابتة لديكم، ولا تكتبوا سعرًا للمنافس. لا عبارة عن جودة أعلى.",
        "Suppose an abaya shop compares two pages of a competitor it named. The owner pastes that the competitor shows tailoring time while their own page does not, and that the competitor's price is not visible. The table records only those two points. The suggestion is: add your tailoring time if it is actually fixed, and do not write a price for the competitor. There is no line about higher quality.",
        faq(
            ("هل تجمعون تقييمات العملاء؟", "لا. لا ننقل نجومًا ولا نختلق شكاوى."),
            ("ماذا لو لم يظهر السعر؟", "نكتب أن السعر غير ظاهر. لا نقدّره."),
            ("هل ننصح بنسخ عرض المنافس؟", "لا. المقارنة توضّح فرقًا يمكنكم سدّه بصدق، لا عرضًا تُنسخ جملته."),
        ),
        faq(
            ("Do you collect customer ratings?", "No. We do not import stars or invent complaints."),
            ("What if the price is not shown?", "We write that the price is not visible. We do not estimate it."),
            ("Do you recommend copying a competitor's offer?", "No. The comparison shows a gap you can close honestly, not a sentence to copy."),
        ),
    )
    put(
        "business_ideas",
        (
            "مستشار أفكار المشاريع يساعد صاحب مهارة أو ميزانية محدودة أن يرى أفكارًا يمكن البدء بها، لا قائمة أحلام. المدخل: ما الذي يعرفه الشخص أن يعمله، والوقت الأسبوعي، والمبلغ الذي يستطيع خسارته من غير أن يتوقف معاشه، والمدينة. الفكرة التي تحتاج رأس مال أكبر من هذا المبلغ تُستبعد أو تُؤجل صراحة.",
            "كل فكرة تُكتب مع أول خطوة هذا الأسبوع، ومع ما ينقص، ومع السبب الذي قد يجعلها غير مناسبة. لا نرتب الأفكار بحسب الربح المتوقع لأن الربح غير محسوب هنا. الترتيب بحسب قربها من مهارة الشخص ومن قيد الوقت.",
            "لا فكرة مبنية على وعد حكومي أو على مناقصة لم تُذكر. لا اسم شريك مقترح. إذا كانت الفكرة تحتاج ترخيصًا يعرفه صاحبها، يُذكر الترخيص كشرط مفتوح لا كأنه حصل. التحقق النظامي عند مستشار القانون لا عند هذه الصفحة.",
            "المخرج ثلاث أفكار على الأكثر حتى يمكن المقارنة. بعد الاختيار، خطة التنفيذ عند مدير المشاريع، والحساب عند محلل المالية. هذه الصفحة لا تكتب عقدًا ولا سجلًا تجاريًا.",
        ),
        (
            "The business-ideas advisor helps someone with a skill and a limited budget see ideas they can start, not a list of dreams. The input is what the person knows how to do, the weekly time, the amount they can lose without stopping their income, and the city. An idea that needs more capital than that amount is dropped or postponed in writing.",
            "Each idea is written with a first step for this week, with what is missing, and with the reason it might be a poor fit. Ideas are not ranked by expected profit, because profit is not calculated here. The order follows how close the idea is to the person's skill and to the time limit.",
            "No idea is built on a government promise or a tender that was not mentioned. No partner is named. If the person knows a licence is required, the licence is written as an open condition, not as something already obtained. Checking the rule belongs with the legal advisor, not with this page.",
            "The output is three ideas at most, so they can be compared. After a choice, the project manager writes the execution plan and the finance analyst does the numbers. This page does not draft a contract or a commercial registration.",
        ),
        "لنفترض شخصًا يخيط في المنزل ولديه مساءان في الأسبوع ومبلغ صغير لشراء قماش تجربة، في مدينة واحدة. الأفكار: تعديل ملابس جاهزة للجيران بموعد محدد، أو قطعة واحدة تُعرض بالطلب من غير متجر، أو تعليم الخياطة لمجموعة صغيرة إن وُجد مكان. تُستبعد فكرة مصنع صغير لأنها تتجاوز المبلغ. لا رقم ربح.",
        "Suppose someone who sews at home, with two evenings a week and a small amount for trial fabric, in one city. The ideas are: alterations for neighbours with a fixed appointment, one made-to-order piece with no shop, or teaching a small group if a place exists. A small factory is excluded because it passes the amount. No profit figure is given.",
        faq(
            ("هل تعدون بربح الفكرة؟", "لا. نقارن الفكرة بالمهارة والوقت والمبلغ. الربح يُحسب لاحقًا إن لزم."),
            ("كم فكرة؟", "ثلاث على الأكثر، حتى يمكن الاختيار. لا قائمة طويلة."),
            ("هل تكتبون العقد؟", "لا. بعد الاختيار تنتقل الخطة إلى مدير المشاريع والحساب إلى محلل المالية."),
        ),
        faq(
            ("Do you promise the idea will profit?", "No. We compare the idea with skill, time, and the amount. Profit is calculated later if needed."),
            ("How many ideas?", "Three at most, so a choice is possible. Not a long list."),
            ("Do you write the contract?", "No. After a choice, the plan goes to the project manager and the numbers to the finance analyst."),
        ),
    )
    put(
        "project_manager",
        (
            "مدير المشاريع يحوّل هدفًا وافق عليه صاحب النشاط إلى خطوات لها مالك وموعد ونهاية. المدخل: ما الذي يُعد انتهى، ومن يعمل على كل جزء، وما الذي يعتمد على جزء آخر، وأين يتوقف العمل بانتظار قرار. الخطة التي لا تعرف شكل الانتهاء تبقى قائمة مهام مفتوحة.",
            "كل خطوة تُكتب بحيث يمكن مراجعتها: ناتج ظاهر، لا عبارة نعمل على التحسين. إذا تأخرت خطوة، يُذكر أثرها على ما بعدها من غير لوم. إعادة الترتيب قرار صاحب النشاط حين يتغير النطاق.",
            "المخاطر هنا عملية: مادة لم تصل، شخص غير متاح، قرار لم يُحسم. لا نسجل خطرًا عامًا مثل السوق صعب. لكل خطر إجراء واحد: نسأل، أو نؤجل، أو نوقف. أكثر من ذلك يتحوّل إلى قلق مكتوب لا إلى إدارة.",
            "هذه الصفحة لا تدير فريقًا داخل أداة خارجية ولا ترسل تذكيرات بنفسها. تسلّم خطة يمكن لصاحب النشاط أن ينسخها إلى جدوله. إن كان العمل ماليًا، الأرقام عند محلل المالية. إن كان نصًا، الكاتب المختص ينفذه والبوابة تراجعه لاحقًا.",
        ),
        (
            "The project manager turns a goal the owner has accepted into steps with an owner, a date, and an end. The input is what done looks like, who works on each part, what depends on something else, and where work stops for a decision. A plan that does not know the shape of finished stays an open task list.",
            "Each step is written so it can be reviewed: a visible output, not a sentence that says we are improving. If a step is late, its effect on what follows is stated without blame. Reordering is the owner's decision when the scope changes.",
            "Risks here are practical: material that has not arrived, a person who is not available, a decision that is not made. We do not log a vague risk such as the market is hard. Each risk has one action: ask, postpone, or stop. More than that becomes written worry, not management.",
            "This page does not run a team inside an outside tool and does not send reminders itself. It delivers a plan the owner can copy into their own schedule. If the work is financial, the figures sit with the finance analyst. If it is text, the specialist writer does it and the quality gate can review it later.",
        ),
        "لنفترض تجهيز ركن تغليف لمتجر خلال ثلاثة أسابيع. الانتهاء يعني: طاولة، ومخزون أكياس لشهر، وجملة على الكيس وافق عليها صاحب المتجر. الخطة تفصل شراء الطاولة، وتجربة جملة الكيس مع كاتب المحتوى، وتوقفًا إذا تأخر المورد. لا خطوة عن حملة إعلان لأن الحملة خارج النطاق.",
        "Suppose fitting a packing corner for a shop within three weeks. Done means a table, a month of bags in stock, and a sentence on the bag the owner has approved. The plan separates buying the table, trying the bag sentence with the content writer, and a stop if the supplier is late. There is no advertising step, because the campaign is outside the scope.",
        faq(
            ("هل ترسلون تذكيرات للفريق؟", "لا. نسلّم خطة. صاحب النشاط يضعها في جدوله."),
            ("ماذا يعني انتهى؟", "ناتج يمكن رؤيته، يُتفق عليه قبل توزيع الخطوات."),
            ("هل تضمّون أعمالًا خارج النطاق؟", "لا. ما لم يُذكر في الهدف لا يدخل الخطة."),
        ),
        faq(
            ("Do you send reminders to the team?", "No. We deliver a plan. The owner places it on their schedule."),
            ("What does done mean?", "An output someone can see, agreed before the steps are assigned."),
            ("Do you add work outside the scope?", "No. What was not in the goal does not enter the plan."),
        ),
    )
    put(
        "time_manager",
        (
            "مدرب إدارة الوقت يرتب يوم صاحب النشاط بحسب الطاقة والمواعيد الثابتة، لا بحسب قائمة أمنيات. المدخل: ساعات العمل الحقيقية، والمهام التي لها موعد خارجي، والمهام التي يستطيع تفويضها، وما الذي يتعبه بعد الظهر إن قال ذلك. الخطة لا تملأ كل ساعة.",
            "نترك فراغًا بين العمل العميق والردود. الردود تُجمع في نافذة، لا تُوزع على اليوم كله. المهمة التي لا موعد لها ولا ناتج لها تُؤجل أو تُحذف باقتراح، لا تُزيَّن بعنوان إنتاجية.",
            "الخطة أسبوع واحد أولًا. تعميمها على الشهر قبل أن تُجرَّب كذبة مرتبة. بعد الأسبوع يراجع صاحب النشاط ماذا اكتمل وماذا كان تقدير وقته خاطئًا. نعدّل التقدير، ولا نلوم الشخص.",
            "هذا ليس علاجًا ولا تشخيصًا لحالة صحية. إذا قال صاحب النشاط إن الإرهاق خارج ترتيب المهام، نوقفه عند حد الخطة ونقترح أن يتحدث إلى مختص. الصفحة ترتب العمل فقط.",
        ),
        (
            "The time manager orders the owner's day by energy and by fixed appointments, not by a wish list. The input is the real working hours, the tasks with an outside deadline, the tasks that can be handed to someone else, and what tires the person in the afternoon if they say so. The plan does not fill every hour.",
            "A gap stays between deep work and replies. Replies are gathered into one window. They are not spread across the day. A task with no deadline and no output is postponed or proposed for deletion. It is not decorated with a productivity title.",
            "The plan is one week first. Stretching it across a month before it is tried is a tidy fiction. After the week, the owner reviews what finished and where the time estimate was wrong. We correct the estimate. We do not blame the person.",
            "This is not treatment and not a diagnosis of a health condition. If the owner says the exhaustion is beyond task order, we stop at the plan and suggest they speak to a specialist. The page only orders work.",
        ),
        "لنفترض صاحبة متجر تعمل من التاسعة إلى الثالثة، وعندها توصيل ثابت يوم الثلاثاء، وتريد كتابة أوصاف منتجات. الخطة تضع الكتابة صباح الأحد والاثنين، والتوصيل كتلة الثلاثاء، والردود بعد الظهر في نافذة واحدة. مساء الخميس يبقى فارغًا لأن الطاقة لم تُذكر فيه. لا مهمة إضافية بعنوان تطوير الذات.",
        "Suppose a shop owner works from nine to three, has a fixed delivery on Tuesday, and wants to write product descriptions. The plan puts writing on Sunday and Monday mornings, delivery as a Tuesday block, and replies in one afternoon window. Thursday evening stays empty because no energy was described for it. There is no extra task titled self-development.",
        faq(
            ("هل تملأون اليوم بالكامل؟", "لا. الفراغ جزء من الخطة. الردود تُجمع ولا تُوزع على كل ساعة."),
            ("هل هذه استشارة نفسية؟", "لا. ترتيب عمل فقط. الإرهاق خارج المهام يُحال إلى مختص."),
            ("لماذا أسبوع واحد؟", "حتى يُجرَّب التقدير قبل نسخه على شهر."),
        ),
        faq(
            ("Do you fill the whole day?", "No. Empty space is part of the plan. Replies are gathered, not spread across every hour."),
            ("Is this psychological advice?", "No. It only orders work. Exhaustion beyond tasks is referred to a specialist."),
            ("Why only one week?", "So the estimate is tried before it is copied across a month."),
        ),
    )
    put(
        "data_analyst",
        (
            "محلل البيانات يجيب عن سؤال محدد من جدول أو أرقام يلصقها صاحب النشاط. السؤال يُكتب قبل النظر إلى الأرقام: ما الذي نريد أن نعرف، وبأي وحدة، وعن أي فترة. تحليل من غير سؤال ينتج وصفًا لكل عمود ولا قرارًا.",
            "نذكر ما فُحص: صفوف ناقصة، ووحدة مختلطة، وتاريخ خارج الفترة. الصف الناقص لا يُملأ بمتوسط من غير أن نُعلّم ذلك كافتراض رفضناه أصلًا. نحن لا نملأه. نُسقطه من الحساب ونقول كم صفًا سقط.",
            "النتيجة جملة ثم رقم. لا لوحة مليئة بمؤشرات لم تُسأل. إذا كان الحساب حساسًا للسعر أو للتكلفة، يُحال التحقق إلى محلل المالية. هنا وصف لما في الجدول، لا تسعير.",
            "لا نتصل بقاعدة بيانات المتجر مباشرة. ملف أو أرقام ملصقة فقط. بيانات العملاء الشخصية تُطلب مزالة قبل اللصق. إن وصلت، نطلب حذفها ولا نبني عليها نتيجة.",
        ),
        (
            "The data analyst answers a specific question from a table or figures the owner pastes. The question is written before the numbers are read: what we want to know, in which unit, and for which period. Analysis without a question describes every column and decides nothing.",
            "We state what was checked: missing rows, mixed units, dates outside the period. A missing row is not filled with an average unless that fill is labelled, and we do not fill it. We drop it from the calculation and say how many rows dropped.",
            "The result is a sentence, then a figure. There is no board of indicators nobody asked for. If the calculation depends on price or cost, the check goes to the finance analyst. Here we describe what is in the table. We do not set a price.",
            "We do not connect to the shop database. A file or pasted figures only. Personal customer data should be removed before it is pasted. If it arrives, we ask for it to be deleted and we do not build a result on it.",
        ),
        "لنفترض جدول طلبات أسبوع لمتجر: أعمدة التاريخ والحالة والمدينة. السؤال: كم طلبًا اكتمل داخل الرياض هذا الأسبوع. الحساب يعدّ الصفوف المطابقة ويستبعد صفًا بلا مدينة وصفًا خارج الأسبوع، ويذكر العددين المستبعدين. لا متوسط قيمة الطلب لأن العمود غير موجود، ولا تعليق عن رضا العملاء.",
        "Suppose a week of shop orders with columns for date, status, and city. The question is how many orders were completed inside Riyadh this week. The count includes matching rows, drops a row with no city and a row outside the week, and states both exclusions. There is no average order value because that column is absent, and no comment on customer satisfaction.",
        faq(
            ("هل تتصلون بقاعدة البيانات؟", "لا. ملف أو أرقام يلصقها صاحب النشاط فقط."),
            ("ماذا عن الصفوف الناقصة؟", "تُستبعد ويُذكر عددها. لا نملؤها بمتوسط صامت."),
            ("هل تحسبون الربح؟", "لا. سؤال الجدول هنا. السعر والتكلفة عند محلل المالية."),
        ),
        faq(
            ("Do you connect to the database?", "No. Only a file or figures the owner pastes."),
            ("What about missing rows?", "They are excluded and the count is stated. We do not fill them with a silent average."),
            ("Do you calculate profit?", "No. This page answers the table's question. Price and cost sit with the finance analyst."),
        ),
    )
    put(
        "cv_writer",
        (
            "كاتب السير الذاتية يرتب خبرة الشخص كما يرويها، بصيغة يقدر أن يراجعها قبل أن يرسلها. المدخل: الدور الذي يستهدفه، والخبرات بتواريخها، وما الذي لا يريد ذكره. لا نضيف مهارة، ولا شهادة، ولا لغة، ولا رقم إنجاز لم يقله الشخص.",
            "كل خبرة تُكتب بناتج يمكن لقارئ السيرة أن يفهمه: ماذا كان دوره، وما الذي كان يسلّمه. العبارات العامة مثل قائد فريق ديناميكي تُحذف. إذا لم يوجد ناتج، نكتب المسؤولية من غير أن نختلق أثرًا.",
            "الترتيب يخدم الدور المستهدف. خبرة قديمة لا علاقة لها قد تُختصر إن وافق صاحب السيرة، لا تُحذف من غير أن يراها. فجوات التاريخ تبقى ظاهرة. إخفاؤها أسوأ من شرحها بجملة صادقة إن أراد هو ذلك.",
            "السيرة ليست خطاب توظيف كاملًا إلا إذا طُلب خطاب منفصل. ولا نعد بأن الصيغة ستمر في نظام فرز. نحن نرتب الحقيقة فقط. الأسماء والجهات تُكتب كما أُمليت.",
        ),
        (
            "The CV writer orders a person's experience as they tell it, in a form they can review before sending. The input is the role they are aiming at, the jobs with dates, and what they do not want included. We do not add a skill, a certificate, a language, or an achievement figure the person did not state.",
            "Each job is written as an output a reader can understand: what the role was, and what they delivered. Empty phrases such as dynamic team leader are removed. If there is no output, we write the responsibility and do not invent an effect.",
            "The order serves the target role. An old job that is unrelated may be shortened if the person agrees. It is not deleted before they see it. Gaps in the dates stay visible. Hiding a gap is worse than explaining it in one honest sentence if they want that.",
            "The CV is not a full cover letter unless a separate letter was requested. We do not promise the format will pass a screening system. We only order the truth. Names and organisations are spelled as dictated.",
        ),
        "لنفترض محاسبة تستهدف دور مراجعة داخلية. تذكر ثلاث سنوات في مكتب، ومهمة مطابقة فواتير، ولا تذكر شهادة مهنية. السيرة تبرز المطابقة والفترة، وتترك خانة الشهادة فارغة. لا جملة عن رفع كفاءة المكتب بنسبة. الفجوة بين وظيفتين تبقى بالتاريخ كما قالته.",
        "Suppose an accountant aiming at an internal-review role. She names three years in an office, a task of matching invoices, and no professional certificate. The CV highlights the matching work and the period, and leaves the certificate line empty. There is no sentence about raising the office's efficiency by a percentage. A gap between two jobs stays dated as she stated it.",
        faq(
            ("هل تضيفون مهارات؟", "لا. ما لم يذكره صاحب السيرة لا يُكتب."),
            ("هل تخفون فجوة في التاريخ؟", "لا. الفجوة تبقى ظاهرة. الشرح اختياري وبجملة صادقة."),
            ("هل تضمنون قبول السيرة في نظام فرز؟", "لا. نرتب الخبرة فقط. لا وعد بمرور آلي."),
        ),
        faq(
            ("Do you add skills?", "No. What the person did not mention is not written."),
            ("Do you hide a gap in the dates?", "No. The gap stays visible. An explanation is optional and must be an honest sentence."),
            ("Do you guarantee a screening system will accept it?", "No. We only order the experience. There is no promise of an automatic pass."),
        ),
    )
