"""PDF renderer. Cairo is embedded and the page is Arabic right-to-left.

WeasyPrint shapes Arabic with the font's OpenType tables. A presentation-form
hack drops letters Cairo does not encode as isolated glyphs (notably alef).
"""

from __future__ import annotations

import html
from pathlib import Path

from src.services.docgen.schema import Analysis, DocGenError, DocMeta, Narrative

_FONT_DIR = Path(__file__).resolve().parent / "fonts"


def render_pdf(meta: DocMeta, analysis: Analysis, narrative: Narrative) -> bytes:
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise DocGenError("محرك PDF غير متاح على الخادم") from exc
    regular = _FONT_DIR / "Cairo-Regular.ttf"
    bold = _FONT_DIR / "Cairo-Bold.ttf"
    if not regular.is_file() or not bold.is_file():
        raise DocGenError("خط القاهرة غير مضمّن في الخادم")
    document = HTML(string=_html(meta, analysis, narrative), base_url=str(_FONT_DIR))
    return document.write_pdf()


def _html(meta: DocMeta, analysis: Analysis, narrative: Narrative) -> str:
    rows = _fact_rows(analysis)
    insights = "".join(f"<li>{html.escape(line)}</li>" for line in narrative.insights_ar)
    steps = "".join(f"<li>{html.escape(line)}</li>" for line in narrative.recommendations_ar)
    notes = "".join(f"<p class='note'>{html.escape(line)}</p>" for line in analysis.notes_ar)
    brief = html.escape((meta.brief or "").strip()[:2000])
    client = html.escape(meta.client_name) if meta.client_name else ""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<style>
@font-face {{ font-family: Cairo; src: url("Cairo-Regular.ttf") format("truetype"); font-weight: 400; }}
@font-face {{ font-family: Cairo; src: url("Cairo-Bold.ttf") format("truetype"); font-weight: 700; }}
@page {{ size: A4; margin: 16mm 14mm 18mm 14mm; }}
* {{ box-sizing: border-box; }}
body {{
  font-family: Cairo, sans-serif;
  color: #292524;
  background: #ffffff;
  margin: 0;
  font-size: 12pt;
  line-height: 1.7;
}}
header {{
  background: #141414;
  color: #f6f5f4;
  padding: 18px 20px 14px;
  border-bottom: 6px solid #ff5a36;
}}
header .brand {{ font-size: 12pt; letter-spacing: 0; margin: 0 0 6px; }}
header h1 {{ font-size: 26pt; line-height: 1.25; margin: 0; font-weight: 700; color: #f6f5f4; }}
header p {{ margin: 8px 0 0; color: #b9b8c0; font-size: 11pt; }}
main {{ padding: 16px 4px 0; }}
h2 {{ font-size: 16pt; color: #ff5a36; margin: 16px 0 8px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
th {{ background: #ff5a36; color: #141414; text-align: right; padding: 8px 10px; font-size: 11pt; }}
td {{ border-bottom: 1px solid #e7e5e4; padding: 7px 10px; vertical-align: top; }}
td.num {{ direction: ltr; unicode-bidi: isolate; text-align: left; font-weight: 700; }}
ul {{ margin: 0; padding-inline-start: 18px; }}
.note {{ color: #57534e; font-size: 10.5pt; }}
footer {{ margin-top: 18px; color: #57534e; font-size: 10pt; }}
</style>
</head>
<body>
<header>
  <p class="brand">النرجس للذكاء الاصطناعي</p>
  <h1>{html.escape(meta.title_ar)}</h1>
  <p>{html.escape(meta.agent_name_ar)} · {html.escape(meta.generated_on)}{(' · ' + client) if client else ''}</p>
</header>
<main>
  <h2>{html.escape(narrative.headline_ar)}</h2>
  <p>{html.escape(narrative.summary_ar)}</p>
  {"<h2>الطلب</h2><p>" + brief + "</p>" if brief else ""}
  {"<h2>الأرقام المحسوبة</h2><table><thead><tr><th>المؤشر</th><th>القيمة</th></tr></thead><tbody>" + rows + "</tbody></table>" if rows else ""}
  {"<h2>ملاحظات</h2><ul>" + insights + "</ul>" if insights else ""}
  {"<h2>الخطوة التالية</h2><ul>" + steps + "</ul>" if steps else ""}
  {notes}
  <footer>الأرقام في هذا التقرير محسوبة من البيانات. ملف إكسل يحمل الصيغ نفسها، والعرض يعرضها دون إضافة رقم.</footer>
</main>
</body>
</html>
"""


def _fact_rows(analysis: Analysis) -> str:
    wanted = {"row_count", "column_count", "growth_pct", "forecast_next"}
    for stat in analysis.numeric_columns:
        wanted.add(f"total:{stat.name}")
        if analysis.primary_metric and stat.name == analysis.primary_metric:
            wanted.update({f"average:{stat.name}", f"minimum:{stat.name}", f"maximum:{stat.name}"})
    cells = []
    for fact in analysis.facts:
        if fact.key not in wanted:
            continue
        cells.append(
            "<tr><td>"
            + html.escape(fact.label_ar)
            + "</td><td class='num'>"
            + html.escape(fact.display)
            + "</td></tr>"
        )
    return "".join(cells)
