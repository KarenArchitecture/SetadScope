"""Database-backed matching keywords shared by auction and tender importers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AppSetting
from app.services.keyword_matching import KEYWORDS, normalize_fa

SETTING_KEY = "auction_keywords"


def configured_keywords(db: Session) -> tuple[str, ...]:
    setting = db.get(AppSetting, SETTING_KEY)
    if setting and isinstance(setting.value, dict):
        words = setting.value.get("keywords")
        if isinstance(words, list) and words and all(isinstance(w, str) for w in words):
            return tuple(words)
    return KEYWORDS


def validate_keywords(words: list[str]) -> list[str]:
    if not words or len(words) > 100:
        raise ValueError("بین ۱ تا ۱۰۰ کلیدواژه وارد کنید.")
    result = []
    seen = set()
    for word in words:
        value = " ".join(word.split())
        normalized = normalize_fa(value)
        if not normalized or len(value) > 80:
            raise ValueError("طول هر کلیدواژه باید بین ۱ تا ۸۰ نویسه باشد.")
        if normalized in seen:
            raise ValueError("کلیدواژه تکراری وجود دارد: " + value)
        seen.add(normalized)
        result.append(value)
    return result
