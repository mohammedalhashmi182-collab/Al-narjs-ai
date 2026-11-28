"""Protect the scoped preview workshop UI and honest integration copy."""
from fastapi.testclient import TestClient

from src.main import app


def test_glass_preview_home_has_inline_details_and_only_market_ready_channels(monkeypatch):
    monkeypatch.setenv("DISABLE_LEGACY_REDIRECT", "1")
    with TestClient(app, base_url="https://narjis-workshop-preview.onrender.com") as client:
        for lang, hidden in (("ar", "قادم قريبًا"), ("en", "Coming soon")):
            response = client.get(f"/{lang}/home")
            assert response.status_code == 200
            page = response.text
            assert f'data-lang="{lang}"' in page
            assert 'id="njInlineDetail"' in page
            assert 'data-workshop-detail' in page
            assert f'{lang}/services/chatbots' in page
            assert 'narjis-workshop-detail.js?v=1' in page
            assert 'narjis-workshop-contrast.css?v=1' in page
            assert 'narjis-glass-towers.svg' not in page
            assert all(f'flow-{tower}.webp' in page for tower in ('kingdom', 'faisaliah', 'tv', 'majdoul'))
            assert "Moyasar" not in page and "ميسر" not in page
            assert "/api/pulse" not in page and "pulseLeads" not in page
            assert hidden not in page and "feat-coming" not in page.split("<body", 1)[1]
            pricing = client.get(f"/{lang}/pricing").text
            assert "feat-coming" not in pricing.split("<body", 1)[1]
            assert 'href="/terms"' in page
            sections = ['top', 'services', 'team', 'how', 'integrations', 'pricing']
            indices = [page.index(f'id="{section}"') for section in sections]
            assert indices == sorted(indices)


def test_public_details_match_glass_but_do_not_restyle_legal(monkeypatch):
    monkeypatch.setenv("DISABLE_LEGACY_REDIRECT", "1")
    with TestClient(app, base_url="https://narjis-workshop-preview.onrender.com") as client:
        for lang in ("ar", "en"):
            for subpath in ("services/chatbots", "ai-agent/social_media"):
                response = client.get(f"/{lang}/{subpath}")
                assert response.status_code == 200
                assert "narjis-workshop-detail-page.css" in response.text
            response = client.get(f"/{lang}/terms")
            assert response.status_code == 200
            assert "narjis-workshop-detail-page.css" not in response.text


def test_crystal_opening_preserves_the_original_art_and_one_quote_form(monkeypatch):
    monkeypatch.setenv("DISABLE_LEGACY_REDIRECT", "1")
    with TestClient(app, base_url="https://narjis-workshop-preview.onrender.com") as client:
        for lang in ("ar", "en"):
            html = client.get(f"/{lang}/home").text
            hero = html.split('<section class="hero"', 1)[1].split("</section>", 1)[0]
            assert 'src="/static/img/hero-najdi.webp"' in hero
            assert 'srcset="/static/img/hero-najdi-800.webp"' in hero
            assert hero.count('id="ngHeroForm"') == html.count('id="ngHeroForm"') == 1
            assert hero.count('name="problem"') == 1
            assert 'id="ngHeroForm" action="/api/ceo/consult" method="post"' in hero
            assert hero.index('id="heroCeo"') < hero.index('id="ngHeroForm"') < hero.index('id="heroWhatsapp"')
            assert 'data-open-sample' in hero and 'id="start-ceo"' in hero
