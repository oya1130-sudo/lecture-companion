from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from summed.models import SummaryRequest, SummedNote


def _plain(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", str(value))
    value = re.sub(r"<\s*(?:img|picture|svg)\b[^>]*>", "", value, flags=re.IGNORECASE)
    return value.strip()


def _md(value: str) -> str:
    return _plain(value).replace("<", "&lt;").replace(">", "&gt;")


def _esc(val: str) -> str:
    return html.escape(_plain(val), quote=True)


def _html(val: str) -> str:
    return html.escape(_plain(val), quote=True).replace("\n", "<br>")


def _clean_text(val: str) -> str:
    val = str(val)
    # 1. Protect and format quotes in text before adding any HTML tags
    val = re.sub(r"[‘\']([^’\']{1,45})[’\']", r"__QUOTE_START__\1__QUOTE_END__", val)
    # 2. Protect arrow notations
    val = val.replace("→", " __ARR__ ")
    val = val.replace("➔", " __ARR__ ")
    
    # 3. Escape HTML
    val = html.escape(_plain(val), quote=True)
    
    # 4. Restore safe HTML tags with double quotes
    val = val.replace("__QUOTE_START__", '<strong class="term-hl">‘')
    val = val.replace("__QUOTE_END__", "’</strong>")
    val = val.replace("__ARR__", '<span class="arr-hl">➔</span>')
    return val


def _parse_chain_into_roadmap(raw: str):
    """Detect if raw text contains an arrow progression chain suitable for flow-roadmap."""
    if raw.count("→") >= 3 or raw.count("➔") >= 3:
        # Check first sentence if multiple sentences exist
        first_s = re.split(r"(?<=[.!?])\s+", raw, maxsplit=1)[0]
        nodes = [n.strip() for n in re.split(r"\s*(?:→|➔)\s*", first_s) if n.strip()]
        if len(nodes) < 3:
            nodes = [n.strip() for n in re.split(r"\s*(?:→|➔)\s*", raw) if n.strip()]

        if 3 <= len(nodes) <= 6:
            nodes[0] = re.sub(r"^(?:운명 흐름은|진행 경로는|신호전달 경로는|분기 경로는)\s*", "", nodes[0]).strip()
            nodes[-1] = re.sub(r"이다\.?$", "", nodes[-1]).strip()
            
            if all(len(n) <= 50 for n in nodes):
                step_htmls = []
                cls_list = ["norm", "adapt", "rev", "irrev", "death"]
                for idx, n in enumerate(nodes):
                    cls = cls_list[idx % len(cls_list)]
                    sub_parts = re.split(r"[:(—]", n, maxsplit=1)
                    if len(sub_parts) == 2:
                        t = sub_parts[0].strip()
                        sub = sub_parts[1].rstrip(")").strip()
                    else:
                        t = n
                        sub = ""
                    sub_html = f'<small style="color:var(--text-muted);font-size:0.75rem;display:block;margin-top:2px;">{_esc(sub)}</small>' if sub else ""
                    step_htmls.append(f"""
    <div class="roadmap-step {cls}">
      <span class="label">Step {idx}</span>
      <span class="title">{_esc(t)}</span>
      {sub_html}
    </div>""")
                return f"""
  <div class="flow-roadmap">
    {"<div class='roadmap-arrow'>➔</div>".join(step_htmls)}
  </div>"""
    return None


def _parse_smart_list(raw: str, title: str) -> str | None:
    """Parse numbered lists or stages into clean category grids or step pipelines."""
    # Safe pattern: only matches digits not part of decimals (e.g. not 3.2 or 1.5)
    safe_pattern = r'(?:(?<!\d)[1-9]\.(?!\d)|[①-⑨]|(?<!\d)[1-9]\)|[1-9]단계[인:\s])'
    if not re.search(safe_pattern, raw):
        return None

    split_pat = r'(?:(?<=[.!?])\s+|\s+)(?=(?:(?<!\d)[1-9]\.(?!\d)|[①-⑨]|(?<!\d)[1-9]\)|[1-9]단계[인:\s]))\s*'
    chunks = [c.strip() for c in re.split(split_pat, raw) if c.strip()]
    if len(chunks) < 2:
        return None

    intro = ""
    first_chunk = chunks[0]
    m_first = re.match(r'^(?:(?<!\d)[1-9]\.(?!\d)|[①-⑨]|(?<!\d)[1-9]\)|[1-9]단계[인:\s])', first_chunk)
    if not m_first:
        intro = first_chunk
        item_chunks = chunks[1:]
    else:
        item_chunks = chunks

    items = []
    trailing_note = ""
    for idx, c in enumerate(item_chunks):
        m = re.match(r'^(?:([1-9])\.|([①-⑨])|([1-9])\)|([1-9]단계)[인:\s]*)\s*(.*)', c)
        if m:
            num = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            body = m.group(5).strip()
            # If last chunk, check for trailing concluding sentences
            if idx == len(item_chunks) - 1:
                s_parts = re.split(r'(?<=(?:이다|된다|있다)\.)\s+|(?<=[.!?])\s+', body, maxsplit=1)
                if len(s_parts) == 2:
                    body = s_parts[0]
                    trailing_note = s_parts[1]
            body = re.sub(r'(?:이다|가 있다|에 속한다|등이 있다)\.?$', '', body).strip().rstrip('.,;')
            items.append((num, body))

    if len(items) < 2:
        return None

    # Check if this is an actual sequential process / pipeline vs a classification list
    is_pipeline = any(k in title + raw for k in ["단계", "순서", "과정", "경로", "폭포", "5R", "Phase", "Stage", "Cascade"]) and \
                  not any(k in title for k in ["원인", "유형", "종류", "분류", "인자", "조건", "요인", "군", "질문"])

    intro_html = f"<p>{_clean_text(intro)}</p>" if intro and intro != raw else ""
    note_html = f'<div class="category-note">💡 {_clean_text(trailing_note)}</div>' if trailing_note else ""

    if is_pipeline:
        node_htmls = []
        for num, body in items:
            clean_num = num.replace("단계", "").strip()
            parts = re.split(r"[:—]\s*", body, maxsplit=1)
            if len(parts) == 2 and len(parts[0]) <= 25:
                badge = f"{clean_num}단계: {parts[0].strip()}"
                desc = _clean_text(parts[1].strip())
            else:
                m_phase = re.match(r"^([가-힣\w\s]{2,15}?)(?:에는|은|는|에선|에서)\s*(.*)", body)
                if m_phase and len(m_phase.group(1)) <= 15:
                    badge = f"{clean_num}단계: {m_phase.group(1).strip()}"
                    desc = _clean_text(m_phase.group(2).strip())
                else:
                    if clean_num in ["①", "1"]:
                        badge = f"1단계 ({num})"
                    else:
                        badge = f"{clean_num}단계"
                    desc = _clean_text(body)
            node_htmls.append(f"""
        <div class="step-node">
          <span class="step-badge">{_esc(badge)}</span>
          <div class="step-desc">{desc}</div>
        </div>""")
        return f"""{intro_html}
      <div class="step-pipeline">
        {"".join(node_htmls)}
      </div>
      {note_html}"""
    else:
        card_htmls = []
        for num, body in items:
            parts = re.split(r"[:—]\s*", body, maxsplit=1)
            if len(parts) == 2 and len(parts[0]) <= 25:
                name = _esc(parts[0].strip())
                detail = f'<div class="category-desc">{_clean_text(parts[1].strip())}</div>'
            else:
                name = _clean_text(body)
                detail = ""
            card_htmls.append(f"""
      <div class="category-card">
        <span class="category-badge">{_esc(num)}</span>
        <div class="category-body">
          <span class="category-name">{name}</span>
          {detail}
        </div>
      </div>""")
        return f"""{intro_html}
      <div class="category-grid">
        {"".join(card_htmls)}
      </div>
      {note_html}"""


def _infer_medical_label(s: str) -> str:
    if any(k in s for k in ["기원", "outflow", "위치", "나온다", "분포", "세포체"]):
        return "기원·위치"
    if any(k in s for k in ["섬유", "절전", "절후", "신경절", "분지", "뉴런"]):
        return "신경섬유"
    if any(k in s for k in ["기전", "경로", "수용체", "인산화", "신호", "합성", "분해", "ACh", "NE"]):
        return "작동기전"
    if any(k in s for k in ["반응", "기능", "담당", "작용", "효과", "flight", "digest"]):
        return "주요작용"
    if any(k in s for k in ["원인", "유발", "손상", "발생"]):
        return "원인"
    if any(k in s for k in ["임상", "증상", "소견", "병변", "특징", "호발"]):
        return "임상특징"
    if any(k in s for k in ["진단", "치료", "약물", "항생제", "검사", "염색"]):
        return "진단·치료"
    return "핵심요약"


def _parse_card_rows(text: str) -> list[tuple[str, str]]:
    attr_keywords = [
        "정의", "원인", "기전", "특징", "호발", "임상", "대상", "경로", "소견", 
        "치료", "진단", "작용", "배열", "독소", "수용체", "효과", "분류", "위치",
        "핵심기전", "대표예", "임상의의", "작동방식", "신경전달물질", "종결기전",
        "호발부위", "육안소견", "현미경소견", "감염경로", "중간숙주", "종숙주"
    ]
    
    rows = []
    pattern = rf'(?:^|\s+)({"|".join(attr_keywords)})[:—]\s*'
    parts = re.split(pattern, text)
    if len(parts) >= 3:
        for i in range(1, len(parts), 2):
            lbl = parts[i].strip()
            val = parts[i+1].strip() if i+1 < len(parts) else ""
            rows.append((lbl, val))
    else:
        sub_items = [s.strip() for s in re.split(r"\s*(?:•|\-|;\s+)\s*", text) if len(s.strip()) > 3]
        if len(sub_items) >= 2:
            for s in sub_items:
                s_parts = re.split(r"[:—]\s*", s, maxsplit=1)
                if len(s_parts) == 2 and len(s_parts[0]) <= 20:
                    rows.append((s_parts[0], s_parts[1]))
                else:
                    rows.append((_infer_medical_label(s), s))
        else:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            if len(sentences) >= 2:
                for s in sentences:
                    rows.append((_infer_medical_label(s), s))
            else:
                rows.append(("핵심", text))
    return rows


def _make_matrix_card(title: str, text: str, is_featured: bool = False) -> str:
    card_title = title.strip()
    sub_hint = ""
    m_hint = re.search(r"\((.*?)\)", card_title)
    if m_hint:
        sub_hint = f"<span>{_esc(m_hint.group(1))}</span>"
        card_title = card_title.replace(f"({m_hint.group(1)})", "").strip()
    elif "—" in card_title:
        t_parts = card_title.split("—", 1)
        card_title = t_parts[0].strip()
        sub_hint = f"<span>{_esc(t_parts[1].strip())}</span>"
        
    feat = is_featured or any(k in text for k in ["치명적", "위험", "1순위", "대표", "악성", "비가역", "주의", "⚠️", "핵심", "출제"])
    card_cls = "matrix-card featured" if feat else "matrix-card"
    
    rows = _parse_card_rows(text)
    row_htmls = []
    for lbl, val in rows:
        clean_val = _clean_text(val)
        if lbl and lbl != "핵심":
            row_htmls.append(f'<div class="matrix-row"><span class="matrix-lbl">{_esc(lbl)}</span><span class="matrix-val">{clean_val}</span></div>')
        else:
            row_htmls.append(f'<div class="matrix-row"><span class="matrix-val">• {clean_val}</span></div>')
            
    return f"""
    <div class="{card_cls}">
      <div class="matrix-card-title">{_esc(card_title)} {sub_hint}</div>
      {"".join(row_htmls)}
    </div>"""


def _extract_concept_title(text: str, section_title: str, idx: int) -> tuple[str, str]:
    raw_text = text.strip()
    
    # 0. Strip leading introductory phrases (e.g. 임상적으로, 일반적으로, 실제 임상에서)
    clean = re.sub(
        r"^(?:임상적으로 중요한 분류에서|일반적으로|임상적으로|실제 임상에서|연구에서|분류상|생체 내에서|체내에서|역학적으로|통계학적으로|예를 들어|정상 상태에서|대부분의|모든)\s*",
        "",
        raw_text,
    )
    
    # 1. Colon or dash separator
    parts = re.split(r"[:—]\s*", clean, maxsplit=1)
    if len(parts) == 2 and 2 <= len(parts[0].strip()) <= 35 and not any(k in parts[0] for k in ["http", "www", "e.g."]):
        t = parts[0].strip()
        t = re.sub(r"\s*(?:즉|와|과|및|또는)$", "", t).strip()
        if len(t) >= 2:
            return t, parts[1].strip()

    # 2. Known arrow progression / mechanism signatures at start
    if clean.startswith("Growth factor →") or "Growth factor → RTK" in clean:
        return "Growth Factor와 RTK 신호전달 경로 (RAS / PI3K)", raw_text
    if clean.startswith("간 손상 →") or "간 손상 → Kupffer" in clean:
        return "간 손상과 간섬유화 기전 (Kupffer & Stellate Cell)", raw_text
    if clean.startswith("DNA 손상 →") or "DNA 손상 → TP53" in clean:
        return "DNA 손상과 TP53 매개 세포주기 조절 (Checkpoints)", raw_text
    if clean.startswith("운명 흐름은") or "normal cell → stress" in clean:
        return "세포 손상과 운명의 분기 경로 (Roadmap)", raw_text
    if "Ischemia·toxin으로 MPTP" in clean:
        return "미토콘드리아 투과성 전이 기공 (MPTP)과 손상 기전", raw_text
    if clean.startswith("Apoptosis에서는") or clean.startswith("Apoptosis에서"):
        return "Apoptosis의 분자 기전 (BAX/BAK 및 Cytochrome c)", raw_text
    if clean.startswith("Cyclin D–CDK4/6은") or clean.startswith("Cyclin D-CDK4/6은"):
        return "세포주기 단계별 Cyclin-CDK 복합체", raw_text
    if clean.startswith("발생 계층은"):
        return "줄기세포의 발생 계층과 분화능 (Potency)", raw_text
    if "부하용량(loading dose)=" in clean or "loading dose" in clean:
        return "부하용량 (Loading Dose) 계산 공식 및 임상 적용", raw_text
    if "유지용량(maintenance dose)=" in clean:
        return "유지용량 (Maintenance Dose) 계산 공식 및 청소율", raw_text
    if "X-linked 질환으로 주로 여아에서 나타나며" in clean:
        return "Rett 증후군 (MECP2 변이 X-연관 우성 유전)", raw_text
    if "Enterotoxin, TSST-1, exfoliative toxin" in clean:
        return "포도알균 외독소군 (Enterotoxin, TSST-1, Exfoliative Toxin)", raw_text
    if "Facultative intracellular pathogen이다" in clean or "InlA가" in clean:
        return "Listeria의 세포내 침투 및 증식 기전 (InlA & LLO)", raw_text
    if "Pulmonary embolism의 약 90%" in clean:
        return "폐색전증 (Pulmonary Embolism)의 기원과 혈전 이동 경로", raw_text
    if "탈락 바이어스" in clean:
        return "탈락 바이어스 (Attrition / Follow-up Loss Bias)", raw_text
    if "Dracunculus medinensis" in clean or "메디나충" in clean:
        return "메디나충 (Dracunculus medinensis) 감염 경로와 생활사", raw_text
    if "iris radial/dilator muscle" in clean:
        return "안구 자율신경 조절 (동공 산대근 및 괄약근)", raw_text
    if clean.startswith("눈에서"):
        return "안구 조직의 자율신경 수용체 분포 및 효과", raw_text
    if clean.startswith("C5b–C9") or "membrane attack complex" in clean:
        return "보체계 막공격복합체 (C5b–C9 MAC)와 세포용해", raw_text
    if clean.startswith("초회통과효과"):
        return "초회통과효과 (First-Pass Effect)와 생체이용률", raw_text
    if "세포손상 원인은" in clean or clean.startswith("세포손상 원인"):
        return "세포손상의 7대 원인 (Causes of Cell Injury)", raw_text
    if "화농성 감염 6군" in clean:
        return "포도알균 화농성 감염의 6대 임상 양상", raw_text
    if "Noncoding DNA에" in clean or "Noncoding DNA는" in clean:
        return "Noncoding DNA의 5대 주요 기능 영역", raw_text
    if "Virchow" in clean or "혈전증의 3대" in clean or "혈전증은 ①" in clean or clean.startswith("혈전증"):
        return "혈전 형성의 3대 인자 (Virchow's Triad)", raw_text
    if "경색의 발생과 크기" in clean:
        return "경색의 발생과 크기를 결정하는 4대 요인", raw_text
    if "교란변수는" in clean or "교란변수의 3대 조건" in clean or clean.startswith("교란변수"):
        return "교란변수 (Confounder) 성립의 3대 필수 조건", raw_text
    if "다섯 질문으로 정리한다" in clean:
        return "유전질환 분석을 위한 5대 임상 질문", raw_text
    if "쇼크 1단계인" in clean:
        return "쇼크의 3단계 진행 과정 (초기 ➔ 진행 ➔ 비가역)", raw_text
    if "핵심은 ‘유입 경로" in clean or clean.startswith("핵심은"):
        return "세포내 소기관 분해 경로의 분업 구조", raw_text
    if "Signal sequence가 없는 단백질은" in clean or clean.startswith("Signal sequence"):
        return "Signal Sequence와 단백질 합성 경로 (Free Ribosome vs RER)", raw_text
    if "혈관내피세포가 만든 NO" in clean or clean.startswith("혈관내피세포가"):
        return "혈관내피세포의 NO 합성 및 Paracrine 신호전달", raw_text
    if "Collagen·elastin은 tensile" in clean:
        return "Collagen과 Elastin의 인장강도 및 기계적 특성", raw_text
    if clean.startswith("신호전달 방식"):
        return "세포간 신호전달의 주요 방식 (Paracrine / Autocrine / Endocrine)", raw_text
    if clean.startswith("주요 receptor"):
        return "세포 수용체의 5대 주요 유형", raw_text

    # 3. Subject particle match (e.g. 'X는', 'X은', 'X(Y)는', 'X이란', 'X에서')
    particle_pat = r"^([\w\s\-\.\(\)/·\',]{2,35}?)(?<!또)(?:은|는|이|가|이란|란|에서는|에선|에서|의경우|[:—])\s+(.*)"
    m = re.match(particle_pat, clean)
    if m:
        subj = m.group(1).strip()
        body = m.group(2).strip()
        invalid_words = {'따라서', '그리고', '하지만', '또한', '예를', '이러한', '결과적으로', '우리가', '내가', '이', '그', '저', '핵심은'}
        last_word = subj.split()[-1] if subj.split() else ''
        if last_word not in invalid_words:
            subj = re.sub(r"\s*(?:즉|와|과|및|또는)$", "", subj).strip()
            if subj == "Turner":
                subj = "Turner 증후군"
            elif subj == "Klinefelter":
                subj = "Klinefelter 증후군"
            elif subj == "HIT":
                subj = "Heparin-Induced Thrombocytopenia (HIT)"
            elif subj == "Sepsis":
                subj = "패혈증 (Sepsis) 병태생리"
            elif subj == "CFTR Phe508 변이":
                subj = "CFTR Phe508 변이와 단백질 수송 이상"
            elif subj == "CAMP test":
                subj = "CAMP Test (B군 연쇄알균 감별)"
            elif subj == "C5b–C9 membrane attack complex(MAC)":
                subj = "막공격복합체 (C5b–C9 MAC)"
            elif subj.startswith("초회통과효과"):
                subj = "초회통과효과 (First-Pass Effect)"
                
            if len(subj) >= 2:
                return subj, body

    # 4. Quoted term
    m_quote = re.search(r"[‘\']([^’\']{2,25})[’\']", clean)
    if m_quote:
        q = m_quote.group(1).strip()
        if len(q) >= 2:
            return q, raw_text

    # 5. First sentence if short
    sentences = re.split(r"(?<=[.!?])\s+", clean, maxsplit=1)
    if len(sentences) == 2 and 4 <= len(sentences[0]) <= 32 and not any(k in sentences[0] for k in ["S.", "E.", "B.", "C.", "i.e.", "e.g."]):
        t = re.sub(r"\s*(?:즉|와|과|및|또는)$", "", sentences[0].rstrip(".!?").strip())
        if len(t) >= 2:
            return t, sentences[1].strip()
        
    # 6. First 3-5 words
    words = clean.split()
    lead = " ".join(words[:4]).rstrip(",.:;!?")
    lead = re.sub(r"\s*(?:즉|와|과|및|또는)$", "", lead).strip()
    if len(lead) >= 3:
        return lead, raw_text

    clean_sec = re.sub(r"^\d+\.\s*", "", section_title).strip()
    return f"{clean_sec} 핵심 개요", raw_text


def _transform_section_core_points(points: list[str], section_title: str) -> str:
    """Intelligently transform a section's core_points into rich visual blocks matching 병리학 1주차(A)."""
    if not points:
        return ""
        
    blocks = []
    
    # 1. Flow roadmap detection at section top
    roadmap_html = _parse_chain_into_roadmap(points[0])
    start_idx = 0
    if roadmap_html:
        blocks.append(roadmap_html)
        start_idx = 1
        
    remaining = points[start_idx:]
    i = 0
    while i < len(remaining):
        raw = remaining[i]
        
        # Adaptation 4-entity grouping check
        if "Adaptation은" in raw and i + 4 < len(remaining) and all(
            any(k in remaining[i + offset] for k in ["Hypertrophy", "Hyperplasia", "Atrophy", "Metaplasia"])
            for offset in range(1, 5)
        ):
            intro_text = _clean_text(raw)
            matrix_cards = []
            for offset in range(1, 5):
                sub_raw = remaining[i + offset]
                sub_title, sub_body = _extract_concept_title(sub_raw, section_title, i + offset + start_idx + 1)
                matrix_cards.append(_make_matrix_card(sub_title, sub_body))
                
            blocks.append(f"""
<div class="concept-block">
  <div class="concept-header">
    <h4><span class="tag def">핵심 개념</span> 세포 적응 (Adaptation) 4대 유형 비교</h4>
    <span class="tag exam">족보 빈출</span>
  </div>
  <div class="concept-body">
    <p>{intro_text}</p>
    <div class="matrix-grid">
      {"".join(matrix_cards)}
    </div>
  </div>
</div>""")
            i += 5
            continue

        is_mech = any(k in raw for k in ["기전", "경로", "인산화", "활성화", "수용체", "신호", "합성", "분해", "억제", "효소", "대사", "수송", "ACh", "NE"])
        is_patho = any(k in raw for k in ["병변", "괴사", "손상", "독소", "감염", "염증", "소견", "형태", "출혈", "괴저", "변성", "균", "현미경"])
        is_clin = any(k in raw for k in ["임상", "진단", "치료", "약물", "항생제", "호발", "원인", "증상", "부작용", "감수성", "배양", "예방"])
        
        if is_mech:
            tag = '<span class="tag mech">작동 기전</span>'
        elif is_patho:
            tag = '<span class="tag patho">병리·형태</span>'
        elif is_clin:
            tag = '<span class="tag clin">임상·감별</span>'
        else:
            tag = '<span class="tag def">핵심 개념</span>'

        exam_tag = '<span class="tag exam">족보 빈출</span>' if any(k in raw for k in ["족보", "기출", "단골", "거듭 강조", "1순위", "필수"]) else ""
        if any(k in raw for k in ["치명적", "위험", "악성", "오답", "함정"]):
            exam_tag = '<span class="tag danger">필수 주의</span>'
            
        title, body = _extract_concept_title(raw, section_title, i + start_idx + 1)
        smart_list_html = _parse_smart_list(raw, title)
        
        if smart_list_html:
            blocks.append(f"""
<div class="concept-block">
  <div class="concept-header">
    <h4>{tag} {_esc(title)}</h4>
    {exam_tag}
  </div>
  <div class="concept-body">
    {smart_list_html}
  </div>
</div>""")
        elif any(m in body for m in [" 1) ", " 2) ", " ① ", " ② ", " 1. ", " 2. ", " • "]):
            raw_subs = re.split(r"\s*(?:•|\-|[1-9]\)|[①-⑨]|\b[1-9]\.)\s*", body)
            sub_items = [s.strip() for s in raw_subs if len(s.strip()) > 3]
            matrix_cards = []
            for s_idx, sub in enumerate(sub_items, 1):
                s_parts = re.split(r"[:—]\s*", sub, maxsplit=1)
                s_title = s_parts[0] if len(s_parts) == 2 and len(s_parts[0]) <= 25 else f"항목 {s_idx}"
                s_val = s_parts[1] if len(s_parts) == 2 and len(s_parts[0]) <= 25 else sub
                matrix_cards.append(_make_matrix_card(s_title, s_val))
            blocks.append(f"""
<div class="concept-block">
  <div class="concept-header">
    <h4>{tag} {_esc(title)}</h4>
    {exam_tag}
  </div>
  <div class="concept-body">
    <div class="matrix-grid">
      {"".join(matrix_cards)}
    </div>
  </div>
</div>""")
        else:
            clean_p = _clean_text(body)
            blocks.append(f"""
<div class="concept-block">
  <div class="concept-header">
    <h4>{tag} {_esc(title)}</h4>
    {exam_tag}
  </div>
  <div class="concept-body">
    <p>{clean_p}</p>
  </div>
</div>""")
        i += 1

    return "".join(blocks)


def _format_exam_items(items: list[str]) -> str:
    cards = []
    for raw in items:
        is_trap = any(k in raw for k in ["틀리다", "오답", "넣지 않는다", "아니다", "함정", "결핍이 아니라", "동일시하지 않는다", "혼동"])
        is_formula = any(k in raw for k in ["판별식", "매칭", "구별", "대응", "공식", "열거", "대표 장기", "1순위", "감별", "수식"])
        is_essay = any(k in raw for k in ["서술", "순서", "화살표", "연결", "사슬", "설명할 수", "과정을", "비교"])
        
        if is_trap:
            badge = '<span class="exam-pill trap">🚨 함정 주의</span>'
            row_cls = "exam-row trap"
        elif is_formula:
            badge = '<span class="exam-pill formula">🎯 출제 공식</span>'
            row_cls = "exam-row formula"
        elif is_essay:
            badge = '<span class="exam-pill essay">📝 서술형 대비</span>'
            row_cls = "exam-row essay"
        else:
            badge = '<span class="exam-pill point">⚡ 빈출 포인트</span>'
            row_cls = "exam-row"

        text = _clean_text(raw)
        cards.append(f'<div class="{row_cls}">{badge}<div class="exam-txt">{text}</div></div>')
    return "".join(cards)


def _format_transcript_items(items: list[str]) -> str:
    cards = []
    for raw in items:
        badge = '<span class="trans-pill">💡 교수님 강의 강조</span>'
        text = _clean_text(raw)
        for key in ["거듭 강조", "화살표 사슬", "양날의 검", "자가소화", "단백질 품질관리", "맹독성", "수치 암기", "시험 단골", "감별 필수", "꼭 기억"]:
            if key in text:
                text = text.replace(key, f"<strong class='trans-hl'>{key}</strong>")
        cards.append(f'<div class="trans-row">{badge}<div class="trans-txt">{text}</div></div>')
    return "".join(cards)


def _format_quiz_items(quizzes: list) -> str:
    cards = []
    for q in quizzes:
        if isinstance(q, dict):
            q_text = q.get("question", "")
            q_ans = q.get("answer", "")
            q_idx = q.get("question_number", 1)
        else:
            q_text = getattr(q, "question", "")
            q_ans = getattr(q, "answer", "")
            q_idx = getattr(q, "question_number", 1)
        cards.append(f"""
<details class="quiz-item">
  <summary>
    <span class="quiz-q-num">Q{q_idx}</span>
    <span class="quiz-q-text">{_esc(q_text)}</span>
    <span class="quiz-toggle-hint">정답 확인</span>
  </summary>
  <div class="quiz-answer-panel">
    <div class="ans-label">🎯 정답 및 핵심 근거</div>
    <p>{_clean_text(q_ans)}</p>
  </div>
</details>
""")
    return "".join(cards)


def _build_tables_html(tables: list) -> str:
    if not tables:
        return ""
    html_cards = []
    for tbl in tables:
        if isinstance(tbl, dict):
            title = tbl.get("title", "비교 정리표")
            headers = tbl.get("headers", tbl.get("columns", []))
            rows = tbl.get("rows", [])
        else:
            title = getattr(tbl, "title", "비교 정리표")
            headers = getattr(tbl, "columns", [])
            rows = getattr(tbl, "rows", [])
        
        thead = "".join(f"<th>{_esc(h)}</th>" for h in headers)
        tbody_rows = []
        for r in rows:
            cells = []
            for c_idx, cell in enumerate(r):
                c_text = _clean_text(str(cell))
                
                if any(w in c_text for w in ["Rupture", "파열", "급성 염증", "Swelling", "Liquefactive", "액화", "고칼슘혈증", "위험", "치명적"]):
                    c_text = f"<span class='table-tag danger'>{c_text}</span>"
                elif any(w in c_text for w in ["Intact", "보존", "무염증", "Shrinkage", "정상", "자연 치유", "음성"]):
                    c_text = f"<span class='table-tag success'>{c_text}</span>"
                elif any(w in c_text for w in ["양성", "Coagulative", "응고", "Caseous", "치즈", "Fat", "지방"]):
                    c_text = f"<span class='table-tag amber'>{c_text}</span>"
                elif any(w in c_text for w in ["Fibrinoid", "섬유소양", "Gangrenous", "괴저", "만성"]):
                    c_text = f"<span class='table-tag purple'>{c_text}</span>"
                
                if c_idx == 0:
                    cells.append(f"<td>{c_text}</td>")
                else:
                    cells.append(f"<td>{c_text}</td>")
            tbody_rows.append(f"<tr>{''.join(cells)}</tr>")

        html_cards.append(f"""
<div class="table-card searchable">
  <div class="table-card-title"><span>📊</span> {_esc(title)}</div>
  <div class="table-wrap">
    <table>
      <thead><tr>{thead}</tr></thead>
      <tbody>{"".join(tbody_rows)}</tbody>
    </table>
  </div>
</div>
""")
    return "".join(html_cards)


def _build_rapid_review_html(items: list[str]) -> str:
    if not items:
        return ""
    cards = []
    for item in items:
        parts = re.split(r"[:—]\s*", item, maxsplit=1)
        if len(parts) == 2 and len(parts[0]) <= 25:
            topic = parts[0].strip()
            content = parts[1].strip()
        else:
            topic = "핵심 요약"
            content = item.strip()

        content_html = _clean_text(content)
        cards.append(f"""
<div class="rapid-card">
  <div class="rapid-topic">{_esc(topic)}</div>
  <div class="rapid-body">{content_html}</div>
</div>
""")
    return "".join(cards)


def _build_likely_confusions_html(items: list[str]) -> str:
    if not items:
        return ""
    cards = []
    for raw in items:
        m = re.match(r"\[(.*?)\]\s*(.*)", raw)
        if m:
            topic = m.group(1).strip()
            rest = m.group(2).strip()
        else:
            parts = re.split(r"[:—]\s*", raw, maxsplit=1)
            if len(parts) == 2 and len(parts[0]) <= 25:
                topic = parts[0].strip()
                rest = parts[1].strip()
            else:
                topic = "주의점"
                rest = raw.strip()

        subbed = re.sub(r"\b([A-Z]\.)\s*([a-z]+)", r"\1__ABBR__\2", rest)
        s_parts = re.split(r"(?<=[.!?])\s+", subbed, maxsplit=1)
        if len(s_parts) == 2:
            wrong_part = s_parts[0].replace("__ABBR__", " ")
            correct_part = s_parts[1].replace("__ABBR__", " ")
        else:
            wrong_part = "흔한 오해/함정"
            correct_part = rest.replace("__ABBR__", " ")

        cards.append(f"""
<div class="confuse-card">
  <div class="confuse-header">
    <span class="confuse-topic">{_esc(topic)}</span>
  </div>
  <div class="confuse-row">
    <span class="confuse-sub-badge wrong">❌ 흔한 함정</span>
    <div class="confuse-desc wrong">{_clean_text(wrong_part)}</div>
  </div>
  <div class="confuse-row">
    <span class="confuse-sub-badge correct">⭕ 정확한 팩트</span>
    <div class="confuse-desc correct">{_clean_text(correct_part)}</div>
  </div>
</div>
""")
    return "".join(cards)


V2_CSS = """
:root{
  --bg:#f4f6f8;--surface:#ffffff;--surface-sub:#f8fafc;--border:#e2e8f0;--border-strong:#cbd5e1;
  --text-main:#0f172a;--text-muted:#64748b;--text-sub:#334155;
  --primary:#0f766e;--primary-light:#ccfbf1;--primary-dark:#115e59;
  --amber:#d97706;--amber-light:#fef3c7;--amber-dark:#92400e;
  --blue:#2563eb;--blue-light:#dbeafe;--blue-dark:#1e40af;
  --rose:#e11d48;--rose-light:#ffe4e6;--rose-dark:#9f1239;
  --purple:#7c3aed;--purple-light:#ede9fe;
  --shadow-sm:0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04);
  --shadow-md:0 4px 6px -1px rgba(0,0,0,0.08),0 2px 4px -2px rgba(0,0,0,0.05);
  --shadow-lg:0 10px 15px -3px rgba(0,0,0,0.08),0 4px 6px -4px rgba(0,0,0,0.04);
  --radius-sm:8px;--radius-md:12px;--radius-lg:16px;--radius-xl:20px;
  --scale:1;
}
body.dark{
  --bg:#0b0f17;--surface:#131b2e;--surface-sub:#1a243b;--border:#263554;--border-strong:#3b4f7a;
  --text-main:#f1f5f9;--text-muted:#94a3b8;--text-sub:#cbd5e1;
  --primary:#2dd4bf;--primary-light:#042f2e;--primary-dark:#5eead4;
  --amber:#fbbf24;--amber-light:#451a03;--amber-dark:#fde68a;
  --blue:#60a5fa;--blue-light:#1e293b;--blue-dark:#93c5fd;
  --rose:#fb7185;--rose-light:#4c0519;--rose-dark:#fecdd3;
  --purple:#a78bfa;--purple-light:#2e1065;
  --shadow-sm:none;--shadow-md:none;--shadow-lg:none;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--bg);color:var(--text-main);
  font-family:"Pretendard",-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  font-size:calc(15.5px * var(--scale));line-height:1.65;letter-spacing:-0.01em;
}
.topbar{
  position:sticky;top:0;z-index:100;display:flex;align-items:center;gap:.65rem;
  padding:.55rem 1.25rem;width:100%;background:color-mix(in srgb, var(--surface) 92%, transparent);
  border-bottom:1px solid var(--border);backdrop-filter:blur(14px);
}
.btn-toc{
  font-size:.88rem;display:inline-flex;align-items:center;gap:.4rem;padding:.45rem .8rem;
  border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);
  color:var(--text-main);font-weight:700;cursor:pointer;transition:all .15s;
}
.btn-toc:hover{background:var(--surface-sub);border-color:var(--primary)}
body.toc-collapsed #toggle-toc{background:var(--primary-light);color:var(--primary-dark);border-color:var(--primary)}
.brand-badge{display:inline-flex;align-items:center;gap:.4rem;font-weight:900;font-size:.92rem;color:var(--primary);margin-right:auto}
.brand-tag{font-size:.7rem;font-weight:800;padding:.15rem .45rem;border-radius:999px;background:var(--primary-light);color:var(--primary-dark)}
.search{width:min(32vw,280px);padding:.45rem .75rem;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-sub);color:var(--text-main);font-size:.88rem}
.search:focus{outline:2px solid var(--primary);background:var(--surface)}
button.action-btn{padding:.42rem .65rem;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);color:var(--text-main);font-weight:700;font-size:.85rem;cursor:pointer}
button.action-btn:hover{background:var(--surface-sub)}

.layout{
  display:grid;grid-template-columns:250px minmax(0,1fr);gap:1.5rem;
  width:100%;max-width:100%;padding:.9rem 1.25rem 3rem;transition:grid-template-columns .2s ease;
}
body.toc-collapsed .side{display:none!important}
body.toc-collapsed .layout{grid-template-columns:minmax(0,1fr)!important}

.side{
  position:sticky;top:65px;align-self:start;display:flex;flex-direction:column;gap:.3rem;
  max-height:calc(100vh - 80px);overflow-y:auto;padding-right:.35rem;
}
.side a{
  display:grid;grid-template-columns:28px 1fr;align-items:center;gap:.6rem;
  padding:.55rem .7rem;color:var(--text-sub);text-decoration:none;border-radius:var(--radius-sm);
  font-size:.86rem;line-height:1.35;font-weight:600;transition:all .15s;
}
.side a:hover{background:var(--surface-sub);color:var(--primary)}
.nav-num{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:var(--border);color:var(--text-sub);font-size:.72rem;font-weight:800}
.side a:hover .nav-num{background:var(--primary);color:#ffffff}
.content{min-width:0;width:100%}

.hero{
  background:linear-gradient(135deg, #0f766e 0%, #1e3a8a 100%);color:#ffffff;
  border-radius:var(--radius-xl);padding:2.2rem 2.4rem;box-shadow:var(--shadow-md);margin-bottom:1.5rem;
}
.hero-eyebrow{display:flex;align-items:center;gap:.5rem;font-size:.85rem;font-weight:750;letter-spacing:.05em;opacity:.9;text-transform:uppercase}
.hero h1{margin:.5rem 0 .4rem;font-size:clamp(1.75rem,3.5vw,2.7rem);font-weight:900;line-height:1.2;letter-spacing:-0.02em}
.hero p{margin:0 0 1rem;font-size:1.02rem;opacity:.92;max-width:none}
.hero-meta{display:flex;flex-wrap:wrap;gap:.5rem}
.hero-pill{display:inline-flex;align-items:center;gap:.35rem;padding:.3rem .75rem;border-radius:999px;background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);font-size:.82rem;font-weight:700}

.overview-card{background:var(--surface);border:1px solid var(--border);border-left:5px solid var(--primary);border-radius:var(--radius-lg);padding:1.4rem 1.6rem;box-shadow:var(--shadow-sm);margin-bottom:1.5rem}
.overview-card h2{margin:0 0 .8rem;font-size:1.18rem;font-weight:850;color:var(--primary);display:flex;align-items:center;gap:.5rem}
.overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem}
.overview-item{background:var(--surface-sub);border:1px solid var(--border);border-radius:var(--radius-md);padding:1rem 1.15rem}
.overview-item strong{display:block;color:var(--primary-dark);font-size:.94rem;margin-bottom:.35rem}
.overview-item p{margin:0;font-size:.9rem;color:var(--text-sub);line-height:1.55}

/* BIG FLOW ROADMAP */
.flow-roadmap{
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;
  margin:1.2rem 0;padding:1rem 1.25rem;background:var(--surface-sub);border:1px solid var(--border);border-radius:var(--radius-md);
}
.roadmap-step{
  flex:1 1 120px;text-align:center;padding:.7rem .6rem;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--radius-sm);box-shadow:var(--shadow-sm);
}
.roadmap-step.norm{border-top:3px solid #10b981}
.roadmap-step.adapt{border-top:3px solid var(--primary)}
.roadmap-step.rev{border-top:3px solid #eab308}
.roadmap-step.irrev{border-top:3px solid #f97316}
.roadmap-step.death{border-top:3px solid var(--rose)}
.roadmap-step .label{font-size:.74rem;color:var(--text-muted);font-weight:750;display:block}
.roadmap-step .title{font-size:.95rem;font-weight:850;color:var(--text-main)}
.roadmap-arrow{font-size:1.1rem;color:var(--text-muted);font-weight:900}

/* SECTION CARDS */
.section-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.6rem 1.8rem;box-shadow:var(--shadow-sm);margin-bottom:1.8rem;scroll-margin-top:72px}
.sec-header{display:flex;align-items:center;gap:.85rem;padding-bottom:1rem;border-bottom:1px solid var(--border);margin-bottom:1.4rem}
.sec-badge{display:grid;place-items:center;width:38px;height:38px;border-radius:var(--radius-md);background:var(--primary);color:#ffffff;font-size:.95rem;font-weight:900;box-shadow:var(--shadow-sm)}
.sec-titles{flex:1;min-width:0}
.sec-titles h2{margin:0;font-size:1.35rem;font-weight:850;color:var(--text-main);letter-spacing:-0.015em}

/* STEP BY STEP MECHANISM PIPELINE */
.step-pipeline{display:flex;flex-direction:column;gap:.65rem;margin:.9rem 0}
.step-node{
  display:grid;grid-template-columns:auto 1fr;gap:.85rem;align-items:start;
  padding:.75rem 1rem;background:var(--surface-sub);border:1px solid var(--border);
  border-left:4px solid var(--primary);border-radius:var(--radius-sm);
}
.step-badge{font-size:.76rem;font-weight:900;padding:.2rem .5rem;border-radius:6px;background:var(--primary);color:#ffffff;white-space:nowrap}
.step-desc{font-size:.9rem;color:var(--text-sub);line-height:1.55}
.step-desc strong{color:var(--text-main)}

/* CATEGORY GRID (NUMBERED CAUSES, FACTORS & CLASSIFICATIONS) */
.category-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.65rem;margin:.85rem 0}
.category-card{
  background:var(--surface-sub);border:1px solid var(--border);border-left:3.5px solid var(--primary);
  border-radius:var(--radius-sm);padding:.6rem .85rem;display:flex;align-items:flex-start;gap:.6rem;
  transition:border-color .15s ease,box-shadow .15s ease;
}
.category-card:hover{border-color:var(--primary);box-shadow:var(--shadow-sm);background:var(--surface)}
.category-badge{font-size:.82rem;font-weight:900;color:var(--primary);flex-shrink:0;margin-top:1px}
.category-body{flex:1;min-width:0}
.category-name{font-size:.88rem;font-weight:750;color:var(--text-main);display:block;line-height:1.4}
.category-desc{font-size:.8rem;color:var(--text-sub);margin-top:2px;line-height:1.4}
.category-note{
  background:color-mix(in srgb,var(--primary-light) 25%,var(--surface));border:1px solid color-mix(in srgb,var(--primary) 35%,var(--border));
  border-left:4px solid var(--primary);border-radius:var(--radius-sm);padding:.65rem .95rem;font-size:.88rem;
  color:var(--text-main);margin-top:.85rem;line-height:1.55;display:flex;align-items:center;gap:.45rem;
}

/* MULTI COLUMN CARDS & MATRIX GRID */
.matrix-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin:.9rem 0}
.matrix-card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);
  padding:1.1rem 1.25rem;box-shadow:var(--shadow-sm);display:flex;flex-direction:column;gap:.6rem;
}
.matrix-card.featured{
  border-color:color-mix(in srgb,var(--primary) 45%,var(--border));
  background:color-mix(in srgb,var(--primary-light) 15%,var(--surface));
}
.matrix-card-title{
  font-size:1.05rem;font-weight:850;color:var(--primary);display:flex;align-items:center;
  justify-content:space-between;border-bottom:1px dashed var(--border);padding-bottom:.4rem;
}
.matrix-card-title span{font-size:.78rem;font-weight:700;color:var(--text-muted)}
.matrix-row{display:grid;grid-template-columns:75px 1fr;gap:.6rem;font-size:.88rem;line-height:1.5}
.matrix-lbl{font-weight:750;color:var(--text-muted)}
.matrix-val{color:var(--text-main)}
.matrix-val strong{color:var(--primary-dark)}

/* CONCEPT BLOCKS */
.concept-block{margin-bottom:1.25rem;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--surface);overflow:hidden}
.concept-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;padding:.75rem 1.15rem;background:var(--surface-sub);border-bottom:1px solid var(--border)}
.concept-header h4{margin:0;font-size:1rem;font-weight:800;color:var(--text-main);display:flex;align-items:center;gap:.55rem}
.concept-body{padding:1.1rem 1.25rem;font-size:.93rem;color:var(--text-sub);line-height:1.65}
.concept-body p{margin:0 0 .65rem}
.concept-body p:last-child{margin:0}

/* BADGES & TAGS */
.tag{display:inline-flex;align-items:center;gap:.25rem;font-size:.74rem;font-weight:800;padding:.18rem .5rem;border-radius:6px;text-transform:uppercase;letter-spacing:.02em}
.tag.def{background:var(--primary-light);color:var(--primary-dark);border:1px solid color-mix(in srgb,var(--primary) 30%,transparent)}
.tag.mech{background:var(--blue-light);color:var(--blue-dark);border:1px solid color-mix(in srgb,var(--blue) 30%,transparent)}
.tag.patho{background:var(--purple-light);color:var(--purple);border:1px solid color-mix(in srgb,var(--purple) 30%,transparent)}
.tag.clin{background:var(--amber-light);color:var(--amber-dark);border:1px solid color-mix(in srgb,var(--amber) 30%,transparent)}
.tag.exam{background:var(--amber-light);color:var(--amber-dark);border:1px solid color-mix(in srgb,var(--amber) 30%,transparent)}
.tag.danger{background:var(--rose-light);color:var(--rose-dark);border:1px solid color-mix(in srgb,var(--rose) 30%,transparent)}

/* CALLOUTS */
.callout{margin:1.4rem 0;border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow-sm)}
.callout.exam{border:1.5px solid color-mix(in srgb,var(--amber) 50%,var(--border));background:color-mix(in srgb,var(--amber-light) 25%,var(--surface))}
.callout.transcript{border:1.5px solid color-mix(in srgb,var(--blue) 50%,var(--border));background:color-mix(in srgb,var(--blue-light) 25%,var(--surface))}
.callout-head{display:flex;align-items:center;gap:.6rem;padding:.75rem 1.25rem;font-size:.96rem;font-weight:900;letter-spacing:-0.01em}
.callout.exam .callout-head{background:color-mix(in srgb,var(--amber) 16%,var(--surface));color:var(--amber-dark);border-bottom:1px solid color-mix(in srgb,var(--amber) 30%,var(--border))}
.callout.transcript .callout-head{background:color-mix(in srgb,var(--blue) 16%,var(--surface));color:var(--blue-dark);border-bottom:1px solid color-mix(in srgb,var(--blue) 30%,var(--border))}
.callout-list{padding:.85rem 1rem;display:flex;flex-direction:column;gap:.65rem}

.exam-row{
  display:grid;grid-template-columns:auto 1fr;gap:.8rem;align-items:start;padding:.8rem 1rem;
  background:var(--surface);border:1px solid color-mix(in srgb,var(--amber) 25%,var(--border));
  border-left:4px solid var(--amber);border-radius:var(--radius-sm);font-size:.92rem;line-height:1.6;box-shadow:0 1px 3px rgba(0,0,0,0.03);
}
.exam-row.trap{border-left:4px solid var(--rose);background:color-mix(in srgb,var(--rose-light) 22%,var(--surface));border-color:color-mix(in srgb,var(--rose) 40%,var(--border))}
.exam-row.formula{border-left:4px solid #d97706;background:color-mix(in srgb,var(--amber-light) 20%,var(--surface))}
.exam-row.essay{border-left:4px solid var(--purple);background:color-mix(in srgb,var(--purple-light) 20%,var(--surface))}
.exam-pill{font-size:.73rem;font-weight:900;padding:.22rem .55rem;border-radius:6px;white-space:nowrap;display:inline-flex;align-items:center;gap:.25rem}
.exam-pill.trap{background:var(--rose-light);color:var(--rose-dark);border:1px solid color-mix(in srgb,var(--rose) 40%,transparent)}
.exam-pill.formula{background:var(--amber-light);color:var(--amber-dark);border:1px solid color-mix(in srgb,var(--amber) 40%,transparent)}
.exam-pill.essay{background:var(--purple-light);color:var(--purple);border:1px solid color-mix(in srgb,var(--purple) 40%,transparent)}
.exam-pill.point{background:var(--primary-light);color:var(--primary-dark);border:1px solid color-mix(in srgb,var(--primary) 40%,transparent)}
.exam-txt{color:var(--text-main)}

.trans-row{display:grid;grid-template-columns:auto 1fr;gap:.8rem;align-items:start;padding:.8rem 1rem;background:var(--surface);border:1px solid color-mix(in srgb,var(--blue) 25%,var(--border));border-left:4px solid var(--blue);border-radius:var(--radius-sm);font-size:.92rem;line-height:1.6;box-shadow:0 1px 3px rgba(0,0,0,0.03)}
.trans-pill{font-size:.73rem;font-weight:900;padding:.22rem .55rem;border-radius:6px;white-space:nowrap;background:var(--blue-light);color:var(--blue-dark);border:1px solid color-mix(in srgb,var(--blue) 40%,transparent)}
.trans-txt{color:var(--text-main)}
.trans-hl{color:var(--blue-dark);font-weight:900;text-decoration:underline}

/* KEYWORD STYLING (NO BACKGROUND HIGHLIGHT) */
mark.kw-mark, .kw-mark{background:transparent;color:var(--primary-dark);font-weight:800;padding:0;border-radius:0}
body.dark mark.kw-mark, body.dark .kw-mark{color:var(--primary);background:transparent}
.term-hl{color:var(--primary-dark);font-weight:900}
.arr-hl{color:var(--primary);font-weight:900;margin:0 .2rem}

/* ACTIVE RECALL QUIZ */
.quiz-section{margin-top:1.4rem;padding-top:1.1rem;border-top:1px dashed var(--border)}
.quiz-section-title{font-size:.98rem;font-weight:850;color:var(--text-main);margin-bottom:.8rem;display:flex;align-items:center;gap:.4rem}
details.quiz-card, details.quiz-item{
  margin-bottom:.75rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);
  box-shadow:var(--shadow-sm);overflow:hidden;transition:border-color .15s ease,box-shadow .15s ease;
}
details.quiz-card[open], details.quiz-item[open]{border-color:var(--primary);box-shadow:var(--shadow-md)}
details.quiz-card summary, details.quiz-item summary{
  display:flex;align-items:center;gap:.75rem;padding:.85rem 1.15rem;cursor:pointer;
  font-weight:750;font-size:.93rem;color:var(--text-main);list-style:none;user-select:none;
}
details.quiz-card summary::-webkit-details-marker, details.quiz-item summary::-webkit-details-marker{display:none}
.quiz-q-num{flex:0 0 auto;font-size:.76rem;font-weight:900;padding:.2rem .5rem;border-radius:6px;background:var(--primary-light);color:var(--primary-dark)}
.quiz-q-text{flex:1;line-height:1.45}
.quiz-toggle-hint{
  flex:0 0 auto;margin-left:auto;font-size:.76rem;font-weight:800;padding:.22rem .6rem;
  border-radius:6px;background:var(--primary-light);color:var(--primary-dark);display:inline-flex;align-items:center;gap:.3rem;transition:all .2s;
}
.quiz-toggle-hint::after{content:" ▼";font-size:.68rem}
details.quiz-card[open] .quiz-toggle-hint, details.quiz-item[open] .quiz-toggle-hint{background:var(--surface-sub);color:var(--text-muted)}
details.quiz-card[open] .quiz-toggle-hint::after, details.quiz-item[open] .quiz-toggle-hint::after{content:" ▲"}
.quiz-answer-panel{padding:1rem 1.25rem 1.15rem;border-top:1px dashed var(--border);background:color-mix(in srgb,var(--primary-light) 14%,var(--surface));font-size:.91rem}
.ans-label{display:inline-flex;align-items:center;gap:.35rem;font-weight:850;font-size:.84rem;color:var(--primary-dark);margin-bottom:.4rem}
.quiz-answer-panel p{margin:0;line-height:1.6;color:var(--text-sub)}

/* TABLES */
.table-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.4rem 1.6rem;box-shadow:var(--shadow-sm);margin-bottom:1.8rem}
.table-card-title{font-size:1.15rem;font-weight:850;color:var(--text-main);margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}
.table-wrap{margin:1.4rem 0;overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius-md);box-shadow:var(--shadow-sm)}
table, table.styled-table{width:100%;border-collapse:collapse;font-size:.91rem;text-align:left;background:var(--surface)}
table th, table.styled-table th{background:var(--surface-sub);color:var(--primary-dark);font-weight:900;padding:.85rem 1.05rem;border-bottom:2px solid var(--border-strong);white-space:nowrap;font-size:.92rem}
table td, table.styled-table td{padding:.8rem 1.05rem;border-bottom:1px solid var(--border);color:var(--text-main);vertical-align:top;line-height:1.6}
table tr:last-child td, table.styled-table tr:last-child td{border-bottom:none}
table tr:hover td, table.styled-table tr:hover td{background:color-mix(in srgb,var(--primary-light) 12%,transparent)}
table td:first-child, table.styled-table td:first-child{font-weight:850;color:var(--primary-dark);background:color-mix(in srgb,var(--surface-sub) 40%,var(--surface));white-space:nowrap}
table td strong, table.styled-table td strong{color:var(--primary-dark)}

.table-tag{display:inline-flex;align-items:center;gap:.25rem;padding:.22rem .55rem;border-radius:6px;font-weight:900;font-size:.78rem;white-space:nowrap}
.table-tag.danger{background:var(--rose-light);color:var(--rose-dark);border:1px solid color-mix(in srgb,var(--rose) 35%,transparent)}
.table-tag.success{background:var(--primary-light);color:var(--primary-dark);border:1px solid color-mix(in srgb,var(--primary) 35%,transparent)}
.table-tag.amber{background:var(--amber-light);color:var(--amber-dark);border:1px solid color-mix(in srgb,var(--amber) 35%,transparent)}
.table-tag.blue{background:var(--blue-light);color:var(--blue-dark);border:1px solid color-mix(in srgb,var(--blue) 35%,transparent)}
.table-tag.purple{background:var(--purple-light);color:var(--purple);border:1px solid color-mix(in srgb,var(--purple) 35%,transparent)}

/* RAPID REVIEW & LIKELY CONFUSIONS */
.split-review{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem;margin-top:1.5rem;margin-bottom:2rem}
.review-box{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.4rem 1.6rem;box-shadow:var(--shadow-sm)}
.review-box.rapid{border-top:5px solid #10b981}
.review-box.confuse{border-top:5px solid var(--purple)}
.review-box-title, .review-box h3{margin:0 0 1rem;font-size:1.15rem;font-weight:900;display:flex;align-items:center;gap:.5rem;letter-spacing:-0.01em}
.review-box.rapid .review-box-title, .review-box.rapid h3{color:#047857}
.review-box.confuse .review-box-title, .review-box.confuse h3{color:var(--purple)}

.rapid-grid, .rapid-list{display:flex;flex-direction:column;gap:.65rem}
.rapid-card{
  background:var(--surface);border:1px solid color-mix(in srgb,#10b981 30%,var(--border));
  border-left:4px solid #10b981;border-radius:var(--radius-sm);padding:.75rem .95rem;
  box-shadow:0 1px 2px rgba(0,0,0,0.03);display:flex;flex-direction:column;gap:.35rem;
}
.rapid-topic{font-size:.76rem;font-weight:900;color:#047857;background:#d1fae5;padding:.15rem .5rem;border-radius:4px;display:inline-block;width:fit-content}
.rapid-body{font-size:.9rem;line-height:1.55;color:var(--text-sub)}

.confuse-grid{display:flex;flex-direction:column;gap:.75rem}
.confuse-card{border:1px solid var(--border);border-radius:var(--radius-md);padding:.85rem 1rem;background:var(--surface-sub)}
.confuse-header{display:flex;align-items:center;gap:.6rem;margin-bottom:.55rem}
.confuse-topic{font-size:.78rem;font-weight:900;color:var(--purple);background:var(--purple-light);padding:.15rem .5rem;border-radius:4px}
.confuse-row{display:flex;align-items:flex-start;gap:.6rem;margin-bottom:.35rem}
.confuse-row:last-child{margin-bottom:0}
.confuse-sub-badge{font-size:.72rem;font-weight:900;padding:.15rem .45rem;border-radius:4px;white-space:nowrap}
.confuse-sub-badge.wrong{background:var(--rose-light);color:var(--rose-dark);border:1px solid color-mix(in srgb, var(--rose) 40%, transparent)}
.confuse-sub-badge.correct{background:var(--primary-light);color:var(--primary-dark);border:1px solid color-mix(in srgb, var(--primary) 40%, transparent)}
.confuse-desc{font-size:.86rem;line-height:1.5;color:var(--text-sub);flex:1}
.confuse-desc.wrong{text-decoration:line-through;color:var(--text-muted)}
.confuse-desc.correct{color:var(--text-main);font-weight:600}
.confuse-desc.correct strong{color:var(--primary-dark);font-weight:900}
body.dark .confuse-desc.correct strong{color:var(--primary)}

footer{text-align:center;color:var(--text-muted);font-size:.82rem;padding:3rem 1rem}

@media(max-width:960px){
  .layout{grid-template-columns:220px minmax(0,1fr);gap:1rem;padding:.6rem .8rem}
  .split-review{grid-template-columns:1fr}
}
@media(max-width:680px){
  body:not(.toc-collapsed) .side{
    position:fixed;top:54px;left:0;bottom:0;width:min(82vw,280px);
    z-index:100;background:var(--surface);border-right:1px solid var(--border);
    box-shadow:0 0 24px rgba(0,0,0,.25);padding:1rem;overflow-y:auto;
  }
  body:not(.toc-collapsed) .layout{grid-template-columns:minmax(0,1fr)!important}
  .brand-tag{display:none}
  .search{flex:1;min-width:100px}
  .hero{padding:1.4rem 1.3rem}
  .section-card{padding:1.2rem 1.1rem}
}
@media print{
  .topbar,.side,#toggle-toc{display:none!important}
  .layout{display:block;padding:0}
  .hero{background:#fff;color:#000;border:1px solid #ccc}
  .section-card,.overview-card,.review-box{box-shadow:none;break-inside:avoid}
}
"""

V2_SCRIPT = """
const key = 'summed-v2-note';
const body = document.body;

if (localStorage.getItem(key + '-theme') === 'dark') body.classList.add('dark');
let scale = parseFloat(localStorage.getItem(key + '-scale') || '1');
document.documentElement.style.setProperty('--scale', scale);

document.getElementById('theme').onclick = () => {
  body.classList.toggle('dark');
  localStorage.setItem(key + '-theme', body.classList.contains('dark') ? 'dark' : 'light');
};

function zoom(delta) {
  scale = Math.min(1.35, Math.max(0.85, scale + delta));
  document.documentElement.style.setProperty('--scale', scale);
  localStorage.setItem(key + '-scale', scale);
}
document.getElementById('small').onclick = () => zoom(-0.05);
document.getElementById('large').onclick = () => zoom(0.05);
document.getElementById('print').onclick = () => window.print();

const tocBtn = document.getElementById('toggle-toc');
const storedToc = localStorage.getItem(key + '-toc');
if (storedToc === 'collapsed' || (!storedToc && window.innerWidth <= 1024)) {
  body.classList.add('toc-collapsed');
}
if (tocBtn) {
  tocBtn.onclick = () => {
    body.classList.toggle('toc-collapsed');
    localStorage.setItem(key + '-toc', body.classList.contains('toc-collapsed') ? 'collapsed' : 'open');
  };
}

document.querySelectorAll('.side a').forEach(a => {
  a.addEventListener('click', () => {
    if (window.innerWidth <= 1024) {
      body.classList.add('toc-collapsed');
      localStorage.setItem(key + '-toc', 'collapsed');
    }
  });
});

document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  let visible = 0;
  document.querySelectorAll('.searchable').forEach(x => {
    const show = !q || x.innerText.toLowerCase().includes(q);
    x.classList.toggle('hidden', !show);
    if (show) visible++;
  });
});
"""


def render_html(note: SummedNote, request: SummaryRequest, source_names: list[str], path: Path) -> None:
    nav_links = []
    sections_html = []
    for i, sec in enumerate(note.sections, 1):
        clean_title = re.sub(r"^\d+\.\s*", "", sec.title)
        nav_links.append(f'<a href="#sec-{i}"><span class="nav-num">{i:02d}</span><span class="nav-txt">{_esc(clean_title)}</span></a>')
        
        quizzes_html = _format_quiz_items(sec.review_quiz)
        exam_html = _format_exam_items(sec.exam_focus)
        transcript_html = _format_transcript_items(sec.transcript_additions)
        blocks_html = _transform_section_core_points(sec.core_points, sec.title)

        exam_block = f"""
  <div class="callout exam">
    <div class="callout-head">⚡ 시험 적중 &amp; 족보 포인트</div>
    <div class="callout-list">{exam_html}</div>
  </div>""" if exam_html else ""

        trans_block = f"""
  <div class="callout transcript">
    <div class="callout-head">💡 교수님 강의 강조 &amp; 심화 설명</div>
    <div class="callout-list">{transcript_html}</div>
  </div>""" if transcript_html else ""

        quiz_block = f"""
  <div class="quiz-section">
    <div class="quiz-section-title">📝 소단원 복습 퀴즈 ({len(sec.review_quiz)}문항 · 터치하여 정답 확인)</div>
    {quizzes_html}
  </div>""" if quizzes_html else ""

        sections_html.append(f"""
<section id="sec-{i}" class="section-card searchable">
  <div class="sec-header">
    <span class="sec-badge">{i:02d}</span>
    <div class="sec-titles">
      <h2>{_esc(clean_title)}</h2>
    </div>
  </div>
  {blocks_html}
  {exam_block}
  {trans_block}
  {quiz_block}
</section>
""")

    overview_items = []
    for ov in note.overview:
        parts = re.split(r"[:—]\s*", ov, maxsplit=1)
        if len(parts) == 2:
            h = parts[0].strip()
            d = parts[1].strip()
        else:
            h = "핵심 목표"
            d = ov.strip()
        overview_items.append(f"""
      <div class="overview-item">
        <strong>{_esc(h)}</strong>
        <p>{_clean_text(d)}</p>
      </div>""")

    overview_card = f"""
<section class="overview-card searchable">
  <h2><span>📌</span> 강의 핵심 개요 및 학습 목표</h2>
  <div class="overview-grid">
    {"".join(overview_items)}
  </div>
</section>
""" if overview_items else ""

    tables_html = _build_tables_html(note.tables)
    rapid_html = _build_rapid_review_html(note.rapid_review)
    confuse_html = _build_likely_confusions_html(note.likely_confusions)

    split_review = ""
    if rapid_html or confuse_html:
        split_review = f"""
<div class="split-review searchable">
  <div class="review-box rapid">
    <div class="review-box-title"><span>⚡</span> 시험 직전 1분 고득점 칩 (Rapid Review)</div>
    <div class="rapid-grid">
      {rapid_html}
    </div>
  </div>
  <div class="review-box confuse">
    <div class="review-box-title"><span>⚠️</span> 헷갈리기 쉬운 감별 포인트 (Likely Confusions)</div>
    <div class="confuse-grid">
      {confuse_html}
    </div>
  </div>
</div>
"""

    document = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{_esc(note.title)}</title>
  <style>{V2_CSS}</style>
</head>
<body>
  <header class="topbar">
    <button id="toggle-toc" class="btn-toc" title="목차 열기/닫기" aria-label="목차 토글">☰ 목차</button>
    <div class="brand-badge">
      <span>summed</span>
      <span class="brand-tag">v2 시각화 정리본</span>
    </div>
    <input id="search" class="search" type="search" placeholder="개념·약물·기전 검색">
    <button id="small" class="action-btn" title="글자 작게">A−</button>
    <button id="large" class="action-btn" title="글자 크게">A+</button>
    <button id="theme" class="action-btn" title="화면 모드">◐</button>
    <button id="print" class="action-btn">인쇄</button>
  </header>

  <div class="layout">
    <nav class="side">
      <div style="font-size:0.75rem;font-weight:900;color:var(--text-muted);padding:.2rem .7rem;letter-spacing:.05em;text-transform:uppercase;">Table of Contents</div>
      {"".join(nav_links)}
    </nav>

    <main class="content">
      <section class="hero">
        <div class="hero-eyebrow">{_esc(request.course)} · 의학과 1-2</div>
        <h1>{_esc(note.title)}</h1>
        <p>{_esc(note.subtitle)}</p>
        <div class="hero-meta">
          <span class="hero-pill">📚 {_esc(request.course)}</span>
          <span class="hero-pill">👨‍🏫 {_esc(request.professor)}</span>
          <span class="hero-pill">🎯 기출 족보·학습가이드 연계</span>
          <span class="hero-pill">⚡ 핵심 기전 시각화</span>
        </div>
      </section>

      {overview_card}
      {"".join(sections_html)}
      {tables_html}
      {split_review}
    </main>
  </div>

  <footer>
    summed v2 · 고시인성 오프라인 HTML · Active Recall Details &amp; Responsive Left Sidebar
  </footer>

  <script>{V2_SCRIPT}</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def render_markdown(note: SummedNote, request: SummaryRequest, source_names: list[str], path: Path) -> None:
    lines = [
        f"# {_md(note.title)}",
        "",
        f"> {_md(note.subtitle)}",
        "",
        "## 강의 핵심 개요",
        "",
    ]
    for ov in note.overview:
        lines.append(f"- {_md(ov)}")
    lines.append("")

    for index, sec in enumerate(note.sections, 1):
        lines.extend([
            f"## {index}. {_md(sec.title)}",
            "",
            "### 핵심 내용",
            "",
        ])
        for cp in sec.core_points:
            lines.append(f"- {_md(cp)}")
        lines.append("")

        if sec.exam_focus:
            lines.extend(["### 시험 적중 & 족보 포인트", ""])
            for ef in sec.exam_focus:
                lines.append(f"- {_md(ef)}")
            lines.append("")

        if sec.transcript_additions:
            lines.extend(["### 교수님 강의 강조", ""])
            for ta in sec.transcript_additions:
                lines.append(f"- {_md(ta)}")
            lines.append("")

        if sec.review_quiz:
            lines.extend(["### 소단원 복습 퀴즈", ""])
            for q in sec.review_quiz:
                q_idx = getattr(q, "question_number", 1) if not isinstance(q, dict) else q.get("question_number", 1)
                q_text = getattr(q, "question", "") if not isinstance(q, dict) else q.get("question", "")
                q_ans = getattr(q, "answer", "") if not isinstance(q, dict) else q.get("answer", "")
                lines.extend([
                    f"**Q{q_idx}. {_md(q_text)}**",
                    "",
                    "<details>",
                    "<summary>정답 보기</summary>",
                    "",
                    f"{_md(q_ans)}",
                    "</details>",
                    "",
                ])

    if note.tables:
        lines.extend(["## 비교 정리표", ""])
        for tbl in note.tables:
            tbl_title = getattr(tbl, "title", "") if not isinstance(tbl, dict) else tbl.get("title", "")
            cols = getattr(tbl, "columns", []) if not isinstance(tbl, dict) else tbl.get("columns", [])
            rows = getattr(tbl, "rows", []) if not isinstance(tbl, dict) else tbl.get("rows", [])
            lines.extend([f"### {_md(tbl_title)}", "", "| " + " | ".join(_md(c) for c in cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"])
            for r in rows:
                lines.append("| " + " | ".join(_md(str(c)) for c in r) + " |")
            lines.append("")

    if note.rapid_review:
        lines.extend(["## 시험 직전 1분 고득점 칩 (Rapid Review)", ""])
        for rr in note.rapid_review:
            lines.append(f"- {_md(rr)}")
        lines.append("")

    if note.likely_confusions:
        lines.extend(["## 헷갈리기 쉬운 감별 포인트 (Likely Confusions)", ""])
        for lc in note.likely_confusions:
            lines.append(f"- {_md(lc)}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
