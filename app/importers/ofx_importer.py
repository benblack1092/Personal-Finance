"""OFX / QFX importer.

OFX (and its Quicken variant QFX) is the richest export most banks offer: every
transaction carries a stable ``FITID`` we use directly for deduplication.

OFX is SGML-like — tags are often unclosed — so instead of a full XML parse we
extract the ``<STMTTRN>`` blocks and read the fields we care about with small
regexes. This keeps the importer dependency-free and tolerant of the many
slightly-malformed files banks produce.
"""
import re
from datetime import date

from app.importers.common import clean_merchant

_TRN_BLOCK = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)


def _tag(block: str, name: str) -> str | None:
    """Read a single OFX field value (handles closed and unclosed tags)."""
    m = re.search(rf"<{name}>([^<\r\n]*)", block, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_ofx_date(raw: str | None) -> date | None:
    if not raw:
        return None
    # OFX dates look like YYYYMMDD or YYYYMMDDHHMMSS[.xxx][tz]; take first 8 digits.
    digits = re.sub(r"[^0-9]", "", raw)[:8]
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def parse_ofx(content: bytes, account_id: int) -> list[dict]:
    """Parse an OFX/QFX file into transaction dicts.

    Returns an empty list if no transactions can be found.
    """
    text = content.decode("utf-8", errors="replace")
    out: list[dict] = []
    for block in _TRN_BLOCK.findall(text):
        txn_date = _parse_ofx_date(_tag(block, "DTPOSTED") or _tag(block, "DTUSER"))
        amount_raw = _tag(block, "TRNAMT")
        if txn_date is None or amount_raw is None:
            continue
        try:
            amount = float(amount_raw.replace(",", ""))
        except ValueError:
            continue

        name = _tag(block, "NAME") or ""
        memo = _tag(block, "MEMO") or ""
        description = (name or memo).strip()
        if name and memo and memo.lower() not in name.lower():
            description = f"{name} {memo}".strip()

        fitid = _tag(block, "FITID")
        out.append(
            {
                "txn_date": txn_date,
                "amount": amount,  # OFX sign already reflects debit/credit
                "description": description,
                "merchant": clean_merchant(name or memo),
                "external_id": fitid or None,
            }
        )
    return out
