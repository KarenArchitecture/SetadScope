"""Persian-aware, deterministic keyword matching with OR semantics."""
import re
import unicodedata

KEYWORDS = (
    "تراورس", "صنوبر", "درخت", "درختان", "جنگل", "چوب", "چوب آلات",
    "اشجار", "برگ", "نهال", "منابع طبیعی", "پروانه قطع",
)
_TRANSLATION = str.maketrans({"ي":"ی","ى":"ی","ك":"ک","ة":"ه","ۀ":"ه","أ":"ا","إ":"ا","ٱ":"ا"})
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_SPACES = re.compile(r"\s+")

def normalize_fa(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_TRANSLATION)
    text = _ZERO_WIDTH.sub(" ", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return _SPACES.sub(" ", text).strip().casefold()

def matched_keywords(*texts: object, keywords: tuple[str, ...] | list[str] | None = None) -> list[str]:
    text = normalize_fa(" ".join(str(v or "") for v in texts))
    return [word for word in (KEYWORDS if keywords is None else keywords) if re.search(r"(?<!\w)" + re.escape(normalize_fa(word)) + r"(?!\w)", text)]
