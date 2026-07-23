"""Auto-categorization engine.

Applies user-defined :class:`~app.models.Rule` rows to transactions. Rules are
evaluated highest-priority-first; the first match wins. A small set of sensible
default rules and categories is seeded on first run so the app is useful
immediately.
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Rule, Transaction

# (category name, color, [substrings that map to it])
DEFAULT_CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("Groceries", "#16a34a", ["whole foods", "trader joe", "safeway", "kroger", "aldi", "grocery", "supermarket", "wegmans", "publix", "costco wholesale"]),
    ("Restaurants", "#f97316", ["restaurant", "cafe", "coffee", "starbucks", "doordash", "uber eats", "grubhub", "mcdonald", "chipotle", "pizza", "bar & grill"]),
    ("Transport", "#0ea5e9", ["uber", "lyft", "shell", "chevron", "exxon", "gas station", "parking", "transit", "metro", "bp ", "toll"]),
    ("Shopping", "#a855f7", ["amazon", "target", "walmart", "best buy", "ebay", "etsy", "store"]),
    ("Subscriptions", "#e11d48", ["netflix", "spotify", "hulu", "disney+", "youtube premium", "apple.com/bill", "prime video", "patreon"]),
    ("Utilities", "#0891b2", ["electric", "water", "gas company", "comcast", "xfinity", "at&t", "verizon", "t-mobile", "utility"]),
    ("Housing", "#7c3aed", ["rent", "mortgage", "hoa", "property mgmt", "landlord"]),
    ("Health", "#dc2626", ["pharmacy", "cvs", "walgreens", "doctor", "dental", "clinic", "hospital", "medical", "fitness", "gym"]),
    ("Entertainment", "#db2777", ["cinema", "movie", "theater", "steam", "playstation", "xbox", "concert", "ticketmaster"]),
    ("Travel", "#2563eb", ["airline", "delta", "united", "hotel", "airbnb", "expedia", "booking.com", "marriott", "hilton"]),
    ("Income", "#059669", ["payroll", "direct deposit", "salary", "deposit from", "interest paid"]),
    ("Transfers", "#64748b", ["transfer", "zelle", "venmo", "paypal", "autopay", "payment thank you", "online payment"]),
    ("Fees", "#b91c1c", ["fee", "interest charge", "service charge", "atm", "overdraft"]),
    ("Uncategorized", "#94a3b8", []),
]


def seed_defaults(db: Session) -> None:
    """Create default categories and rules if the tables are empty."""
    existing = db.scalar(select(Category).limit(1))
    if existing is not None:
        return

    name_to_cat: dict[str, Category] = {}
    for name, color, _ in DEFAULT_CATEGORIES:
        cat = Category(name=name, color=color)
        db.add(cat)
        name_to_cat[name] = cat
    db.flush()  # assign ids

    for name, _color, patterns in DEFAULT_CATEGORIES:
        cat = name_to_cat[name]
        for pat in patterns:
            db.add(Rule(pattern=pat, field="description", category_id=cat.id, priority=10))
    db.commit()


def _matches(rule: Rule, text: str) -> bool:
    if not text:
        return False
    if rule.is_regex:
        try:
            return re.search(rule.pattern, text, re.IGNORECASE) is not None
        except re.error:
            return False
    return rule.pattern.lower() in text.lower()


def categorize_transaction(txn: Transaction, rules: list[Rule]) -> bool:
    """Apply the highest-priority matching rule to ``txn`` in place.

    Returns True if a category was assigned. Rules must be pre-sorted by
    descending priority.
    """
    for rule in rules:
        target = txn.description if rule.field == "description" else (txn.merchant or "")
        if _matches(rule, target):
            txn.category_id = rule.category_id
            if rule.set_merchant and not txn.merchant:
                txn.merchant = rule.set_merchant
            return True
    return False


def load_rules(db: Session) -> list[Rule]:
    """Return all rules sorted so the highest priority is evaluated first."""
    return list(db.scalars(select(Rule).order_by(Rule.priority.desc(), Rule.id.asc())))


def recategorize_all(db: Session, only_uncategorized: bool = True) -> int:
    """Re-run rules over existing transactions. Returns number changed."""
    rules = load_rules(db)
    stmt = select(Transaction)
    if only_uncategorized:
        stmt = stmt.where(Transaction.category_id.is_(None))
    changed = 0
    for txn in db.scalars(stmt):
        if categorize_transaction(txn, rules):
            changed += 1
    db.commit()
    return changed
