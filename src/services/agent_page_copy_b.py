"""Public agent pages, second group. Same rules as agent_page_copy."""

from __future__ import annotations


def register(put, faq) -> None:
    put(
        "text_improver",
        (
            "محسّن النصوص يشتغل على نص موجود، لا على صفحة بيضاء. صاحب النشاط يلصق الرسالة أو المنشور أو وصف الخدمة، ويحدد ما الذي يجب أن يبقى: المعنى، والأسماء، والأرقام، وأي جملة قانونية لا تُمس. التحسين يوضح التركيب ويخفف التكرار، من غير أن يبدّل العرض أو يضيف ميزة لم تكن في الأصل.",
            "قبل التسليم تُعرض النسخة الأصل والنسخة المقترحة بطريقة يستطيع المراجع أن يقارنها. إذا حُذفت جملة، يُذكر السبب: تكرار، أو غموض، أو عبارة تعد بشيء لم يُكتب في المصدر. إذا بقيت جملة ضعيفة لأن حذفها يغيّر المعنى، تُترك ويُشرح ذلك. التحسين ليس إعادة كتابة تخفي ما قاله صاحب النشاط.",
            "النبرة تُطلب صراحة. نص يخاطب عميلًا غاضبًا لا يُصاغ كنص حملة. نص داخلي بين موظفين لا يُصاغ كإعلان. إذا لم تُحدد النبرة، نسأل ولا نفترض لهجة دعائية. الأسماء التجارية تُكتب كما وردت، لا كما نظن أن شكلها أشهر.",
            "هذا الوكيل لا يراجع الحقائق الخارجية. إذا كان النص يقول إن التوصيل يتم في يوم، نبقي اليوم إن كان موجودًا في المصدر، ولا نبحث هل هذا صحيح في الطريق. التحقق من الواقع مهمة محلل أو صاحب النشاط. هنا نحمي المعنى ونرفع الوضوح.",
        ),
        (
            "The text improver works on a text that already exists, not on a blank page. The owner pastes the message, the post, or the service description, and names what must stay: the meaning, the names, the figures, and any legal sentence that is not to be touched. The edit clarifies structure and cuts repetition. It does not change the offer or add a feature that was not in the source.",
            "Before delivery, the original and the suggestion are shown so a reviewer can compare them. If a sentence is removed, the reason is stated: repetition, ambiguity, or a promise that was not in the source. If a weak sentence stays because cutting it would change the meaning, it stays and the note says why. Improvement is not a rewrite that hides what the owner said.",
            "Tone is requested outright. A reply to an unhappy customer is not shaped like a campaign. An internal note between staff is not shaped like an ad. If tone is missing, we ask. We do not assume a promotional voice. Brand names are spelled as supplied, not as we guess they are usually written.",
            "This agent does not check outside facts. If the text says delivery takes a day, the day stays when it is in the source. We do not go and see whether the road really allows it. Checking reality belongs to an analyst or to the owner. Here we protect meaning and raise clarity.",
        ),
        "لنفترض رسالة واتساب من متجر إلى عميل تأخر طلبه. النص الأصل يعتذر ويذكر أن التأخير بسبب نقص قماش، وأن الموعد الجديد يوم الخميس، ويطلب تأكيد العنوان. التحسين يرتب الجمل الثلاث ويزيل تكرار الاعتذار، ويبقي سبب التأخير واليوم وطلب العنوان. لا يضيف خصمًا، ولا يقول إن التأخير لن يتكرر.",
        "Suppose a shop message to a customer whose order is late. The original apologises, says the delay is a missing fabric, names Thursday as the new day, and asks the customer to confirm the address. The edit orders those three points and removes a repeated apology. It keeps the cause, the day, and the address request. It does not add a discount, and it does not say the delay will not happen again.",
        faq(
            ("هل تغيّرون الأرقام؟", "لا. الأرقام والأسماء والجمل التي طُلب إبقاؤها تبقى كما هي."),
            ("هل هذا تدقيق لغوي فقط؟", "هو وضوح وترتيب وحماية للمعنى. ليس مراجعة قانونية ولا تحققًا من صحة الوقائع."),
            ("ماذا أرسل؟", "النص كاملًا، والنبرة المطلوبة، وما الذي يُمنع تغييره."),
        ),
        faq(
            ("Do you change figures?", "No. Figures, names, and sentences you asked to keep stay as they are."),
            ("Is this only proofreading?", "It is clarity, order, and protection of meaning. It is not a legal review and not a check that the facts are true."),
            ("What should I send?", "The full text, the tone you want, and what must not change."),
        ),
    )
    put(
        "product_describer",
        (
            "كاتب وصف المنتجات يكتب وصفًا يطابق المنتج الذي بين يدي البائع، لا وصفًا عامًا لفئة كاملة. المدخلات هي الاسم، والمادة أو المكوّن إن وُجد، والمقاس أو الوزن، وما الذي يشمله السعر، وما الذي لا يشمله. إذا نقص حقل، يبقى فارغًا في الوصف ويُذكر أنه غير مؤكد، بدل أن نملأه بعبارة تسويقية.",
            "الوصف يفصل بين ما يراه المشتري وما يجب أن يفعله. جملة عن شكل القطعة، وجملة عن الاستخدام، وجملة عن العناية أو الحفظ إن كانت معروفة. لا نكتب أن المنتج الأكثر مبيعًا، ولا أنه طبي، ولا أنه يناسب الجميع، ما لم تكن هذه الجملة في مصدر صاحب المتجر ومقبولة عنده. الكلمات المفتاحية تُدخل إن كانت تصف المنتج فعلًا، لا حشوًا مكررًا.",
            "إن كان للمتجر نبرة محفوظة في ذاكرة الأسلوب، يلتزم الوصف بها. وإن لم توجد، نكتب فصحى واضحة يمكن لصاحب المتجر أن يحوّلها إلى لهجته. الوحدة والعملة تُكتبان كما يحددها المتجر. لا نحوّل المقاس ولا نقرّب الوزن.",
            "الوصف لا يرفع المنتج على المتجر، ولا يغيّر السعر في لوحة التحكم. ربط سلة أو زد ما زال غير مشمول كربط مباشر، ويُذكر ذلك حتى لا يظن صاحب المتجر أن النص نُشر وحده. النشر مراجعة بشرية بعد القراءة.",
        ),
        (
            "The product description writer describes the item in the seller's hands, not a generic category. The inputs are the name, the material or ingredient if there is one, the size or weight, what the price includes, and what it does not include. If a field is missing, the description leaves it blank and says it is unconfirmed, instead of filling it with a marketing phrase.",
            "The description separates what the buyer sees from what the buyer must do. One sentence on the object, one on use, one on care or storage when that is known. We do not write that it is the best seller, that it is medical, or that it suits everyone, unless that sentence is in the owner's source and the owner accepts it. Search words are included only when they actually describe the item.",
            "If the shop has a style profile in style memory, the description follows it. If not, we write clear formal Arabic the owner can shift into their own voice. Units and currency stay as the shop states them. We do not convert a size or round a weight.",
            "The description does not upload the product and does not change the price in a dashboard. A direct Salla or Zid connection is not included yet, and the page says so, so the owner does not think the text published itself. Publishing is a human review after reading.",
        ),
        "لنفترض عبوة قهوة مختصة. صاحب المتجر يكتب: الوزن كيلو، التحميص متوسط، السعر يشمل الضريبة إن كانت مسجلة عنده، ولا يشمل الطحن إلا إذا طُلب. الوصف يذكر الوزن ودرجة التحميص وخيار الطحن، ولا يقول إن القهوة تعالج الأرق، ولا إن الكمية تنفد. خانة المنشأ تبقى فارغة لأنه لم يذكر بلد البن.",
        "Suppose a bag of specialty coffee. The owner writes: the weight is one kilo, the roast is medium, the price includes tax if they are registered, and grinding is not included unless requested. The description names the weight, the roast, and the grind option. It does not say the coffee treats insomnia, and it does not say stock is running out. Origin stays blank because the bean country was not given.",
        faq(
            ("هل ترفعون المنتج على المتجر؟", "لا. نسلّم نصًا. الربط المباشر مع سلة أو زد غير مشمول حاليًا."),
            ("ماذا لو نقصت معلومة؟", "تبقى الخانة فارغة مع تنبيه. لا نكملها من منتجات شبيهة."),
            ("هل تكتبون لهجة عامية؟", "إن وُجد ملف أسلوب نلتزمه. وإلا فصحى واضحة يمكن تعديلها."),
        ),
        faq(
            ("Do you upload the product?", "No. We deliver text. A direct Salla or Zid connection is not included yet."),
            ("What if a fact is missing?", "The field stays blank with a note. We do not fill it from a similar product."),
            ("Do you write in dialect?", "If a style profile exists, we follow it. Otherwise the draft is clear formal Arabic you can edit."),
        ),
    )
    put(
        "store_manager",
        (
            "مدير المتجر يراجع رحلة الشراء كما يصفها صاحب المتجر، لا كما نتخيل متجرًا مثاليًا. نطلب ما الذي يبيعه، وأين يتعثر العميل: صفحة المنتج، أو الشحن، أو الدفع، أو ما بعد الطلب. الملاحظة تُربط بخطوة يقدر صاحب المتجر أن يفتحها ويتأكد منها. اقتراح من غير موضع في الرحلة لا يُسلَّم.",
            "التحسينات المقترحة عملية: توضيح ما يشمله السعر، وإظهار مدة التجهيز قبل الدفع، وفصل المنتجات غير المتوفرة عن المعروضة. لا نقترح إعادة بناء المتجر، ولا نعد بأن التعديل يرفع المبيعات. إن كان السبب مجهولًا، نكتب أن السبب غير معروف ونقترح سؤالًا واحدًا يسأله المتجر للعميل الذي ترك السلة، لا لوحة أسباب مخترعة.",
            "الربط مع سلة أو زد غير مشمول كتشغيل مباشر. لذلك لا يدّعي هذا الوكيل أنه قرأ طلبات المتجر الحية. إن لصق صاحب المتجر وصف مشكلة أو قائمة ملاحظات، نعمل عليها. إن لم يلصق شيئًا، نسأله ولا نخمن من اسم النشاط وحده.",
            "ما بعد الاقتراح يبقى عند صاحب المتجر: تعديل الصفحة، أو تدريب موظف، أو إيقاف منتج. الوكيل يرتب الأولوية بين ثلاث ملاحظات كحد معقول، حتى لا تتحول المراجعة إلى قائمة طويلة لا تُنفذ. الأولوية تُشرح بسبب واحد لكل بند.",
        ),
        (
            "The store manager reviews the buying path as the owner describes it, not as an ideal shop we imagine. We ask what is sold, and where the customer stalls: the product page, shipping, payment, or after the order. A note is tied to a step the owner can open and check. A suggestion with no place in the path is not delivered.",
            "The suggested changes are practical: say what the price includes, show preparation time before payment, and separate unavailable items from items on offer. We do not propose rebuilding the shop, and we do not promise that an edit will raise sales. If the cause is unknown, we write that it is unknown and suggest one question the shop can ask a customer who left a basket. We do not invent a chart of causes.",
            "A live Salla or Zid connection is not included, so this agent does not claim it read live orders. If the owner pastes a problem or a list of notes, we work from that. If they paste nothing, we ask. We do not guess from the business name alone.",
            "What happens after the suggestion stays with the owner: editing the page, training a person, or pausing a product. The agent ranks at most three notes, so the review does not become a long list nobody executes. Each item has one reason for its place in the order.",
        ),
        "لنفترض متجر أدوات منزلية يقول إن العملاء يسألون عن مدة التجهيز بعد الدفع، وإن المنتجات النافذة ما زالت ظاهرة. المراجعة تقترح إظهار مدة التجهيز قبل زر الدفع، وإخفاء النافد أو وسمه بوضوح، وسؤالًا واحدًا لمن يتواصل بعد الطلب. لا تقترح تغيير هوية المتجر، ولا تذكر رقم مبيعات.",
        "Suppose a home-goods shop says customers ask about preparation time after they pay, and sold-out items are still visible. The review suggests showing preparation time before the pay button, hiding or clearly marking sold-out items, and one question for people who write after ordering. It does not suggest a new brand identity, and it cites no sales figure.",
        faq(
            ("هل تقرأون طلبات سلة أو زد مباشرة؟", "لا. الربط المباشر غير مشمول. نعمل على ما يصفه صاحب المتجر أو يلصقه."),
            ("هل تعدون بزيادة المبيعات؟", "لا. نرتب ملاحظات على رحلة الشراء. الأثر لا يُخمَّن."),
            ("كم ملاحظة تُسلَّم؟", "حتى ثلاث ملاحظات مرتبة بسبب، حتى يمكن تنفيذها."),
        ),
        faq(
            ("Do you read Salla or Zid orders directly?", "No. A direct connection is not included. We work from what the owner describes or pastes."),
            ("Do you promise higher sales?", "No. We order notes on the buying path. Effect is not guessed."),
            ("How many notes are delivered?", "Up to three, ranked with a reason, so they can actually be done."),
        ),
    )
    put(
        "customer_manager",
        (
            "مدير علاقات العملاء يقرأ ما حدث مع العميل ويقترح الخطوة التالية، لا خطاب ولاء عام. المدخل محادثة أو ملخص يكتبه صاحب النشاط: ماذا طُلب، وماذا وُعد، وما الذي لم يُغلق. الاقتراح يسمي الإجراء: رد يوضح الموعد، أو اعتذار محدد، أو تحويل إلى شخص في الفريق، أو إيقاف المتابعة إن كان العميل طلب ذلك.",
            "لا نخمّن شعور العميل ولا نصنّفه في شريحة وفاء من غير إشارة في النص. إذا تكرر التأخير، نقول إن النمط الظاهر هو تكرار التأخير في هذه العينة فقط، لا إن كل العملاء غاضبون. العينة هي ما لُصق. توسيعها على المنشأة كلها ادّعاء لا نملكه.",
            "جدول المتابعة، إن طُلب، قصير: من يتواصل، ومتى، وبأي جملة، وما الذي لا يُعاد فتحه. لا جدول اتصالات يومي ثقيل لعميل طلب مسافة. الاحترام هنا قاعدة لا أسلوب لطيف فقط.",
            "هذا الدور لا يرد على العميل بنفسه ولا يرى صندوق الوارد. موظف الخدمة يكتب الرد حين تكون المهمة ردًا واحدًا. هنا نرتب العلاقة عبر عدة محادثات إن وُجدت. الاثنان لا يكتبان رسالتين مختلفتين عن الموعد نفسه.",
        ),
        (
            "The customer relationship manager reads what happened with a customer and suggests the next step, not a generic loyalty speech. The input is a conversation or a summary the owner writes: what was asked, what was promised, and what is still open. The suggestion names the action: a reply that states the date, a specific apology, a handoff to someone on the team, or stopping follow-up if the customer asked for space.",
            "We do not guess how the customer feels, and we do not place them in a loyalty segment without a sign in the text. If delay repeats, we say the visible pattern is repeated delay in this sample only, not that every customer is angry. The sample is what was pasted. Stretching it across the whole business is a claim we do not have.",
            "A follow-up list, when requested, is short: who writes, when, with which sentence, and what must not be reopened. There is no heavy daily call plan for a customer who asked for distance. Respect is a rule, not only a pleasant tone.",
            "This role does not answer the customer itself and does not see the inbox. The service agent drafts a reply when the task is one answer. Here we order the relationship across several conversations when they exist. The two agents do not write two different messages about the same date.",
        ),
        "لنفترض عميلًا اشتكى مرتين من تأخير التوصيل، وفي الرسالة الأخيرة طلب ألا يُتصل به صباحًا. الملخص يذكر الوعد القديم بيوم الثلاثاء والموعد الجديد يوم الجمعة. الاقتراح: رسالة واحدة تؤكد الجمعة، وتعتذر عن الثلاثاء تحديدًا، وتلتزم بعدم الاتصال صباحًا، وتحيل القرار إن تكرر التأخير إلى صاحب النشاط. لا خصم ما لم يُذكر حد للتعويض.",
        "Suppose a customer complained twice about late delivery, and the last message asked not to be called in the morning. The summary names the old Tuesday promise and the new Friday date. The suggestion is one message that confirms Friday, apologises for Tuesday specifically, keeps the morning-call ban, and hands the decision back to the owner if the delay happens again. No discount, unless a compensation limit was stated.",
        faq(
            ("هل ترون صندوق الوارد؟", "لا. نعمل على المحادثة أو الملخص الذي تلصقه."),
            ("هل تصنّفون العملاء شرائح؟", "لا من غير إشارة في النص. لا نعمّم عينة صغيرة على كل العملاء."),
            ("ما الفرق عن موظف الخدمة؟", "موظف الخدمة يصيغ ردًا واحدًا. هنا تُرتب الخطوة التالية عبر أكثر من تواصل."),
        ),
        faq(
            ("Do you see the inbox?", "No. We work from the conversation or summary you paste."),
            ("Do you segment customers?", "Not without a sign in the text. A small sample is not generalised to every customer."),
            ("How is this different from the service agent?", "The service agent drafts one reply. Here the next step is ordered across more than one contact."),
        ),
    )
    put(
        "customer_service",
        (
            "موظف خدمة العملاء يكتب ردًا على سؤال أو شكوى واحدة، بأسلوب يمكن لصاحب النشاط أن يرسله كما هو بعد قراءة سريعة. الرد يجيب عن السؤال المطروح أولًا، ثم يذكر ما الذي يستطيع النشاط فعله اليوم، ثم ما الذي يحتاج وقتًا أو شخصًا آخر. لا يدفن الجواب تحت ترحيب طويل.",
            "إذا كان الجواب غير موجود في سياسة النشاط أو في نص صاحب النشاط، نقول إن المعلومة غير متوفرة ونقترح سؤالًا واحدًا يُعاد به إلى العميل، بدل اختراع سياسة استبدال أو مدة توصيل. الوعد الذي لم يُكتب عندكم لا يُكتب في الرد.",
            "النبرة هادئة حتى لو كانت رسالة العميل حادة. لا نرد على الإساءة بإساءة، ولا نبالغ في الاعتذار حتى نقرّ بخطأ لم يثبته النص. إن كان الخطأ واضحًا في ما لصقه صاحب النشاط، يُذكر بعبارة محددة. إن كان محل خلاف، يُحال إلى صاحب النشاط قبل أي التزام.",
            "الرد مسودة. الإرسال من صندوق النشاط. لا دخول إلى واتساب ولا إلى بريد العميل من هذه الصفحة. وإذا احتاج الرد معلومة من وصف منتج أو من سياسة مكتوبة، نطلبها ولا نكمل من الذاكرة.",
        ),
        (
            "The customer service agent drafts a reply to one question or one complaint, in a form the owner can send after a short read. The reply answers the question first, then says what the business can do today, then what needs time or another person. The answer is not buried under a long greeting.",
            "If the answer is not in the business policy or in the owner's text, we say the information is not available and suggest one question to send back, instead of inventing a return policy or a delivery time. A promise you have not written is not written into the reply.",
            "The tone stays calm even when the customer's message is sharp. We do not answer an insult with an insult, and we do not apologise so broadly that we admit a fault the text does not show. If the fault is clear in what the owner pasted, it is named in one specific sentence. If it is disputed, it goes back to the owner before any commitment.",
            "The reply is a draft. Sending it happens from the business inbox. This page does not open WhatsApp or the customer's email. If the reply needs a product fact or a written policy, we ask for it. We do not complete it from memory.",
        ),
        "لنفترض عميلًا يسأل: هل يمكن استبدال المقاس خلال ثلاثة أيام، والشحن على من؟ صاحب المتجر لم يكتب سياسة استبدال، وكتب فقط أن التجهيز يومان داخل الرياض. الرد يقول إن سياسة الاستبدال غير مذكورة عنده ويجب أن يؤكدها صاحب المتجر، ويذكر يومي التجهيز داخل الرياض فقط، ولا يعدّ بشحن مجاني. الجملة الأخيرة تطلب من صاحب المتجر كتابة قاعدة الاستبدال قبل إرسال الرد.",
        "Suppose a customer asks whether a size can be exchanged within three days, and who pays shipping. The owner has not written an exchange policy, and has only said preparation takes two days inside Riyadh. The draft says the exchange rule is not on file and the owner must confirm it, states the two preparation days inside Riyadh only, and does not promise free shipping. The last line asks the owner to write the exchange rule before the reply is sent.",
        faq(
            ("هل يُرسل الرد مباشرة للعميل؟", "لا. المسودة تُراجع ثم تُرسل من صندوقكم."),
            ("ماذا لو لم تكن هناك سياسة؟", "نقول إن المعلومة غير متوفرة. لا نخترع مدة استبدال أو من يتحمل الشحن."),
            ("هل تردون على الإساءة بالمثل؟", "لا. النبرة تبقى هادئة، والالتزام لا يُكتب قبل موافقة صاحب النشاط."),
        ),
        faq(
            ("Is the reply sent to the customer?", "No. The draft is reviewed, then sent from your own inbox."),
            ("What if there is no policy?", "We say the information is not available. We do not invent an exchange window or who pays shipping."),
            ("Do you answer an insult in kind?", "No. The tone stays calm, and no commitment is written before the owner agrees."),
        ),
    )
    put(
        "email_writer",
        (
            "كاتب الرسائل الإلكترونية يكتب رسالة واحدة بهدف واحد: متابعة عرض، أو إرسال ملف، أو توضيح موعد، أو دعوة لخطوة تالية. العنوان يصف المحتوى حتى يعرف المستلم لماذا فُتحت الرسالة. لا عنوان مبهم يعدّ بمفاجأة.",
            "متن الرسالة قصير. الجملة الأولى تقول الغرض، ثم التفصيل اللازم، ثم الفعل المطلوب إن وُجد، ثم الطريقة التي يرد بها المستلم. إذا كان هناك مرفق، يُذكر اسمه وما الذي يُراجع داخله. لا نطلب من المستلم قراءة ثلاث صفحات ليفهم الطلب.",
            "الأسلوب مهني ويمكن أن يكون دافئًا من غير مبالغة. لا نكتب أن المستلم من نخبة العملاء، ولا نهدد بإغلاق الحساب، ولا نعدّ بخصم لم يُعتمد. إن كانت الرسالة متابعة ثانية، نذكر الرسالة السابقة بتاريخها إن ذُكر، ولا نلوم المستلم على الصمت.",
            "الرسالة مسودة في البريد. لا إرسال جماعي، ولا قائمة بريدية، ولا ربط بأداة تسويق من هذه الصفحة. إن كان المطلوب سلسلة من ثلاث رسائل، تُكتب كثلاث مسودات منفصلة كل واحدة بهدفها، لا كرسالة واحدة مكررة.",
        ),
        (
            "The email writer drafts one message with one aim: following up an offer, sending a file, confirming a time, or inviting a next step. The subject describes the content so the reader knows why the message was opened. It is not a vague subject that promises a surprise.",
            "The body stays short. The first sentence states the purpose, then the necessary detail, then the action if there is one, then how the reader replies. If there is an attachment, its name is stated and what to review inside it. We do not ask the reader to finish three pages before they understand the request.",
            "The manner is professional and can be warm without exaggeration. We do not write that the reader is among elite customers, we do not threaten to close an account, and we do not promise a discount that was not approved. If this is a second follow-up, we mention the earlier message and its date when that date was given. We do not blame the reader for silence.",
            "The message is a draft in email. There is no bulk send, no mailing list, and no connection to a marketing tool from this page. If three messages are needed, they are three separate drafts, each with its own aim, not one message pasted three times.",
        ),
        "لنفترض مكتب تصميم يريد تذكير عميل بمراجعة مخطط أُرسل يوم الأحد، والمهلة يوم الأربعاء، ولا خصم للتأخير. الرسالة عنوانها مراجعة المخطط قبل الأربعاء. المتن يذكر تاريخ الإرسال، ويسأل عن موافقة أو ملاحظة واحدة، ويوضح أن الصمت لا يُعد موافقة. لا جملة عن إغلاق المشروع.",
        "Suppose a design studio wants to remind a client to review a plan sent on Sunday, with Wednesday as the deadline, and no discount for delay. The subject is a review of the plan before Wednesday. The body names the send date, asks for approval or one note, and says silence is not approval. There is no line about closing the project.",
        faq(
            ("هل ترسلون الرسالة إلى العميل؟", "لا. نسلّم مسودة. الإرسال من بريدكم."),
            ("هل تبنون قائمة بريدية؟", "لا. كل رسالة هدفها مكتوب. لا حملات جماعية من هذه الصفحة."),
            ("ماذا عن العنوان؟", "يصف المحتوى مباشرة. لا وعود مبهمة."),
        ),
        faq(
            ("Do you send the email?", "No. We deliver a draft. Sending happens from your mailbox."),
            ("Do you build a mailing list?", "No. Each message has a written aim. There is no bulk campaign from this page."),
            ("What about the subject line?", "It describes the content directly. No vague promises."),
        ),
    )
