import re
from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")

Category = Literal["savings", "credit_card", "loan", "investment"]
Status = Literal["active", "pending", "closed"]


class Envelope(BaseModel, Generic[T]):
    """Every successful response uses this shape."""

    success: bool = True
    data: T
    message: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain at least one letter and one number")
        return v

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProductOut(BaseModel):
    id: int
    category: Category
    name: str
    status: Status
    opened_at: date
    balance: float  # headline amount used for sorting
    masked_number: str | None = None
    details: dict[str, Any]
    metadata: dict[str, Any] | None = None


class TransactionOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    txn_type: Literal["credit", "debit"]
    amount: float
    description: str
    created_at: datetime


class ApplicationCreate(BaseModel):
    category: Category
    product_name: str = Field(min_length=2, max_length=120)
    requested_amount: float | None = Field(default=None, gt=0, le=100_000_000)
    notes: str | None = Field(default=None, max_length=500)


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: Category
    product_name: str
    requested_amount: float | None
    notes: str | None
    status: str
    created_at: datetime


class DashboardStats(BaseModel):
    total_products: int
    active_products: int
    pending_applications: int
    total_balance: float
    portfolio: list[dict[str, Any]]
    cashflow: list[dict[str, Any]]
