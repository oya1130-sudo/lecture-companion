import pytest

from prestudy.metadata import JokchekMetadataError, infer_jokchek_metadata


def test_metadata_comes_from_jokchek_filename_not_author_name():
    metadata = infer_jokchek_metadata(
        ["약리학_1주차(3)_김자은_Pharmacokinetics-2&metabolism_김진후.pdf"],
        expected_course="약리학",
    )

    assert metadata.professor == "김자은"
    assert metadata.topic == "Pharmacokinetics-2&metabolism"


def test_split_jokchek_files_with_same_lecture_are_deduplicated():
    metadata = infer_jokchek_metadata(
        [
            "병리학_2주차(4-1)_이소민_Hemodynamic disorders_박민웅.pdf",
            "병리학_2주차(4-2)_이소민_Hemodynamic Disorders_신성하.pdf",
        ],
        expected_course="병리학",
    )

    assert metadata.professor == "이소민"
    assert metadata.topic.casefold() == "hemodynamic disorders"


def test_distinct_topics_are_combined_but_professors_cannot_conflict():
    metadata = infer_jokchek_metadata(
        [
            "약리학_1주차(2)_김자은_pharmacokinetics-1_윤창훈.pdf",
            "약리학_1주차(3)_김자은_Pharmacokinetics-2&metabolism_김진후.pdf",
        ],
        expected_course="약리학",
    )

    assert metadata.topic == "pharmacokinetics-1 / Pharmacokinetics-2&metabolism"

    with pytest.raises(JokchekMetadataError, match="교수명이 서로 다릅니다"):
        infer_jokchek_metadata(
            [
                "약리학_1주차(3)_김자은_약동학_작성자.pdf",
                "약리학_2주차(1)_박승준_자율신경계_작성자.pdf",
            ],
            expected_course="약리학",
        )


def test_nonlecture_or_wrong_course_file_is_rejected():
    with pytest.raises(JokchekMetadataError, match="파일명에서"):
        infer_jokchek_metadata(["2025 예방 기말 시험지 원본.pdf"], expected_course="예방의학")

    with pytest.raises(JokchekMetadataError, match="선택한 과목은 병리학"):
        infer_jokchek_metadata(
            ["약리학_1주차(1)_김자은_pharmacodynamics_이유승.pdf"],
            expected_course="병리학",
        )
