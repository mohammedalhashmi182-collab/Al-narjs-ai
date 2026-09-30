# Al-Narjis Design System — ODSF v0.3

Single source of truth for the visual identity of [karmaai.online](https://karmaai.online).
`tests/test_design_system.py` enforces this file. If a test fails, fix the CSS — not the test.

**ODSF v0.3** keeps the gold/green/Cairo brand DNA (sections 2–7 below) and adds the
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

The light values below are the canonical brand palette — the single source of the brand hues
(gold, green) and the neutral surfaces for printed invoices. Public pages present them in the
Luxury Dark mode of §8.

| Token | Value | Role |
| --- | --- | --- |
| `--gold` | `#F4C430` | Primary — the warm heart of the narjis flower. Primary buttons, active states, key emphasis. |
| `--gold-deep` | `#C9A227` | Pressed / hover state, gold text on light surfaces (contrast-safe). |
| `--gold-wash` | `#FEF6DC` | Tinted background for highlighted blocks. |
| `--green` | `#4F7942` | Secondary — calm herbal green. Outlines, links, "organic/automation" accents, success. |
| `--green-deep` | `#3D5F33` | Pressed state, green text on light surfaces. |
| `--green-wash` | `#EEF3EA` | Tinted background. |
| `--bg` | `#FAFAF9` | Page background — very light ivory. Wide, restful whitespace. |
| `--surface` | `#FFFFFF` | Cards, panels, sheets. |
| `--ink` | `#292524` | Primary text. High-contrast warm dark grey. |
| `--ink-2` | `#57534E` | Secondary text, captions. |
| `--ink-3` | `#8A8580` | Muted text, placeholders, disabled. |
| `--line` | `#E7E5E4` | Hairline borders and dividers. |
| `--line-soft` | `#F0EFEE` | Inner dividers, table rules. |

**Rules**

- Gold is the *action* colour. Never use it for body text on `--bg` (fails contrast) — use
  `--gold-deep` for gold text.
- Green is the *structure* colour: secondary buttons, links, informational accents.
- Exactly one gold primary button per view. A second gold button halves the first one's power.
- Do not introduce a third brand hue. Status colours (`--ok`, `--warn`, `--err`) are the only
  permitted exception and must not be used decoratively.

```css
:root {
  --gold:      #F4C430;
  --gold-deep: #C9A227;
  --gold-wash: #FEF6DC;
  --green:      #4F7942;
  --green-deep: #3D5F33;
  --green-wash: #EEF3EA;
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
| `.btn-primary` | `--gold` background, `--ink` text, `rounded-lg` (12px), weight 600. Hover `--gold-deep`. |
| `.btn-secondary` | Transparent background, 1px `--green` border, `--green-deep` text, `rounded-lg`. |
| `.btn-ghost` | No border, `--ink-2` text. Tertiary actions only. |

Every button: 48px min touch height, 16px×24px padding, visible `:focus-visible` ring in
`--green` at 2px offset. Disabled state uses `--ink-3` on `--bg`.

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

- **Telegram is the only support channel** — <https://t.me/AlNarjs7BOT>, support deep link
  `?start=support`. Public pages must link Telegram and must never contain `wa.me` or any
  WhatsApp reference. `tests/test_design_system.py` enforces this.
- The WhatsApp Cloud API integration (router, sender, webhook, 360dialog gateway) was
  **retired**. The `WHATSAPP_*` settings remain as inert no-ops so no deployed environment or
  secret store breaks; removing them is a separate, explicitly-approved step.
- `src/services/intent_classify.py` holds the channel-neutral intent classification shared by
  inbound pipelines.
- Outreach drafts carry a Telegram share deep link, never a `wa.me` link.

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
| `--lux-glow` | `rgba(0,212,156,.28)` | Aura behind mint actions (public dark). |

> **Owner revision (Humain-inspired, Luxury Dark):** on the public dark presentation the single
> action hue is a **Humain-family green** — mint `#00D49C` (action) / teal `#00AD92` (hover) /
> deep aqua `#00879F` (structure) with the signature lime `#D0F94A` accent and the
> `lime → mint → aqua` gradient on key headlines and CTAs. The yellow/gold was removed from the
> public site on the owner's request ("ثيم مثل موقع هيومين على خلفية داكنة"). Token names that
> historically said "gold" (`--gold`, `--odsf-gold`, `.btn-gold`…) are kept for compatibility but
> reference for printed light surfaces; the owner console keeps its own dark admin accent.

**Rules**

- Brand hues, radii, Cairo type and the one-single-action rule carry over unchanged from §1–§5,
  with the action hue resolved to the Humain mint family on the public dark surfaces (see revision note above).
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
