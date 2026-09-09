from __future__ import annotations

import re
import sys
from pathlib import Path

SUMMED_STYLES = """
:root{--bg:#f3f5f2;--paper:#fffdf8;--ink:#1d2925;--muted:#69756f;--forest:#214d3d;--mint:#dcebe3;--amber:#f6e9c9;--blue:#e1edf2;--quiz:#edf3e8;--line:#d9dfda;--shadow:0 14px 34px rgba(29,55,45,.08);--scale:1}
body.dark{--bg:#111814;--paper:#19221d;--ink:#edf4ef;--muted:#aab7af;--forest:#91c9ae;--mint:#20392e;--amber:#3c3522;--blue:#20343c;--quiz:#243328;--line:#34443b;--shadow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;font-size:calc(16px * var(--scale));line-height:1.72}
.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:.55rem;padding:.6rem 1.2rem;width:100%;background:color-mix(in srgb,var(--paper) 92%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}
.btn-toc{font-size:.9rem;display:inline-flex;align-items:center;gap:.35rem;white-space:nowrap;padding:.48rem .75rem;background:var(--paper)}
body.toc-collapsed #toggle-toc{background:var(--mint);color:var(--forest)}
.brand{font-weight:900;color:var(--forest);letter-spacing:.04em;margin-right:auto}
.search{width:min(38vw,340px);padding:.55rem .75rem;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)}
button{padding:.48rem .65rem;border:1px solid var(--line);border-radius:9px;background:var(--paper);color:var(--ink);font-weight:750;cursor:pointer}
.layout{display:grid;grid-template-columns:240px minmax(0,1fr);gap:1.2rem;width:100%;max-width:100%;margin:0;padding:.8rem 1.2rem;transition:grid-template-columns .2s ease}
body.toc-collapsed .side{display:none!important}
body.toc-collapsed .layout{grid-template-columns:minmax(0,1fr)!important}
.side{position:sticky;top:68px;align-self:start;display:grid;gap:.35rem;max-height:calc(100vh - 82px);overflow-y:auto;padding-right:.25rem}
.side a{display:grid;grid-template-columns:32px 1fr;align-items:center;gap:.55rem;color:var(--ink);text-decoration:none;padding:.6rem;border-radius:10px}
.side a:hover{background:var(--mint)}
.side span,.section-heading span{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:var(--forest);color:var(--paper);font-size:.75rem;font-weight:900}
.content{min-width:0;width:100%}
.hero{padding:2rem;border-radius:22px;color:#fff;background:linear-gradient(135deg,#214d3d,#3b7961);box-shadow:var(--shadow)}
.eyebrow{font-size:.85rem;font-weight:800;opacity:.78}
.hero h1{margin:.45rem 0 .35rem;font-size:clamp(1.8rem,4vw,3.2rem);line-height:1.15}
.hero p{margin:.2rem 0}
.meta{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1.1rem}
.meta span{padding:.34rem .65rem;border:1px solid rgba(255,255,255,.3);border-radius:999px;font-size:.82rem}
.overview,.card,.split>section,.sources{margin-top:1rem;padding:1.15rem 1.25rem;background:var(--paper);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}
h2{margin:.1rem 0 .7rem;color:var(--forest);font-size:1.25rem}
.section-heading{display:flex;align-items:center;gap:.7rem}
.section-heading h2{margin:0}
.panel{margin-top:.8rem;padding:.85rem 1rem;border-radius:12px;background:var(--bg)}
.panel h3{margin:0 0 .35rem;font-size:.95rem;color:var(--forest)}
.panel.exam{background:var(--amber)}
.panel.transcript{background:var(--blue)}
.quiz{margin-top:1rem;padding:1rem;border:1px solid var(--line);border-radius:12px;background:var(--quiz)}
.quiz h3{margin:0;color:var(--forest);font-size:1rem}
.quiz-guide{margin:.15rem 0 .65rem;color:var(--muted);font-size:.86rem}
.quiz-item{margin:.45rem 0;border:1px solid var(--line);border-radius:10px;background:var(--paper)}
.quiz-item summary{display:flex;align-items:flex-start;gap:.55rem;padding:.65rem .75rem;cursor:pointer;font-weight:750;list-style:none}
.quiz-item summary::-webkit-details-marker{display:none}
.quiz-item summary span{flex:0 0 auto;color:var(--forest)}
.quiz-answer{padding:.6rem .75rem .75rem;border-top:1px solid var(--line)}
.quiz-answer strong{color:var(--forest);font-size:.82rem}
.quiz-answer p{margin:.2rem 0 0}
ul{margin:.25rem 0;padding-left:1.25rem}
li{margin:.33rem 0}
.reason{color:var(--muted);font-size:.9rem}
.table-wrap{overflow:auto}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th,td{padding:.65rem;border:1px solid var(--line);vertical-align:top;text-align:left}
th{background:var(--mint);color:var(--forest)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.empty{color:var(--muted)}
.sources{color:var(--muted);font-size:.83rem}
.hidden{display:none!important}
.no-result{display:none;text-align:center;padding:2rem;color:var(--muted)}
footer{text-align:center;color:var(--muted);padding:2rem 1rem 4rem;font-size:.82rem}
@media(max-width:960px){
.layout{grid-template-columns:200px minmax(0,1fr);gap:1rem;padding:.6rem .8rem}
.topbar{padding:.5rem .8rem}
.hero{padding:1.4rem}
}
@media(max-width:640px){
body:not(.toc-collapsed) .side{position:fixed;top:56px;left:0;bottom:0;width:min(82vw,270px);z-index:100;background:var(--paper);border-right:1px solid var(--line);box-shadow:0 0 24px rgba(0,0,0,.2);padding:.8rem;overflow-y:auto}
body:not(.toc-collapsed) .layout{grid-template-columns:minmax(0,1fr)!important}
.brand{display:none}
.search{flex:1;min-width:100px}
.split{grid-template-columns:1fr}
.card{scroll-margin-top:70px}
}
@media print{
.topbar,.side,#toggle-toc{display:none!important}
.layout{display:block;max-width:none;padding:0}
.hero{background:#fff;color:#000;border:1px solid #bbb}
.card,.overview,.split>section,.sources{box-shadow:none;break-inside:avoid}
}
"""

SUMMED_SCRIPT_TEMPLATE = """
const key='summed-{key}'; const body=document.body;
if(localStorage.getItem(key+'-theme')==='dark')body.classList.add('dark');
let scale=parseFloat(localStorage.getItem(key+'-scale')||'1');document.documentElement.style.setProperty('--scale',scale);
document.getElementById('theme').onclick=()=>{{body.classList.toggle('dark');localStorage.setItem(key+'-theme',body.classList.contains('dark')?'dark':'light')}};
function zoom(delta){{scale=Math.min(1.35,Math.max(.85,scale+delta));document.documentElement.style.setProperty('--scale',scale);localStorage.setItem(key+'-scale',scale)}}
document.getElementById('small').onclick=()=>zoom(-.05);document.getElementById('large').onclick=()=>zoom(.05);document.getElementById('print').onclick=()=>window.print();
const tocBtn=document.getElementById('toggle-toc');
const storedToc=localStorage.getItem(key+'-toc');
if(storedToc==='collapsed'||(!storedToc&&window.innerWidth<=1024))body.classList.add('toc-collapsed');
if(tocBtn){{tocBtn.onclick=()=>{{body.classList.toggle('toc-collapsed');localStorage.setItem(key+'-toc',body.classList.contains('toc-collapsed')?'collapsed':'open')}};}}
document.querySelectorAll('.side a').forEach(a=>{{a.addEventListener('click',()=>{{if(window.innerWidth<=1024){{body.classList.add('toc-collapsed');localStorage.setItem(key+'-toc','collapsed');}}}});}});
document.getElementById('search').addEventListener('input',e=>{{const q=e.target.value.trim().toLowerCase();let visible=0;document.querySelectorAll('.searchable').forEach(x=>{{const show=!q||x.innerText.toLowerCase().includes(q);x.classList.toggle('hidden',!show);if(show)visible++}});document.getElementById('none').style.display=visible?'none':'block'}});
"""


def _upgrade_summed_html(content: str) -> str:
    m = re.search(r"const key='summed-([^']+)';", content)
    doc_key = m.group(1) if m else "default"

    updated = content

    # Add toggle button to topbar if missing
    if 'id="toggle-toc"' not in updated:
        updated = re.sub(
            r'(<header class="topbar">)(.*?)(<div class="brand">summed</div>)',
            r'\1<button id="toggle-toc" class="btn-toc" title="목차 열기/닫기" aria-label="목차 토글">☰ 목차</button>\3',
            updated,
            count=1,
        )

    # Replace <style>...</style>
    updated = re.sub(
        r"<style>.*?</style>",
        f"<style>{SUMMED_STYLES}</style>",
        updated,
        flags=re.DOTALL,
        count=1,
    )

    # Replace <script>...</script>
    new_script = SUMMED_SCRIPT_TEMPLATE.format(key=doc_key)
    updated = re.sub(
        r"<script>.*?</script>",
        f"<script>{new_script}</script>",
        updated,
        flags=re.DOTALL,
        count=1,
    )

    return updated


def _upgrade_prestudy_html(content: str) -> str:
    from prestudy import html_renderer

    has_toggle = 'id="toggle-toc"' in content
    m = re.search(r'const rootKey="prestudy-([^"]+)";', content)
    doc_key = m.group(1) if m else "default"

    source = Path(html_renderer.__file__).read_text(encoding="utf-8")
    styles_m = re.search(r"styles = r'''(.*?)'''\s+styles \+=", source, re.DOTALL)
    styles2_m = re.search(r"styles \+= r'''\n\.source-manifest(.*?)'''\s+styles \+=", source, re.DOTALL)
    styles3_m = re.search(r"styles \+= r'''\n:root\{--gold(.*?)'''\s+script = r'''", source, re.DOTALL)
    script_m = re.search(r"script = r'''(.*?)'''\.replace\(\"__DOC_KEY__\", document_key\)", source, re.DOTALL)

    if not (styles_m and styles2_m and styles3_m and script_m):
        return content

    prestudy_styles = styles_m.group(1) + "\n.source-manifest" + styles2_m.group(1) + "\n:root{--gold" + styles3_m.group(1)
    prestudy_script = script_m.group(1).replace("__DOC_KEY__", doc_key)

    updated = content
    if not has_toggle:
        updated = re.sub(
            r'(<header class="topbar">)(.*?)(<div class="brand">수업 동반 노트</div>)',
            r'\1<button id="toggle-toc" class="btn-toc" title="목차 열기/닫기" aria-label="목차 토글">☰ 목차</button>\3',
            updated,
            count=1,
        )

    updated = re.sub(
        r"<style>.*?</style>",
        f"<style>{prestudy_styles}</style>",
        updated,
        flags=re.DOTALL,
        count=1,
    )

    updated = re.sub(
        r"<script>.*?</script>",
        f"<script>{prestudy_script}</script>",
        updated,
        flags=re.DOTALL,
        count=1,
    )

    return updated


def migrate_file(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[ERR] Failed to read {path}: {exc}")
        return False

    is_summed = "summed" in path.name.lower() or "summed" in content[:2000]
    is_prestudy = "수업 동반 노트" in content[:2000] or "수업동반노트" in path.name

    if is_summed:
        new_content = _upgrade_summed_html(content)
    elif is_prestudy:
        new_content = _upgrade_prestudy_html(content)
    else:
        if 'class="layout"' in content:
            new_content = _upgrade_summed_html(content)
        elif 'class="shell"' in content:
            new_content = _upgrade_prestudy_html(content)
        else:
            return False

    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main():
    target_dirs = [
        Path("G:/내 드라이브/summed"),
        Path(".summed-data/outputs"),
        Path(".summed-data/backups"),
        Path("H:/내 드라이브/수업 동반 노트"),
        Path.home() / ".summed/outputs",
    ]

    total_scanned = 0
    total_upgraded = 0

    for d in target_dirs:
        if not d.is_dir():
            continue
        html_files = list(d.rglob("*.html"))
        print(f"Checking {d} ({len(html_files)} html files)...")
        for f in html_files:
            total_scanned += 1
            if migrate_file(f):
                total_upgraded += 1

    print(f"\nMigration finished: {total_upgraded}/{total_scanned} files upgraded.")


if __name__ == "__main__":
    main()

