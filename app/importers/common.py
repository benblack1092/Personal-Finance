"""Shared helpers used by every importer."""
import re
from datetime import date

from dateutil import parser as dateparser

# Noise commonly appended to card/bank descriptions that we strip to derive a
# clean merchant name.
_NOISE_PATTERNS = [
    r"\bPOS\b",
    r"\bPURCHASE\b",
    r"\bDEBIT\b",
    r"\bCARD\b",
    r"\bXXXX\d+",
    r"#\d{3,}",
    r"\b\d{2}/\d{2}\b",
    r"\bAUTH\b",
    r"\bRECURRING\b",
    r"\bONLINE\b",
    r"\bPAYMENT\b",
]
_MULTISPACE = re.compile(r"\s{2,}")
_TRAILING_LOC = re.compile(r"\s+[A-Z]{2}\s*$")  # trailing state code like " CA"


def clean_merchant(description: str) -> str:
    """Best-effort extraction of a human-friendly merchant name.

    This is intentionally conservative — it only tidies obvious statement noise
    so charts group sensibly. Users can always override the merchant per-row.
    """
    if not description:
        return ""
    text = description.strip()
    for pat in _NOISE_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    text = _TRAILING_LOC.sub("", text)
    text = _MULTISPACE.sub(" ", text).strip(" -*.")
    # Title-case ALL-CAPS statement text but leave mixed case alone.
    if text.isupper():
        text = text.title()
    return text[:160]


def parse_date(value: str, date_format: str | None = None) -> date:
    """Parse a date string, honouring an explicit strptime format when given."""
    value = (value or "").strip()
    if not value:
        raise ValueError("empty date")
    if date_format:
        from datetime import datetime

        return datetime.strptime(value, date_format).date()
    # dateutil handles the wide variety of bank formats (MM/DD/YYYY, ISO, etc.).
    return dateparser.parse(value, dayfirst=False).date()


def parse_amount(value) -> float:
    """Parse a currency string like ``$1,234.56`` or ``(12.00)`` to a float."""
    if value is None:
        raise ValueError("empty amount")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        raise ValueError("empty amount")
    negative = False
    if s.startswith("(") and s.endswith(")"):  # accounting notation
        negative = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").replace(" ", "").strip()
    if s.startswith("-"):
        negative = True
        s = s[1:]
    if s.endswith("-"):  # trailing-minus style
        negative = True
        s = s[:-1]
    amount = float(s)
    return -amount if negative else amount
