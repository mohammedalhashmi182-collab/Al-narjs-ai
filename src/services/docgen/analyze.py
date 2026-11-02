"""Pandas analysis for a DocPack. Totals, averages, growth, and a linear forecast.

No figure in the returned facts is estimated by a model. A text brief contributes
only the numbers the client actually wrote; everything else is arithmetic on
those numbers or on the uploaded table.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

import pandas as pd

from src.services.docgen.guard import extract_numbers
from src.services.docgen.schema import (
    Analysis,
    ColumnStat,
    DocGenError,
    Fact,
    PeriodPoint,
    display_number,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLS = 40

_PERIOD_HINTS = ("date", "month", "period", "year", "شهر", "تاريخ", "فترة")
_METRIC_HINTS = (
    "revenue", "sales", "amount", "total", "value", "qty", "quantity",
    "مبيعات", "إيراد", "ايراد", "قيمة", "كمية", "إجمالي", "اجمالي",
)
_PRICE_HINTS = ("price", "سعر")
_ISO_PERIOD = re.compile(r"^(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?$")


def linear_forecast_next(values: list[float]) -> float:
    """Ordinary least squares. x is 0..n-1 and the forecast is the line at x = n."""
    count = len(values)
    if count == 0:
        raise DocGenError("لا توجد قيم للتوقع")
    if count == 1:
        return float(values[0])
    xs = list(range(count))
    mean_x = sum(xs) / count
    mean_y = sum(values) / count
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return float(values[-1])
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values, strict=True))
    slope = cov / var_x
    intercept = mean_y - slope * mean_x
    return float(intercept + slope * count)


def load_table(filename: str, data: bytes) -> pd.DataFrame:
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocGenError("الملف أكبر من 10 ميجابايت")
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    buffer = io.BytesIO(data)
    if ext == "csv":
        frame = _read_csv(buffer)
    elif ext in ("xlsx", "xlsm"):
        try:
            frame = pd.read_excel(buffer, engine="openpyxl")
        except Exception as exc:
            raise DocGenError("تعذّر قراءة ملف إكسل") from exc
    else:
        raise DocGenError("نوع الملف غير مدعوم — CSV أو XLSX فقط")
    frame = frame.dropna(how="all").dropna(axis=1, how="all")
    if frame.empty:
        raise DocGenError("لا توجد بيانات في الملف")
    frame.columns = _unique_headers(list(frame.columns))
    if frame.shape[1] > MAX_COLS:
        frame = frame.iloc[:, :MAX_COLS]
    if len(frame) > MAX_ROWS:
        frame = frame.iloc[:MAX_ROWS]
    return frame.reset_index(drop=True)


def analyze_frame(frame: pd.DataFrame, *, today: date | None = None, source_kind: str = "file") -> Analysis:
    today = today or date.today()
    headers = [str(column) for column in frame.columns]
    numeric = {name: series for name, series in ((str(c), _numeric(frame[c])) for c in frame.columns) if series is not None}
    period_name = _period_column(frame, set(numeric))
    rows = _sheet_rows(frame, headers, numeric)
    letters = {headers[index]: _column_letter(index + 1) for index in range(len(headers))}
    stats = [
        ColumnStat(
            name=name,
            letter=letters[name],
            total=float(series.sum(skipna=True)),
            average=float(series.mean(skipna=True)),
            minimum=float(series.min(skipna=True)),
            maximum=float(series.max(skipna=True)),
            count=int(series.notna().sum()),
        )
        for name, series in numeric.items()
    ]
    primary = _primary_metric(stats)
    primary_letter = letters.get(primary) if primary else None
    period_letter = letters.get(period_name) if period_name else None
    periods = _periods(frame, period_name, primary) if period_name and primary else []
    growth = _growth(periods)
    forecast = linear_forecast_next([point.value for point in periods]) if len(periods) >= 2 else None
    first = periods[0].value if periods else None
    last = periods[-1].value if periods else None
    facts: list[Fact] = []
    _add(facts, "row_count", "عدد الصفوف", "Row count", float(len(frame)), "count")
    _add(facts, "column_count", "عدد الأعمدة", "Column count", float(len(headers)), "count")
    for stat in stats:
        _add(facts, f"total:{stat.name}", f"إجمالي {stat.name}", f"Total {stat.name}", stat.total, "total")
        _add(facts, f"average:{stat.name}", f"متوسط {stat.name}", f"Average {stat.name}", stat.average, "average")
        _add(facts, f"min:{stat.name}", f"أدنى {stat.name}", f"Minimum {stat.name}", stat.minimum, "minimum")
        _add(facts, f"max:{stat.name}", f"أعلى {stat.name}", f"Maximum {stat.name}", stat.maximum, "maximum")
        _add(facts, f"count:{stat.name}", f"عدد قيم {stat.name}", f"Count of {stat.name}", float(stat.count), "count")
    for name, series in numeric.items():
        for index, value in enumerate(series.tolist()):
            if pd.isna(value):
                continue
            _add(facts, f"cell:{name}:{index}", f"{name} صف {index + 1}", f"{name} row {index + 1}", float(value), "source")
    for point in periods:
        _add(facts, f"period:{point.label}", f"فترة {point.label}", f"Period {point.label}", point.value, "period")
        for part in _date_parts(point.label):
            _add(facts, f"date:{point.label}:{part}", f"جزء التاريخ {part}", f"Date part {part}", float(part), "calendar")
    if growth is not None:
        _add(facts, "growth_pct", "النمو من أول فترة إلى آخرها (%)", "Growth from first period to last (%)", growth, "growth")
    if forecast is not None:
        _add(facts, "forecast_next", "التوقع الخطي للفترة التالية", "Linear forecast for the next period", forecast, "forecast")
    if first is not None:
        _add(facts, "period_first", "قيمة أول فترة", "First period value", first, "period")
    if last is not None:
        _add(facts, "period_last", "قيمة آخر فترة", "Last period value", last, "period")
    _add_calendar(facts, today)
    notes: list[str] = []
    if not stats:
        notes.append("لا يوجد عمود رقمي، لذلك لم يُحسب إجمالي.")
    if primary and not periods:
        notes.append("لا توجد سلسلة زمنية، لذلك لم يُحسب نمو ولا توقع.")
    elif len(periods) == 1:
        notes.append("الفترة واحدة، لذلك لم يُحسب نمو ولا توقع.")
    return Analysis(
        source_kind=source_kind,
        headers=headers,
        rows=rows,
        numeric_columns=stats,
        primary_metric=primary,
        primary_letter=primary_letter,
        period_column=period_name,
        period_letter=period_letter,
        periods=periods,
        growth_pct=growth,
        forecast=forecast,
        first_period=first,
        last_period=last,
        facts=_dedupe(facts),
        notes_ar=notes,
        row_count=len(frame),
    )


def analyze_brief(brief: str, *, today: date | None = None) -> Analysis:
    """A brief with no table. The only inputs are numbers the client wrote."""
    today = today or date.today()
    values = extract_numbers(brief or "")
    if len(values) < 1:
        facts: list[Fact] = []
        _add_calendar(facts, today)
        return Analysis(
            source_kind="empty",
            headers=[],
            rows=[],
            numeric_columns=[],
            primary_metric=None,
            primary_letter=None,
            period_column=None,
            period_letter=None,
            periods=[],
            growth_pct=None,
            forecast=None,
            first_period=None,
            last_period=None,
            facts=_dedupe(facts),
            notes_ar=["لا يحتوي الطلب على أرقام، لذلك لم يُحسب إجمالي أو نمو أو توقع."],
            row_count=0,
        )
    frame = pd.DataFrame({"القيمة": values})
    analysis = analyze_frame(frame, today=today, source_kind="brief")
    for value in values:
        _add(analysis.facts, f"quoted:{value}", "رقم مذكور في الطلب", "Number written in the brief", value, "quoted")
    analysis.facts = _dedupe(analysis.facts)
    return analysis


def analyze_upload(filename: str, data: bytes, *, brief: str = "", today: date | None = None) -> Analysis:
    analysis = analyze_frame(load_table(filename, data), today=today, source_kind="file")
    for value in extract_numbers(brief or ""):
        _add(analysis.facts, f"quoted:{value}", "رقم مذكور في الطلب", "Number written in the brief", value, "quoted")
    analysis.facts = _dedupe(analysis.facts)
    return analysis


def _read_csv(buffer: io.BytesIO) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
        buffer.seek(0)
        try:
            return pd.read_csv(buffer, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            raise DocGenError("تعذّر قراءة ملف CSV") from exc
    raise DocGenError("تعذّر قراءة ملف CSV") from last_error


def _unique_headers(columns: list) -> list[str]:
    seen: dict[str, int] = {}
    headers: list[str] = []
    for index, column in enumerate(columns):
        name = str(column).strip()
        if not name or name.lower().startswith("unnamed"):
            name = f"عمود {index + 1}"
        count = seen.get(name, 0) + 1
        seen[name] = count
        headers.append(name if count == 1 else f"{name} ({count})")
    return headers


def _numeric(series: pd.Series) -> pd.Series | None:
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
    else:
        cleaned = series.astype(str).str.replace(",", "", regex=False).str.replace("٬", "", regex=False).str.strip()
        cleaned = cleaned.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        numeric = pd.to_numeric(cleaned, errors="coerce")
    present = int(series.notna().sum())
    if present == 0 or int(numeric.notna().sum()) < max(1, int(0.8 * present)):
        return None
    return numeric


def _period_column(frame: pd.DataFrame, numeric_names: set[str]) -> str | None:
    hinted: list[str] = []
    detected: list[str] = []
    for column in frame.columns:
        name = str(column)
        if name in numeric_names and not any(hint in name.casefold() for hint in _PERIOD_HINTS):
            continue
        if _looks_like_period(frame[column]):
            if any(hint in name.casefold() for hint in _PERIOD_HINTS):
                hinted.append(name)
            else:
                detected.append(name)
    if hinted:
        return hinted[0]
    return detected[0] if detected else None


def _looks_like_period(series: pd.Series) -> bool:
    text = series.dropna().astype(str).str.strip()
    if text.empty:
        return False
    if text.str.match(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$").mean() >= 0.8:
        return True
    # Skip free text. Parsing every product name as a date warns and is wasted work.
    if float(text.str.contains(r"\d{4}", regex=True).mean()) < 0.8:
        return False
    parsed = pd.to_datetime(text, errors="coerce")
    return float(parsed.notna().mean()) >= 0.8 and int(text.nunique()) >= 2


def _primary_metric(stats: list[ColumnStat]) -> str | None:
    if not stats:
        return None

    def hinted(stat: ColumnStat) -> bool:
        name = stat.name.casefold()
        return any(hint in name for hint in _METRIC_HINTS) and not any(hint in name for hint in _PRICE_HINTS)

    preferred = [stat for stat in stats if hinted(stat)]
    pool = preferred or [stat for stat in stats if not any(hint in stat.name.casefold() for hint in _PRICE_HINTS)] or stats
    return max(pool, key=lambda stat: abs(stat.total)).name


def _periods(frame: pd.DataFrame, period_name: str, metric: str) -> list[PeriodPoint]:
    labels = frame[period_name].map(_cell_label)
    values = _numeric(frame[metric])
    if values is None:
        return []
    grouped: dict[str, float] = {}
    order: list[str] = []
    for label, value in zip(labels.tolist(), values.tolist(), strict=True):
        if not label or label == "nan" or pd.isna(value):
            continue
        if label not in grouped:
            order.append(label)
            grouped[label] = 0.0
        grouped[label] += float(value)
    order.sort(key=_period_sort_key)
    return [PeriodPoint(label=label, value=grouped[label]) for label in order]


def _growth(periods: list[PeriodPoint]) -> float | None:
    if len(periods) < 2 or periods[0].value == 0:
        return None
    return (periods[-1].value - periods[0].value) / periods[0].value * 100.0


def _sheet_rows(frame: pd.DataFrame, headers: list[str], numeric: dict[str, pd.Series]) -> list[list]:
    rows: list[list] = []
    for index in range(len(frame)):
        row: list = []
        for name in headers:
            if name in numeric:
                value = numeric[name].iloc[index]
                row.append(None if pd.isna(value) else float(value))
            else:
                value = frame.iloc[index][name]
                if pd.isna(value):
                    row.append(None)
                else:
                    row.append(_cell_label(value))
        rows.append(row)
    return rows


def _cell_label(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (datetime, pd.Timestamp)):
        if value.day == 1:
            return value.strftime("%Y-%m")
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _period_sort_key(label: str) -> tuple:
    match = _ISO_PERIOD.match(label.strip())
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 1), label)
    return (9999, 99, 99, label)


def _date_parts(label: str) -> list[int]:
    match = _ISO_PERIOD.match(label.strip())
    if not match:
        return []
    parts = [int(match.group(1)), int(match.group(2))]
    if match.group(3):
        parts.append(int(match.group(3)))
    return parts


def _add(facts: list[Fact], key: str, label_ar: str, label_en: str, value: float, kind: str) -> None:
    if value is None or pd.isna(value):
        return
    number = float(value)
    facts.append(Fact(
        key=key,
        label_ar=label_ar,
        label_en=label_en,
        value=number,
        display=display_number(number),
        kind=kind,
    ))


def _add_calendar(facts: list[Fact], today: date) -> None:
    _add(facts, "generated_year", "سنة الإصدار", "Year of issue", float(today.year), "calendar")
    _add(facts, "generated_month", "شهر الإصدار", "Month of issue", float(today.month), "calendar")
    _add(facts, "generated_day", "يوم الإصدار", "Day of issue", float(today.day), "calendar")


def _dedupe(facts: list[Fact]) -> list[Fact]:
    seen: set[str] = set()
    kept: list[Fact] = []
    for fact in facts:
        if fact.key in seen:
            continue
        seen.add(fact.key)
        kept.append(fact)
    return kept


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
