# Agent knowledge packs (تدريب الوكلاء بالمعرفة)

We cannot retrain the base model. "Training" = grounding: each agent gets a curated pack in
`knowledge/agents/<slug>.json` (role prompt, guardrails, playbooks, sourced domain facts, a few-shot
example) plus shared Saudi-compliance facts in `knowledge/agents/_shared.json`.

- Loader: `src/services/agent_knowledge.py` (`expert_block(slug, query)` retrieves the most relevant facts
  with the same token-overlap search as the customer KB).
- Wiring: `agent_tools.run_context` adds the pack to every portal agent run; `ceo_advisor._llm_prompt` adds
  the orchestrator (الرئيس التنفيذي) playbook. Tools: web search now also for `marketing_agent` and
  `lead_acquisition`; project KB also for `sales_closer` (so offers come only from the client's own KB).
- Evals: `evals/agent_evals.json` (35 agents × 10 Saudi-context tasks, any-of keyword criteria);
  `python scripts/run_agent_evals.py`.

## Eval method and its limits
No model API key was available in the build environment, so evals run with a **mocked model** that can
only repeat what it was given. The score is *grounding coverage*: the share of grading criteria whose
required knowledge is present in what the model receives (agent prompt + Saudi context [+ pack]).
It shows the knowledge is available. It does **not** measure how well a live model answers. Re-run with a live model before
claiming quality gains. The criteria were written alongside the packs, so expect some optimism.

## Scores (grounding coverage %, mocked model)
| Agent | الاسم | Specialty | Sources | Before | After |
|---|---|---|---|---|---|
| orchestrator | الرئيس التنفيذي الافتراضي | Virtual CEO / الرئيس التنفيذي: diagnosis, staffing, priorities, owner reporting | 2 | 23.3 | 83.3 |
| policy_guardian | حارس السياسات | Policy & approvals guardian: checks actions vs owner rules, PDPL, ad/consumer law | 7 | 28.3 | 78.3 |
| quality_gate | بوابة الجودة | Quality gate: reviews deliverables for accuracy, brand, Arabic quality, compliance | 4 | 23.3 | 90.0 |
| social_media | مدير حسابات السوشيال ميديا | Social media management for Saudi audiences (Snapchat, TikTok, Instagram, X) | 3 | 30.0 | 85.0 |
| ad_writer | كاتب إعلانات | Ad copywriting for Meta, Google, TikTok, Snapchat in Saudi market | 9 | 38.3 | 95.0 |
| marketing_agent | استراتيجي التسويق | Marketing strategy: positioning, channel mix, budget, funnel for Saudi SMEs | 3 | 15.0 | 80.0 |
| sales_closer | مسؤول إقناع المبيعات | Sales conversations & objection handling (WhatsApp-first, Saudi buyers) | 5 | 20.0 | 75.0 |
| search_discovery | خبير تحسين البحث SEO | SEO for Arabic/Saudi search: technical, on-page, local, content | 5 | 20.0 | 90.0 |
| content_ideas | مولّد أفكار المحتوى | Content ideation tied to business goals, Saudi seasons and audience questions | 2 | 30.0 | 90.0 |
| text_improver | محسّن النصوص | Arabic/English text editing: clarity, correctness, tone, readability | 1 | 35.0 | 95.0 |
| email_writer | كاتب الرسائل الإلكترونية | Business & marketing email writing with deliverability and consent rules | 2 | 50.0 | 90.0 |
| content_writer | كاتب المحتوى | Short-form content writing for social, web and WhatsApp (Saudi voice) | 4 | 15.0 | 90.0 |
| article_writer | كاتب المقالات | Long-form articles: SEO-aware, people-first, cited, Arabic | 4 | 40.0 | 75.0 |
| content_manager | مدير المحتوى | Editorial planning: calendar, workflow, governance, measurement | 1 | 10.0 | 80.0 |
| localization | خبير التعريب والتوطين | Arabic localization & transcreation for Saudi market (dialect, RTL, culture) | 1 | 20.0 | 85.0 |
| product_describer | كاتب وصف المنتجات | E-commerce product descriptions (Salla/Zid, Google Shopping, SEO) | 6 | 51.7 | 100.0 |
| store_manager | مدير المتجر الإلكتروني | E-commerce store operations & conversion (Salla/Zid metrics) | 5 | 10.0 | 80.0 |
| customer_service | موظف خدمة العملاء | Customer service replies (WhatsApp-first), escalation, returns, Saudi etiquette | 4 | 15.0 | 90.0 |
| customer_manager | مدير علاقات العملاء | CRM & retention: segmentation, lifecycle, win-back, NPS | 4 | 25.0 | 95.0 |
| market_analyst | محلل السوق | Saudi market analysis: sizing, segments, trends, official data | 2 | 40.0 | 100.0 |
| competitor_analyst | محلل المنافسين | Competitive analysis from public info: positioning, pricing, gaps | 2 | 30.0 | 100.0 |
| data_analyst | محلل البيانات | Business data analysis: KPIs, cohorts, cleaning, clear charts (uploaded files) | 2 | 15.0 | 80.0 |
| business_ideas | مستشار أفكار المشاريع | Business idea validation for Saudi entrepreneurs (licensing, lean validation) | 6 | 35.0 | 90.0 |
| project_manager | مدير المشاريع | Project planning & delivery: scope, schedule, risks, agile | 1 | 25.0 | 95.0 |
| time_manager | مدير إدارة الوقت | Personal productivity & time management (Saudi work rhythm) | 2 | 45.0 | 80.0 |
| cv_writer | كاتب السيرة الذاتية | CV/resume writing for Saudi & GCC job market (ATS-friendly, bilingual) | 2 | 40.0 | 90.0 |
| lead_acquisition | وكيل اكتساب العملاء المحتملين | Lead generation for B2B/B2C in KSA with consent-first outreach | 4 | 0.0 | 80.0 |
| software_engineer | مهندس البرمجيات | Software engineering: secure, maintainable code and reviews | 4 | 5.0 | 75.0 |
| prototype_engineer | مهندس النماذج الأولية | Rapid prototyping & MVP scoping | 2 | 40.0 | 100.0 |
| product_designer | مصمم المنتجات | UI/UX & visual design for Arabic RTL products, accessibility | 3 | 10.0 | 90.0 |
| qa_engineer | مهندس ضمان الجودة | Quality assurance & testing: test plans, cases, bug reports | 4 | 20.0 | 90.0 |
| integrations_engineer | مهندس التكاملات | Integrations: WhatsApp Cloud API, Salla/Zid, webhooks, OAuth | 7 | 25.0 | 100.0 |
| security_compliance | خبير الأمن والامتثال | Cybersecurity & compliance for Saudi SMEs (NCA ECC, PDPL, OWASP) | 5 | 10.0 | 86.7 |
| legal_privacy | مستشار القانون والخصوصية | Saudi legal & privacy guidance (PDPL, e-commerce, consumer, terms) — not legal advice | 4 | 3.3 | 80.0 |
| finance_pricing | محلل المالية والتسعير | Pricing, unit economics, VAT/ZATCA invoicing, cash flow for SMEs | 3 | 20.0 | 95.0 |
| **Mean** | | | | 24.7 | 88.0 |

## Sources (distilled in our own words; no copyrighted text copied)
Saudi government sites (ZATCA, SDAIA, MC, GAMR, GASTAT, Monsha'at, SBC) were not reachable from the
build box (geo/firewall), so their facts are well-established points with official links. Verify the
current text on the official page before you quote it to a customer.

- `zatca_einv` — ZATCA — E-Invoicing (Fatoora) — https://zatca.gov.sa/en/E-Invoicing/Pages/default.aspx
- `zatca_tax` — ZATCA — Taxes rules & regulations (VAT, Zakat) — https://zatca.gov.sa/en/RulesRegulations/Taxes/Pages/default.aspx
- `pdpl` — SDAIA — Personal Data Protection (PDPL) portal — https://dgp.sdaia.gov.sa/wps/portal/pdp/home
- `mc` — Ministry of Commerce — Laws & regulations (E-Commerce Law, Consumer protection) — https://mc.gov.sa/en/Regulations/Pages/default.aspx
- `gamr` — General Authority for Media Regulation (GAMR) — https://gmedia.gov.sa/
- `mawthooq` — GAMR — Mawthooq advertiser licence — https://mawthooq.gmedia.gov.sa/
- `wa_policy` — WhatsApp Business Messaging Policy — https://business.whatsapp.com/policy
- `wa_optin` — Meta — WhatsApp: getting opt-in — https://developers.facebook.com/docs/whatsapp/overview/getting-opt-in
- `wa_pricing` — Meta — WhatsApp pricing & conversation windows — https://developers.facebook.com/docs/whatsapp/pricing
- `wa_templates` — Meta — WhatsApp message templates — https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates
- `wa_limits` — Meta — WhatsApp messaging limits & quality — https://developers.facebook.com/docs/whatsapp/messaging-limits
- `meta_ads_specs` — Meta Business Help — ad specs/guide — https://www.facebook.com/business/help/980593475366490
- `meta_ad_standards` — Meta Advertising Standards — https://transparency.meta.com/policies/ad-standards/
- `google_rsa` — Google Ads Help — Responsive search ads — https://support.google.com/google-ads/answer/7684791
- `tiktok_ads` — TikTok Ads policies — https://ads.tiktok.com/help/article/tiktok-ads-policies
- `snap_biz` — Snapchat for Business / Business Help — https://businesshelp.snapchat.com/
- `g_seo` — Google Search Central — SEO Starter Guide — https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- `g_helpful` — Google Search Central — Creating helpful, reliable, people-first content — https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- `g_hreflang` — Google Search Central — Localized versions (hreflang) — https://developers.google.com/search/docs/specialty/international/localized-versions
- `cwv` — web.dev — Core Web Vitals — https://web.dev/articles/vitals
- `merchant` — Google Merchant Center — Product data specification — https://support.google.com/merchants/answer/7052112
- `gmail_senders` — Google Workspace — Email sender guidelines — https://support.google.com/a/answer/81126
- `salla` — Salla developer docs — https://docs.salla.dev/
- `zid` — Zid developer docs — https://docs.zid.sa/
- `owasp` — OWASP Top 10 — https://owasp.org/Top10/
- `asvs` — OWASP ASVS — https://owasp.org/www-project-application-security-verification-standard/
- `nca_ecc` — NCA — Essential Cybersecurity Controls (ECC) — https://nca.gov.sa/en/regulatory-documents/controls-list/ecc/
- `wcag` — W3C — WCAG 2.2 — https://www.w3.org/TR/WCAG22/
- `w3c_i18n` — W3C Internationalization — scripts & RTL — https://www.w3.org/International/questions/qa-scripts
- `scrum` — The Scrum Guide (2020) — https://scrumguides.org/scrum-guide.html
- `12factor` — The Twelve-Factor App — https://12factor.net/
- `oauth` — RFC 6749 — OAuth 2.0 — https://www.rfc-editor.org/rfc/rfc6749
- `gastat` — GASTAT — General Authority for Statistics — https://www.stats.gov.sa/en
- `monshaat` — Monsha'at — SME General Authority — https://www.monshaat.gov.sa/en
- `sbc` — Saudi Business Center (business.sa) — https://business.sa/
- `cst` — Communications, Space & Technology Commission (CST) — https://www.cst.gov.sa/en/
- `freelance` — Freelance document platform (freelance.sa) — https://freelance.sa/
- `sfda` — Saudi Food & Drug Authority (SFDA) — https://www.sfda.gov.sa/en
- `hrsd` — Ministry of Human Resources & Social Development — https://www.hrsd.gov.sa/en
- `istqb` — ISTQB — testing glossary & syllabi — https://www.istqb.org/
- `pomodoro` — Francesco Cirillo — The Pomodoro Technique — https://www.pomodorotechnique.com/
- `aida` — AIDA model (overview) — https://en.wikipedia.org/wiki/AIDA_(marketing)
- `leancanvas` — Lean Canvas (Ash Maurya) — https://www.leancanvas.com/
- `rfm` — RFM analysis (overview) — https://en.wikipedia.org/wiki/RFM_(market_research)
- `spin` — Neil Rackham — SPIN Selling (book, 1988; summarised)
- `alnarjs` — Al-Narjs internal facts (ALNARJS.md, pricing v2, lessons)

## Updating
Edit the JSON pack, keep facts short and sourced, then run `pytest tests/test_agent_knowledge.py` and
`python scripts/run_agent_evals.py`. On any price change, update `orchestrator.json` and `finance_pricing.json`
(lesson 3).
