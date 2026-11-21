"""Public pages must not advertise free offers or discounts."""


import httpx
import pytest
from src.main import app

FORBIDDEN = (
    "التشخيص مجاني",
    "The diagnosis is free",
    "شهران مجاناً",
    "شهرين مجاناً",
    "2 months free",
    "ادفع 10 أشهر واحصل على 12",
    "تدفع 10 أشهر وتحصل على 12",
    "تدفع ١٠ أشهر وتحصل على ١٢",
    "pay for 10 months, get 12",
    "Pay for 10 months, get 12",
    "توفّر 1,580",
    "save SAR 1,580",
    "save SAR",
    "دليل مجاني",
    "Free Guide",
    "Download the guide for free",
    "حمّل الدليل مجاناً",
    "12 شهراً بسعر 10",
    "12 months for the price of 10",
    "12 months for 10",
    "تجربة أولية مجانية",
    "Free initial diagnosis",
)

PUBLIC_PATHS = (
    "/ar/home",
    "/en/home",
    "/ar/pricing",
    "/en/pricing",
    "/ar/packages/bidaya",
    "/en/packages/bidaya",
    "/ar/packages/numuw",
    "/en/packages/numuw",
    "/ar/packages/sharikat",
    "/en/packages/sharikat",
    "/ar/terms",
    "/en/terms",
    "/ar/privacy",
    "/en/privacy",
    "/ar/guide",
    "/en/guide",
    "/ar/consult",
    "/en/consult",
    "/ar/voice",
    "/en/voice",
    "/llms.txt",
)


async def _get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        return await client.get(path)


@pytest.mark.parametrize("path", PUBLIC_PATHS)
async def test_public_pages_have_no_free_or_discount_offers(path: str) -> None:
    response = await _get(path)
    assert response.status_code == 200, path
    html = response.text
    for phrase in FORBIDDEN:
        assert phrase not in html, f"{path} still contains {phrase!r}"


def test_assistant_prompts_have_no_discount_framing() -> None:
    from src.services import smart_reply, social_agent

    text = smart_reply.plan_lines("numuw") + social_agent.compose_post("plan_spotlight", "numuw")
    for phrase in FORBIDDEN:
        assert phrase not in text, f"assistant copy still contains {phrase!r}"
