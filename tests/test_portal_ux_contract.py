"""Portal UX contract; browser behavior is covered by tests/browser/portal-ux.cjs."""
import httpx
import pytest

from src.main import app


@pytest.mark.parametrize('path,label', [
    ('/ar/portal', 'اختيار باقة ${p.name}'),
    ('/en/portal', 'Select ${p.name_en} plan'),
])
async def test_package_selection_exposes_accessible_controls(path, label):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
        response = await c.get(path)
    assert response.status_code == 200
    html = response.text
    assert 'role="button"' in html and 'tabindex="0"' in html
    assert 'aria-pressed="false"' in html and label in html
    assert 'aria-live="polite"' in html
    assert "e.key === 'Enter' || e.key === ' '" in html


async def test_annual_period_is_shown_and_renewal_uses_correct_unit():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
        response = await c.get('/ar/portal?billing=annual')
    assert response.status_code == 200
    assert 'فوترة سنوية' in response.text
    assert "coBilling === 'annual' ? txt('سنة', 'yr') : txt('شهر', 'mo')" in response.text
