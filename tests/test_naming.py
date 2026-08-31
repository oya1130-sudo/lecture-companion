from datetime import date

from prestudy.naming import companion_title


def test_companion_title_uses_existing_mmdd_course_professor_topic_format():
    assert companion_title(
        date(2026, 8, 31),
        "병리학",
        "이소민",
        "Hemodynamic Disorders(2)",
    ) == "0831 병리학 이소민 Hemodynamic Disorders(2)"


def test_companion_title_accepts_iso_date_from_lecture_request():
    assert companion_title(
        "2026-09-02",
        "약리학",
        "김자은",
        "Pharmacokinetics",
    ).startswith("0902 약리학 김자은 ")
