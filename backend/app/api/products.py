from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.database.mongo import log_activity, log_audit, mongo
from app.database.postgres import get_db
from app.database.redis_client import cache
from app.models import ProductApplication, User
from app.schemas.schemas import (
    ApplicationCreate,
    ApplicationOut,
    Category,
    DashboardStats,
    Envelope,
    ProductOut,
    Status,
    TransactionOut,
)
from app.services import products as svc

router = APIRouter()

# ---------- products ----------


@router.get("/products", response_model=Envelope[list[ProductOut]], tags=["Products"])
def list_products(
    category: Category | None = None,
    status_: Status | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=100),
    sort_by: Literal["date", "balance"] = "date",
    order: Literal["asc", "desc"] = "desc",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = f"u{user.id}:products:{category}:{status_}:{search}:{sort_by}:{order}"
    data = cache.get_json(key)
    if data is None:
        data = svc.list_products(db, user.id, category, status_, search, sort_by, order)
        cache.set_json(key, data)
    return {"data": data}


@router.get("/products/category/{category}", response_model=Envelope[list[ProductOut]], tags=["Products"])
def products_by_category(
    category: Category,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"data": svc.list_products(db, user.id, category=category)}


@router.get("/products/{product_id}", response_model=Envelope[ProductOut], tags=["Products"])
def product_detail(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = svc.get_product(db, user.id, product_id)
    if product is None:  # also hides other customers' products
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    log_activity(user.id, "view_product", product_id=product_id)
    return {"data": svc.serialize_product(product, with_metadata=True)}


# ---------- applications ----------


@router.post(
    "/applications", response_model=Envelope[ApplicationOut], status_code=status.HTTP_201_CREATED, tags=["Applications"]
)
def submit_application(
    payload: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = ProductApplication(user_id=user.id, **payload.model_dump())
    db.add(app)
    db.commit()
    cache.delete_prefix(f"u{user.id}:")  # dashboard numbers changed
    log_audit(user.id, "application_submitted", application_id=app.id, category=payload.category)
    return {"data": app, "message": "Application submitted"}


@router.get("/applications", response_model=Envelope[list[ApplicationOut]], tags=["Applications"])
def my_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ProductApplication)
        .where(ProductApplication.user_id == user.id)
        .order_by(ProductApplication.created_at.desc())
    ).all()
    return {"data": rows}


# ---------- dashboard / transactions / activity ----------


@router.get("/dashboard/stats", response_model=Envelope[DashboardStats], tags=["Dashboard"])
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    key = f"u{user.id}:stats"
    data = cache.get_json(key)
    if data is None:
        data = svc.dashboard_stats(db, user.id)
        cache.set_json(key, data)
    return {"data": data}


@router.get("/transactions", response_model=Envelope[list[TransactionOut]], tags=["Transactions"])
def transactions(
    product_id: int | None = None,
    txn_type: Literal["credit", "debit"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"data": svc.list_transactions(db, user.id, product_id, txn_type, limit, offset)}


@router.get("/activity", response_model=Envelope[list[dict]], tags=["Activity"])
def my_activity(user: User = Depends(get_current_user)):
    return {"data": mongo.recent("activity_logs", {"user_id": user.id}, limit=20)}


# ---------- admin (RBAC) ----------


@router.get("/admin/users", tags=["Admin"])
def admin_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    return {
        "success": True,
        "data": [
            {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active}
            for u in users
        ],
    }
