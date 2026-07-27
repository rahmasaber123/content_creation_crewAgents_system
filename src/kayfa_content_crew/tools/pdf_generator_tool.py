"""PDF generation for approved BlogPost content.

Two fixes verified against real failures during development, both required:
1. `new_x="LMARGIN", new_y="NEXT"` on every multi_cell -- this fpdf2 version
   defaults new_x to RIGHT, leaving the cursor near the page edge and
   starving the next call of width ('Not enough horizontal space...').
2. `_pdf_safe()` -- core Helvetica font only supports Latin-1; Arabic/Unicode
   chars are replaced with '?' and long unbroken runs are hard-wrapped so
   fpdf2 always has a break point. Production upgrade: a Unicode TTF font
   (pdf.add_font(...)) + arabic-reshaper/python-bidi for real Arabic rendering.
"""

from __future__ import annotations

import logging
import textwrap

from fpdf import FPDF

from kayfa_content_crew.schemas import BlogPost

logger = logging.getLogger(__name__)


def _pdf_safe(text: str, width: int = 90) -> str:
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    wrapped_lines: list[str] = []
    for line in safe.split("\n"):
        if not line.strip():
            wrapped_lines.append(line)
            continue
        wrapped_lines.extend(
            textwrap.wrap(line, width=width, break_long_words=True, break_on_hyphens=False) or [""]
        )
    return "\n".join(wrapped_lines)


def _cell(pdf: FPDF, h: float, text: str) -> None:
    pdf.multi_cell(0, h, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")


def generate_pdf(post: BlogPost, path: str) -> str:
    """Renders an approved BlogPost to PDF. Branches layout by content_type."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        _cell(pdf, 10, post.title)
        pdf.set_font("Helvetica", "", 11)
        _cell(pdf, 8, f"Meta: {post.meta_description}\n")

        if post.content_type == "technical_writing":
            pdf.set_font("Helvetica", "B", 12)
            _cell(pdf, 8, "Prerequisites:")
            pdf.set_font("Helvetica", "", 11)
            for item in post.prerequisites:
                _cell(pdf, 7, f"  - {item}")
            _cell(pdf, 8, "\n" + post.intro + "\n")
            for i, step in enumerate(post.steps, start=1):
                pdf.set_font("Helvetica", "B", 12)
                _cell(pdf, 8, f"Step {i}: {step.heading}")
                pdf.set_font("Helvetica", "", 11)
                _cell(pdf, 7, step.body + "\n")
            pdf.set_font("Helvetica", "", 11)
            _cell(pdf, 7, post.conclusion)
        else:
            pdf.set_font("Helvetica", "B", 12)
            _cell(pdf, 8, "Key Takeaways:")
            pdf.set_font("Helvetica", "", 11)
            for point in post.key_takeaways:
                _cell(pdf, 7, f"  - {point}")
            _cell(pdf, 8, "\n" + post.intro + "\n")
            for section in post.sections:
                pdf.set_font("Helvetica", "B", 12)
                _cell(pdf, 8, section.heading)
                pdf.set_font("Helvetica", "", 11)
                _cell(pdf, 7, section.body + "\n")
            pdf.set_font("Helvetica", "", 11)
            _cell(pdf, 7, post.conclusion + "\n" + post.cta)
            _cell(pdf, 7, " ".join(f"#{h.lstrip('#')}" for h in post.hashtags))

        pdf.output(path)
        return path
    except Exception:
        logger.exception("generate_pdf failed for title=%r", post.title)
        raise
