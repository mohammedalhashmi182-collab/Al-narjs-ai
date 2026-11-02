"""DocPack types. Every printed figure is a Fact computed before any narrative."""

from __future__ import annotations

from dataclasses import dataclass, field


class DocGenError(ValueError):
    """A caller-facing refusal: bad file, unknown agent, or an empty request."""


def display_number(value: float) -> str:
    """Stable display. Thousands separators are commas; the decimal point is a dot."""
    number = float(value)
    if abs(number - round(number)) < 1e-6:
        return f"{int(round(number)):,}"
    return f"{number:,.2f}"


@dataclass(frozen=True)
class Fact:
    key: str
    label_ar: str
    label_en: str
    value: float
    display: str
    kind: str


@dataclass(frozen=True)
class ColumnStat:
    name: str
    letter: str
    total: float
    average: float
    minimum: float
    maximum: float
    count: int


@dataclass(frozen=True)
class PeriodPoint:
    label: str
    value: float


@dataclass
class Analysis:
    """Everything the renderers and the narrative guard are allowed to use."""

    source_kind: str
    headers: list[str]
    rows: list[list]
    numeric_columns: list[ColumnStat]
    primary_metric: str | None
    primary_letter: str | None
    period_column: str | None
    period_letter: str | None
    periods: list[PeriodPoint]
    growth_pct: float | None
    forecast: float | None
    first_period: float | None
    last_period: float | None
    facts: list[Fact] = field(default_factory=list)
    notes_ar: list[str] = field(default_factory=list)
    row_count: int = 0

    def allowed_values(self) -> list[float]:
        return [fact.value for fact in self.facts]

    def facts_of(self, kind: str) -> list[Fact]:
        return [fact for fact in self.facts if fact.kind == kind]


@dataclass
class Narrative:
    headline_ar: str
    summary_ar: str
    insights_ar: list[str]
    recommendations_ar: list[str]
    headline_en: str
    summary_en: str
    source: str
    rejected_numbers: list[str] = field(default_factory=list)

    def full_text(self) -> str:
        parts = [
            self.headline_ar,
            self.summary_ar,
            self.headline_en,
            self.summary_en,
            *self.insights_ar,
            *self.recommendations_ar,
        ]
        return "\n".join(part for part in parts if part)


@dataclass(frozen=True)
class DocMeta:
    title_ar: str
    title_en: str
    agent_key: str
    agent_name_ar: str
    agent_name_en: str
    client_name: str
    brief: str
    generated_on: str


@dataclass(frozen=True)
class BuiltFile:
    format: str
    filename: str
    content: bytes
    media_type: str
    label_ar: str
    label_en: str


@dataclass
class DocPack:
    files: list[BuiltFile]
    analysis: Analysis
    narrative: Narrative
    meta: DocMeta
