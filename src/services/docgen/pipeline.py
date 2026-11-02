"""One request in, a branded file set out. Numbers are fixed before the model speaks."""

from __future__ import annotations

from datetime import date

from src.services.docgen.analyze import analyze_brief, analyze_upload
from src.services.docgen.compose import compose_narrative
from src.services.docgen.render_docx import render_docx
from src.services.docgen.render_pdf import render_pdf
from src.services.docgen.render_pptx import render_pptx
from src.services.docgen.render_xlsx import render_xlsx
from src.services.docgen.schema import BuiltFile, DocGenError, DocMeta, DocPack

DEFAULT_FORMATS = ("pdf", "xlsx", "pptx")
ALLOWED_FORMATS = ("pdf", "xlsx", "pptx", "docx")
_FILENAMES = {
    "pdf": ("narjis-docpack.pdf", "application/pdf", "تقرير PDF", "PDF report"),
    "xlsx": ("narjis-docpack.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "ملف إكسل", "Excel workbook"),
    "pptx": ("narjis-docpack.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "عرض تقديمي", "Slide deck"),
    "docx": ("narjis-docpack.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "مستند وورد", "Word document"),
}
_RENDERERS = {
    "pdf": render_pdf,
    "xlsx": render_xlsx,
    "pptx": render_pptx,
    "docx": render_docx,
}


def parse_formats(raw: str | None) -> list[str]:
    if raw is None or not str(raw).strip():
        return list(DEFAULT_FORMATS)
    parts = [part.strip().lower().lstrip(".") for part in str(raw).replace(";", ",").split(",") if part.strip()]
    if not parts:
        return list(DEFAULT_FORMATS)
    unknown = [part for part in parts if part not in ALLOWED_FORMATS]
    if unknown:
        raise DocGenError("الصيغ المدعومة: pdf و xlsx و pptx و docx")
    return list(dict.fromkeys(parts))


async def build_docpack(
    *,
    brief: str = "",
    file_bytes: bytes | None = None,
    filename: str | None = None,
    agent_key: str,
    agent_name_ar: str,
    agent_name_en: str,
    formats: list[str] | None = None,
    model_provider=None,
    client_name: str = "",
    today: date | None = None,
    title_ar: str | None = None,
    title_en: str | None = None,
) -> DocPack:
    text = (brief or "").strip()
    if not file_bytes and not text:
        raise DocGenError("أرفق ملفاً أو اكتب وصفاً يحتوي البيانات")
    chosen = list(formats or DEFAULT_FORMATS)
    unknown = [fmt for fmt in chosen if fmt not in _RENDERERS]
    if unknown:
        raise DocGenError("الصيغ المدعومة: pdf و xlsx و pptx و docx")
    today = today or date.today()
    if file_bytes:
        analysis = analyze_upload(filename or "data.xlsx", file_bytes, brief=text, today=today)
    else:
        analysis = analyze_brief(text, today=today)
    narrative = await compose_narrative(analysis, brief=text, model_provider=model_provider)
    meta = DocMeta(
        title_ar=(title_ar or f"تقرير {agent_name_ar}").strip(),
        title_en=(title_en or f"{agent_name_en} report").strip(),
        agent_key=agent_key,
        agent_name_ar=agent_name_ar,
        agent_name_en=agent_name_en,
        client_name=(client_name or "").strip()[:120],
        brief=text[:4000],
        generated_on=today.isoformat(),
    )
    files = [
        BuiltFile(
            format=fmt,
            filename=_FILENAMES[fmt][0],
            content=_RENDERERS[fmt](meta, analysis, narrative),
            media_type=_FILENAMES[fmt][1],
            label_ar=_FILENAMES[fmt][2],
            label_en=_FILENAMES[fmt][3],
        )
        for fmt in chosen
    ]
    return DocPack(files=files, analysis=analysis, narrative=narrative, meta=meta)
