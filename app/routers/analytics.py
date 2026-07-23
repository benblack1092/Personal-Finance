"""Spending analytics: summary totals, by-category, by-merchant, by-month."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Transaction
from app.schemas import CategorySpend, MerchantSpend, MonthlySpend, SummaryOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _base_filters(stmt, account_id, start_date, end_date):
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if start_date is not None:
        stmt = stmt.where(Transaction.txn_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Transaction.txn_date <= end_date)
    return stmt


@router.get("/summary", response_model=SummaryOut)
def summary(
    db: Session = Depends(get_db),
    account_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    merchant_limit: int = 10,
):
    """Aggregate spending for the dashboard.

    Spending is the sum of negative amounts (reported as a positive number);
    income is the sum of positive amounts. Transfers between your own accounts
    are excluded from both to avoid double-counting.
    """
    spend_expr = func.sum(func.abs(Transaction.amount))

    # ---- Totals -------------------------------------------------------- #
    spend_stmt = _base_filters(
        select(func.coalesce(spend_expr, 0.0)).where(Transaction.amount < 0),
        account_id, start_date, end_date,
    ).where(_not_transfer())
    income_stmt = _base_filters(
        select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(Transaction.amount > 0),
        account_id, start_date, end_date,
    ).where(_not_transfer())
    count_stmt = _base_filters(
        select(func.count(Transaction.id)), account_id, start_date, end_date
    )

    total_spending = float(db.scalar(spend_stmt) or 0.0)
    total_income = float(db.scalar(income_stmt) or 0.0)
    txn_count = int(db.scalar(count_stmt) or 0)

    # ---- By category (spending only) ----------------------------------- #
    cat_stmt = (
        _base_filters(
            select(
                Transaction.category_id,
                func.coalesce(Category.name, "Uncategorized"),
                Category.color,
                func.sum(func.abs(Transaction.amount)),
                func.count(Transaction.id),
            )
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .where(Transaction.amount < 0),
            account_id, start_date, end_date,
        )
        .group_by(Transaction.category_id)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
    )
    by_category = [
        CategorySpend(
            category_id=row[0],
            category_name=row[1],
            color=row[2],
            total=float(row[3] or 0.0),
            count=int(row[4]),
        )
        for row in db.execute(cat_stmt)
    ]

    # ---- By merchant (spending only) ----------------------------------- #
    merch_stmt = (
        _base_filters(
            select(
                func.coalesce(Transaction.merchant, "Unknown"),
                func.sum(func.abs(Transaction.amount)),
                func.count(Transaction.id),
            ).where(Transaction.amount < 0),
            account_id, start_date, end_date,
        )
        .where(_not_transfer())
        .group_by(func.coalesce(Transaction.merchant, "Unknown"))
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .limit(merchant_limit)
    )
    by_merchant = [
        MerchantSpend(merchant=row[0], total=float(row[1] or 0.0), count=int(row[2]))
        for row in db.execute(merch_stmt)
    ]

    # ---- By month ------------------------------------------------------ #
    month_expr = func.strftime("%Y-%m", Transaction.txn_date)
    month_stmt = (
        _base_filters(
            select(
                month_expr,
                func.coalesce(func.sum(func.abs(Transaction.amount)).filter(Transaction.amount < 0), 0.0),
                func.coalesce(func.sum(Transaction.amount).filter(Transaction.amount > 0), 0.0),
            ).where(_not_transfer()),
            account_id, start_date, end_date,
        )
        .group_by(month_expr)
        .order_by(month_expr)
    )
    by_month = [
        MonthlySpend(month=row[0], spending=float(row[1] or 0.0), income=float(row[2] or 0.0))
        for row in db.execute(month_stmt)
        if row[0] is not None
    ]

    return SummaryOut(
        total_spending=total_spending,
        total_income=total_income,
        net=total_income - total_spending,
        transaction_count=txn_count,
        by_category=by_category,
        by_merchant=by_merchant,
        by_month=by_month,
        start_date=start_date,
        end_date=end_date,
    )


def _not_transfer():
    """Exclude the built-in Transfers category from spend/income aggregates."""
    transfer_sub = select(Category.id).where(Category.name == "Transfers").scalar_subquery()
    return (Transaction.category_id.is_(None)) | (Transaction.category_id != transfer_sub)
