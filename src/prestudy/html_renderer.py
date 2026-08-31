from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Sequence
from pathlib import Path

from .models import (
    CauseEffectFlow,
    CitedItem,
    CoreNote,
    LectureRequest,
    SourceDocument,
    SourceKind,
    StudyGuide,
    StudyTable,
)
from .naming import companion_title
from .page_basis import citation_page_labels, page_basis_filenames


def _safe(value: str) -> str:
    normalized = value.replace("\u2212", "-")
    display_terms = {
        "lecture_flow": "강의 흐름",
        "ready_notes": "필기 대체 노트",
        "listen_for": "설명을 들으며 연결할 것",
        "minimal_live_notes": "수업 중 최소 확인",
        "quick_reference": "빠른 참조",
        "professor_and_exam_signals": "집중 신호",
        "exam_style_summary": "출제 스타일",
        "cause_effect_flows": "원인→결과 흐름",
        "trap_points": "함정 포인트",
        "final_checklist": "최종 체크리스트",
    }
    for internal, label in display_terms.items():
        normalized = normalized.replace(internal, label)
    return html.escape(normalized, quote=True).replace("\n", "<br>")


def _citation_pages(
    citations: list[str],
    allowed_filenames: set[str] | None = None,
) -> str:
    return " · ".join(citation_page_labels(citations, allowed_filenames))


def _first_page(
    item: CitedItem | CoreNote,
    allowed_filenames: set[str] | None = None,
) -> int:
    match = re.search(r"\d+", _citation_pages(item.citations, allowed_filenames))
    return int(match.group()) if match else 10**9


def _range_start(value: str) -> int:
    match = re.search(r"\d+", value)
    return int(match.group()) if match else 10**9


def _cited_item(item: CitedItem, allowed_filenames: set[str] | None = None) -> str:
    pages = _citation_pages(item.citations, allowed_filenames)
    page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
    evidence_html = _evidence_badges(item.importance, item.exam_years)
    return f'<li><div>{_safe(item.content)}</div><div class="item-meta">{evidence_html}{page_html}</div></li>'


def _cited_list(
    items: list[CitedItem],
    allowed_filenames: set[str] | None = None,
) -> str:
    ordered = sorted(items, key=lambda item: _first_page(item, allowed_filenames))
    return (
        '<ul class="note-list">'
        + "".join(_cited_item(item, allowed_filenames) for item in ordered)
        + "</ul>"
    )


def _core_note_cards(
    items: list[CoreNote],
    allowed_filenames: set[str] | None = None,
) -> str:
    ordered = sorted(items, key=lambda item: _first_page(item, allowed_filenames))
    cards: list[str] = []
    for index, item in enumerate(ordered, 1):
        pages = _citation_pages(item.citations, allowed_filenames)
        page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
        details = "".join(f"<li>{_safe(detail)}</li>" for detail in item.details)
        detail_html = f'<ul class="core-details">{details}</ul>' if details else ""
        cards.append(
            '<article class="core-note-card searchable">'
            '<div class="core-note-heading">'
            f'<span class="core-note-index">{index:02d}</span>'
            f'<span class="core-note-kind">{_safe(item.kind)}</span>'
            f'<h5>{_safe(item.heading)}</h5>{page_html}'
            '</div>'
            f'<p class="core-takeaway">{_safe(item.takeaway)}</p>'
            f'{detail_html}</article>'
        )
    return (
        '<div class="core-panel-heading"><h4>필기 대신 읽을 핵심</h4>'
        f'<span>{len(ordered)}개 핵심 개념</span></div>'
        f'<div class="core-note-list">{"".join(cards)}</div>'
    )


def _exam_year_label(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if normalized.endswith("년") or "확인" in normalized or "미상" in normalized:
        return normalized
    return f"{normalized}년"


def _evidence_badges(importance: int, exam_years: Sequence[str]) -> str:
    badges: list[str] = []
    if importance > 0:
        badges.append(
            f'<span class="importance" aria-label="기출 중요도 {importance}점">{"⭐" * importance}</span>'
        )
    years = [_exam_year_label(value) for value in exam_years]
    years = [value for value in years if value]
    if importance > 0 and not years:
        years = ["연도 확인 불가"]
    if years:
        if len(years) == 1 and ("확인" in years[0] or "미상" in years[0]):
            year_text = f"기출 {years[0]}"
        else:
            year_text = f'{", ".join(years)} 기출'
        badges.append(f'<span class="exam-years">{_safe(year_text)}</span>')
    return "".join(badges)


def _section_evidence(section) -> tuple[int, list[str]]:
    importance = max((item.importance for item in section.emphasis_signals), default=0)
    years: list[str] = []
    for item in section.emphasis_signals:
        for year in item.exam_years:
            if year not in years:
                years.append(year)
    return importance, years


def _study_table(table: StudyTable, allowed_filenames: set[str] | None) -> str:
    if not table.headers:
        return ""
    header_html = "".join(f"<th>{_safe(value)}</th>" for value in table.headers)
    body_rows: list[str] = []
    width = len(table.headers)
    for row in table.rows:
        cells = [*row[:width], *([""] * max(0, width - len(row)))]
        body_rows.append("<tr>" + "".join(f"<td>{_safe(value)}</td>" for value in cells) + "</tr>")
    pages = _citation_pages(table.citations, allowed_filenames)
    page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
    return f'''<section class="study-table-block searchable">
  <div class="block-heading"><h4>{_safe(table.title)}</h4>{page_html}</div>
  <div class="study-table-scroll"><table><thead><tr>{header_html}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>
</section>'''


def _cause_effect_flow(flow: CauseEffectFlow, allowed_filenames: set[str] | None) -> str:
    steps = []
    for index, step in enumerate(flow.steps):
        steps.append(f'<div class="mechanism-step">{_safe(step)}</div>')
        if index < len(flow.steps) - 1:
            steps.append('<div class="mechanism-arrow" aria-hidden="true">↓</div>')
    pages = _citation_pages(flow.citations, allowed_filenames)
    page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
    return f'''<section class="mechanism-block searchable">
  <div class="block-heading"><h4>{_safe(flow.title)}</h4>{page_html}</div>
  <div class="mechanism-flow">{''.join(steps)}</div>
</section>'''


def _trap_blocks(items: list[CitedItem], allowed_filenames: set[str] | None) -> str:
    blocks = []
    for item in items:
        pages = _citation_pages(item.citations, allowed_filenames)
        page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
        blocks.append(
            f'<blockquote class="trap-point searchable"><strong>🔥 함정</strong>'
            f'<div>{_safe(item.content)}</div><div class="item-meta">{page_html}</div></blockquote>'
        )
    return "".join(blocks)


def _checklist_items(
    items: list[CitedItem],
    document_key: str,
    group: str,
    allowed_filenames: set[str] | None,
) -> str:
    rows = []
    for index, item in enumerate(items, 1):
        pages = _citation_pages(item.citations, allowed_filenames)
        page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
        evidence_html = _evidence_badges(item.importance, item.exam_years)
        rows.append(
            f'<label class="check-row"><input type="checkbox" data-store="{document_key}-{group}-{index}">'
            f'<span class="check-copy">{_safe(item.content)}<span class="item-meta">'
            f'{evidence_html}{page_html}</span></span></label>'
        )
    return "".join(rows)


def _source_manifest(sources: Sequence[SourceDocument]) -> str:
    grouped: dict[SourceKind, list[str]] = {kind: [] for kind in SourceKind}
    for source in sources:
        filename = source.path.name
        if filename not in grouped[source.kind]:
            grouped[source.kind].append(filename)

    groups: list[str] = []
    for kind in (
        SourceKind.GUIDE,
        SourceKind.LECTURE,
        SourceKind.JOKCHEK,
        SourceKind.SUMMARY,
    ):
        filenames = grouped[kind]
        if not filenames:
            continue
        items = "".join(f"<li>{_safe(filename)}</li>" for filename in filenames)
        groups.append(
            '<div class="source-group">'
            f'<div class="source-kind">{_safe(kind.value)} <span>{len(filenames)}개</span></div>'
            f"<ul>{items}</ul>"
            "</div>"
        )

    if not groups:
        return ""
    return (
        '<div class="source-manifest" aria-labelledby="source-manifest-title">'
        '<h2 id="source-manifest-title">사용한 원본 자료</h2>'
        '<p>이 노트를 만드는 데 실제로 사용한 PDF입니다.</p>'
        f'<div class="source-groups">{"".join(groups)}</div>'
        "</div>"
    )


def render_study_guide_html(
    guide: StudyGuide,
    lecture: LectureRequest,
    output_path: Path,
    sources: Sequence[SourceDocument] = (),
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    display_title = companion_title(
        lecture.lecture_date,
        lecture.course,
        lecture.professor,
        lecture.topic,
    ) or guide.title
    ordered_flow = sorted(guide.lecture_flow, key=lambda section: (_range_start(section.source_range), section.order))
    source_manifest = _source_manifest(sources)
    page_filenames, page_kind = page_basis_filenames(sources)
    page_filter = page_filenames or None
    document_key = hashlib.sha1(
        f"{lecture.course}|{lecture.professor}|{lecture.topic}|{lecture.lecture_date}".encode("utf-8")
    ).hexdigest()[:12]

    nav_links = []
    roadmap_cards = []
    flow_sections = []
    for display_order, section in enumerate(ordered_flow, 1):
        section_id = f"flow-{display_order}"
        section_importance, section_years = _section_evidence(section)
        section_evidence = _evidence_badges(section_importance, section_years)
        nav_links.append(
            f'<a href="#{section_id}"><span>{display_order}</span><strong>{_safe(section.source_range)}</strong>'
            f'<small>{_safe(section.title)}</small></a>'
        )
        roadmap_cards.append(
            f'<a class="roadmap-card searchable" href="#{section_id}">'
            f'<span class="roadmap-number">{display_order:02d}</span>'
            f'<span class="roadmap-copy"><small>{_safe(section.source_range)}</small>'
            f'<strong>{_safe(section.title)}</strong><span class="roadmap-evidence">{section_evidence}</span></span>'
            '<span class="roadmap-go" aria-hidden="true">→</span></a>'
        )
        live_notes = ""
        if section.minimal_live_notes:
            rows = []
            for note_index, note in enumerate(section.minimal_live_notes, 1):
                key = f"{document_key}-{section_id}-{note_index}"
                rows.append(
                    '<div class="live-note">'
                    f'<label><input type="checkbox" data-store="{key}-check"> {_safe(note)}</label>'
                    f'<textarea data-store="{key}-text" rows="2" placeholder="필요할 때만 짧게 메모"></textarea>'
                    "</div>"
                )
            live_notes = '<div class="note-panel live"><h4>수업 중 딱 이것만 확인</h4>' + "".join(rows) + "</div>"

        tables_html = "".join(_study_table(table, page_filter) for table in section.tables)
        mechanisms_html = "".join(
            _cause_effect_flow(flow, page_filter) for flow in section.cause_effect_flows
        )
        exam_panel = ""
        if section.emphasis_signals:
            exam_panel = (
                '<div class="note-panel emphasis"><h4>기출 포인트</h4>'
                f'{_cited_list(section.emphasis_signals, page_filter)}</div>'
            )
        trap_html = _trap_blocks(section.trap_points, page_filter)
        listen_panel = ""
        if section.listen_for:
            listen_panel = (
                '<div class="note-panel listen"><h4>설명을 들으며 연결할 것</h4>'
                f'{_cited_list(section.listen_for, page_filter)}</div>'
            )

        flow_sections.append(
            f'''<details class="flow-section searchable" id="{section_id}" open>
  <summary>
    <span class="flow-number">{display_order}</span>
    <span class="flow-heading"><strong>{_safe(section.title)}</strong><small>{_safe(section.source_range)}</small></span>
    <span class="section-evidence">{section_evidence}</span>
    <span class="chevron">⌄</span>
  </summary>
  <div class="flow-content">
    <div class="note-panel core">{_core_note_cards(section.ready_notes, page_filter)}</div>
    {tables_html}
    {mechanisms_html}
    {exam_panel}
    <div class="trap-stack">{trap_html}</div>
    {listen_panel}
    {live_notes}
  </div>
</details>'''
        )

    quick_cards = []
    for card in guide.quick_reference:
        pages = _citation_pages(card.citations, page_filter)
        page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
        quick_cards.append(
            f'''<article class="reference-card searchable">
  <h3>{_safe(card.title)}</h3>
  <div class="formula">{_safe(card.content)}</div>
  <p><strong>언제 찾나</strong> · {_safe(card.use_when)}</p>
  {page_html}
</article>'''
        )

    focus_items = _cited_list(guide.professor_and_exam_signals, page_filter)
    confusion_items = _cited_list(guide.common_confusions, page_filter)
    how_to = "".join(f"<li>{_safe(item)}</li>" for item in guide.how_to_use)
    live_checklist = "".join(
        f'<label class="check-row"><input type="checkbox" data-store="{document_key}-global-{index}"> {_safe(item)}</label>'
        for index, item in enumerate(guide.minimal_live_checklist, 1)
    )
    comparison_checklist = _checklist_items(
        guide.final_checklist.comparisons,
        document_key,
        "comparison",
        page_filter,
    )
    cause_checklist = _checklist_items(
        guide.final_checklist.cause_and_effect,
        document_key,
        "cause-effect",
        page_filter,
    )
    trap_checklist = _checklist_items(
        guide.final_checklist.traps,
        document_key,
        "trap",
        page_filter,
    )
    uncertainties = "".join(f"<li>{_safe(item)}</li>" for item in guide.uncertainties)

    styles = r'''
:root{--bg:#f5f7f8;--surface:#fff;--text:#17212b;--muted:#66727d;--navy:#18324a;--blue:#2f6b8a;--line:#d8e1e6;--core:#fff;--emphasis:#fff6d8;--listen:#eaf3f7;--live:#eaf6ef;--danger:#fceeef;--shadow:0 12px 32px rgba(24,50,74,.08);--scale:1}
body.dark{--bg:#111820;--surface:#19232d;--text:#eaf0f4;--muted:#a8b5bf;--navy:#dceefa;--blue:#75badc;--line:#344653;--core:#19232d;--emphasis:#3b3521;--listen:#203746;--live:#213a2d;--danger:#40282d;--shadow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;font-size:calc(16px * var(--scale));line-height:1.7}.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:.65rem;padding:.65rem max(1rem,calc((100vw - 1380px)/2));background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}.topbar .brand{font-weight:800;color:var(--navy);margin-right:auto;white-space:nowrap}.search{min-width:180px;max-width:340px;width:30vw;padding:.55rem .75rem;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--text)}button{border:1px solid var(--line);background:var(--surface);color:var(--text);border-radius:9px;padding:.5rem .7rem;font-weight:700;cursor:pointer}.shell{max-width:1380px;margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:1.25rem;padding:1.25rem}.sidebar{position:sticky;top:72px;align-self:start;max-height:calc(100vh - 90px);overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1rem;box-shadow:var(--shadow)}.sidebar h2{font-size:.85rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin:.2rem 0 .8rem}.sidebar a{display:grid;grid-template-columns:26px 1fr;gap:.1rem .55rem;text-decoration:none;color:var(--text);padding:.65rem;border-radius:10px}.sidebar a:hover{background:var(--listen)}.sidebar a span{grid-row:1/3;display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:var(--navy);color:var(--surface);font-size:.78rem;font-weight:800}.sidebar a strong{font-size:.82rem;color:var(--blue)}.sidebar a small{font-size:.78rem;color:var(--muted);line-height:1.35}.content{min-width:0}.hero{background:linear-gradient(145deg,var(--navy),#2f6b8a);color:#fff;border-radius:22px;padding:2.1rem;box-shadow:var(--shadow)}.hero .eyebrow{opacity:.8;font-weight:700}.hero h1{font-size:clamp(1.75rem,4vw,3rem);line-height:1.2;margin:.45rem 0}.hero p{margin:.3rem 0;opacity:.9}.meta{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.25rem}.meta span{padding:.35rem .65rem;border:1px solid rgba(255,255,255,.28);border-radius:999px;font-size:.86rem}.usage,.section-card{margin-top:1rem;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.1rem 1.3rem;box-shadow:var(--shadow)}.usage h2,.section-card h2{color:var(--navy);margin:.1rem 0 .65rem}.usage ol{margin:.25rem 0;padding-left:1.35rem}.flow-actions{display:flex;justify-content:flex-end;gap:.45rem;margin:1rem 0 .65rem}.flow-section{scroll-margin-top:78px;margin-bottom:.85rem;background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}.flow-section summary{display:flex;align-items:center;gap:.8rem;padding:1rem 1.15rem;cursor:pointer;list-style:none}.flow-section summary::-webkit-details-marker{display:none}.flow-number{display:grid;place-items:center;flex:0 0 34px;height:34px;border-radius:50%;background:var(--navy);color:var(--surface);font-weight:900}.flow-heading{display:flex;flex-direction:column;min-width:0}.flow-heading strong{color:var(--navy);font-size:1.12rem}.flow-heading small{color:var(--blue);font-weight:800}.chevron{margin-left:auto;font-size:1.25rem;transition:.2s}.flow-section[open] .chevron{transform:rotate(180deg)}.flow-content{padding:0 1rem 1rem;display:grid;gap:.7rem}.note-panel{border:1px solid var(--line);border-radius:12px;padding:.85rem 1rem}.note-panel h4{margin:0 0 .45rem;color:var(--navy)}.note-panel.core{background:var(--core)}.note-panel.emphasis{background:var(--emphasis)}.note-panel.listen{background:var(--listen)}.note-panel.live{background:var(--live)}.note-list{padding-left:1.25rem;margin:.2rem 0}.note-list li{padding:.35rem 0}.page-ref{display:inline-block;color:var(--blue);font-size:.78rem;font-weight:800;margin-top:.15rem}.live-note{border-top:1px dashed var(--line);padding:.7rem 0}.live-note:first-of-type{border-top:0}.live-note label,.check-row{display:block;font-weight:700}.live-note textarea{width:100%;resize:vertical;margin-top:.45rem;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text);padding:.65rem;font:inherit}.reference-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.reference-card{border:1px solid var(--line);border-radius:12px;padding:1rem;background:var(--surface)}.reference-card h3{color:var(--blue);margin:0 0 .45rem}.reference-card .formula{font-weight:700;white-space:normal}.reference-card p{color:var(--muted);font-size:.9rem}.split{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.focus{background:var(--emphasis)}.confusion{background:var(--danger)}.check-row{padding:.55rem 0;border-bottom:1px solid var(--line)}.uncertainties{color:var(--muted)}.hidden-by-search{display:none!important}.empty-search{display:none;padding:2rem;text-align:center;color:var(--muted)}footer{text-align:center;color:var(--muted);padding:2rem 1rem 4rem}
@media(max-width:900px){.shell{grid-template-columns:1fr;padding:.75rem}.sidebar{position:static;max-height:none;display:flex;gap:.35rem;overflow-x:auto;border-radius:12px}.sidebar h2{display:none}.sidebar a{min-width:150px}.hero{padding:1.4rem}.reference-grid,.split{grid-template-columns:1fr}.topbar .brand{display:none}.search{width:100%;max-width:none}.topbar{padding:.55rem}.flow-section summary{padding:.85rem}.flow-content{padding:0 .65rem .65rem}.note-panel{padding:.75rem}}
@media print{.topbar,.sidebar,.flow-actions{display:none!important}.shell{display:block;max-width:none;padding:0}.flow-section{break-inside:avoid;box-shadow:none}.flow-section:not([open])>.flow-content{display:block}.hero{background:#fff;color:#000;border:1px solid #ccc}.section-card,.usage{box-shadow:none}}
'''

    styles += r'''
.source-manifest{margin-top:1.25rem;padding:1rem 1.1rem;border:1px solid rgba(255,255,255,.24);border-radius:14px;background:rgba(255,255,255,.1)}
.source-manifest h2{margin:0;font-size:1rem;color:#fff}.source-manifest>p{margin:.15rem 0 .75rem;font-size:.82rem;opacity:.75}
.source-groups{display:grid;gap:.55rem}.source-group{display:grid;grid-template-columns:minmax(7.5rem,auto) minmax(0,1fr);gap:.75rem;align-items:start}
.source-kind{font-size:.85rem;font-weight:800}.source-kind span{margin-left:.3rem;font-size:.72rem;opacity:.7}
.source-group ul{margin:0;padding-left:1.1rem;font-size:.84rem}.source-group li{overflow-wrap:anywhere}
@media(max-width:900px){.source-group{grid-template-columns:1fr;gap:.15rem}}
@media print{.source-manifest{background:#fff;border-color:#ccc}.source-manifest h2{color:#000}}
'''

    styles += r'''
:root{--gold:#f0b429;--gold-soft:#fff8dd;--red:#c94b4b;--red-soft:#fff1f1;--table-head:#edf3f6;--step:#eef6fa;--core-soft:#f4f9fb;--core-accent:#2f6b8a}
body.dark{--gold:#ffd166;--gold-soft:#40371f;--red:#ff8a8a;--red-soft:#40282d;--table-head:#24333e;--step:#203746;--core-soft:#1d2d38;--core-accent:#75badc}
.note-panel.core{padding:1rem;background:linear-gradient(180deg,var(--core-soft),var(--surface))}.core-panel-heading{display:flex;align-items:center;justify-content:space-between;gap:.75rem;margin-bottom:.7rem}.core-panel-heading h4{margin:0;color:var(--navy);font-size:1.08rem}.core-panel-heading>span{color:var(--muted);font-size:.78rem;font-weight:800}.core-note-list{display:grid;gap:.65rem}.core-note-card{border:1px solid var(--line);border-left:4px solid var(--core-accent);border-radius:10px;padding:.8rem .9rem;background:var(--surface)}.core-note-heading{display:flex;align-items:center;flex-wrap:wrap;gap:.45rem}.core-note-index{color:var(--muted);font-size:.7rem;font-weight:900;font-variant-numeric:tabular-nums}.core-note-kind{padding:.08rem .42rem;border-radius:999px;background:var(--listen);color:var(--blue);font-size:.7rem;font-weight:900;white-space:nowrap}.core-note-heading h5{flex:1 1 12rem;margin:0;color:var(--navy);font-size:1rem;line-height:1.35}.core-note-heading .page-ref{margin:0}.core-takeaway{margin:.55rem 0 .35rem;font-weight:800;line-height:1.55}.core-details{margin:.25rem 0 0;padding-left:1.2rem;color:var(--text)}.core-details li{padding:.18rem 0;line-height:1.55}.core-details li::marker{color:var(--core-accent)}
.roadmap{margin-top:1rem;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.15rem 1.3rem;box-shadow:var(--shadow)}
.section-kicker{margin:0 0 .1rem;color:var(--blue);font-size:.76rem;font-weight:900;letter-spacing:.1em}.roadmap h2{margin:.1rem 0 .25rem;color:var(--navy)}
.exam-style-summary{margin:.85rem 0 1rem;padding:.8rem 1rem;border-left:4px solid var(--gold);border-radius:0 10px 10px 0;background:var(--gold-soft)}.exam-style-summary strong{display:block;color:var(--navy);font-size:.82rem;margin-bottom:.15rem}
.roadmap-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}.roadmap-card{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:.75rem;align-items:center;padding:.8rem .9rem;border:1px solid var(--line);border-radius:12px;color:var(--text);text-decoration:none;background:var(--bg)}.roadmap-card:hover{border-color:var(--blue);transform:translateY(-1px)}
.roadmap-number{font-variant-numeric:tabular-nums;color:var(--blue);font-size:.78rem;font-weight:900}.roadmap-copy{display:flex;flex-direction:column;min-width:0}.roadmap-copy small{color:var(--blue);font-weight:800}.roadmap-copy strong{line-height:1.35}.roadmap-evidence{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.25rem}.roadmap-go{color:var(--muted);font-size:1.15rem}
.section-evidence,.item-meta,.block-heading{display:flex;align-items:center;flex-wrap:wrap;gap:.4rem}.section-evidence{margin-left:auto;justify-content:flex-end}.item-meta{margin-top:.18rem}.item-meta:empty{display:none}.importance{color:var(--gold);font-size:.83rem;letter-spacing:-.08em;white-space:nowrap}.exam-years{display:inline-block;border:1px solid color-mix(in srgb,var(--gold) 55%,var(--line));border-radius:999px;padding:.08rem .45rem;background:var(--gold-soft);color:var(--text);font-size:.72rem;font-weight:850;white-space:nowrap}
.block-heading{justify-content:space-between;margin-bottom:.55rem}.block-heading h4{margin:0;color:var(--navy)}
.study-table-block,.mechanism-block{border:1px solid var(--line);border-radius:12px;padding:.9rem 1rem;background:var(--surface)}.study-table-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:9px}.study-table-block table{width:100%;min-width:520px;border-collapse:collapse;font-size:.9rem;line-height:1.5}.study-table-block th,.study-table-block td{padding:.6rem .7rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.study-table-block th{background:var(--table-head);color:var(--navy);font-weight:900}.study-table-block tr:last-child td{border-bottom:0}.study-table-block th:last-child,.study-table-block td:last-child{border-right:0}
.mechanism-flow{display:flex;flex-direction:column;align-items:stretch;gap:.2rem;max-width:760px;margin:auto}.mechanism-step{padding:.62rem .8rem;border:1px solid color-mix(in srgb,var(--blue) 35%,var(--line));border-radius:10px;background:var(--step);text-align:center;font-weight:750}.mechanism-arrow{text-align:center;color:var(--blue);font-size:1.25rem;font-weight:900;line-height:1}
.trap-stack:empty{display:none}.trap-point{margin:0;padding:.8rem 1rem;border:0;border-left:5px solid var(--red);border-radius:0 11px 11px 0;background:var(--red-soft)}.trap-point+ .trap-point{margin-top:.55rem}.trap-point strong{display:block;color:var(--red);font-size:.84rem;margin-bottom:.2rem}
.final-checklist{border-top:5px solid var(--navy)}.final-checklist-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem}.check-card{border:1px solid var(--line);border-radius:12px;padding:.85rem;background:var(--bg)}.check-card h3{margin:0 0 .45rem;color:var(--navy);font-size:1rem}.check-card.comparison{border-top:3px solid var(--blue)}.check-card.cause{border-top:3px solid #4b9b72}.check-card.traps{border-top:3px solid var(--red)}.check-copy{display:block;min-width:0}.check-row{display:flex;align-items:flex-start;gap:.5rem}.check-row input{margin-top:.42rem;flex:0 0 auto}
@media(max-width:900px){.roadmap-grid,.final-checklist-grid{grid-template-columns:1fr}.section-evidence{width:100%;margin-left:42px;justify-content:flex-start}.flow-section summary{flex-wrap:wrap}.roadmap{padding:1rem}.study-table-block,.mechanism-block{padding:.75rem}.note-panel.core{padding:.7rem}.core-note-card{padding:.72rem}.core-note-heading h5{flex-basis:10rem}.core-panel-heading{align-items:flex-start}}
@media print{.roadmap-card{break-inside:avoid}.study-table-scroll{overflow:visible}.study-table-block table{min-width:0}.trap-point,.core-note-card{break-inside:avoid}.final-checklist{break-before:page}}
'''

    script = r'''
const rootKey="prestudy-__DOC_KEY__";
const body=document.body;
const savedTheme=localStorage.getItem(rootKey+"-theme");
if(savedTheme==="dark") body.classList.add("dark");
const savedScale=parseFloat(localStorage.getItem(rootKey+"-scale")||"1");
document.documentElement.style.setProperty("--scale",String(savedScale));
document.querySelectorAll("[data-store]").forEach(el=>{
  const key=rootKey+"-"+el.dataset.store;
  const saved=localStorage.getItem(key);
  if(el.type==="checkbox") el.checked=saved==="1"; else if(saved!==null) el.value=saved;
  el.addEventListener("input",()=>localStorage.setItem(key,el.type==="checkbox"?(el.checked?"1":"0"):el.value));
});
document.getElementById("theme").onclick=()=>{body.classList.toggle("dark");localStorage.setItem(rootKey+"-theme",body.classList.contains("dark")?"dark":"light")};
function changeScale(delta){let current=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--scale"))||1;current=Math.min(1.35,Math.max(.85,current+delta));document.documentElement.style.setProperty("--scale",String(current));localStorage.setItem(rootKey+"-scale",String(current))}
document.getElementById("smaller").onclick=()=>changeScale(-.05);document.getElementById("larger").onclick=()=>changeScale(.05);
document.getElementById("collapse").onclick=()=>document.querySelectorAll(".flow-section").forEach(x=>x.open=false);
document.getElementById("expand").onclick=()=>document.querySelectorAll(".flow-section").forEach(x=>x.open=true);
document.getElementById("print").onclick=()=>window.print();
const search=document.getElementById("search");
search.addEventListener("input",()=>{const q=search.value.trim().toLowerCase();let visible=0;document.querySelectorAll(".searchable").forEach(el=>{const show=!q||el.innerText.toLowerCase().includes(q);el.classList.toggle("hidden-by-search",!show);if(show)visible++});document.getElementById("empty-search").style.display=visible?"none":"block"});
'''.replace("__DOC_KEY__", document_key)

    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{_safe(display_title)}</title><style>{styles}</style></head>
<body>
<header class="topbar"><div class="brand">수업 동반 노트</div><input id="search" class="search" type="search" placeholder="개념·약물·공식 검색"><button id="smaller" title="글자 작게">A−</button><button id="larger" title="글자 크게">A+</button><button id="theme">◐</button><button id="print">인쇄</button></header>
<div class="shell">
<nav class="sidebar"><h2>강의 흐름</h2>{''.join(nav_links)}</nav>
<main class="content">
  <section class="hero"><div class="eyebrow">{_safe(lecture.course)} · {_safe(lecture.professor)}</div><h1>{_safe(display_title)}</h1><p>{_safe(guide.subtitle)}</p><div class="meta"><span>{_safe(lecture.topic)}</span><span>{_safe(lecture.lecture_date or '강의일 미지정')}</span><span>{len(ordered_flow)}개 구간</span><span>페이지 기준 · {_safe(page_kind.value)}</span></div>{source_manifest}</section>
  <section class="roadmap" id="roadmap"><p class="section-kicker">LECTURE ROADMAP</p><h2>수업 로드맵</h2><div class="exam-style-summary"><strong>교수님 출제 스타일 · 적용 전략</strong>{_safe(guide.exam_style_summary)}</div><div class="roadmap-grid">{''.join(roadmap_cards)}</div></section>
  <section class="usage"><h2>이 파일을 쓰는 법</h2><ol>{how_to}</ol></section>
  <div class="flow-actions"><button id="collapse">모두 접기</button><button id="expand">모두 펼치기</button></div>
  <div id="empty-search" class="empty-search">검색 결과가 없습니다.</div>
  {''.join(flow_sections)}
  <section class="section-card"><h2>수업 중 빠른 참조</h2><div class="reference-grid">{''.join(quick_cards)}</div></section>
  <div class="split"><section class="section-card focus searchable"><h2>교수님·족보 기반 집중 신호</h2>{focus_items}</section><section class="section-card confusion searchable"><h2>헷갈리기 쉬운 구분</h2>{confusion_items}</section></div>
  <section class="section-card final-checklist" id="final-checklist"><p class="section-kicker">FINAL REVIEW</p><h2>최종 체크리스트</h2><div class="final-checklist-grid"><div class="check-card comparison"><h3>A vs B 비교</h3>{comparison_checklist}</div><div class="check-card cause"><h3>Cause &amp; Effect</h3>{cause_checklist}</div><div class="check-card traps"><h3>🔥 함정 포인트</h3>{trap_checklist}</div></div></section>
  <section class="section-card"><h2>수업 중 최소 확인</h2>{live_checklist}</section>
  <details class="section-card uncertainties"><summary><strong>자료 간 차이와 확인이 필요한 점</strong></summary><ul>{uncertainties}</ul></details>
</main></div>
<footer>오프라인 단일 HTML · 체크와 메모는 이 기기의 브라우저에 자동 저장됩니다.</footer>
<script>{script}</script></body></html>'''
    output_path.write_text(document, encoding="utf-8")
