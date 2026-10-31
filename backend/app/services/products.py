from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.masking import mask_number
from app.database.mongo import mongo
from app.models import BankingProduct, ProductApplication, Transaction


def _f(value) -> float:
    return float(value) if value is not None else 0.0


def serialize_product(p: BankingProduct, with_metadata: bool = False) -> dict:
    """Flatten a product + its category row into one API shape. Numbers are always masked."""
    if p.category == "savings" and p.savings:
        s = p.savings
        balance, masked = _f(s.balance), mask_number(s.account_number)
        details = {
            "account_number": masked,
            "available_balance": balance,
            "interest_rate": _f(s.interest_rate),
        }
    elif p.category == "credit_card" and p.card:
        c = p.card
        limit, owed = _f(c.credit_limit), _f(c.outstanding_amount)
        balance, masked = owed, mask_number(c.card_number)
        details = {
            "card_number": masked,
            "credit_limit": limit,
            "available_credit": max(limit - owed, 0),
            "outstanding_amount": owed,
        }
    elif p.category == "loan" and p.loan:
        ln = p.loan
        balance, masked = _f(ln.loan_amount), None
        details = {
            "loan_amount": balance,
            "interest_rate": _f(ln.interest_rate),
            "emi_amount": _f(ln.emi_amount),
            "next_due_date": ln.next_due_date.isoformat() if ln.next_due_date else None,
            "tenure_months": ln.tenure_months,
        }
    elif p.category == "investment" and p.investment:
        inv = p.investment
        invested, current = _f(inv.invested_amount), _f(inv.current_value)
        returns = round((current - invested) / invested * 100, 2) if invested else 0.0
        balance, masked = current, None
        details = {
            "investment_amount": invested,
            "current_value": current,
            "returns_percent": returns,
        }
    else:
        balance, masked, details = 0.0, None, {}

    out = {
        "id": p.id,
        "category": p.category,
        "name": p.name,
        "status": p.status,
        "opened_at": p.opened_at.isoformat(),
        "balance": balance,
        "masked_number": masked,
        "details": details,
        "metadata": None,
    }
    if with_metadata:
        meta = mongo.get("product_metadata", {"category": p.category})
        if meta:
            out["metadata"] = {k: v for k, v in meta.items() if k not in ("category", "ts", "_id")}
    return out


def _product_query(user_id: int):
    return (
        select(BankingProduct)
        .where(BankingProduct.user_id == user_id)
        .options(
            selectinload(BankingProduct.savings),
            selectinload(BankingProduct.card),
            selectinload(BankingProduct.loan),
            selectinload(BankingProduct.investment),
        )
    )


def list_products(
    db: Session,
    user_id: int,
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = "date",
    order: str = "desc",
) -> list[dict]:
    q = _product_query(user_id)
    if category:
        q = q.where(BankingProduct.category == category)
    if status:
        q = q.where(BankingProduct.status == status)
    if search:
        # parameterised LIKE: SQLAlchemy binds the value, so there is no SQL injection risk
        q = q.where(BankingProduct.name.ilike(f"%{search.strip()}%"))
    items = [serialize_product(p) for p in db.scalars(q).all()]
    key = (lambda x: x["balance"]) if sort_by == "balance" else (lambda x: (x["opened_at"], x["id"]))
    return sorted(items, key=key, reverse=(order == "desc"))


def get_product(db: Session, user_id: int, product_id: int) -> BankingProduct | None:
    return db.scalars(_product_query(user_id).where(BankingProduct.id == product_id)).first()


def list_transactions(
    db: Session,
    user_id: int,
    product_id: int | None = None,
    txn_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    q = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .options(selectinload(Transaction.product))
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if product_id:
        q = q.where(Transaction.product_id == product_id)
    if txn_type:
        q = q.where(Transaction.txn_type == txn_type)
    return [
        {
            "id": t.id,
            "product_id": t.product_id,
            "product_name": t.product.name,
            "txn_type": t.txn_type,
            "amount": _f(t.amount),
            "description": t.description,
            "created_at": t.created_at,
        }
        for t in db.scalars(q).all()
    ]


def dashboard_stats(db: Session, user_id: int) -> dict:
    products = [serialize_product(p) for p in db.scalars(_product_query(user_id)).all()]
    pending_apps = len(
        db.scalars(
            select(ProductApplication.id).where(
                ProductApplication.user_id == user_id, ProductApplication.status == "pending"
            )
        ).all()
    )
    total_balance = sum(p["balance"] for p in products if p["category"] == "savings" and p["status"] == "active")

    # value of each category, shown as the portfolio breakdown chart
    by_cat: dict[str, float] = defaultdict(float)
    for p in products:
        if p["status"] == "active":
            by_cat[p["category"]] += p["balance"]
    portfolio = [{"category": c, "value": round(v, 2)} for c, v in by_cat.items()]

    # last six calendar months of credits vs debits
    now = datetime.now(timezone.utc)
    months = []
    y, m = now.year, now.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    buckets = {mk: {"month": datetime(mk[0], mk[1], 1).strftime("%b"), "credit": 0.0, "debit": 0.0} for mk in months}
    for t in db.scalars(select(Transaction).where(Transaction.user_id == user_id)).all():
        mk = (t.created_at.year, t.created_at.month)
        if mk in buckets:
            buckets[mk][t.txn_type] += _f(t.amount)
    cashflow = [{**b, "credit": round(b["credit"], 2), "debit": round(b["debit"], 2)} for b in buckets.values()]

    return {
        "total_products": len(products),
        "active_products": sum(1 for p in products if p["status"] == "active"),
        "pending_applications": pending_apps,
        "total_balance": round(total_balance, 2),
        "portfolio": portfolio,
        "cashflow": cashflow,
    }
