from pathlib import Path

import pytest

from prestudy.ai import FileValidationError, validate_pdf


def test_validate_pdf_accepts_pdf_signature(tmp_path: Path):
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    validate_pdf(path)


def test_validate_pdf_rejects_wrong_signature(tmp_path: Path):
    path = tmp_path / "sample.pdf"
    path.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(FileValidationError):
        validate_pdf(path)
