"""Data-to-Deck DocPack: computed files, narrative only from those figures."""

from src.services.docgen.pipeline import ALLOWED_FORMATS, DEFAULT_FORMATS, build_docpack, parse_formats
from src.services.docgen.render_pptx import DESIGNED_SLIDE_COUNT
from src.services.docgen.schema import DocGenError

__all__ = [
    "ALLOWED_FORMATS",
    "DEFAULT_FORMATS",
    "DESIGNED_SLIDE_COUNT",
    "DocGenError",
    "build_docpack",
    "parse_formats",
]
