"""Acceptance tests for the separate white-label ASGI service."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError
from src.white_label.app import build_app
from src.white_label.config import Manifest
from starlette.testclient import TestClient

TEST_TENANT = {
    "tenant_id": "example-one",
    "domain": "one.example.test",
    "brand": {
        "name_ar": "العلامة الأولى",
        "name_en": "Brand One",
        "description_ar": "صفحة الشركة الأولى",
        "description_en": "The first company",
        "support_email": "team@one.example.test",
        "accent": "#FF5A36",
    },
    "license": {"state": "active", "expires_on": "2099-01-01"},
    "features": {"public_brand_page": True},
}


def manifest(*tenants, mode="hosted"):
    return Manifest.model_validate_json(json.dumps({"mode": mode, "tenants": tenants}))


def test_host_mapping_localization_and_no_core_routes():
    second = deepcopy(TEST_TENANT)
    second.update(tenant_id="example-two", domain="TWO.EXAMPLE.TEST.")
    second["brand"].update(name_en="Brand Two", support_email="other@two.example.test")
    with TestClient(build_app(manifest(TEST_TENANT, second))) as client:
        first = client.get(
            "/?lang=en",
            headers={
                "host": "one.example.test",
                "x-forwarded-host": "two.example.test",
                "x-tenant-id": "example-two",
                "cookie": "narjis_owner=irrelevant",
            },
        )
        assert first.status_code == 200
        assert '<html lang="en" dir="ltr">' in first.text
        assert "Brand One" in first.text
        assert "Brand Two" not in first.text
        assert "other@two.example.test" not in first.text
        assert first.headers["cache-control"] == "private, no-store"
        assert first.headers["x-robots-tag"] == "noindex, nofollow"
        assert "set-cookie" not in first.headers

        arabic = client.get("/", headers={"host": "one.example.test:443"})
        assert '<html lang="ar" dir="rtl">' in arabic.text
        assert "العلامة الأولى" in arabic.text
        assert "Brand Two" in client.get(
            "/?lang=en", headers={"host": "two.example.test"}
        ).text

        for path in ("/owner", "/portal", "/api/owner/summary", "/payments", "/voice"):
            assert client.get(path, headers={"host": "one.example.test"}).status_code == 404
        for host in ("unknown.example.test", "one.example.test.invalid", "one.example.test:81"):
            assert client.get("/", headers={"host": host}).status_code == 404
        duplicate_host = client.get("/", headers=[
            ("host", "one.example.test"), ("host", "two.example.test"),
        ])
        assert duplicate_host.status_code == 404


@pytest.mark.parametrize("reason", ["pending", "suspended", "revoked", "expired", "flag-off"])
def test_public_assets_also_require_current_license_and_flag(reason):
    tenant = deepcopy(TEST_TENANT)
    if reason == "flag-off":
        tenant["features"] = {}
    elif reason == "expired":
        tenant["license"]["expires_on"] = "2020-01-01"
    else:
        tenant["license"]["state"] = reason
    with TestClient(build_app(manifest(tenant))) as client:
        for path in ("/", "/brand.css", "/logo.png"):
            assert client.get(path, headers={"host": tenant["domain"]}).status_code == 404


def test_brand_content_is_escaped_and_color_comes_from_configuration():
    tenant = deepcopy(TEST_TENANT)
    tenant["brand"]["name_en"] = "A & B < Partners"
    with TestClient(build_app(manifest(tenant))) as client:
        headers = {"host": tenant["domain"]}
        response = client.get("/?lang=en", headers=headers)
        assert "A &amp; B &lt; Partners" in response.text
        assert "default-src 'none'" in response.headers["content-security-policy"]
        assert "mailto:team@one.example.test" in response.text
        assert "#FF5A36" in client.get("/brand.css", headers=headers).text
        assert client.get("/logo.png", headers=headers).status_code == 404


def test_logos_are_available_on_the_intended_domain_only(tmp_path):
    first = deepcopy(TEST_TENANT)
    second = deepcopy(TEST_TENANT)
    second.update(tenant_id="example-two", domain="two.example.test")
    first["brand"]["logo_png"] = True
    second["brand"]["logo_png"] = True
    logos = {}
    for tenant, color in ((first, "red"), (second, "blue")):
        data = BytesIO()
        Image.new("RGB", (10, 10), color).save(data, "PNG")
        logos[tenant["tenant_id"]] = data.getvalue()
        (tmp_path / f'{tenant["tenant_id"]}.png').write_bytes(data.getvalue())
    with TestClient(build_app(manifest(first, second), tmp_path)) as client:
        for tenant in (first, second):
            headers = {"host": tenant["domain"]}
            response = client.get("/logo.png", headers=headers)
            assert response.content == logos[tenant["tenant_id"]]
            assert response.headers["content-type"] == "image/png"
            assert 'src="/logo.png"' in client.get("/", headers=headers).text

    (tmp_path / "example-two.png").unlink()
    (tmp_path / "example-two.png").write_bytes(bytes.fromhex("89504e470d0a1a0a"))
    with pytest.raises(ValueError, match="valid PNG"):
        build_app(manifest(first, second), tmp_path)

    (tmp_path / "example-two.png").unlink()
    (tmp_path / "example-two.png").symlink_to(tmp_path / "example-one.png")
    with pytest.raises(ValueError, match="local PNG"):
        build_app(manifest(first, second), tmp_path)


def test_manifest_fails_closed_on_ambiguous_or_unsafe_configuration():
    second = deepcopy(TEST_TENANT)
    second.update(tenant_id="example-two", domain="ONE.EXAMPLE.TEST.")
    with pytest.raises(ValidationError, match="domains must be unique"):
        manifest(TEST_TENANT, second)

    second["domain"] = "two.example.test"
    with pytest.raises(ValidationError, match="exactly one tenant"):
        manifest(TEST_TENANT, second, mode="standalone")

    for domain in ("alnarjisai.com", "www.karmaai.online", "two.example.test/path", "K.example.test"):
        second["domain"] = domain
        with pytest.raises(ValidationError):
            manifest(second)

    second["domain"] = "two.example.test"
    second["license"].pop("expires_on")
    with pytest.raises(ValidationError, match="must have an expiration date"):
        manifest(second)

    second["license"]["state"] = "pending"
    second["brand"]["accent"] = "red; display: none"
    with pytest.raises(ValidationError):
        manifest(second)


def test_standalone_starts_without_core_secrets_or_database(tmp_path):
    config = tmp_path / "manifest.json"
    config.write_text(
        json.dumps({"mode": "standalone", "tenants": [TEST_TENANT]}), encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import sys; from src.white_label.app import create_app; create_app(); "
            "assert 'src.main' not in sys.modules and 'src.db.session' not in sys.modules",
        ],
        env={"NARJIS_WHITE_LABEL_MANIFEST": str(config), "PATH": os.defpath},
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, result.stderr
