"""Pydantic request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class AccountBase(BaseModel):
    name: str
    type: str = "other"
    institution: str | None = None
    currency: str = "USD"


class AccountCreate(AccountBase):
    pass


class AccountOut(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
class CategoryBase(BaseModel):
    name: str
    parent_id: int | None = None
    color: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
class RuleBase(BaseModel):
    pattern: str
    is_regex: bool = False
    field: str = "description"
    category_id: int
    priority: int = 0
    set_merchant: str | None = None


class RuleCreate(RuleBase):
    pass


class RuleOut(RuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
class TransactionBase(BaseModel):
    account_id: int
    txn_date: date
    amount: float
    description: str = ""
    merchant: str | None = None
    category_id: int | None = None
    notes: str | None = None
    pending: bool = False


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    txn_date: date | None = None
    amount: float | None = None
    description: str | None = None
    merchant: str | None = None
    category_id: int | None = None
    notes: str | None = None
    pending: bool | None = None


class TransactionOut(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    external_id: str | None = None
    category_name: str | None = None
    account_name: str | None = None


# --------------------------------------------------------------------------- #
# Imports
# --------------------------------------------------------------------------- #
class ColumnMapping(BaseModel):
    """Maps CSV column headers to transaction fields for the generic importer."""

    date: str
    amount: str | None = None
    # Some banks split debits/credits into two columns instead of one signed one.
    debit: str | None = None
    credit: str | None = None
    description: str
    # Optional column naming a canonical merchant; used verbatim when present.
    merchant: str | None = None
    # When True, positive numbers in the amount column mean spending and are
    # flipped to negative (common for credit-card exports).
    flip_sign: bool = False
    date_format: str | None = None  # e.g. "%m/%d/%Y"; auto-detected when omitted


class WebImportPayload(BaseModel):
    """Payload the browser extension POSTs after scraping a page.

    Both the generic-table and Amazon paths use this one shape: ``records`` is a
    list of ``{header: value}`` rows and ``mapping`` says how to read them.
    """

    account_id: int
    source: str = "web"  # "web" | "amazon"
    mapping: ColumnMapping
    records: list[dict] = Field(default_factory=list)


class SuggestMappingRequest(BaseModel):
    headers: list[str]


class ImportResult(BaseModel):
    batch_id: int
    source: str
    row_count: int
    imported_count: int
    skipped_count: int
    categorized_count: int = 0


class CsvPreview(BaseModel):
    headers: list[str]
    sample_rows: list[dict]
    suggested_mapping: ColumnMapping | None = None


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #
class CategorySpend(BaseModel):
    category_id: int | None
    category_name: str
    color: str | None
    total: float
    count: int


class MerchantSpend(BaseModel):
    merchant: str
    total: float
    count: int


class MonthlySpend(BaseModel):
    month: str  # YYYY-MM
    spending: float
    income: float


class SummaryOut(BaseModel):
    total_spending: float
    total_income: float
    net: float
    transaction_count: int
    by_category: list[CategorySpend]
    by_merchant: list[MerchantSpend]
    by_month: list[MonthlySpend]
    start_date: date | None = None
    end_date: date | None = None
