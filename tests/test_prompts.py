from prestudy.models import LectureRequest, SourceKind
from prestudy.prompts import digest_prompt, synthesis_prompt


def test_lecture_material_prompt_uses_material_for_pages_but_not_title():
    lecture = LectureRequest(
        course="약리학",
        professor="김자은",
        topic="Pharmacokinetics-2&metabolism",
    )

    digest = digest_prompt(SourceKind.LECTURE, lecture, "강의자료.pdf")
    synthesis = synthesis_prompt(lecture, "[]", has_lecture_material=True)

    assert "현재 강의 내용과 페이지 순서를 정하는 최우선 근거" in digest
    assert "교수명과 강의 제목은 이 파일에서 추정하지 마라" in digest
    assert "표시할 모든 페이지는 강의자료 PDF만 기준" in synthesis
    assert "족첵은 교수명·강의 제목과 출제 신호의 기준" in synthesis
    assert "lecture_flow는 강의자료의 실제 진행 순서" in synthesis
    assert "lecture_flow는 족첵 속 현재 강의자료" not in synthesis
    assert "importance는 ⭐ 1~3개" in synthesis
    assert "exam_years" in synthesis
    assert "짤족/탈족 정보가 직접 확인될 때만" in synthesis
    assert "tables는 A vs B 비교" in synthesis
    assert "cause_effect_flows" in synthesis
    assert "final_checklist.comparisons" in synthesis
    assert "heading, kind, takeaway, details, citations" in synthesis
    assert "개수 상한 때문에 서로 다른 주요 개념을 빼거나" in synthesis
    assert "그림·표 해석" in synthesis


def test_jokchek_remains_page_basis_when_material_is_not_selected():
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")

    synthesis = synthesis_prompt(lecture, "[]", has_lecture_material=False)

    assert "표시 페이지는 족첵 속 강의자료 부분을 기준" in synthesis
