# Search strategy — karmaai.online

Written October 2026. Every ranking claim below is sourced to Google's own
documentation or to 2026 reporting, and every recommendation is checked against
what this site actually has. **No search volumes appear anywhere in this
document.** Volumes come from Google Search Console and a keyword tool; inventing
them here would be the exact "business data we cannot prove" the site refuses to
publish on its own pages.

---

## 1. What Google actually rewards right now

Confirmed update record, from Google Search Central:

| Date | Update |
|---|---|
| 27 Mar 2026 | Core update (rolled out to 8 Apr) |
| 24 Mar 2026 | Spam update |
| 21 May 2026 | Core update (complete 2 Jun), alongside the I/O AI-search overhaul |
| 18 Aug 2026 | Spam update |
| 24 Sep 2026 | Spam update |

Three corrections to widely repeated but wrong beliefs:

1. **There is no separate "Helpful Content Update".** The standalone helpful-content
   classifier was folded into the core ranking systems in the March 2024 core
   update. Helpfulness is now assessed by core systems. Anyone still writing
   "recover from the HCU" is describing a 2023-era model.
2. **A core update is not a penalty.** It is a periodic, index-wide reassessment.
   There is nothing to "remove" and no penalty to lift. Only a *manual action*
   is a penalty in the ordinary sense, and only that appears in Search Console.
3. **The Quality Rater Guidelines are not a ranking algorithm.** John Mueller
   stated plainly in May 2026 that the guidelines are not a guide for search
   ranking. They describe what quality looks like to a human rater; they do not
   tell you what the algorithm rewards. Treat them as an editorial lens, not a
   checklist.

The nine signals that carry the load, in order of impact per hour:

1. **Helpful, people-first content** — content that could only have been written
   by this business. Google updated its "main content" guidance in October 2026
   and added explicit attributes: effort, originality, skill/experience, and
   accuracy, plus a direct warning on **deceptive authorship** — fake personas
   and fabricated bios are now named as a low-quality signal.
2. **E-E-A-T, with Experience acting as a filter.** There is no "E-E-A-T score"
   to raise. What is rewarded: named, verifiable people, first-hand specifics,
   and timestamps that match the content.
3. **Search-intent match.** A buying query needs a product page, not a blog post.
4. **Core Web Vitals.** Note the tightening: the "Good" threshold for Largest
   Contentful Paint moved from 2.5s to **2.0s** on mobile. INP and CLS also
   tightened.
5. **Mobile experience.** Mobile is indexed first.
6. **Quality backlinks.** Earned, never bought; topical relevance beats volume.
7. **Internal structure.** Clean architecture and deliberate internal links.
8. **Structured data.** Now a gateway to AI Overviews citations, not just rich
   results — FAQ, HowTo and LocalBusiness schema are over-represented among
   cited sources.
9. **Freshness, meaning real freshness.** Decaying content loses quietly; date
   manipulation is not rewarded.

Explicitly *not* direct ranking factors, despite how often they are sold:
dwell time, bounce rate, social shares and likes. They matter only as indirect
causes of the signals above.

---

## 2. Keyword map

Grouped by intent, because intent decides the page that ranks, not the keyword.

### 2.1 Transactional — the money pages (`/home`, `/portal`)

| Arabic | English | Page |
|---|---|---|
| اشتراك وكلاء ذكاء اصطناعي | ai agent subscription | /home |
| فريق تسويق بالذكاء الاصطناعي | ai marketing team saudi | /home |
| إدارة حسابات التواصل بالذكاء الاصطناعي | ai social media management | /home |
| محتوى تسويقي بالذكاء الاصطناعي | ai content marketing service | /home |
| متجر إلكتروني بالسعودية | ecommerce saudi arabia | /home |
| اشتراك شهري بفاتورة ضريبية | monthly subscription with vat invoice | /home |

### 2.2 Local / discovery — the local pack and AI Overviews

| Arabic | English |
|---|---|
| وكالة ذكاء اصطناعي الرياض | ai agency riyadh |
| شركة تسويق رقمي الرياض | digital marketing company riyadh |
| مطاعم الرياض تسويق | restaurant marketing riyadh |
| عيادات الرياض تسويق رقمي | clinic digital marketing riyadh |
| متاجر سعوديةRZ | saudi stores online presence |

### 2.3 Informational — the guides and blog (`/guide`, `/blog`)

| Arabic | English |
|---|---|
| كيف تعمل وكلاء الذكاء الاصطناعي | how ai agents work for business |
| هل أحتاج موظف أم وكيل ذكاء اصطناعي | ai agent vs employee |
| ما هو أتمتة التسويق | what is marketing automation |
| متى أحتاج متجر إلكتروني | when do you need an online store |
| تسويق بالمحتوى للمطاعم | content marketing for restaurants |

### 2.4 Existing long-tail pages — already indexable, keep and deepen

`/ai-agent/<slug>` exists for all 35 agents and is the site's strongest topical
coverage. `ItemList` schema is already in place. These pages are the answer to
"*does* AI agent for [specific job] exist" queries and should be the entry point
for long-tail discovery, not a list of generic blog posts.

### Rules for using these

- One page per intent. Do not build five URLs for the same query.
- No keyword stuffing. If a sentence reads worse after inserting the term, delete
  the term.
- Every new page must carry a real, dated, specific detail that only this
  business can produce — otherwise it is exactly the commodity content the
  October 2026 guidance says gets filtered.

---

## 3. Gaps on this site, ranked by expected value

### 3.1 No `LocalBusiness` / `ProfessionalService` schema — HIGHEST ROI

The site emits `Organization`, `WebSite`, `FAQPage`, `Service` and `ItemList`.
It does **not** emit a local business entity with geography, service area,
opening hours or price range. 2026 reporting specifically identifies
`LocalBusiness` schema as disproportionately represented among AI Overview
citations, and local pack ranking for a Riyadh business is decided on proximity,
relevance and prominence — of which the entity is the foundation.

**Action:** add `ProfessionalService` (a subtype of `LocalBusiness`) carrying
`geo`, `areaServed`, `openingHoursSpecification`, `priceRange`, `hasOfferCatalog`
built from the real catalogue, and the payment methods actually offered.

### 3.2 No `BreadcrumbList` — MEDIUM

Breadcrumbs are how a crawler learns hierarchy. The per-agent pages form a clear
tree (`/ai-agent/<slug>` under the team) and currently declare no path.

**Action:** emit `BreadcrumbList` on deep pages.

### 3.3 No human author entity — MEDIUM, and a trust problem beyond SEO

E-E-A-T is a filter now, and deceptive authorship is called out by name. A site
selling a managed team, with no named accountable human anywhere, is weak on
exactly the signal the guidance says is being used to filter. This is not a
technical fix — it requires a real person to be named, with a real bio, and it
needs the owner's decision.

### 3.4 `sameAs` carries one profile — LOW but free

`sameAs` currently lists the Telegram bot only. No Instagram or Facebook profile
exists to link to. When those exist, this is a one-line change and it helps entity
disambiguation.

### 3.5 LCP must clear 2.0s, not 2.5s — MEASURE, DO NOT ASSUME

The threshold tightened in early 2026. This must be measured in the field
(Search Console CWV report or CrUX), not asserted from a local run.

### 3.6 Google Business Profile — NOT YET ACTIVE

Local pack prominence now weights *recent activity*: businesses posting to their
GBP a few times a month and responding to reviews hold position; dormant profiles
slide. For a Riyadh company this is a recurring 15-minute weekly task and it is
worth more than any on-page change.

---

## 4. What NOT to do

- **Do not write "updated" dates on pages that did not change.** Freshness is
  measured against real decay; a fake date is a lie that Google can detect and
  it destroys trust when a reader notices.
- **Do not mass-generate location or service pages.** "Scaled content abuse" is
  a named spam policy, and commodity pages actively hurt the domain.
- **Do not buy links.** Link spam updates target exactly this, and a manual
  action is the only true penalty — with a formal reconsideration process you
  would not want to invite.
- **Do not chase the Quality Rater Guidelines as a checklist.** Mueller's own
  position, quoted above.
- **Do not delete content reflexively after a core update.** Google's guidance is
  explicit that most sites do not need to do anything, and that deleting is a
  last resort which often signals the content was written for engines, not people.

---

## 5. Measurement, in this order

1. **Google Search Console**, before anything else: which queries actually
   impression, and which pages lost ground. A drop is diagnosable only here.
2. **Manual Actions report** — separates a human penalty from an algorithmic
   reassessment. The recovery paths are completely different.
3. **Core Web Vitals**, field data, against the 2.0s LCP bar.
4. **Rich Results Test** on the schema, after 3.1 lands.
5. **Compare the week before a confirmed update against the week after rollout
   completes** — not mid-rollout. Rollouts take one to six weeks and rankings
   swing in both directions while they run.

---

## 6. Sourcing

- Google Search Central, *Core Updates* and *March 2024 core update & new spam policies*
- Google Search Central, *Creating helpful, reliable, people-first content* (updated October 2026)
- Search Engine Journal, *Google Algorithm Updates: A Complete History* (updated April 2026)
- Search Engine Journal, *Google Changed Its Helpful Content Guidelines To Emphasize Good "Main Content"* (October 2026)
- Search Engine Journal / Aergos, coverage of Mueller's May 2026 clarification that the rater guidelines are not a ranking guide
- White Hat Agency, *9 SEO Ranking Factors That Actually Matter in 2026*
- Koira, *Google's 2025–2026 Algorithm Shifts: What Small Businesses Actually Need to Do*