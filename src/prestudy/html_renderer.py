from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from .models import CitedItem, LectureRequest, StudyGuide


def _safe(value: str) -> str:
    normalized = value.replace("\u2212", "-")
    display_terms = {
        "lecture_flow": "강의 흐름",
        "ready_notes": "필기 대체 노트",
        "listen_for": "설명을 들으며 연결할 것",
        "minimal_live_notes": "수업 중 최소 확인",
        "quick_reference": "빠른 참조",
        "professor_and_exam_signals": "집중 신호",
    }
    for internal, label in display_terms.items():
        normalized = normalized.replace(internal, label)
    return html.escape(normalized, quote=True).replace("\n", "<br>")


def _citation_pages(citations: list[str]) -> str:
    pages: list[str] = []
    for citation in citations:
        for value in re.findall(r"p\.\s*(\d+(?:\s*[–-]\s*\d+)?)", citation, flags=re.IGNORECASE):
            page = "p." + re.sub(r"\s+", "", value).replace("-", "–")
            if page not in pages:
                pages.append(page)
    return " · ".join(pages)


def _first_page(item: CitedItem) -> int:
    match = re.search(r"\d+", _citation_pages(item.citations))
    return int(match.group()) if match else 10**9


def _range_start(value: str) -> int:
    match = re.search(r"\d+", value)
    return int(match.group()) if match else 10**9


def _cited_item(item: CitedItem) -> str:
    pages = _citation_pages(item.citations)
    page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
    return f'<li><div>{_safe(item.content)}</div>{page_html}</li>'


def _cited_list(items: list[CitedItem]) -> str:
    return '<ul class="note-list">' + "".join(_cited_item(item) for item in sorted(items, key=_first_page)) + "</ul>"


def render_study_guide_html(guide: StudyGuide, lecture: LectureRequest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered_flow = sorted(guide.lecture_flow, key=lambda section: (_range_start(section.source_range), section.order))
    document_key = hashlib.sha1(
        f"{lecture.course}|{lecture.professor}|{lecture.topic}|{lecture.lecture_date}".encode("utf-8")
    ).hexdigest()[:12]

    nav_links = []
    flow_sections = []
    for display_order, section in enumerate(ordered_flow, 1):
        section_id = f"flow-{display_order}"
        nav_links.append(
            f'<a href="#{section_id}"><span>{display_order}</span><strong>{_safe(section.source_range)}</strong>'
            f'<small>{_safe(section.title)}</small></a>'
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

        flow_sections.append(
            f'''<details class="flow-section searchable" id="{section_id}" open>
  <summary>
    <span class="flow-number">{display_order}</span>
    <span class="flow-heading"><strong>{_safe(section.title)}</strong><small>{_safe(section.source_range)}</small></span>
    <span class="chevron">⌄</span>
  </summary>
  <div class="flow-content">
    <div class="note-panel core"><h4>필기 대신 읽을 핵심</h4>{_cited_list(section.ready_notes)}</div>
    <div class="note-panel emphasis"><h4>강조될 가능성이 높은 지점</h4>{_cited_list(section.emphasis_signals)}</div>
    <div class="note-panel listen"><h4>설명을 들으며 연결할 것</h4>{_cited_list(section.listen_for)}</div>
    {live_notes}
  </div>
</details>'''
        )

    quick_cards = []
    for card in guide.quick_reference:
        pages = _citation_pages(card.citations)
        page_html = f'<span class="page-ref">{_safe(pages)}</span>' if pages else ""
        quick_cards.append(
            f'''<article class="reference-card searchable">
  <h3>{_safe(card.title)}</h3>
  <div class="formula">{_safe(card.content)}</div>
  <p><strong>언제 찾나</strong> · {_safe(card.use_when)}</p>
  {page_html}
</article>'''
        )

    focus_items = _cited_list(guide.professor_and_exam_signals)
    confusion_items = _cited_list(guide.common_confusions)
    how_to = "".join(f"<li>{_safe(item)}</li>" for item in guide.how_to_use)
    checklist = "".join(
        f'<label class="check-row"><input type="checkbox" data-store="{document_key}-global-{index}"> {_safe(item)}</label>'
        for index, item in enumerate(guide.minimal_live_checklist, 1)
    )
    uncertainties = "".join(f"<li>{_safe(item)}</li>" for item in guide.uncertainties)

    styles = r'''
:root{--bg:#f5f7f8;--surface:#fff;--text:#17212b;--muted:#66727d;--navy:#18324a;--blue:#2f6b8a;--line:#d8e1e6;--core:#fff;--emphasis:#fff6d8;--listen:#eaf3f7;--live:#eaf6ef;--danger:#fceeef;--shadow:0 12px 32px rgba(24,50,74,.08);--scale:1}
body.dark{--bg:#111820;--surface:#19232d;--text:#eaf0f4;--muted:#a8b5bf;--navy:#dceefa;--blue:#75badc;--line:#344653;--core:#19232d;--emphasis:#3b3521;--listen:#203746;--live:#213a2d;--danger:#40282d;--shadow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;font-size:calc(16px * var(--scale));line-height:1.7}.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:.65rem;padding:.65rem max(1rem,calc((100vw - 1380px)/2));background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}.topbar .brand{font-weight:800;color:var(--navy);margin-right:auto;white-space:nowrap}.search{min-width:180px;max-width:340px;width:30vw;padding:.55rem .75rem;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--text)}button{border:1px solid var(--line);background:var(--surface);color:var(--text);border-radius:9px;padding:.5rem .7rem;font-weight:700;cursor:pointer}.shell{max-width:1380px;margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:1.25rem;padding:1.25rem}.sidebar{position:sticky;top:72px;align-self:start;max-height:calc(100vh - 90px);overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1rem;box-shadow:var(--shadow)}.sidebar h2{font-size:.85rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin:.2rem 0 .8rem}.sidebar a{display:grid;grid-template-columns:26px 1fr;gap:.1rem .55rem;text-decoration:none;color:var(--text);padding:.65rem;border-radius:10px}.sidebar a:hover{background:var(--listen)}.sidebar a span{grid-row:1/3;display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:var(--navy);color:var(--surface);font-size:.78rem;font-weight:800}.sidebar a strong{font-size:.82rem;color:var(--blue)}.sidebar a small{font-size:.78rem;color:var(--muted);line-height:1.35}.content{min-width:0}.hero{background:linear-gradient(145deg,var(--navy),#2f6b8a);color:#fff;border-radius:22px;padding:2.1rem;box-shadow:var(--shadow)}.hero .eyebrow{opacity:.8;font-weight:700}.hero h1{font-size:clamp(1.75rem,4vw,3rem);line-height:1.2;margin:.45rem 0}.hero p{margin:.3rem 0;opacity:.9}.meta{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.25rem}.meta span{padding:.35rem .65rem;border:1px solid rgba(255,255,255,.28);border-radius:999px;font-size:.86rem}.usage,.section-card{margin-top:1rem;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.1rem 1.3rem;box-shadow:var(--shadow)}.usage h2,.section-card h2{color:var(--navy);margin:.1rem 0 .65rem}.usage ol{margin:.25rem 0;padding-left:1.35rem}.flow-actions{display:flex;justify-content:flex-end;gap:.45rem;margin:1rem 0 .65rem}.flow-section{scroll-margin-top:78px;margin-bottom:.85rem;background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}.flow-section summary{display:flex;align-items:center;gap:.8rem;padding:1rem 1.15rem;cursor:pointer;list-style:none}.flow-section summary::-webkit-details-marker{display:none}.flow-number{display:grid;place-items:center;flex:0 0 34px;height:34px;border-radius:50%;background:var(--navy);color:var(--surface);font-weight:900}.flow-heading{display:flex;flex-direction:column;min-width:0}.flow-heading strong{color:var(--navy);font-size:1.12rem}.flow-heading small{color:var(--blue);font-weight:800}.chevron{margin-left:auto;font-size:1.25rem;transition:.2s}.flow-section[open] .chevron{transform:rotate(180deg)}.flow-content{padding:0 1rem 1rem;display:grid;gap:.7rem}.note-panel{border:1px solid var(--line);border-radius:12px;padding:.85rem 1rem}.note-panel h4{margin:0 0 .45rem;color:var(--navy)}.note-panel.core{background:var(--core)}.note-panel.emphasis{background:var(--emphasis)}.note-panel.listen{background:var(--listen)}.note-panel.live{background:var(--live)}.note-list{padding-left:1.25rem;margin:.2rem 0}.note-list li{padding:.35rem 0}.page-ref{display:inline-block;color:var(--blue);font-size:.78rem;font-weight:800;margin-top:.15rem}.live-note{border-top:1px dashed var(--line);padding:.7rem 0}.live-note:first-of-type{border-top:0}.live-note label,.check-row{display:block;font-weight:700}.live-note textarea{width:100%;resize:vertical;margin-top:.45rem;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text);padding:.65rem;font:inherit}.reference-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.reference-card{border:1px solid var(--line);border-radius:12px;padding:1rem;background:var(--surface)}.reference-card h3{color:var(--blue);margin:0 0 .45rem}.reference-card .formula{font-weight:700;white-space:normal}.reference-card p{color:var(--muted);font-size:.9rem}.split{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.focus{background:var(--emphasis)}.confusion{background:var(--danger)}.check-row{padding:.55rem 0;border-bottom:1px solid var(--line)}.uncertainties{color:var(--muted)}.hidden-by-search{display:none!important}.empty-search{display:none;padding:2rem;text-align:center;color:var(--muted)}footer{text-align:center;color:var(--muted);padding:2rem 1rem 4rem}
@media(max-width:900px){.shell{grid-template-columns:1fr;padding:.75rem}.sidebar{position:static;max-height:none;display:flex;gap:.35rem;overflow-x:auto;border-radius:12px}.sidebar h2{display:none}.sidebar a{min-width:150px}.hero{padding:1.4rem}.reference-grid,.split{grid-template-columns:1fr}.topbar .brand{display:none}.search{width:100%;max-width:none}.topbar{padding:.55rem}.flow-section summary{padding:.85rem}.flow-content{padding:0 .65rem .65rem}.note-panel{padding:.75rem}}
@media print{.topbar,.sidebar,.flow-actions{display:none!important}.shell{display:block;max-width:none;padding:0}.flow-section{break-inside:avoid;box-shadow:none}.flow-section:not([open])>.flow-content{display:block}.hero{background:#fff;color:#000;border:1px solid #ccc}.section-card,.usage{box-shadow:none}}
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
<title>{_safe(guide.title)}</title><style>{styles}</style></head>
<body>
<header class="topbar"><div class="brand">수업 동반 노트</div><input id="search" class="search" type="search" placeholder="개념·약물·공식 검색"><button id="smaller" title="글자 작게">A−</button><button id="larger" title="글자 크게">A+</button><button id="theme">◐</button><button id="print">인쇄</button></header>
<div class="shell">
<nav class="sidebar"><h2>강의 흐름</h2>{''.join(nav_links)}</nav>
<main class="content">
  <section class="hero"><div class="eyebrow">{_safe(lecture.course)} · {_safe(lecture.professor)}</div><h1>{_safe(guide.title)}</h1><p>{_safe(guide.subtitle)}</p><div class="meta"><span>{_safe(lecture.topic)}</span><span>{_safe(lecture.lecture_date or '강의일 미지정')}</span><span>{len(ordered_flow)}개 구간</span></div></section>
  <section class="usage"><h2>이 파일을 쓰는 법</h2><ol>{how_to}</ol></section>
  <div class="flow-actions"><button id="collapse">모두 접기</button><button id="expand">모두 펼치기</button></div>
  <div id="empty-search" class="empty-search">검색 결과가 없습니다.</div>
  {''.join(flow_sections)}
  <section class="section-card"><h2>수업 중 빠른 참조</h2><div class="reference-grid">{''.join(quick_cards)}</div></section>
  <div class="split"><section class="section-card focus searchable"><h2>교수님·족보 기반 집중 신호</h2>{focus_items}</section><section class="section-card confusion searchable"><h2>헷갈리기 쉬운 구분</h2>{confusion_items}</section></div>
  <section class="section-card"><h2>수업 중 최소 확인</h2>{checklist}</section>
  <details class="section-card uncertainties"><summary><strong>자료 간 차이와 확인이 필요한 점</strong></summary><ul>{uncertainties}</ul></details>
</main></div>
<footer>오프라인 단일 HTML · 체크와 메모는 이 기기의 브라우저에 자동 저장됩니다.</footer>
<script>{script}</script></body></html>'''
    output_path.write_text(document, encoding="utf-8")
