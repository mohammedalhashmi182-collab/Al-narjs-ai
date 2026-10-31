# Al-Narjis Design System — ODSF v0.3

Single source of truth for the visual identity of [karmaai.online](https://karmaai.online).
`tests/test_design_system.py` enforces this file. If a test fails, fix the CSS — not the test.

**ODSF v0.4** keeps Cairo as the only type family (sections 2–7 below), uses vermilion
`#FF5A36` as the only action hue, and adds the
**Luxury Dark** public presentation (section 8): the whole public site is a cinematic,
near-black, glassmorphic storefront inspired by premium product films. The light palette in
section 2 remains the canonical neutral reference (printed invoices) and the single source
of the brand hues.

---

## 1. Brand voice

**Apple-style / Premium SaaS.** Clean, professional interfaces built on a *cinematic luxury*
identity: generous white space, one decisive call to action per view, and motion that
supports reading rather than competing with it.

Arabic is the primary language and the layout is RTL. Type is **Cairo** (see §5).

---

## 2. Core colors (canonical brand tokens)

The light values below are the canonical brand palette — the single source of the brand hue
(vermilion accent) and the neutral surfaces for printed invoices. Public pages present them in the
Luxury Dark mode of §8. Visible colour is black, white, and `#FF5A36`, plus the darker text orange
and the status red documented below.

| Token | Value | Role |
| --- | --- | --- |
| `--accent` | `#FF5A36` | Primary — vermilion. Large text, button fills, active states, key emphasis. |
| `--accent-ink` | `#C2410C` | Small text and small UI marks on white and ivory. |
| `--accent-deep` | `#D93F1E` | Pressed / hover fill only. Not for small text. |
| `--accent-wash` | `#FFEAE4` | Tinted background for highlighted blocks. |

**Why vermilion and not gold.** Gold (`#F4C430`) was the action hue until the owner
retired it. The replacement was chosen from 2026 evidence rather than taste, and
every claim below is measured:

| Requirement | Result |
|---|---|
| One saturated accent on a near-black canvas (the 2026 norm for AI/SaaS) | 6.30:1 against `#060607` — AA |
| Ink text on an accent-filled control | 5.62:1 — AA at body size |
| **White text on the accent fill** | **3.10:1 — fails AA. Every accent-filled control therefore uses the dark ink, never `#fff`.** |
| Outside the 220°–280° band that research now identifies as AI-generated convergence (indigo, blue→purple gradients) | `#FF5A36` sits at ~14° |
| Clear of the Telegram blue `#229ED9`, so a CTA never reads as a chat link | no collision |

The old names are **retired, not deleted**: `--gold`, `--gold-deep`, `--gold-wash`,
`--n-gold*` and `--odsf-gold*` all resolve to the accent family so nothing breaks.
New code must use the accent names.
| `--bg` | `#FAFAF9` | Page background — very light ivory. Wide, restful whitespace. |
| `--surface` | `#FFFFFF` | Cards, panels, sheets. |
| `--ink` | `#292524` | Primary text. High-contrast warm dark grey. |
| `--ink-2` | `#57534E` | Secondary text, captions. |
| `--ink-3` | `#8A8580` | Muted text, placeholders, disabled. |
| `--line` | `#E7E5E4` | Hairline borders and dividers. |
| `--line-soft` | `#F0EFEE` | Inner dividers, table rules. |

**Rules**

- `#FF5A36` on white is **3.10:1** and on `#FAFAF9` is **2.97:1**. It fails WCAG AA for normal text.
- Small text and small UI marks on those light surfaces use `--accent-ink` (`#C2410C`): **5.18:1** on `#FFFFFF` and **4.96:1** on `#FAFAF9`. `#D93F1E` is only 4.49:1 on white, so it is a hover fill, not body text.
- Keep `#FF5A36` for large text (24px, or bold at 18.67px and up), for button and accent fills, and for orange on near-black (**6.53:1** on `#060607`).
- Accent-filled controls use `#000000` (**6.77:1**) or `#292524` (**4.89:1**). White on `#FF5A36` is 3.10:1 and is not used for labels.
- Success and error do not share a colour. Success is a neutral — near-white on dark, near-black on light — with a check mark or its own wording. Error is red: `#B91C1C` on light (**6.47:1** on white) and `#FF8F8F` on the dark console (**7.98:1** on `#1C1917`), with a different icon or label.
- Exactly one accent primary button per view. A second one halves its power.
- Do not introduce another brand hue. Status red is the only permitted exception and must not be used decoratively.

```css
:root {
  --accent:      #FF5A36;
  --accent-ink:  #C2410C;
  --accent-deep: #D93F1E;
  --accent-wash: #FFEAE4;
  --bg:         #FAFAF9;
  --surface:    #FFFFFF;
  --ink:        #292524;
  --ink-2:      #57534E;
  --ink-3:      #8A8580;
  --line:       #E7E5E4;
  --line-soft:  #F0EFEE;
}
```

---

## 3. Spacing & layout — the 8pt grid

All spacing is a multiple of **8px**. `spacing-16` is the default card padding; `spacing-32`
separates top-level sections.

| Token | Value | Typical use |
| --- | --- | --- |
| `--sp-1` | 8px | Icon gaps, chip padding |
| `--sp-2` | 16px | **Default card padding** (`spacing-16`) |
| `--sp-3` | 24px | Inner block gap |
| `--sp-4` | 32px | **Section separation** (`spacing-32`) |
| `--sp-6` | 48px | Card gap in a grid |
| `--sp-8` | 64px | Section padding (tablet) |
| `--sp-12` | 96px | Section padding (desktop) |
| `--sp-16` | 128px | Hero padding, footer breathing room |

- Content max width: **1200px** (`--wrap`), prose 720px.
- Section padding: 96px top/bottom on desktop, 64px tablet, 48px mobile. The 128px value is
  reserved for the hero and footer, not for every section.
- Grid: 12 columns, 24px gutter.

```css
:root {
  --sp-1: 8px;  --sp-2: 16px; --sp-3: 24px; --sp-4: 32px;
  --sp-6: 48px; --sp-8: 64px; --sp-12: 96px; --sp-16: 128px;
  --wrap: 1200px;
}
```

---

## 4. Typography

- **Cairo** is the only family, Arabic and Latin, 400/500/600/700.
  `Tajawal`, `Almarai`, `Manrope`, `IBM Plex Sans Arabic` and `Inter` are retired.
- Display sizes use weight 700 with a slight negative letter-spacing; body copy stays 400 and
  never drops below 16px. Line-height 1.7 for Arabic body, 1.2 for headlines.
- Numerals in tables and prices use `font-variant-numeric: tabular-nums`.

---

## 5. Components

### Buttons

| Class | Style |
| --- | --- |
| `.btn-primary` | `--accent` (`#FF5A36`) background, `#000000` text, `rounded-lg` (12px), weight 600. Hover `--accent-deep`. |
| `.btn-secondary` | Transparent background, 1px `--line` border, `--ink` text, `rounded-lg`. |
| `.btn-ghost` | No border, `--ink-2` text. Tertiary actions only. |

Every button: 48px min touch height, 16px×24px padding, visible `:focus-visible` ring in
`--accent-ink` at 2px offset. Disabled state uses `--ink-3` on `--bg`.

### Cards

- `--surface` background, 1px `--line` border, `rounded-lg` (12px), `--shadow-sm`
  (`0 1px 2px rgba(41,37,36,.06), 0 8px 24px rgba(41,37,36,.04)`).
- Hover lifts 2px and deepens the shadow to `--shadow-md` — never a glow, never a scale
  beyond `1.01`.
- `spacing-16` internal padding as the default.

### Sections

- Scroll-driven reveals: opacity + 16px translate, 600ms `cubic-bezier(.16,1,.3,1)`, staggered
  60ms per child, triggered by `IntersectionObserver` at 20% visibility.
- Every reveal is disabled under `prefers-reduced-motion: reduce`.
- No parallax on text. No autoplaying video with sound.

---

## 6. Support channel & integrations

- **Customer contact is the on-site assistant only; work is delivered by email.** No phone or email is published as a public contact channel; keep the operator legal identity (Ahmed Abdullah Al-Zahrani, FL-272182297).
  Public pages must not publish WhatsApp or Telegram short links, and must not tell visitors
  to message the company on WhatsApp or Telegram.
- The Telegram bot and the WhatsApp Cloud API stay owner-enabled product channels. Their
  routes stay live; do not assume either one is the public contact path.
- `src/services/intent_classify.py` holds the channel-neutral intent classification shared by
  inbound pipelines.
- Outreach drafts are private messages to one lead, never a WhatsApp or Telegram short link; no public page lists a phone or email as a contact channel.

---

## 7. Voice of customer-facing copy

Practical, clear, motivating, direct. No filler.

- Arabic first; English is a translation, not a rewrite.
- Say the price, the deliverable, and the next step. No "revolutionary", "game-changing",
  "unleash", "seamless".
- Never claim customers, results, or metrics that do not exist.

---

## 8. Luxury Dark public presentation (ODSF v0.3)

Every public page (`landing`, `portal`, `guide`, `consult`, `package`, `payment_status`,
`agent_public`, `blog_*`, `intent_agents`, `login`, `privacy`/`terms`/`data_deletion`) renders
on a deep near-black canvas. The owner console (`narjis-dark-admin.css`) keeps its own dark
surfaces. Printed invoices (`invoice.html`, `invoice_en.html`) stay light on purpose.

| Token (public dark) | Value | Role |
| --- | --- | --- |
| `--lux-bg` | `#060607` | Page background — near-black with a warm hint. |
| `--lux-bg-alt` | `#0B0B0D` | Alternating section background. |
| `--lux-surface` | `#101014` | Opaque card base under the glass layer. |
| `--lux-glass` | `rgba(255,255,255,.04)` | Glassmorphism fill. |
| `--lux-glass-line` | `rgba(246,245,244,.09)` | Hairline border on glass. |
| `--lux-ink` | `#F6F5F4` | Primary text — near-white, warm. |
| `--lux-ink-2` | `#B9B8C0` | Secondary text. |
| `--lux-ink-3` | `#8E8D96` | Muted text, captions. |
| `--lux-glow` | `rgba(255,90,54,.28)` | Aura behind vermilion actions (public dark). |

> **Owner revision (2026-10-31, supersedes gold and the Humain mint):** the visible palette
> is black, white, and `#FF5A36`. Kouki confirmed the star mark is `#FF5A36`, not gold.
> Small text on light surfaces uses `#C2410C`. The earlier mint/teal direction
> (`#00D49C` / `#00AD92` / `#00879F`) and the herbal structure colour are retired and
> must not appear on a visible surface. Gold (`#F4C430` and the star's old `#E9C873` /
> `#C9A24A`) is retired the same way.
>
> Tokens that historically named a retired hue are kept for compatibility; only their
> values change. `tests/test_design_system.py` enforces this section.

**Rules**

- Brand hues, radii, Cairo type and the one-single-action rule carry over unchanged from §1–§5.
  On the public dark surfaces the action hue is `#FF5A36` (see the revision note above).
- Cards: `--lux-glass` fill, 1px `--lux-glass-line` border, `--lux-surface` fallback,
  `backdrop-filter: blur(14px)`, radius 16px, and a faint border glow that brightens on hover
  — never a hard neon, always a whisper (alpha ≤ `.28`).
- Heading scale is intentionally oversized and hard: `clamp(2.5rem, 8vw, 6rem)` for the hero,
  weight 800, tight leading, generous white space. Muted grey (`--lux-ink-2/-3`) carries captions.
- Cinematic hero: a moving light sequence (CSS conic beams + canvas particle field) sits behind
  the interactive agent console; no external video, no audio, `prefers-reduced-motion` disables
  the motion.
- Smooth scroll and scroll-driven reveals use **Lenis + GSAP/ScrollTrigger**, vendored locally
  (no CDN). Reveals are opacity + `16px` translate, ≤600ms, and are fully disabled under
  `prefers-reduced-motion: reduce`.
- Content and SEO contracts are unchanged: no dead CTAs, catalog-sourced numbers, per-view
  single action, bilingual copy, JSON-LD, `body [data-lang]` scoped hide rule.

Practical, clear, motivating, direct. No filler.

- Arabic first; English is a translation, not a rewrite.
- Say the price, the deliverable, and the next step. No "revolutionary", "game-changing",
  "unleash", "seamless".
- Never claim customers, results, or metrics that do not exist.

---

## v2 "Najd Night" — public landing (CEO-advisor rebrand, 2026-10)

The landing page (`/home`) now uses its own layer, `src/web/static/css/narjis-v2.css`.
App pages (portal, consult, invoices, owner console) keep ODSF v0.2 above until migrated.

| Token | Value | Use |
|---|---|---|
| `--v2-canvas` | `#0c0a08` | deep warm black: hero, dark sections, footer, `theme-color` |
| `--v2-ivory` | `#f6f3ea` | reading canvas |
| `--v2-ink` | `#10201a` | body text |
| `--v2-green` | `#c2410c` | Light-theme action fill (white label 5.18:1). The name is historical; the value is not green. Dark pricing overrides it to `#FF5A36` with a black label. |
| `--v2-saffron` | `#ff5a36` | Detail accent on the dark pricing page. Not a large field. |
| `--v2-saudi` | `#c2410c` on the light layer, `#fafaf9` on dark pricing | Confirmation marks. Not a green. |

Type: **Alexandria** (display) + **Noto Sans Arabic** (text). One primary button per block.
The page is rendered in one language server-side (`/ar/...`, `/en/...`), RTL first.
All motion honours `prefers-reduced-motion`. `tests/test_design_system.py` enforces these tokens,
the contrast ratios and the font loading.
