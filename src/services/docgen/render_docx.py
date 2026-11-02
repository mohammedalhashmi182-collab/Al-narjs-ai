"""DOCX renderer: Arabic right-to-left, Cairo on every run."""

from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from src.services.docgen.schema import Analysis, DocMeta, Narrative

_INK = RGBColor(0x14, 0x14, 0x14)
_ACCENT = RGBColor(0xFF, 0x5A, 0x36)


def render_docx(meta: DocMeta, analysis: Analysis, narrative: Narrative) -> bytes:
    document = Document()
    _set_section_rtl(document)
    _set_default_font(document)
    _paragraph(document, meta.title_ar, size=22, bold=True, color=_ACCENT)
    _paragraph(document, "النرجس للذكاء الاصطناعي", size=12, bold=True)
    subtitle = f"{meta.agent_name_ar} · {meta.generated_on}"
    if meta.client_name:
        subtitle = f"{meta.client_name} · {subtitle}"
    _paragraph(document, subtitle, size=11)
    if meta.brief.strip():
        _paragraph(document, "الطلب", size=14, bold=True)
        _paragraph(document, meta.brief.strip()[:2000], size=12)
    _paragraph(document, narrative.headline_ar, size=16, bold=True)
    if narrative.summary_ar:
        _paragraph(document, narrative.summary_ar, size=12)
    _facts_table(document, analysis)
    if narrative.insights_ar:
        _paragraph(document, "ملاحظات", size=14, bold=True)
        for line in narrative.insights_ar:
            _paragraph(document, line, size=12)
    if narrative.recommendations_ar:
        _paragraph(document, "الخطوة التالية", size=14, bold=True)
        for line in narrative.recommendations_ar:
            _paragraph(document, line, size=12)
    for note in analysis.notes_ar:
        _paragraph(document, note, size=11)
    _paragraph(
        document,
        "الأرقام في هذا الملف محسوبة من البيانات. الصيغ في ملف إكسل هي مصدر المجاميع.",
        size=10,
    )
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _set_section_rtl(document: Document) -> None:
    sect = document.sections[0]._sectPr
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    sect.append(bidi)


def _set_default_font(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "Cairo"
    style.font.size = Pt(12)
    style.font.color.rgb = _INK
    _rfonts(style.element.get_or_add_rPr())


def _paragraph(document: Document, text: str, *, size: int, bold: bool = False, color: RGBColor | None = None):
    paragraph = document.add_paragraph()
    _paragraph_rtl(paragraph)
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.color.rgb = color or _INK
    run.font.name = "Cairo"
    _rfonts(run._element.get_or_add_rPr())
    return paragraph


def _paragraph_rtl(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    p_pr.append(bidi)


def _rfonts(r_pr) -> None:
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        r_fonts.set(qn(attr), "Cairo")


def _facts_table(document: Document, analysis: Analysis) -> None:
    rows = [
        fact for fact in analysis.facts
        if fact.kind in {"count", "total", "average", "minimum", "maximum", "growth", "forecast"}
        and fact.key in {
            "row_count", "column_count", "growth_pct", "forecast_next",
            *[f"{kind}:{stat.name}" for stat in analysis.numeric_columns for kind in ("total", "average", "minimum", "maximum")],
        }
    ]
    if not rows:
        return
    _paragraph(document, "الأرقام المحسوبة", size=14, bold=True)
    table = document.add_table(rows=1 + len(rows), cols=2)
    table.style = "Table Grid"
    _cell(table.rows[0].cells[0], "المؤشر", bold=True)
    _cell(table.rows[0].cells[1], "القيمة", bold=True)
    for index, fact in enumerate(rows, start=1):
        _cell(table.rows[index].cells[0], fact.label_ar)
        _cell(table.rows[index].cells[1], fact.display)
    tbl_pr = table._tbl.tblPr
    bidi = OxmlElement("w:bidiVisual")
    bidi.set(qn("w:val"), "1")
    tbl_pr.append(bidi)


def _cell(cell, text: str, *, bold: bool = False) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    _paragraph_rtl(paragraph)
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "Cairo"
    run.font.size = Pt(11)
    run.font.color.rgb = _INK
    _rfonts(run._element.get_or_add_rPr())
