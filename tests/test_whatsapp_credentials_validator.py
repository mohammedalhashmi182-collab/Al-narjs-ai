"""Tests for ``scripts/verify_whatsapp_credentials.py``.

The Graph API is never contacted: every check receives an injected transport, so
the suite asserts the report contract (success line, Meta error mapping, secret
hygiene) offline.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_whatsapp_credentials.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_whatsapp_credentials", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vwc = _load_module()


FAKE_TOKEN = "EAA" + "AbCdEf0123456789" * 4  # shape-valid, never real


def _creds(**over: Any) -> dict[str, str]:
    creds = {
        "token": FAKE_TOKEN,
        "phone_id": "123456789012345",
        "waba_id": "",
        "app_id": "",
        "app_secret": "",
        "version": "v21.0",
    }
    creds.update(over)
    return creds


def _token_ok_payload() -> dict[str, Any]:
    return {
        "data": {
            "is_valid": True,
            "type": "SYSTEM_USER",
            "scopes": ["whatsapp_business_management", "whatsapp_business_messaging"],
            "app_id": "998877",
            "expires_at": 0,
            "needs_reauth": False,
        }
    }


def _phone_ok_payload() -> dict[str, Any]:
    return {
        "id": "123456789012345",
        "display_phone_number": "+966 50 000 0000",
        "verified_name": "Al Narjis",
        "quality_rating": "GREEN",
        "code_verification_status": "VERIFIED",
        "status": "CONNECTED",
        "is_official_business_account": True,
    }


def _routes(table: dict[str, dict[str, Any]]):
    def transport(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
        for fragment, payload in table.items():
            if fragment in url:
                return payload
        return {"error": {"message": "unexpected url", "code": 1}}

    return transport


# --------------------------------------------------------------------------- #
# Config parsing
# --------------------------------------------------------------------------- #


def test_load_env_file_reads_quotes_and_skips_comments(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nWHATSAPP_TOKEN=\"abc123\"\nWHATSAPP_PHONE_ID='987'\nBROKEN\n",
        encoding="utf-8",
    )
    values = vwc.load_env_file(env)
    assert values["WHATSAPP_TOKEN"] == "abc123"
    assert values["WHATSAPP_PHONE_ID"] == "987"
    assert "BROKEN" not in values


def test_environ_overrides_env_file() -> None:
    creds = vwc.resolve_credentials(
        {"WHATSAPP_TOKEN": "file-token", "WHATSAPP_PHONE_ID": "111"},
        {"WHATSAPP_TOKEN": "env-token"},
    )
    assert creds["token"] == "env-token"
    assert creds["phone_id"] == "111"


def test_missing_credentials_report_config_failure(capsys) -> None:
    code = vwc.main(["--env-file", "definitely-missing.env", "--no-color"])
    assert code == 1
    out = capsys.readouterr().out
    assert "WHATSAPP_TOKEN" in out
    assert "لمد" not in out  # sanity: Arabic text is present elsewhere
    assert "بيانات الاعتماد غير موجودة" in out


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_valid_token_and_phone_produce_green_success(capsys) -> None:
    report = vwc.build_report(
        _creds(),
        _routes({"/debug_token": _token_ok_payload(), "/123456789012345": _phone_ok_payload()}),
    )
    assert report["ok"] is True
    assert report["checks"]["phone"]["display_phone_number"] == "+966 50 000 0000"
    assert report["checks"]["token"]["expired"] == "permanent"

    vwc.render(report, vwc.Colors(False))
    out = capsys.readouterr().out
    assert vwc.SUCCESS_LINE in out
    assert "+966 50 000 0000" in out
    assert "whatsapp_business_messaging" in out


def test_render_never_prints_the_token(capsys) -> None:
    token = "EAA" + "sUpErSeCrEtVaLuE" * 4
    report = vwc.build_report(
        _creds(token=token),
        _routes({"/debug_token": _token_ok_payload(), "/123456789012345": _phone_ok_payload()}),
    )
    vwc.render(report, vwc.Colors(True))
    out = capsys.readouterr().out
    assert token not in out
    assert str(len(token)) in out


def test_waba_check_runs_when_waba_id_is_present() -> None:
    report = vwc.build_report(
        _creds(waba_id="555000111"),
        _routes({
            "/debug_token": _token_ok_payload(),
            "/555000111": {"id": "555000111", "name": "Al Narjis", "account_review_status": "APPROVED"},
            "/123456789012345": _phone_ok_payload(),
        }),
    )
    assert report["ok"] is True
    assert report["checks"]["waba"]["account_review_status"] == "APPROVED"


def test_debug_token_permission_failure_still_validates_the_phone(capsys) -> None:
    """A token that cannot introspect itself is not a failure — the phone call decides."""
    report = vwc.build_report(
        _creds(),
        _routes({
            "/debug_token": {"error": {"message": "Unsupported get request.", "code": 100, "type": "GraphMethodException"}},
            "/123456789012345": _phone_ok_payload(),
        }),
    )
    assert report["ok"] is True
    assert report["checks"]["token"]["available"] is False
    vwc.render(report, vwc.Colors(False))
    assert vwc.SUCCESS_LINE in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Failure analysis
# --------------------------------------------------------------------------- #


def test_expired_token_reports_code_190_and_fix(capsys) -> None:
    report = vwc.build_report(
        _creds(),
        _routes({"/debug_token": {"data": {"is_valid": False, "expires_at": 0, "scopes": []}}}),
    )
    assert report["ok"] is False
    assert report["failure"]["code"] == 190
    assert "منتهي" in report["failure"]["reason"]
    assert "Permanent Token" in report["failure"]["fix"]

    vwc.render(report, vwc.Colors(False))
    out = capsys.readouterr().out
    assert "فشل التحقق" in out
    assert "190" in out


def test_wrong_phone_id_reports_code_33_with_the_real_fix(capsys) -> None:
    report = vwc.build_report(
        _creds(),
        _routes({
            "/debug_token": _token_ok_payload(),
            "/123456789012345": {
                "error": {"message": "Unsupported get request. Object with ID '123' does not exist", "code": 33}
            },
        }),
    )
    assert report["ok"] is False
    assert report["failure"]["code"] == 33
    assert "Phone Number ID" in report["failure"]["reason"]
    assert "API Setup" in report["failure"]["fix"]
    vwc.render(report, vwc.Colors(False))
    assert "فشل التحقق" in capsys.readouterr().out


def test_permission_denied_maps_to_the_permission_fix() -> None:
    report = vwc.build_report(
        _creds(),
        _routes({
            "/debug_token": _token_ok_payload(),
            "/123456789012345": {"error": {"message": "Permission denied", "code": 10}},
        }),
    )
    reason, fix = report["failure"]["reason"], report["failure"]["fix"]
    assert "صلاحية" in reason
    assert "whatsapp_business_messaging" in fix


def test_network_failure_is_explained() -> None:
    report = vwc.build_report(
        _creds(),
        _routes({
            "/debug_token": {"error": {"message": "network: URLError", "code": 0}},
            "/123456789012345": {"error": {"message": "network: URLError", "code": 0}},
        }),
    )
    assert report["ok"] is False
    assert "الاتصال" in report["failure"]["reason"]


def test_unsupported_graph_version_falls_back() -> None:
    def transport(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
        if "v21.0" in url:
            return {"error": {"message": "Unsupported API version", "code": 100}}
        if "/debug_token" in url:
            return _token_ok_payload()
        return _phone_ok_payload()

    report = vwc.build_report(_creds(), transport)
    assert report["ok"] is True
    assert report["version_fallback_used"] == "v23.0"


@pytest.mark.parametrize(
    ("code", "needle"),
    [
        (190, "منتهي"),
        (33, "Phone Number ID"),
        (10, "غير كافية"),
        (100, "معامل"),
        (200, "غير مفعّلة"),
        (803, "غير معروف"),
    ],
)
def test_error_guide_covers_common_meta_codes(code: int, needle: str) -> None:
    reason, fix = vwc.guide_for(code, "")
    assert needle in reason
    assert fix


def test_unknown_code_falls_back_to_meta_message() -> None:
    reason, fix = vwc.guide_for(12345, "Some brand new Meta failure")
    assert "Some brand new Meta failure" in reason
    assert "error-handling" in fix


# --------------------------------------------------------------------------- #
# Pre-flight shape gate (no network is touched)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("token", "needle"),
    [
        ("1234567890|abcdef1234567890", "App ID | App Secret"),
        ("LLM-something|secret-part", "الرمز |"),
        ("abc123def456ghi789", "EAA"),
        ("EAAtooshort", "قصير"),
    ],
)
def test_token_shape_issue_names_the_wrong_paste(token: str, needle: str) -> None:
    ok, reason, fix = vwc.token_shape_issue(token)
    assert ok is False
    assert needle in reason
    assert fix


def test_token_shape_issue_accepts_a_meta_style_token() -> None:
    ok, reason, fix = vwc.token_shape_issue(FAKE_TOKEN)
    assert (ok, reason, fix) == (True, "", "")


def test_app_id_secret_paste_is_caught_before_any_network_call() -> None:
    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("network must not be called for a wrong token shape")

    report = vwc.build_report(_creds(token="123456789012|secretsecretsecret"), boom)
    assert report["ok"] is False
    assert report["failure"]["stage"] == "token-shape"
    assert "App ID | App Secret" in report["failure"]["reason"]
    assert "Permanent Token" in report["failure"]["fix"]


def test_wrong_phone_id_shape_is_caught_before_any_network_call() -> None:
    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("network must not be called for a wrong phone id shape")

    report = vwc.build_report(_creds(phone_id="12345"), boom)
    assert report["ok"] is False
    assert report["failure"]["stage"] == "phone-shape"
    assert "API Setup" in report["failure"]["fix"]


def test_render_shows_arabic_stage_labels(capsys) -> None:
    report = vwc.build_report(
        _creds(token="not-a-meta-token"),
        _routes({"/debug_token": _token_ok_payload()}),
    )
    vwc.render(report, vwc.Colors(False))
    out = capsys.readouterr().out
    assert "شكل التوكن" in out
    assert "التوجيه الصحيح" in out