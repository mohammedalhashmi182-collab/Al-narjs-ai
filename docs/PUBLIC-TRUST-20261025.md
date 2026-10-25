# Public trust and simulation refresh — 25 October 2026

## Shipped in this change
- `/tour`, `/ar/tour`, `/en/tour`: six-step scripted customer-bot / consultant / specialist / reviewer demonstration. A persistent visible disclosure identifies fictional data and scripted dialogue. There are no business API calls, payment actions, customer quotes or fabricated sales metrics.
- Detailed fictional case description explains inputs, scope, outputs and limitations.
- A real 60-second screen capture of that simulation, with Arabic/English caption tracks and no autoplay. The video is a product illustration, not a recording of a paying customer or proof of delivery.
- Landing page links the tour and highlights five EXISTING practical articles; ten published articles already existed. This change fixes the Arabic blog title rather than creating duplicate SEO pages.
- A second founder-story paragraph describes the product's working method. No invented career history or artificial face is attributed to the founder.
- A public footer adds working links to tour, resources, pricing, story and sitemap.
- The WhatsApp button reads the current business number from the existing setting, validates/normalizes it, and renders on public marketing pages. It opens a real wa.me link; no message is sent automatically. Checkout/invoice/private pages keep their on-site support flow.
- Subscription CTA becomes “اشترك الآن” only when `payments_open()` reports a real available collection method. The Moyasar hold and all payment/activation logic remain unchanged.
- Public Arabic microcopy is more consistent with the service pages: clear professional Arabic, with natural dialogue reserved for labelled examples.

## Owner-supplied evidence still needed
- A genuine founder photo: add an approved file in `src/web/static/founder/` and set `founder_portrait` in `content/public_identity.json` to `{ "filename": "karim.jpg", "owner_approved": true }`. No placeholder image is shown as a real person.
- Official social profile URLs: append entries `{ "label": "LinkedIn", "url": "https://www.linkedin.com/company/ACTUAL_ACCOUNT", "owner_verified": true }` ONLY after verifying the actual account. Defaults are empty; no invented handles or dead social buttons.
- Customer testimonial/case study: use the existing approved-testimonial loader for real quotes. Fictional scenarios must not be put in `content/testimonials.json` or sold as customer outcomes.

## Verification boundaries
Tests can validate the wa.me destination, keyboard/mobile layout and safe rendering. They do not prove that a human monitors that number or that an external social account belongs to the owner.
The simulated transcript is intentionally scripted. It is not an end-to-end production AI, payment, subscription or delivery test.

## Safe release
Feature branch and PR only. Main auto-deploys; review the tour/video and tests before merging. No database migration, pricing change, integration-key update or Render configuration change is included.
