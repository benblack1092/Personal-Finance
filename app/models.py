"""SQLAlchemy ORM models for the personal finance app.

Design notes
------------
* Amounts are stored in the account's currency as a signed float where
  negative = money leaving the account (spending) and positive = income /
  refunds. This mirrors how most bank exports represent transactions.
* ``external_id`` + ``account_id`` form a soft unique key used to deduplicate
  re-imported statements.
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # credit_card | checking | savings | amazon | cash | other
    type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    institution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    # Hex colour used by the dashboard charts, e.g. "#4f46e5".
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)

    parent: Mapped["Category | None"] = relationship(remote_side=[id])
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")


class Rule(Base):
    """Auto-categorization rule.

    When a transaction's searchable text contains ``pattern`` (case-insensitive
    substring, or regex when ``is_regex`` is set) the transaction is assigned
    ``category_id``. Higher ``priority`` wins when several rules match.
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    # Which field to match against: "description" or "merchant".
    field: Mapped[str] = mapped_column(String(20), default="description")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # Optional canonical merchant name to stamp onto matching transactions.
    set_merchant: Mapped[str | None] = mapped_column(String(120), nullable=True)

    category: Mapped["Category"] = relationship()


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)  # csv | ofx | amazon
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # Dedup guard: the same external id can't be imported twice per account.
        UniqueConstraint("account_id", "external_id", name="uq_account_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Signed amount: negative = spending, positive = income/refund.
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    # Raw description straight from the statement.
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Cleaned-up / canonical merchant name.
    merchant: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Stable id from the source used for dedup (statement fitid, amazon order id...).
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
