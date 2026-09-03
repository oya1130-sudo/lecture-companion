from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from .models import SummedNote, SummaryRequest


def _plain(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"<\s*(?:img|picture|svg)\b[^>]*>", "", value, flags=re.IGNORECASE)
    return value.strip()


def _md(value: str) -> str:
    return _plain(value).replace("<", "&lt;").replace(">", "&gt;")


def _html(value: str) -> str:
    return html.escape(_plain(value), quote=True).replace("\n", "<br>")


def _markdown_table(columns: list[str], rows: list[list[str]]) -> str:
    if not columns:
        return ""
    clean_columns = [_md(value).replace("|", "\\|") for value in columns]
    lines = ["| " + " | ".join(clean_columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = list(row[: len(columns)]) + [""] * max(0, len(columns) - len(row))
        lines.append("| " + " | ".join(_md(value).replace("|", "\\|") for value in values) + " |")
    return "\n".join(lines)


def render_markdown(note: SummedNote, request: SummaryRequest, source_names: list[str], path: Path) -> None:
    lines = [
        f"# {_md(note.title)}",
        "",
        f"> {_md(note.subtitle)}",
        "",
        f"- 과목: {_md(request.course)}",
        f"- 교수: {_md(request.professor)}",
        f"- 주제: {_md(request.topic)}",
        f"- 강의일: {request.lecture_date.isoformat()}",
        "",
        "## 한눈에 보기",
        "",
    ]
    lines.extend(f"- {_md(item)}" for item in note.overview)
    for section in note.sections:
        lines.extend(["", f"## {_md(section.title)}", "", "### 핵심 내용", ""])
        lines.extend(f"- {_md(item)}" for item in section.core_points)
        if section.exam_focus:
            lines.extend(["", "### 시험 관점", ""])
            lines.extend(f"- {_md(item)}" for item in section.exam_focus)
        if section.transcript_additions:
            lines.extend(["", "### 전사본 보완", ""])
            lines.extend(f"- {_md(item)}" for item in section.transcript_additions)
        lines.extend(["", "### 소단원 복습 퀴즈", ""])
        for index, item in enumerate(section.review_quiz, 1):
            lines.extend(
                [
                    f"#### Q{index}. {_md(item.question)}",
                    "",
                    "<details>",
                    "<summary>정답 보기</summary>",
                    "",
                    _md(item.answer),
                    "",
                    "</details>",
                    "",
                ]
            )
    for table in note.tables:
        rendered = _markdown_table(table.columns, table.rows)
        if rendered:
            lines.extend(["", f"## {_md(table.title)}", "", f"_{_md(table.why_useful)}_", "", rendered])
    lines.extend(["", "## 시험 직전 빠른 복습", ""])
    lines.extend(f"- {_md(item)}" for item in note.rapid_review)
    lines.extend(["", "## 헷갈리기 쉬운 구분", ""])
    lines.extend(f"- {_md(item)}" for item in note.likely_confusions)
    if note.caveats:
        lines.extend(["", "## 확인이 필요한 점", ""])
        lines.extend(f"- {_md(item)}" for item in note.caveats)
    lines.extend(["", "---", "", "사용한 자료: " + ", ".join(_md(name) for name in source_names), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _list(items: list[str], class_name: str = "") -> str:
    if not items:
        return '<p class="empty">해당 내용 없음</p>'
    return f'<ul class="{class_name}">' + "".join(f"<li>{_html(item)}</li>" for item in items) + "</ul>"


def _html_table(columns: list[str], rows: list[list[str]]) -> str:
    if not columns:
        return ""
    head = "".join(f"<th>{_html(column)}</th>" for column in columns)
    body = []
    for row in rows:
        values = list(row[: len(columns)]) + [""] * max(0, len(columns) - len(row))
        body.append("<tr>" + "".join(f"<td>{_html(value)}</td>" for value in values) + "</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render_html(note: SummedNote, request: SummaryRequest, source_names: list[str], path: Path) -> None:
    document_key = hashlib.sha1(
        f"{request.course}|{request.professor}|{request.topic}|{request.lecture_date}".encode()
    ).hexdigest()[:12]
    nav = []
    sections = []
    for index, section in enumerate(note.sections, 1):
        section_id = f"section-{index}"
        nav.append(f'<a href="#{section_id}"><span>{index:02d}</span>{_html(section.title)}</a>')
        exam = (
            f'<div class="panel exam"><h3>시험 관점</h3>{_list(section.exam_focus)}</div>'
            if section.exam_focus
            else ""
        )
        transcript = (
            f'<div class="panel transcript"><h3>전사본 보완</h3>{_list(section.transcript_additions)}</div>'
            if section.transcript_additions
            else ""
        )
        quiz_items = "".join(
            f'<details class="quiz-item"><summary><span>Q{quiz_index}</span>{_html(item.question)}</summary>'
            f'<div class="quiz-answer"><strong>정답</strong><p>{_html(item.answer)}</p></div></details>'
            for quiz_index, item in enumerate(section.review_quiz, 1)
        )
        quiz = (
            f'<div class="quiz"><h3>소단원 복습 퀴즈</h3><p class="quiz-guide">문제를 먼저 풀고 정답을 펼쳐보세요.</p>{quiz_items}</div>'
        )
        sections.append(
            f'<section id="{section_id}" class="card searchable">'
            f'<div class="section-heading"><span>{index:02d}</span><h2>{_html(section.title)}</h2></div>'
            f'<div class="panel"><h3>핵심 내용</h3>{_list(section.core_points)}</div>{exam}{transcript}{quiz}</section>'
        )
    table_cards = []
    for table in note.tables:
        rendered = _html_table(table.columns, table.rows)
        if rendered:
            table_cards.append(
                f'<section class="card searchable"><h2>{_html(table.title)}</h2>'
                f'<p class="reason">{_html(table.why_useful)}</p>{rendered}</section>'
            )
    sources = "".join(f"<li>{_html(name)}</li>" for name in source_names)
    styles = """
:root{--bg:#f3f5f2;--paper:#fffdf8;--ink:#1d2925;--muted:#69756f;--forest:#214d3d;--mint:#dcebe3;--amber:#f6e9c9;--blue:#e1edf2;--quiz:#edf3e8;--line:#d9dfda;--shadow:0 14px 34px rgba(29,55,45,.08);--scale:1}
body.dark{--bg:#111814;--paper:#19221d;--ink:#edf4ef;--muted:#aab7af;--forest:#91c9ae;--mint:#20392e;--amber:#3c3522;--blue:#20343c;--quiz:#243328;--line:#34443b;--shadow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;font-size:calc(16px * var(--scale));line-height:1.72}.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:.55rem;padding:.7rem max(1rem,calc((100vw - 1240px)/2));background:color-mix(in srgb,var(--paper) 92%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}.brand{font-weight:900;color:var(--forest);letter-spacing:.04em;margin-right:auto}.search{width:min(38vw,340px);padding:.55rem .75rem;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)}button{padding:.48rem .65rem;border:1px solid var(--line);border-radius:9px;background:var(--paper);color:var(--ink);font-weight:750;cursor:pointer}.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:1.2rem;max-width:1240px;margin:auto;padding:1.2rem}.side{position:sticky;top:74px;align-self:start;display:grid;gap:.35rem}.side a{display:grid;grid-template-columns:32px 1fr;align-items:center;gap:.55rem;color:var(--ink);text-decoration:none;padding:.6rem;border-radius:10px}.side a:hover{background:var(--mint)}.side span,.section-heading span{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:var(--forest);color:var(--paper);font-size:.75rem;font-weight:900}.content{min-width:0}.hero{padding:2.3rem;border-radius:24px;color:#fff;background:linear-gradient(135deg,#214d3d,#3b7961);box-shadow:var(--shadow)}.eyebrow{font-size:.85rem;font-weight:800;opacity:.78}.hero h1{margin:.45rem 0 .35rem;font-size:clamp(2rem,5vw,3.5rem);line-height:1.12}.hero p{margin:.2rem 0;max-width:760px}.meta{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1.1rem}.meta span{padding:.34rem .65rem;border:1px solid rgba(255,255,255,.3);border-radius:999px;font-size:.82rem}.overview,.card,.split>section,.sources{margin-top:1rem;padding:1.15rem 1.25rem;background:var(--paper);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}h2{margin:.1rem 0 .7rem;color:var(--forest);font-size:1.25rem}.section-heading{display:flex;align-items:center;gap:.7rem}.section-heading h2{margin:0}.panel{margin-top:.8rem;padding:.85rem 1rem;border-radius:12px;background:var(--bg)}.panel h3{margin:0 0 .35rem;font-size:.95rem;color:var(--forest)}.panel.exam{background:var(--amber)}.panel.transcript{background:var(--blue)}.quiz{margin-top:1rem;padding:1rem;border:1px solid var(--line);border-radius:12px;background:var(--quiz)}.quiz h3{margin:0;color:var(--forest);font-size:1rem}.quiz-guide{margin:.15rem 0 .65rem;color:var(--muted);font-size:.86rem}.quiz-item{margin:.45rem 0;border:1px solid var(--line);border-radius:10px;background:var(--paper)}.quiz-item summary{display:flex;align-items:flex-start;gap:.55rem;padding:.65rem .75rem;cursor:pointer;font-weight:750;list-style:none}.quiz-item summary::-webkit-details-marker{display:none}.quiz-item summary span{flex:0 0 auto;color:var(--forest)}.quiz-answer{padding:.6rem .75rem .75rem;border-top:1px solid var(--line)}.quiz-answer strong{color:var(--forest);font-size:.82rem}.quiz-answer p{margin:.2rem 0 0}ul{margin:.25rem 0;padding-left:1.25rem}li{margin:.33rem 0}.reason{color:var(--muted);font-size:.9rem}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{padding:.65rem;border:1px solid var(--line);vertical-align:top;text-align:left}th{background:var(--mint);color:var(--forest)}.split{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.empty{color:var(--muted)}.sources{color:var(--muted);font-size:.83rem}.hidden{display:none!important}.no-result{display:none;text-align:center;padding:2rem;color:var(--muted)}footer{text-align:center;color:var(--muted);padding:2rem 1rem 4rem;font-size:.82rem}
@media(max-width:820px){.layout{grid-template-columns:1fr;padding:.75rem}.side{position:static;display:flex;overflow-x:auto}.side a{min-width:150px}.split{grid-template-columns:1fr}.hero{padding:1.45rem}.brand{display:none}.search{width:100%}.topbar{padding:.55rem}.card{scroll-margin-top:70px}}
@media print{.topbar,.side{display:none!important}.layout{display:block;max-width:none;padding:0}.hero{background:#fff;color:#000;border:1px solid #bbb}.card,.overview,.split>section,.sources{box-shadow:none;break-inside:avoid}}
"""
    script = f"""
const key='summed-{document_key}'; const body=document.body;
if(localStorage.getItem(key+'-theme')==='dark')body.classList.add('dark');
let scale=parseFloat(localStorage.getItem(key+'-scale')||'1');document.documentElement.style.setProperty('--scale',scale);
document.getElementById('theme').onclick=()=>{{body.classList.toggle('dark');localStorage.setItem(key+'-theme',body.classList.contains('dark')?'dark':'light')}};
function zoom(delta){{scale=Math.min(1.35,Math.max(.85,scale+delta));document.documentElement.style.setProperty('--scale',scale);localStorage.setItem(key+'-scale',scale)}}
document.getElementById('small').onclick=()=>zoom(-.05);document.getElementById('large').onclick=()=>zoom(.05);document.getElementById('print').onclick=()=>window.print();
document.getElementById('search').addEventListener('input',e=>{{const q=e.target.value.trim().toLowerCase();let visible=0;document.querySelectorAll('.searchable').forEach(x=>{{const show=!q||x.innerText.toLowerCase().includes(q);x.classList.toggle('hidden',!show);if(show)visible++}});document.getElementById('none').style.display=visible?'none':'block'}});
"""
    document = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_html(note.title)}</title><style>{styles}</style></head><body>
<header class="topbar"><div class="brand">summed</div><input id="search" class="search" type="search" placeholder="개념·약물·기전 검색"><button id="small" title="글자 작게">A−</button><button id="large" title="글자 크게">A+</button><button id="theme" title="화면 모드">◐</button><button id="print">인쇄</button></header>
<div class="layout"><nav class="side">{''.join(nav)}</nav><main class="content">
<section class="hero"><div class="eyebrow">{_html(request.course)} · {_html(request.professor)}</div><h1>{_html(note.title)}</h1><p>{_html(note.subtitle)}</p><div class="meta"><span>{_html(request.topic)}</span><span>{request.lecture_date.isoformat()}</span><span>이미지 제외</span></div></section>
<section class="overview searchable"><h2>한눈에 보기</h2>{_list(note.overview)}</section><div id="none" class="no-result">검색 결과가 없습니다.</div>
{''.join(sections)}{''.join(table_cards)}
<div class="split"><section class="searchable"><h2>시험 직전 빠른 복습</h2>{_list(note.rapid_review)}</section><section class="searchable"><h2>헷갈리기 쉬운 구분</h2>{_list(note.likely_confusions)}</section></div>
<section class="card searchable"><h2>확인이 필요한 점</h2>{_list(note.caveats)}</section>
<details class="sources"><summary><strong>사용한 자료</strong></summary><ul>{sources}</ul></details>
</main></div><footer>summed · 이미지 없이 생성된 오프라인 HTML</footer><script>{script}</script></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
