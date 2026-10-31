"""Mock banking data for demonstration. No real accounts or payments are involved."""
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.mongo import mongo
from app.models import (
    BankingProduct,
    CreditCard,
    Investment,
    Loan,
    ProductApplication,
    SavingsAccount,
    Transaction,
    User,
)

DEMO_EMAIL, DEMO_PASSWORD = "demo@bank.com", "Demo@1234"
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@bank.com", "Admin@1234"

PRODUCT_METADATA = {
    "savings": {
        "features": ["Zero monthly fees", "Free debit card", "Interest paid monthly"],
        "minimum_balance": 1000,
        "withdrawals_per_month": "Unlimited",
    },
    "credit_card": {
        "features": ["1.5% cashback on dining", "Airport lounge access", "Contactless payments"],
        "annual_fee": 999,
        "interest_free_days": 45,
    },
    "loan": {
        "features": ["No prepayment charges after 12 months", "Flexible tenure", "Paperless approval"],
        "processing_fee_percent": 1.0,
        "max_tenure_months": 60,
    },
    "investment": {
        "features": ["Diversified equity and debt mix", "Quarterly statements", "Exit at any time"],
        "risk_level": "Moderate",
        "benchmark": "Mock Balanced Index",
    },
}


def seed_metadata() -> None:
    for category, doc in PRODUCT_METADATA.items():
        mongo.upsert("product_metadata", {"category": category}, doc)


def _txns(db: Session, user_id: int, product_id: int, rng: random.Random, rows: list[tuple]) -> None:
    now = datetime.now(timezone.utc)
    for description, kind, low, high in rows:
        for _ in range(rng.randint(2, 4)):
            db.add(
                Transaction(
                    user_id=user_id,
                    product_id=product_id,
                    txn_type=kind,
                    amount=round(rng.uniform(low, high), 2),
                    description=description,
                    created_at=now - timedelta(days=rng.randint(0, 170), hours=rng.randint(0, 23)),
                )
            )


def seed_demo_data(db: Session) -> None:
    if db.scalars(select(User.id).limit(1)).first():
        return
    rng = random.Random(42)  # deterministic demo data
    today = date.today()

    demo = User(email=DEMO_EMAIL, full_name="Asha Kumar", hashed_password=hash_password(DEMO_PASSWORD))
    admin = User(
        email=ADMIN_EMAIL, full_name="Bank Admin", hashed_password=hash_password(ADMIN_PASSWORD), role="admin"
    )
    db.add_all([demo, admin])
    db.flush()

    def product(category: str, name: str, status: str, days_ago: int) -> BankingProduct:
        p = BankingProduct(
            user_id=demo.id, category=category, name=name, status=status, opened_at=today - timedelta(days=days_ago)
        )
        db.add(p)
        db.flush()
        return p

    s1 = product("savings", "Premier Savings Account", "active", 900)
    db.add(SavingsAccount(product_id=s1.id, account_number="50100234567891", balance=125430.50, interest_rate=3.50))
    s2 = product("savings", "Goal Saver", "active", 300)
    db.add(SavingsAccount(product_id=s2.id, account_number="50100998877665", balance=48200.00, interest_rate=4.10))
    s3 = product("savings", "Student Savings Account", "closed", 1500)
    db.add(SavingsAccount(product_id=s3.id, account_number="50100112233445", balance=0, interest_rate=2.75))

    c1 = product("credit_card", "Platinum Rewards Card", "active", 600)
    db.add(CreditCard(product_id=c1.id, card_number="4539871200123456", credit_limit=200000, outstanding_amount=45200))
    c2 = product("credit_card", "Travel Elite Card", "pending", 5)
    db.add(CreditCard(product_id=c2.id, card_number="5412750098761234", credit_limit=300000, outstanding_amount=0))

    l1 = product("loan", "Home Renovation Personal Loan", "active", 420)
    db.add(
        Loan(
            product_id=l1.id,
            loan_amount=500000,
            interest_rate=10.5,
            emi_amount=16100,
            next_due_date=today + timedelta(days=12),
            tenure_months=36,
        )
    )
    l2 = product("loan", "Education Loan", "closed", 1800)
    db.add(Loan(product_id=l2.id, loan_amount=250000, interest_rate=9.0, emi_amount=0, tenure_months=48))

    i1 = product("investment", "Balanced Growth Portfolio", "active", 700)
    db.add(Investment(product_id=i1.id, invested_amount=300000, current_value=342500))
    i2 = product("investment", "Gold Savings Plan", "active", 200)
    db.add(Investment(product_id=i2.id, invested_amount=50000, current_value=48750))

    db.add(
        ProductApplication(
            user_id=demo.id, category="loan", product_name="Vehicle Loan", requested_amount=800000, status="pending"
        )
    )

    _txns(db, demo.id, s1.id, rng, [
        ("Salary credit", "credit", 60000, 75000),
        ("Utility bill payment", "debit", 1500, 6000),
        ("Rent transfer", "debit", 18000, 22000),
        ("Interest credit", "credit", 300, 420),
    ])
    _txns(db, demo.id, s2.id, rng, [("Monthly goal deposit", "credit", 5000, 10000)])
    _txns(db, demo.id, c1.id, rng, [
        ("Restaurant purchase", "debit", 800, 4500),
        ("Online shopping", "debit", 1500, 12000),
        ("Card bill payment", "credit", 8000, 30000),
    ])
    _txns(db, demo.id, l1.id, rng, [("EMI payment", "debit", 16100, 16100)])
    _txns(db, demo.id, i1.id, rng, [("SIP instalment", "debit", 10000, 10000)])
    db.commit()
