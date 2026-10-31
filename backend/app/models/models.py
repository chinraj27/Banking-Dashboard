from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="customer")  # customer | admin
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    products: Mapped[list["BankingProduct"]] = relationship(back_populates="user")


class BankingProduct(Base):
    __tablename__ = "banking_products"
    __table_args__ = (Index("ix_products_user_category", "user_id", "category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)  # savings|credit_card|loan|investment
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    opened_at: Mapped[date] = mapped_column(Date, default=date.today)

    user: Mapped[User] = relationship(back_populates="products")
    savings: Mapped[Optional["SavingsAccount"]] = relationship(
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    card: Mapped[Optional["CreditCard"]] = relationship(
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    loan: Mapped[Optional["Loan"]] = relationship(
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    investment: Mapped[Optional["Investment"]] = relationship(
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )


class SavingsAccount(Base):
    __tablename__ = "savings_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("banking_products.id", ondelete="CASCADE"), unique=True
    )
    account_number: Mapped[str] = mapped_column(String(20))
    balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    interest_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    product: Mapped[BankingProduct] = relationship(back_populates="savings")


class CreditCard(Base):
    __tablename__ = "credit_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("banking_products.id", ondelete="CASCADE"), unique=True
    )
    card_number: Mapped[str] = mapped_column(String(19))
    credit_limit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    product: Mapped[BankingProduct] = relationship(back_populates="card")


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("banking_products.id", ondelete="CASCADE"), unique=True
    )
    loan_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    interest_rate: Mapped[float] = mapped_column(Numeric(5, 2))
    emi_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tenure_months: Mapped[int] = mapped_column(default=12)

    product: Mapped[BankingProduct] = relationship(back_populates="loan")


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("banking_products.id", ondelete="CASCADE"), unique=True
    )
    invested_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    current_value: Mapped[float] = mapped_column(Numeric(14, 2))

    product: Mapped[BankingProduct] = relationship(back_populates="investment")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_txn_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(
        ForeignKey("banking_products.id", ondelete="CASCADE"), index=True
    )
    txn_type: Mapped[str] = mapped_column(String(10))  # credit | debit
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[BankingProduct] = relationship()


class ProductApplication(Base):
    __tablename__ = "product_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    product_name: Mapped[str] = mapped_column(String(120))
    requested_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
