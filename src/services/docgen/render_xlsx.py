"""XLSX renderer. Totals, averages, growth and the forecast are formulas.

The data sheet holds values. The summary sheet never pastes a computed total;
it references the data with SUM, AVERAGE, MIN, MAX, and a linear FORECAST.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

from src.services.docgen.schema import Analysis, DocMeta, Narrative

_HEADER_FILL = PatternFill("solid", fgColor="FF5A36")
_HEADER_FONT = Font(name="Cairo", bold=True, color="141414", size=12)
_BODY_FONT = Font(name="Cairo", size=12, color="292524")
_TITLE_FONT = Font(name="Cairo", bold=True, size=16, color="FF5A36")
_THIN = Border(
    left=Side(style="thin", color="E7E5E4"),
    right=Side(style="thin", color="E7E5E4"),
    top=Side(style="thin", color="E7E5E4"),
    bottom=Side(style="thin", color="E7E5E4"),
)
_DATA = "البيانات"
_SUMMARY = "الملخص"
_PERIODS = "الفترات"
_NARRATIVE = "السرد"


def render_xlsx(meta: DocMeta, analysis: Analysis, narrative: Narrative) -> bytes:
    workbook = Workbook()
    workbook.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True)
    data = workbook.active
    data.title = _DATA
    _rtl(data)
    _write_data(data, analysis)
    summary = workbook.create_sheet(_SUMMARY)
    _rtl(summary)
    _write_summary(summary, meta, analysis)
    if len(analysis.periods) >= 2 and analysis.primary_letter and analysis.period_letter:
        periods = workbook.create_sheet(_PERIODS)
        _rtl(periods)
        _write_periods(periods, analysis)
        _write_growth_and_forecast(summary, analysis)
    story = workbook.create_sheet(_NARRATIVE)
    _rtl(story)
    _write_narrative(story, meta, narrative, analysis)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _rtl(worksheet) -> None:
    worksheet.sheet_view.rightToLeft = True
    worksheet.sheet_view.showGridLines = False
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToPage = True
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 1
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.oddHeader.right.text = "النرجس للذكاء الاصطناعي"
    worksheet.oddFooter.right.text = "الأرقام المحسوبة من البيانات · الصيغ تتحدث عند تغيير المصدر"


def _write_data(worksheet, analysis: Analysis) -> None:
    for column, header in enumerate(analysis.headers, start=1):
        cell = worksheet.cell(1, column, _as_text(header))
        _header(cell)
        worksheet.column_dimensions[get_column_letter(column)].width = 22
    for row_index, row in enumerate(analysis.rows, start=2):
        for column, value in enumerate(row, start=1):
            cell = worksheet.cell(row_index, column, _excel_value(value))
            cell.font = _BODY_FONT
            cell.alignment = Alignment(horizontal="right")
            cell.border = _THIN
            if isinstance(value, float):
                cell.number_format = "#,##0.00" if abs(value - round(value)) > 1e-6 else "#,##0"
    worksheet.auto_filter.ref = worksheet.dimensions
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    if analysis.headers:
        worksheet.auto_filter.ref = f"A1:{get_column_letter(len(analysis.headers))}{max(1, len(analysis.rows) + 1)}"


def _write_summary(worksheet, meta: DocMeta, analysis: Analysis) -> None:
    worksheet["A1"] = meta.title_ar
    worksheet["A1"].font = _TITLE_FONT
    worksheet.merge_cells("A1:B1")
    worksheet["A2"] = "النرجس للذكاء الاصطناعي"
    worksheet["A2"].font = Font(name="Cairo", bold=True, size=12, color="292524")
    headers = ("المؤشر", "القيمة")
    for column, header in enumerate(headers, start=1):
        cell = worksheet.cell(4, column, header)
        _header(cell)
    worksheet.column_dimensions["A"].width = 42
    worksheet.column_dimensions["B"].width = 22
    row = 5
    last_data = max(2, len(analysis.rows) + 1)
    labels = {
        "row_count": None,
        "column_count": None,
    }
    for fact in analysis.facts:
        if fact.key in labels and fact.kind == "count":
            worksheet.cell(row, 1, fact.label_ar).font = _BODY_FONT
            value = worksheet.cell(row, 2, fact.value)
            value.font = _BODY_FONT
            value.number_format = "0"
            value.border = _THIN
            worksheet.cell(row, 1).border = _THIN
            row += 1
    for stat in analysis.numeric_columns:
        span = f"'{_DATA}'!{stat.letter}2:{stat.letter}{last_data}"
        specs = (
            (f"إجمالي {stat.name}", f"=SUM({span})", "#,##0.00"),
            (f"متوسط {stat.name}", f"=AVERAGE({span})", "#,##0.00"),
            (f"أدنى {stat.name}", f"=MIN({span})", "#,##0.00"),
            (f"أعلى {stat.name}", f"=MAX({span})", "#,##0.00"),
        )
        for label, formula, fmt in specs:
            label_cell = worksheet.cell(row, 1, label)
            label_cell.font = _BODY_FONT
            label_cell.border = _THIN
            label_cell.alignment = Alignment(horizontal="right")
            formula_cell = worksheet.cell(row, 2, formula)
            formula_cell.font = Font(name="Cairo", size=12, color="141414", bold=label.startswith("إجمالي"))
            formula_cell.number_format = fmt
            formula_cell.border = _THIN
            formula_cell.alignment = Alignment(horizontal="right")
            row += 1
    worksheet.row_dimensions[1].height = 24


def _write_periods(worksheet, analysis: Analysis) -> None:
    for column, header in enumerate(("الفترة", analysis.primary_metric or "القيمة", "المؤشر"), start=1):
        cell = worksheet.cell(1, column, header)
        _header(cell)
        worksheet.column_dimensions[get_column_letter(column)].width = 24
    last_data = max(2, len(analysis.rows) + 1)
    assert analysis.period_letter and analysis.primary_letter
    for index, point in enumerate(analysis.periods):
        row = index + 2
        label = worksheet.cell(row, 1, point.label)
        label.font = _BODY_FONT
        label.border = _THIN
        formula = (
            f"=SUMIF('{_DATA}'!${analysis.period_letter}$2:${analysis.period_letter}${last_data},"
            f"A{row},'{_DATA}'!${analysis.primary_letter}$2:${analysis.primary_letter}${last_data})"
        )
        value = worksheet.cell(row, 2, formula)
        value.font = _BODY_FONT
        value.number_format = "#,##0.00"
        value.border = _THIN
        index_cell = worksheet.cell(row, 3, f"=ROW()-2")
        index_cell.font = _BODY_FONT
        index_cell.border = _THIN


def _write_growth_and_forecast(summary, analysis: Analysis) -> None:
    last = 1 + len(analysis.periods)
    # Find the first empty row under the summary block.
    row = summary.max_row + 1
    growth_label = summary.cell(row, 1, "النمو من أول فترة إلى آخرها (%)")
    growth_label.font = _BODY_FONT
    growth_label.border = _THIN
    growth = summary.cell(
        row,
        2,
        f'=IF(\'{_PERIODS}\'!B2=0,"",(\'{_PERIODS}\'!B{last}-\'{_PERIODS}\'!B2)/\'{_PERIODS}\'!B2*100)',
    )
    growth.font = _BODY_FONT
    growth.number_format = "0.00"
    growth.border = _THIN
    row += 1
    forecast_label = summary.cell(row, 1, "التوقع الخطي للفترة التالية")
    forecast_label.font = _BODY_FONT
    forecast_label.border = _THIN
    next_x = len(analysis.periods)
    forecast = summary.cell(
        row,
        2,
        f"=FORECAST.LINEAR({next_x},'{_PERIODS}'!B2:B{last},'{_PERIODS}'!C2:C{next_x + 1})",
    )
    forecast.font = Font(name="Cairo", bold=True, size=12, color="141414")
    forecast.number_format = "#,##0.00"
    forecast.border = _THIN


def _write_narrative(worksheet, meta: DocMeta, narrative: Narrative, analysis: Analysis) -> None:
    worksheet["A1"] = meta.title_ar
    worksheet["A1"].font = _TITLE_FONT
    worksheet.column_dimensions["A"].width = 88
    lines = [narrative.headline_ar, narrative.summary_ar, *narrative.insights_ar, *narrative.recommendations_ar]
    lines.extend(analysis.notes_ar)
    for index, line in enumerate(line for line in lines if line):
        cell = worksheet.cell(index + 3, 1, line)
        cell.font = _BODY_FONT
        cell.alignment = Alignment(wrap_text=True, horizontal="right", vertical="center")


def _header(cell) -> None:
    cell.font = _HEADER_FONT
    cell.fill = _HEADER_FILL
    cell.alignment = Alignment(horizontal="right", vertical="center")
    cell.border = _THIN


def _excel_value(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _as_text(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
