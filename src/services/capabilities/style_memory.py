"""Per-client style profile, injected into every agent prompt for that client.

Profiles live in memory for the life of the process and, when a database
session is available, in ``client_style_profiles``. Approved edits add banned
words, spelling preferences and a register hint. Nothing here is a public
contact channel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.services.capabilities.config import style_enabled
from src.utils.logger import get_logger

logger = get_logger(__name__)

REGISTERS = {"msa", "saudi"}
_AR_WORD = re.compile(r"[\u0621-\u064A]{3,}")
_DIALECT = ("وش", "أبغى", "ابغى", "الحين", "ياليت", "زين", "مو ")
_STOP = {
    "التي", "الذي", "هذا", "هذه", "ذلك", "على", "من", "في", "عن", "مع",
    "كان", "كانت", "ثم", "كما", "بعد", "قبل", "عند", "كل", "قد",
}


@dataclass
class StyleProfile:
    client_key: str
    brand_ar: str = ""
    brand_en: str = ""
    register: str = "msa"
    tone: str = ""
    banned_words: list[str] = field(default_factory=list)
    colours: str = ""
    fonts: str = ""
    signature: str = ""
    learned: list[dict] = field(default_factory=list)

    def cleaned(self) -> "StyleProfile":
        register = self.register if self.register in REGISTERS else "msa"
        banned = []
        for word in self.banned_words:
            item = str(word).strip()
            if item and item not in banned and len(item) <= 40:
                banned.append(item)
        return StyleProfile(
            client_key=str(self.client_key).strip()[:64],
            brand_ar=self.brand_ar.strip()[:120],
            brand_en=self.brand_en.strip()[:120],
            register=register,
            tone=self.tone.strip()[:200],
            banned_words=banned[:40],
            colours=self.colours.strip()[:200],
            fonts=self.fonts.strip()[:200],
            signature=self.signature.strip()[:500],
            learned=list(self.learned)[:30],
        )


_MEMORY: dict[str, StyleProfile] = {}


def remember(profile: StyleProfile) -> StyleProfile:
    cleaned = profile.cleaned()
    if not cleaned.client_key:
        raise ValueError("client_key is required")
    _MEMORY[cleaned.client_key] = cleaned
    return cleaned


def recall(client_key: str) -> StyleProfile | None:
    return _MEMORY.get((client_key or "").strip())


def clear_memory() -> None:
    _MEMORY.clear()


def _tokens(text: str) -> list[str]:
    return [token for token in _AR_WORD.findall(text or "") if token not in _STOP]


def _dialect_hits(text: str) -> int:
    return sum((text or "").count(marker) for marker in _DIALECT)


def learn_from_edit(profile: StyleProfile, original: str, approved: str, *, persist: bool = True) -> StyleProfile:
    """Learn spelling, banned words and register from one approved edit."""
    current = profile.cleaned()
    original = original or ""
    approved = approved or ""
    removed = [token for token in _tokens(original) if token not in _tokens(approved)]
    added = [token for token in _tokens(approved) if token not in _tokens(original)]
    notes = list(current.learned)
    banned = list(current.banned_words)
    for token in removed:
        if token not in banned and token not in {current.brand_ar}:
            banned.append(token)
            notes.append({"type": "banned", "word": token})
    if len(removed) == 1 and len(added) == 1 and removed[0][:2] == added[0][:2]:
        notes.append({"type": "spelling", "from": removed[0], "to": added[0]})
        if not current.brand_ar:
            current.brand_ar = added[0]
    before, after = _dialect_hits(original), _dialect_hits(approved)
    register = current.register
    if after >= before + 1 and after > 0:
        register = "saudi"
        notes.append({"type": "register", "value": "saudi"})
    elif before >= after + 1 and after == 0 and before > 0:
        register = "msa"
        notes.append({"type": "register", "value": "msa"})
    updated = StyleProfile(
        client_key=current.client_key,
        brand_ar=current.brand_ar,
        brand_en=current.brand_en,
        register=register,
        tone=current.tone,
        banned_words=banned,
        colours=current.colours,
        fonts=current.fonts,
        signature=current.signature,
        learned=notes[-30:],
    ).cleaned()
    if not persist:
        return updated
    return remember(updated)


def render_block(profile: StyleProfile | None) -> str:
    if profile is None or not style_enabled():
        return ""
    profile = profile.cleaned()
    register = (
        "Saudi dialect (اللهجة السعودية البيضاء), not formal MSA"
        if profile.register == "saudi"
        else "Modern Standard Arabic (فصحى), not dialect"
    )
    banned = ", ".join(profile.banned_words) if profile.banned_words else "(none)"
    learned = []
    for item in profile.learned[-8:]:
        kind = item.get("type")
        if kind == "banned":
            learned.append(f"- do not use «{item.get('word')}» (removed in an approved edit)")
        elif kind == "spelling":
            learned.append(f"- spell «{item.get('to')}», not «{item.get('from')}»")
        elif kind == "register":
            learned.append(f"- register learned from an approved edit: {item.get('value')}")
    learned_block = "\n".join(learned) if learned else "- (none yet)"
    return (
        "\n=== CLIENT STYLE MEMORY (follow on every line) ===\n"
        f"Brand Arabic spelling: {profile.brand_ar or '(unset)'}\n"
        f"Brand English spelling: {profile.brand_en or '(unset)'}\n"
        f"Register: {register}\n"
        f"Tone: {profile.tone or '(unset)'}\n"
        f"Banned words: {banned}\n"
        f"Colours: {profile.colours or '(unset)'}\n"
        f"Fonts: {profile.fonts or '(unset)'}\n"
        f"Signature: {profile.signature or '(unset)'}\n"
        "Learned from approved edits:\n"
        f"{learned_block}\n"
        "Do not use a banned word. Keep the brand spelling exact. "
        "Label any figure you were not given as an estimate.\n"
        "=== END CLIENT STYLE MEMORY ==="
    )


async def prompt_block(client_key: str) -> str:
    if not client_key or not style_enabled():
        return ""
    profile = recall(client_key)
    if profile is None:
        profile = await load_profile(client_key)
    return render_block(profile)


def _row_to_profile(row) -> StyleProfile:
    return StyleProfile(
        client_key=row.client_key,
        brand_ar=row.brand_ar or "",
        brand_en=row.brand_en or "",
        register=row.register or "msa",
        tone=row.tone or "",
        banned_words=list(row.banned_words or []),
        colours=row.colours or "",
        fonts=row.fonts or "",
        signature=row.signature or "",
        learned=list(row.learned or []),
    )


async def save_profile(session, profile: StyleProfile) -> StyleProfile:
    from src.models.capabilities import ClientStyleProfile

    cleaned = remember(profile)
    row = await session.get(ClientStyleProfile, cleaned.client_key)
    if row is None:
        row = ClientStyleProfile(client_key=cleaned.client_key)
        session.add(row)
    row.brand_ar = cleaned.brand_ar
    row.brand_en = cleaned.brand_en
    row.register = cleaned.register
    row.tone = cleaned.tone
    row.banned_words = list(cleaned.banned_words)
    row.colours = cleaned.colours
    row.fonts = cleaned.fonts
    row.signature = cleaned.signature
    row.learned = list(cleaned.learned)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return cleaned


async def load_profile(client_key: str):
    cached = recall(client_key)
    if cached is not None:
        return cached
    try:
        from src.db.session import get_session_factory
        from src.models.capabilities import ClientStyleProfile

        factory = await get_session_factory()
        async with factory() as session:
            row = await session.get(ClientStyleProfile, client_key)
            if row is None:
                return None
            return remember(_row_to_profile(row))
    except Exception:  # noqa: BLE001 - style must never break a client reply
        logger.warning("style_profile_load_failed", client_key=client_key[:8])
        return None
