"""SEO surface for public pages: canonical URLs, sitemap.xml, robots.txt.

Single source of truth so the sitemap can never advertise a URL that 404s
or a host that redirects.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from src.config.settings import get_settings

# Paths that must never be indexed or advertised.
PRIVATE_PREFIXES = (
    "/api",
    "/webhooks",
    "/portal",
    "/acquisition",
    "/company",
    "/login",
    "/logout",
    "/workflows",
    "/schedules",
    "/executions",
    "/conversations",
    "/settings",
    "/owner",
    "/agents",  # owner-only agent console (/ai-agent/<slug> is the public one)
    "/demo",
    "/invoice",
    "/payment",
    # Karmish left this application. The console is now a separate product with
    # its own repository, its own host and its own login; nothing under /karmish
    # is served here any more. The entry stays so that any stale link, bookmark
    # or crawler request for it is classified as private rather than public.
    "/karmish",
)

# Public, indexable pages: (path, changefreq, priority)
CORE_PAGES: list[tuple[str, str, float]] = [
    ("/home", "weekly", 1.0),
    ("/pricing", "weekly", 0.9),
    ("/consult", "monthly", 0.9),
    ("/about", "monthly", 0.6),
    ("/contact", "monthly", 0.5),
    ("/voice", "monthly", 0.8),
    ("/guide", "monthly", 0.8),
    ("/early-access", "monthly", 0.7),
    ("/ai-agents-saudi-businesses", "weekly", 0.9),
    ("/blog", "weekly", 0.8),
    ("/privacy", "yearly", 0.2),
    ("/terms", "yearly", 0.2),
    ("/refund-policy", "yearly", 0.2),
    ("/data-deletion", "yearly", 0.2),
    ("/docpack", "monthly", 0.7),
    ("/capabilities/forecast", "monthly", 0.6),
    ("/capabilities/ocr", "monthly", 0.6),
    ("/capabilities/style", "monthly", 0.6),
    ("/capabilities/eval", "monthly", 0.6),
    ("/status", "daily", 0.4),
    ("/changelog", "weekly", 0.5),
    ("/sla", "monthly", 0.4),
    ("/partnerships", "monthly", 0.6),
    ("/docs", "monthly", 0.5),
]

PUBLIC_AGENT_PREFIX = "/ai-agent"
INTENT_PAGE = "/ai-agents-saudi-businesses"
BLOG_PREFIX = "/blog"
SERVICE_PREFIX = "/services"
# Public service pages. Slugs match src/services/public_services.py.
SERVICE_SLUGS = (
    "automation",
    "chatbots",
    "graphic-design",
    "ui-ux-design",
    "content-writing",
    "translation",
)


def site_origin() -> str:
    """Canonical origin. The apex domain is canonical; www redirects to it."""
    domain = (get_settings().domain or "karmaai.online").strip()
    domain = domain.removeprefix("https://").removeprefix("http://").strip("/")
    return f"https://{domain}"


def is_public_path(path: str) -> bool:
    base = _base_path(path)
    if base in ("", "/"):
        return True
    if any(base == p or base.startswith(p + "/") for p in PRIVATE_PREFIXES):
        return False
    if base.startswith(PUBLIC_AGENT_PREFIX + "/") or base.startswith(BLOG_PREFIX + "/"):
        return True
    if base.startswith(SERVICE_PREFIX + "/"):
        return base[len(SERVICE_PREFIX) + 1 :] in SERVICE_SLUGS
    return base in {p for p, _c, _pr in CORE_PAGES}


def arabic_canonical_redirect(path: str) -> str | None:
    """Unprefixed public pages 301 to the Arabic URL. Root and private routes stay.

    ``/`` is the owner dashboard when signed in, so it is not redirected here.
    """
    if not path or path == "/":
        return None
    if path.startswith(("/static", "/brand/", "/api", "/webhooks")):
        return None
    if path in ("/robots.txt", "/sitemap.xml", "/llms.txt", "/favicon.ico"):
        return None
    for lang in ("ar", "en"):
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            return None
    if not is_public_path(path):
        return None
    return "/ar" + path


def _split_locale(path: str) -> tuple[str | None, str]:
    for lang in ("ar", "en"):
        if path == f"/{lang}":
            return lang, "/"
        if path.startswith(f"/{lang}/"):
            return lang, path[len(lang) + 1 :] or "/"
    return None, path


def indexable_page(path: str) -> bool:
    """True only when this exact path is a page we actually serve.

    ``is_public_path`` treats every ``/blog/<slug>`` and ``/ai-agent/<slug>`` as
    public so the sitemap policy stays simple. A redirect must not send people
    to a slug that 404s, so those two prefixes are checked against the catalog.
    """
    base = path if path.startswith("/") else f"/{path}"
    if len(base) > 1:
        base = base.rstrip("/") or "/"
    if base.startswith(f"{BLOG_PREFIX}/"):
        slug = base[len(BLOG_PREFIX) + 1 :]
        if not slug or "/" in slug:
            return False
        from src.services.blog_articles_1 import ARTICLES

        return any(article["slug"] == slug for article in ARTICLES)
    if base.startswith(f"{PUBLIC_AGENT_PREFIX}/"):
        slug = base[len(PUBLIC_AGENT_PREFIX) + 1 :]
        if not slug or "/" in slug:
            return False
        from src.services.catalog import EMPLOYEES

        return slug in EMPLOYEES
    if not is_public_path(base):
        return False
    if base.startswith(f"{SERVICE_PREFIX}/"):
        return base[len(SERVICE_PREFIX) + 1 :] in SERVICE_SLUGS
    return base in {page for page, _freq, _priority in CORE_PAGES}


def suffix_canonical_redirect(path: str) -> str | None:
    """301 target when a public URL ends with a stray hyphen or a trailing slash.

    Starlette's own slash redirect is a temporary 307, and it is built after the
    locale prefix has been stripped. ``/en/refund-policy/`` therefore 307s to
    ``/refund-policy``, and that bare path 301s to the Arabic page. A trailing
    hyphen (``/en/refund-policy-``) never matched a route. Both should land on
    the same language as the request: English stays English, Arabic stays Arabic,
    and an unprefixed URL still goes to Arabic.
    """
    if not path or path in ("/", "/ar", "/en", "/ar/", "/en/"):
        return None
    if path.startswith(("/static", "/brand/", "/api", "/webhooks")):
        return None
    locale, rest = _split_locale(path)
    if not rest or rest == "/":
        return None
    cleaned = rest
    changed = False
    if cleaned.endswith("/"):
        cleaned = cleaned.rstrip("/") or "/"
        changed = True
    if cleaned.endswith("-"):
        cleaned = cleaned.rstrip("-")
        changed = True
    if not changed or cleaned == rest or not cleaned.startswith("/"):
        return None
    if not indexable_page(cleaned):
        return None
    prefix = f"/{locale}" if locale else "/ar"
    return prefix + cleaned


def _base_path(path: str) -> str:
    for lang in ("ar", "en"):
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            path = path[len(lang) + 1 :] or "/"
            break
    return path or "/"


def _loc(path: str) -> str:
    return f"{site_origin()}{path}"


def _url_entry(path: str, changefreq: str, priority: float, lastmod: str | None = None) -> str:
    base = _base_path(path)
    arabic = "/ar" if base == "/" else "/ar" + base
    english = "/en" if base == "/" else "/en" + base
    parts = [
        "  <url>",
        f"    <loc>{escape(_loc(arabic))}</loc>",
        f'    <xhtml:link rel="alternate" hreflang="ar" href="{escape(_loc(arabic))}"/>',
        f'    <xhtml:link rel="alternate" hreflang="en" href="{escape(_loc(english))}"/>',
        f'    <xhtml:link rel="alternate" hreflang="x-default" href="{escape(_loc(arabic))}"/>',
    ]
    if lastmod:
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority:.1f}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


def build_sitemap(agent_slugs: list[str], articles: list[dict]) -> str:
    """Sitemap built from the real route table, never from a hand-kept file."""
    entries: list[str] = []
    for path, changefreq, priority in CORE_PAGES:
        entries.append(_url_entry(path, changefreq, priority))
    for slug in SERVICE_SLUGS:
        entries.append(_url_entry(f"{SERVICE_PREFIX}/{slug}", "monthly", 0.8))
    for slug in agent_slugs:
        entries.append(_url_entry(f"{PUBLIC_AGENT_PREFIX}/{slug}", "monthly", 0.7))
    for article in articles:
        entries.append(
            _url_entry(
                f"{BLOG_PREFIX}/{article['slug']}",
                "monthly",
                0.6,
                lastmod=article.get("date"),
            )
        )
    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def build_robots() -> str:
    lines = ["User-agent: *", "Allow: /"]
    for prefix in PRIVATE_PREFIXES:
        lines.append(f"Disallow: {prefix}")
    lines.append("")
    lines.append(f"Sitemap: {site_origin()}/sitemap.xml")
    lines.append(f"# LLM guidance: {site_origin()}/llms.txt")
    lines.append("")
    return "\n".join(lines)


def build_llms(employees: list[tuple[str, dict]]) -> str:
    """Public /llms.txt. Prices and names are read from the catalog, not typed here."""
    from src.services.catalog import ADDON_AGENT, PACKAGES, PACKAGE_ORDER

    origin = site_origin()
    plans = []
    for key in PACKAGE_ORDER:
        pkg = PACKAGES[key]
        plans.append(
            f"- {pkg['name_en']} ({pkg['name']}): {pkg['price']} SAR per month. {pkg['tagline_en']}"
        )
    agent_lines = []
    for slug, employee in employees:
        agent_lines.append(
            f"- {employee['title_en']} / {employee['title_ar']}: "
            f"{origin}/en/ai-agent/{slug} · {origin}/ar/ai-agent/{slug}"
        )
    pages = [
        ("Home", "/home"),
        ("Pricing", "/pricing"),
        ("Consultant", "/consult"),
        ("Voice advisor", "/voice"),
        ("About", "/about"),
        ("Contact", "/contact"),
        ("Guide", "/guide"),
        ("Blog", "/blog"),
        ("AI agents for Saudi businesses", "/ai-agents-saudi-businesses"),
        ("Privacy", "/privacy"),
        ("Terms", "/terms"),
        ("Refund policy", "/refund-policy"),
        ("Data deletion", "/data-deletion"),
        ("Status", "/status"),
        ("What's new", "/changelog"),
        ("Service level", "/sla"),
        ("Partnerships", "/partnerships"),
        ("API reference", "/docs"),
    ]
    page_lines = [f"- {label}: {origin}/ar{path} · {origin}/en{path}" for label, path in pages]
    service_lines = [
        f"- {origin}/ar/services/{slug} · {origin}/en/services/{slug}" for slug in SERVICE_SLUGS
    ]
    body = [
        "# النرجس AI (Al-Narjis AI)",
        "",
        f"> Arabic-first AI platform for Saudi businesses. Canonical site: {origin}",
        "",
        "Al-Narjis (النرجس) is a Riyadh platform. An AI chief executive reads a business",
        "problem and proposes a specialist agent team. Work is delivered for review.",
        "The public contact paths are the voice advisor and email. This file describes",
        "the site. It is not a quote, a contract, or a customer list.",
        "",
        "## Languages",
        "",
        "- Arabic is the default. Public pages live under /ar/.",
        "- English pages live under /en/ and must stay in English. Do not treat a",
        "  temporary redirect from an /en/ URL as the canonical page.",
        "- Unprefixed public URLs permanently redirect to the Arabic URL.",
        "- The apex host is canonical. www redirects to it.",
        "",
        "## Plans",
        "",
        "Monthly prices in SAR, before VAT. Names and amounts come from the live catalog.",
        "There is no plan called Basic or Business.",
        *plans,
        f"- Extra agent ({ADDON_AGENT['name_en']} / {ADDON_AGENT['name']}): "
        f"{ADDON_AGENT['price']} SAR per agent per month.",
        "- Annual billing bills 10 months and grants 12. Setup fees, when a plan has one,",
        "  are shown on the pricing page and are not waived by annual billing.",
        "",
        "## Contact",
        "",
        f"- Voice advisor: {origin}/ar/voice and {origin}/en/voice",
        "- Email: AlNarjisai@gmail.com",
        "- The public WhatsApp link is on the home, contact, and voice pages only.",
        "- Operator legal identity on the about and terms pages: freelance document FL-272182297.",
        "  Do not invent a personal name for that document.",
        "",
        "## Key pages",
        "",
        *page_lines,
        "",
        "## Services",
        "",
        *service_lines,
        "",
        "## Specialist agents",
        "",
        "Each agent has its own page, with a worked example labelled as an illustration",
        "and questions specific to that role. These are not customer stories.",
        *agent_lines,
        "",
        "## What this site does not publish",
        "",
        "- No customer testimonials, review scores, logos, awards, or named case studies.",
        "- The service-level page (/sla) is a draft. Do not treat its uptime target",
        "  or credit table as an approved commitment.",
        "- Salla, Zid, and WhatsApp Business connections are in development.",
        "  Do not describe them as available.",
        "- No invented revenue, lead counts, or market sizes.",
        "- The owner console (/agents, /portal, /owner, /api, /webhooks) is not public content.",
        "",
        "## Optional",
        "",
        f"- Sitemap: {origin}/sitemap.xml",
        f"- Robots: {origin}/robots.txt",
        "",
    ]
    return "\n".join(body)
