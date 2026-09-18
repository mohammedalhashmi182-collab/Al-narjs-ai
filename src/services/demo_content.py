from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.services import catalog
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEMO_DIR = Path(__file__).resolve().parents[2] / "content" / "demo"


@lru_cache(maxsize=None)
def _load(package_key: str) -> dict | None:
    path = _DEMO_DIR / f"{package_key}.json"
    if not path.is_file():
        logger.warning("Demo content missing for package '%s' at %s", package_key, path)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Failed to read demo content '%s': %s", path, exc)
        return None
    if not isinstance(data, dict) or data.get("demo") is not True:
        logger.error("Demo content '%s' is not marked as demo data", path)
        return None
    return data


def clear_cache() -> None:
    _load.cache_clear()


def get_package_demo(package_key: str) -> dict | None:
    if package_key not in catalog.PACKAGES:
        return None
    return _load(package_key)


def get_demo_label(package_key: str) -> dict:
    data = _load(package_key) or {}
    return {
        "is_demo": True,
        "label_ar": data.get("label_ar", "نموذج توضيحي — بيانات تجريبية"),
        "label_en": data.get("label_en", "Illustrative sample — demo data"),
    }


def get_employee_demo(package_key: str, slug: str) -> dict | None:
    data = _load(package_key)
    if not data:
        return None
    entry = (data.get("employees") or {}).get(slug)
    if not isinstance(entry, dict):
        return None
    return {
        "steps_ar": entry.get("steps_ar") or [],
        "steps_en": entry.get("steps_en") or [],
        "sample_ar": entry.get("sample_ar", ""),
        "sample_en": entry.get("sample_en", ""),
    }


def get_package_detail(package_key: str) -> dict | None:
    pkg = catalog.get_package(package_key)
    if not pkg:
        return None

    slugs = catalog.get_team(package_key)
    names = {slug: (catalog.get_employee(slug) or {}).get("title_ar", slug) for slug in slugs}

    team = []
    for identity in catalog.team_with_identity(slugs, names):
        demo = get_employee_demo(package_key, identity["slug"]) or {}
        team.append({**identity, **demo})

    return {
        **get_demo_label(package_key),
        "key": package_key,
        "name": pkg["name"],
        "name_en": pkg["name_en"],
        "price": pkg["price"],
        "tagline": pkg["tagline"],
        "tagline_en": pkg["tagline_en"],
        "amount": pkg["amount"],
        "team_size": len(team),
        "team": team,
    }
