from __future__ import annotations

import re
from datetime import date, datetime


def _month_day(value: date | str) -> str:
    if isinstance(value, datetime):
        return value.strftime("%m%d")
    if isinstance(value, date):
        return value.strftime("%m%d")

    text = str(value).strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).strftime("%m%d")
    except ValueError:
        pass

    compact = re.sub(r"\D", "", text)
    if len(compact) == 8:
        return compact[4:8]
    if len(compact) == 4:
        return compact
    return ""


def companion_title(
    lecture_date: date | str,
    course: str,
    professor: str,
    topic: str,
) -> str:
    parts = [_month_day(lecture_date), course.strip(), professor.strip(), topic.strip()]
    return " ".join(part for part in parts if part)
