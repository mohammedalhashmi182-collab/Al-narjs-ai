"""Host-isolated, read-only brand pages. Starts without importing Narjis Core."""

from __future__ import annotations

import os
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response
from starlette.routing import Route

from src.white_label.config import RIYADH, Manifest, normalize_domain

_MAX_LOGO_BYTES = 256_000
_MAX_LOGO_DIMENSION = 2048
_HEADERS = {
    "Cache-Control": "private, no-store",
    "Content-Security-Policy": (
        "default-src 'none'; img-src 'self'; style-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Robots-Tag": "noindex, nofollow",
}


def _host(request: Request) -> str:
    hosts = request.headers.getlist("host")
    if len(hosts) != 1:
        return ""
    try:
        # Host comes directly from the TLS ingress. Forwarded headers and
        # nonstandard ports do not select tenants.
        return normalize_domain(hosts[0].removesuffix(":443"))
    except ValueError:
        return ""


def _load_logos(manifest: Manifest, assets_dir: Path | None) -> dict[str, bytes]:
    logos = {}
    for tenant in manifest.tenants:
        if not tenant.brand.logo_png:
            continue
        if assets_dir is None:
            raise ValueError("a logo directory is required for enabled brand logos")
        root = assets_dir.resolve()
        path = root / f"{tenant.tenant_id}.png"
        if path.is_symlink() or not path.is_file():
            raise ValueError("the configured tenant logo must be a local PNG file")
        with path.open("rb") as logo:
            data = logo.read(_MAX_LOGO_BYTES + 1)
        if len(data) > _MAX_LOGO_BYTES:
            raise ValueError("the configured logo must be a PNG under 256 kB")
        try:
            with Image.open(BytesIO(data), formats=("PNG",)) as image:
                if max(image.size) > _MAX_LOGO_DIMENSION:
                    raise ValueError("the configured PNG logo exceeds 2048 pixels per side")
                image.verify()
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError("the configured logo must be a valid PNG") from exc
        logos[tenant.tenant_id] = data
    return logos


def build_app(manifest: Manifest, assets_dir: Path | None = None) -> Starlette:
    tenants = {tenant.domain: tenant for tenant in manifest.tenants}
    logos = _load_logos(manifest, assets_dir)

    async def brand_surface(request: Request) -> Response:
        tenant = tenants.get(_host(request))
        if (
            tenant is None
            or not tenant.features.public_brand_page
            or not tenant.license.allows_service_on(datetime.now(RIYADH).date())
        ):
            return PlainTextResponse("Not found", status_code=404, headers=_HEADERS)

        path = request.url.path
        brand = tenant.brand
        if path == "/logo.png":
            logo = logos.get(tenant.tenant_id)
            if logo is None:
                return PlainTextResponse("Not found", status_code=404, headers=_HEADERS)
            return Response(logo, media_type="image/png", headers=_HEADERS)

        if path == "/brand.css":
            return Response(
                _CSS.replace("--brand-accent", brand.accent),
                media_type="text/css",
                headers=_HEADERS,
            )

        language = request.query_params.get("lang")
        if language not in {"ar", "en"}:
            language = brand.default_language
        arabic = language == "ar"
        direction = "rtl" if arabic else "ltr"
        name = escape(brand.name_ar if arabic else brand.name_en)
        description = escape(brand.description_ar if arabic else brand.description_en)
        toggle = (
            '<a lang="en" href="/?lang=en">English</a>'
            if arabic
            else '<a lang="ar" dir="rtl" href="/?lang=ar">العربية</a>'
        )
        contact = "التواصل عبر البريد" if arabic else "Contact by email"
        email = quote(brand.support_email, safe="@.+-_")
        image = '<img src="/logo.png" alt="" width="104" height="104">' if brand.logo_png else ""
        return HTMLResponse(
            f'<!doctype html><html lang="{language}" dir="{direction}"><head>'
            f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{name}</title><link rel="stylesheet" href="/brand.css"></head>'
            f'<body><header>{toggle}</header><main>{image}<h1>{name}</h1><p>{description}</p>'
            f'<a class="contact" href="mailto:{email}">{contact}</a></main></body></html>',
            headers=_HEADERS,
        )

    app = Starlette(routes=[
        Route("/", brand_surface),
        Route("/brand.css", brand_surface),
        Route("/logo.png", brand_surface),
    ])
    app.router.redirect_slashes = False
    return app


def create_app() -> Starlette:
    """ASGI factory for a dedicated deployment with a private manifest mount."""
    manifest_path = Path(os.environ["NARJIS_WHITE_LABEL_MANIFEST"]).resolve()
    manifest = Manifest.load(manifest_path)
    return build_app(manifest, manifest_path.parent / "brand_assets")


_CSS = """html { color-scheme: dark; background: #12100d; color: #f4eee2; }
body { font: 1rem/1.65 system-ui, sans-serif; margin: auto; max-inline-size: 64rem;
       padding-inline: clamp(1.25rem, 6vw, 4rem); }
header { display: flex; justify-content: flex-end; padding-block: 1.25rem; }
main { border-block-start: 3px solid --brand-accent; padding-block: clamp(2rem, 10vw, 7rem); }
h1 { font-size: clamp(2rem, 8vw, 4rem); line-height: 1.2; margin-block: 1rem; }
p { color: #b8ae9c; max-inline-size: 45ch; overflow-wrap: anywhere; }
img { object-fit: contain; max-width: 100%; }
a { color: inherit; text-underline-offset: 0.35em; }
a:focus-visible { outline: 2px solid #f4eee2; outline-offset: 0.25rem; }
.contact { display: inline-block; margin-block-start: 1rem; padding: 0.7em 1.1em;
           border: 1px solid #b8ae9c; border-radius: 0.5rem; }
"""
