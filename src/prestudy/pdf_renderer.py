from __future__ import annotations

import html
import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import CoreNote, CitedItem, LectureRequest, StudyGuide


NAVY = colors.HexColor("#18324A")
BLUE = colors.HexColor("#2F6B8A")
PALE_BLUE = colors.HexColor("#EAF3F7")
PALE_YELLOW = colors.HexColor("#FFF6D8")
PALE_GREEN = colors.HexColor("#EAF6EF")
PALE_RED = colors.HexColor("#FCEEEF")
GRAY = colors.HexColor("#66727D")


def _find_font(bold: bool = False) -> Path:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("malgunbd.ttf" if bold else "malgun.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError("한글 PDF용 글꼴을 찾지 못했습니다. Noto Sans CJK를 설치해 주세요.")


def _register_fonts() -> tuple[str, str]:
    regular_name = "PrestudyKR"
    bold_name = "PrestudyKRBold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(regular_name, str(_find_font(False))))
    if bold_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(bold_name, str(_find_font(True))))
    return regular_name, bold_name


def _safe(text: str) -> str:
    # Malgun Gothic's ReportLab embedding can drop the mathematical minus
    # (U+2212), which would silently change pharmacokinetic formulas.
    normalized = text.replace("\u2212", "-")
    return html.escape(normalized).replace("\n", "<br/>")


def _citation_pages(citations: list[str]) -> str:
    pages: list[str] = []
    for citation in citations:
        for value in re.findall(r"p\.\s*(\d+(?:\s*[–-]\s*\d+)?)", citation, flags=re.IGNORECASE):
            page = "p." + re.sub(r"\s+", "", value).replace("-", "–")
            if page not in pages:
                pages.append(page)
    return " · ".join(pages)


def _first_page(item: CitedItem | CoreNote) -> int:
    pages = _citation_pages(item.citations)
    match = re.search(r"\d+", pages)
    return int(match.group()) if match else 10**9


def _range_start(source_range: str) -> int:
    match = re.search(r"\d+", source_range)
    return int(match.group()) if match else 10**9


def _cited(item: CitedItem) -> str:
    pages = _citation_pages(item.citations)
    suffix = f"<br/><font color='#66727D' size='8'>{_safe(pages)}</font>" if pages else ""
    return f"{_safe(item.content)}{suffix}"


def render_study_guide(guide: StudyGuide, lecture: LectureRequest, output_path: Path) -> None:
    regular, bold = _register_fonts()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleKR", parent=styles["Title"], fontName=bold, fontSize=24, leading=31, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10)
    subtitle = ParagraphStyle("SubtitleKR", parent=styles["Normal"], fontName=regular, fontSize=10, leading=16, textColor=GRAY, alignment=TA_CENTER)
    heading = ParagraphStyle("HeadingKR", parent=styles["Heading2"], fontName=bold, fontSize=15, leading=21, textColor=NAVY, spaceBefore=13, spaceAfter=7)
    body = ParagraphStyle("BodyKR", parent=styles["BodyText"], fontName=regular, fontSize=9.5, leading=15, textColor=colors.HexColor("#1E2933"), spaceAfter=5)
    small = ParagraphStyle("SmallKR", parent=body, fontSize=8, leading=12, textColor=GRAY)
    question_style = ParagraphStyle("QuestionKR", parent=body, fontName=bold, textColor=BLUE)
    subheading = ParagraphStyle("SubheadingKR", parent=body, fontName=bold, fontSize=10.5, leading=15, textColor=NAVY, spaceBefore=6, spaceAfter=4)
    badge = ParagraphStyle("BadgeKR", parent=small, fontName=bold, textColor=BLUE, spaceAfter=4)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(18 * mm, 12 * mm, f"{lecture.course} · {lecture.professor}")
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=guide.title,
        author="Lecture Companion PDF",
    )
    story = [
        Spacer(1, 18 * mm),
        Paragraph(_safe(guide.title), title),
        Paragraph(_safe(guide.subtitle), subtitle),
        Spacer(1, 10 * mm),
    ]
    meta = [
        [Paragraph("과목", question_style), Paragraph(_safe(lecture.course), body)],
        [Paragraph("교수", question_style), Paragraph(_safe(lecture.professor), body)],
        [Paragraph("주제", question_style), Paragraph(_safe(lecture.topic), body)],
        [Paragraph("강의일", question_style), Paragraph(_safe(lecture.lecture_date or "미지정"), body)],
    ]
    table = Table(meta, colWidths=[28 * mm, 125 * mm], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D7DF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([table, PageBreak()])

    def cited_block(label: str, items: list[CitedItem], background, border):
        if not items:
            return
        story.append(Paragraph(label, subheading))
        rows = [[Paragraph(_cited(item), body)] for item in items]
        block = Table(rows, colWidths=[160 * mm])
        block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("BOX", (0, 0), (-1, -1), 0.5, border),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(block)

    def core_notes_block(items: list[CoreNote]):
        if not items:
            return
        story.append(Paragraph("필기 대신 읽을 핵심", subheading))
        rows = []
        for item in sorted(items, key=_first_page):
            pages = _citation_pages(item.citations)
            details = "<br/>".join(f"- {_safe(detail)}" for detail in item.details)
            details_html = f"<br/>{details}" if details else ""
            pages_html = (
                f"<br/><font color='#66727D' size='8'>{_safe(pages)}</font>"
                if pages
                else ""
            )
            rows.append(
                [
                    Paragraph(
                        f"<font color='#2F6B8A' size='8'><b>{_safe(item.kind)}</b></font> "
                        f"<b>{_safe(item.heading)}</b><br/>"
                        f"{_safe(item.takeaway)}{details_html}{pages_html}",
                        body,
                    )
                ]
            )
        block = Table(rows, colWidths=[160 * mm])
        block.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9D7DF")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5ECEF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(block)

    def add_items(label: str, items: list[CitedItem], background=None):
        story.append(Paragraph(label, heading))
        rows = [[Paragraph(f"{i}. {_cited(item)}", body)] for i, item in enumerate(items, 1)]
        if rows:
            block = Table(rows, colWidths=[160 * mm])
            commands = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
            if background:
                commands.extend([("BACKGROUND", (0, 0), (-1, -1), background), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9C884"))])
            block.setStyle(TableStyle(commands))
            story.append(block)

    story.append(Paragraph("1. 수업 중 사용하는 법", heading))
    for item in guide.how_to_use:
        story.append(Paragraph(f"• {_safe(item)}", body))

    story.append(Paragraph("2. 한눈에 보는 강의 흐름", heading))
    flow_rows = [[
        Paragraph("순서", question_style),
        Paragraph("강의자료", question_style),
        Paragraph("주제", question_style),
    ]]
    ordered_flow = sorted(guide.lecture_flow, key=lambda section: (_range_start(section.source_range), section.order))
    for display_order, section in enumerate(ordered_flow, 1):
        flow_rows.append([
            Paragraph(str(display_order), body),
            Paragraph(_safe(section.source_range), body),
            Paragraph(_safe(section.title), body),
        ])
    flow_table = Table(flow_rows, colWidths=[14 * mm, 32 * mm, 114 * mm], repeatRows=1)
    flow_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D7DF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([flow_table, PageBreak()])

    story.append(Paragraph("3. 강의 흐름별 필기 대체 노트", heading))
    for display_order, section in enumerate(ordered_flow, 1):
        story.append(Paragraph(f"{display_order}. {_safe(section.title)}", heading))
        story.append(Paragraph(f"원본 강의자료 위치 · {_safe(section.source_range)}", badge))
        core_notes_block(section.ready_notes)
        cited_block("강조될 가능성이 높은 지점", sorted(section.emphasis_signals, key=_first_page), PALE_YELLOW, colors.HexColor("#D9C884"))
        cited_block("설명을 들으며 연결할 것", sorted(section.listen_for, key=_first_page), PALE_BLUE, colors.HexColor("#B9CED9"))
        if section.minimal_live_notes:
            story.append(Paragraph("수업 중 딱 이것만 확인", subheading))
            notes = [[Paragraph(f"□ {_safe(item)}", body)] for item in section.minimal_live_notes]
            note_table = Table(notes, colWidths=[160 * mm])
            note_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE_GREEN),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#A8CDB7")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(note_table)
        story.append(Spacer(1, 4 * mm))

    story.append(PageBreak())
    story.append(Paragraph("4. 수업 중 빠른 참조", heading))
    for card in guide.quick_reference:
        cite = _citation_pages(card.citations)
        card_table = Table([[
            Paragraph(_safe(card.title), question_style),
            Paragraph(_safe(card.content), body),
            Paragraph(f"언제 찾나: {_safe(card.use_when)}<br/><font color='#66727D' size='8'>{_safe(cite)}</font>", small),
        ]], colWidths=[34 * mm, 82 * mm, 44 * mm])
        card_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D7DF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([card_table, Spacer(1, 2 * mm)])

    add_items("5. 교수님·족보 기반 집중 신호", guide.professor_and_exam_signals, PALE_YELLOW)
    add_items("6. 헷갈리기 쉬운 구분", guide.common_confusions, PALE_RED)

    story.append(Paragraph("7. 수업 중 최소 확인 체크리스트", heading))
    for item in guide.minimal_live_checklist:
        story.append(Paragraph(f"□ {_safe(item)}", body))

    story.append(Paragraph("8. 충돌·불확실성", heading))
    for item in guide.uncertainties:
        story.append(Paragraph(f"• {_safe(item)}", body))

    story.append(Paragraph("9. 사용한 자료와 적용 방식", heading))
    for item in guide.source_notes:
        story.append(Paragraph(f"• {_safe(item)}", body))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
