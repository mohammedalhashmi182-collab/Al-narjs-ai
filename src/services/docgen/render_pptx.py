"""Seven-slide Arabic deck. The count is part of the design, not a model choice."""

from __future__ import annotations

import io

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from src.services.docgen.schema import Analysis, DocMeta, Narrative

DESIGNED_SLIDE_COUNT = 7

_CANVAS = RGBColor(0x14, 0x14, 0x14)
_INK = RGBColor(0xF6, 0xF5, 0xF4)
_MUTED = RGBColor(0xB9, 0xB8, 0xC0)
_ACCENT = RGBColor(0xFF, 0x5A, 0x36)
_INK_ON_ACCENT = RGBColor(0x14, 0x14, 0x14)


def render_pptx(meta: DocMeta, analysis: Analysis, narrative: Narrative) -> bytes:
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]
    slides = [
        _cover(presentation, blank, meta, narrative),
        _scope(presentation, blank, meta, analysis),
        _totals(presentation, blank, analysis),
        _averages(presentation, blank, analysis),
        _growth(presentation, blank, analysis),
        _forecast(presentation, blank, analysis),
        _next_steps(presentation, blank, narrative),
    ]
    if len(slides) != DESIGNED_SLIDE_COUNT:
        raise RuntimeError("deck layout drifted from the designed slide count")
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def _new(presentation, layout):
    slide = presentation.slides.add_slide(layout)
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _CANVAS
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.16), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _ACCENT
    bar.line.fill.background()
    brand = slide.shapes.add_textbox(Inches(0.5), Inches(7.05), Inches(12.3), Inches(0.35))
    _write(brand, ["النرجس للذكاء الاصطناعي"], size=12, color=_MUTED)
    return slide


def _cover(presentation, layout, meta: DocMeta, narrative: Narrative):
    slide = _new(presentation, layout)
    _write_box(slide, 0.55, 1.5, 12, 1.2, [meta.title_ar], size=40, bold=True, color=_INK)
    _write_box(slide, 0.55, 3.0, 12, 1.4, [narrative.headline_ar], size=24, color=_ACCENT)
    lines = [meta.agent_name_ar, meta.generated_on]
    if meta.client_name:
        lines.insert(0, meta.client_name)
    _write_box(slide, 0.55, 4.8, 12, 1.4, lines, size=18, color=_MUTED)
    return slide


def _scope(presentation, layout, meta: DocMeta, analysis: Analysis):
    slide = _new(presentation, layout)
    _title(slide, "نطاق العمل")
    rows = analysis.facts_of("count")
    counts = [f"{fact.label_ar}: {fact.display}" for fact in rows if fact.key in {"row_count", "column_count"}]
    brief = (meta.brief or "").strip()[:500] or "بدون نص إضافي."
    _write_box(slide, 0.55, 1.8, 12, 4.6, [brief, *counts, *analysis.notes_ar], size=20, color=_INK)
    return slide


def _totals(presentation, layout, analysis: Analysis):
    slide = _new(presentation, layout)
    _title(slide, "الإجماليات المحسوبة")
    lines = [f"{fact.label_ar}: {fact.display}" for fact in analysis.facts_of("total")] or [
        "لا يوجد عمود رقمي يُجمع."
    ]
    _write_box(slide, 0.55, 1.8, 12, 4.8, lines[:8], size=22, color=_INK)
    return slide


def _averages(presentation, layout, analysis: Analysis):
    slide = _new(presentation, layout)
    _title(slide, "المتوسط والمدى")
    lines: list[str] = []
    for kind in ("average", "minimum", "maximum"):
        for fact in analysis.facts_of(kind):
            if analysis.primary_metric and analysis.primary_metric in fact.key:
                lines.append(f"{fact.label_ar}: {fact.display}")
    if not lines:
        lines = ["لا يوجد مؤشر رقمي رئيسي."]
    _write_box(slide, 0.55, 1.8, 12, 4.8, lines[:8], size=22, color=_INK)
    return slide


def _growth(presentation, layout, analysis: Analysis):
    slide = _new(presentation, layout)
    _title(slide, "النمو بين أول فترة وآخرها")
    if analysis.growth_pct is None:
        lines = analysis.notes_ar or ["لم تُحسب نسبة نمو لأن السلسلة أقصر من فترتين أو تبدأ بصفر."]
    else:
        growth = analysis.facts_of("growth")[0]
        first = analysis.facts_of("period")
        lines = [f"{fact.label_ar}: {fact.display}" for fact in first if fact.key in {"period_first", "period_last"}]
        lines.append(f"{growth.label_ar}: {growth.display}")
    _write_box(slide, 0.55, 1.8, 12, 4.8, lines[:8], size=22, color=_INK)
    return slide


def _forecast(presentation, layout, analysis: Analysis):
    slide = _new(presentation, layout)
    _title(slide, "التوقع الخطي للفترة التالية")
    if analysis.forecast is None:
        lines = ["لم يُحسب توقع لأن السلسلة أقصر من فترتين."]
    else:
        forecast = analysis.facts_of("forecast")[0]
        lines = [
            f"{forecast.label_ar}: {forecast.display}",
            "الطريقة: خط المربعات الصغرى على سلسلة الفترات، والنقطة التالية على امتداده.",
        ]
    _write_box(slide, 0.55, 1.8, 12, 4.8, lines, size=22, color=_INK)
    return slide


def _next_steps(presentation, layout, narrative: Narrative):
    slide = _new(presentation, layout)
    _title(slide, "الخطوة التالية")
    lines = narrative.recommendations_ar or ["راجع الأرقام المحسوبة في الملف قبل أي قرار."]
    _write_box(slide, 0.55, 1.8, 12, 4.8, lines[:4], size=22, color=_INK)
    return slide


def _title(slide, text: str) -> None:
    _write_box(slide, 0.55, 0.4, 12, 1.0, [text], size=32, bold=True, color=_ACCENT)


def _write_box(slide, left, top, width, height, lines, *, size, color, bold=False):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    box.text_frame.word_wrap = True
    box.text_frame.auto_size = None
    _anchor(box.text_frame, MSO_ANCHOR.TOP)
    _write(box, lines, size=size, color=color, bold=bold)
    return box


def _write(shape, lines: list[str], *, size: int, color: RGBColor, bold: bool = False) -> None:
    frame = shape.text_frame
    frame.word_wrap = True
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = PP_ALIGN.RIGHT
        paragraph.level = 0
        _rtl(paragraph)
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = "Cairo"
        _cairo(run)


def _rtl(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_pr.set("rtl", "1")
    p_pr.set("algn", "r")


def _cairo(run) -> None:
    r_pr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:cs", "a:ea"):
        element = r_pr.find(qn(tag))
        if element is None:
            element = etree.SubElement(r_pr, qn(tag))
        element.set("typeface", "Cairo")


def _anchor(frame, anchor) -> None:
    frame._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr"}.get(anchor, "t"))
