from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.config import Settings
from app.utils.files import ensure_dir, file_size_ok, safe_filename

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedDocument:
    docx_path: Path
    pdf_path: Path | None


def build_document_markdown(title: str, source_text: str, doc_type: str) -> dict:
    clean = source_text.strip()

    if not clean:
        clean = "Вводные не указаны."

    if doc_type == "commercial_offer":
        sections = [
            ("Цель", "Подготовить понятное коммерческое предложение по вводным клиента."),
            ("Вводные", clean),
            ("Предлагаемое решение", "Описать услугу, этапы работ, сроки, стоимость и ожидаемый результат."),
            ("Следующий шаг", "Согласовать условия, подтвердить старт и зафиксировать договорённости."),
        ]
    elif doc_type == "work_plan":
        sections = [
            ("Цель", "Собрать рабочий план действий."),
            ("Вводные", clean),
            ("Этапы", "1. Уточнение задачи.\n2. Подготовка материалов.\n3. Выполнение.\n4. Проверка результата.\n5. Финальная передача."),
            ("Контроль", "Зафиксировать сроки, ответственных и критерии готовности."),
        ]
    elif doc_type == "meeting_summary":
        sections = [
            ("Краткое резюме", clean),
            ("Договорённости", "Зафиксировать, кто что обещал и к какому сроку."),
            ("Задачи", "Сформировать список следующих действий."),
            ("Риски", "Отметить спорные моменты и зоны неопределённости."),
        ]
    else:
        sections = [
            ("Чек-лист", clean),
            ("Порядок действий", "1. Проверить вводные.\n2. Разложить по шагам.\n3. Выполнить.\n4. Проверить результат."),
        ]

    return {
        "title": title,
        "sections": sections,
    }


class DocumentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.exports_dir = ensure_dir(settings.exports_path)

    def generate(self, title: str, source_text: str, doc_type: str) -> GeneratedDocument:
        data = build_document_markdown(title=title, source_text=source_text, doc_type=doc_type)

        docx_path = self.exports_dir / safe_filename(title, "docx")
        pdf_path = self.exports_dir / safe_filename(title, "pdf")

        self._generate_docx(data=data, path=docx_path)

        pdf_created = False
        try:
            self._generate_pdf(data=data, path=pdf_path)
            pdf_created = file_size_ok(pdf_path, self.settings.max_export_file_bytes)
        except Exception:
            logger.exception("PDF generation failed")

        return GeneratedDocument(
            docx_path=docx_path,
            pdf_path=pdf_path if pdf_created else None,
        )

    @staticmethod
    def _generate_docx(data: dict, path: Path) -> None:
        doc = Document()
        doc.add_heading(data["title"], level=1)

        for heading, body in data["sections"]:
            doc.add_heading(heading, level=2)
            for paragraph in str(body).split("\n"):
                if paragraph.strip():
                    doc.add_paragraph(paragraph.strip())

        doc.add_paragraph("")
        doc.add_paragraph("Создано в «Менеджер ИИ».")
        doc.save(path)

    def _generate_pdf(self, data: dict, path: Path) -> None:
        font_name = self._register_font()

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="CustomTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=18,
            leading=22,
            spaceAfter=10,
        )
        heading_style = ParagraphStyle(
            name="CustomHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            name="CustomBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=14,
        )

        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        story = [Paragraph(data["title"], title_style), Spacer(1, 8)]

        for heading, body in data["sections"]:
            story.append(Paragraph(str(heading), heading_style))
            for paragraph in str(body).split("\n"):
                if paragraph.strip():
                    story.append(Paragraph(paragraph.strip().replace("&", "&amp;"), body_style))
                    story.append(Spacer(1, 4))

        story.append(Spacer(1, 10))
        story.append(Paragraph("Создано в «Менеджер ИИ».", body_style))

        doc.build(story)

    def _register_font(self) -> str:
        candidates = [
            self.settings.pdf_font_path,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                pdfmetrics.registerFont(TTFont("ManagerAIFont", candidate))
                return "ManagerAIFont"

        return "Helvetica"
