import pytest

from src.services import catalog
from src.services.demo_content import (
    clear_cache,
    get_demo_label,
    get_employee_demo,
    get_package_detail,
    get_package_demo,
)

PACKAGE_KEYS = ["social", "ecommerce", "content", "growth"]


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.mark.parametrize("key", PACKAGE_KEYS)
def test_demo_file_loads_and_is_marked_demo(key):
    data = get_package_demo(key)
    assert data is not None, f"missing demo content for {key}"
    assert data["demo"] is True
    assert data["package"] == key
    assert get_demo_label(key)["is_demo"] is True


def test_every_team_member_has_demo_entry():
    for key in PACKAGE_KEYS:
        for slug in catalog.get_team(key):
            demo = get_employee_demo(key, slug)
            assert demo is not None, f"{key}/{slug} has no demo entry"
            assert demo["steps_ar"], f"{key}/{slug} missing Arabic steps"
            assert demo["steps_en"], f"{key}/{slug} missing English steps"
            assert demo["sample_ar"].strip(), f"{key}/{slug} missing Arabic sample"
            assert demo["sample_en"].strip(), f"{key}/{slug} missing English sample"


@pytest.mark.parametrize("key", PACKAGE_KEYS)
def test_package_detail_shape(key):
    detail = get_package_detail(key)
    assert detail is not None
    assert detail["key"] == key
    assert detail["is_demo"] is True
    assert detail["team_size"] == len(catalog.get_team(key))
    assert detail["team_size"] == len(detail["team"])
    for emp in detail["team"]:
        assert emp["no"].startswith("AG-")
        assert emp["title_ar"]
        assert emp["title_en"]


def test_unknown_package_returns_none():
    assert get_package_demo("nope") is None
    assert get_package_detail("nope") is None
    assert get_employee_demo("social", "nope") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
