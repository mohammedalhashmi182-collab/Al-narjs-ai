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
)

# Public, indexable pages: (path, changefreq, priority)
CORE_PAGES: list[tuple[str, str, float]] = [
    ("/home", "weekly", 1.0),
    ("/consult", "monthly", 0.9),
    ("/guide", "monthly", 0.8),
    ("/ai-agents-saudi-businesses", "weekly", 0.9),
    ("/blog", "weekly", 0.8),
    ("/privacy", "yearly", 0.2),
    ("/terms", "yearly", 0.2),
    ("/data-deletion", "yearly", 0.2),
]

PUBLIC_AGENT_PREFIX = "/ai-agent"
INTENT_PAGE = "/ai-agents-saudi-businesses"
BLOG_PREFIX = "/blog"


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
    return base in {p for p, _c, _pr in CORE_PAGES}


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
    parts = [
        "  <url>",
        f"    <loc>{escape(_loc(base))}</loc>",
        f'    <xhtml:link rel="alternate" hreflang="ar" href="{escape(_loc("/ar" + base))}"/>',
        f'    <xhtml:link rel="alternate" hreflang="en" href="{escape(_loc("/en" + base))}"/>',
        f'    <xhtml:link rel="alternate" hreflang="x-default" href="{escape(_loc(base))}"/>',
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
    lines.append("")
    return "\n".join(lines)
