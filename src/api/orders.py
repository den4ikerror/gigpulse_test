from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.proposal_gen import ProposalGenerationError, ProposalGenerator
from src.api.auth import require_telegram_user
from src.database.models import ORDER_CATEGORIES, Order
from src.database.repository import Repository
from src.database.session import get_db_session
from src.services.order_filters import matches_order_filter

router = APIRouter(prefix="/api/orders", tags=["Orders"])


class ProposalRequest(BaseModel):
    user_skills: str = Field(min_length=2, max_length=2000)

    @field_validator("user_skills")
    @classmethod
    def validate_user_skills(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Provide at least two characters of skills")
        return value


def _order_response(order: Order, is_favorite: bool = False) -> dict:
    return {
        "id": order.id,
        "category": order.category,
        "title": order.title,
        "summary": order.summary,
        "budget": order.budget,
        "source_name": order.source_name,
        "contact_url": order.contact_url,
        "created_at": order.created_at,
        "is_favorite": is_favorite,
    }


@router.get("")
async def get_orders(
    category: str | None = Query(default=None),
    min_budget: float = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    if category and category not in ORDER_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    user = await Repository.get_user_by_telegram_id(session, user_data["id"])
    if user is None:
        user = await Repository.get_or_create_user(
            session,
            user_data["id"],
            user_data.get("username"),
        )
    filters = await Repository.get_user_filters(session, user.id)
    enabled_filters = {
        item.category: item
        for item in filters
        if item.enabled
    }
    if category and category not in enabled_filters:
        return {"orders": []}
    categories = [category] if category else list(enabled_filters)
    requires_client_filter = min_budget > 0 or any(
        item.min_budget > 0 or item.keywords
        for item in enabled_filters.values()
        if item.category in categories
    )
    if requires_client_filter:
        orders = await Repository.get_recent_orders(
            session,
            categories=categories,
            limit=1000,
            hours=24,
            search=search,
        )
        selected = []
        for order in orders:
            user_filter = enabled_filters.get(order.category)
            threshold = max(min_budget, user_filter.min_budget if user_filter else 0)
            if not matches_order_filter(
                order.title,
                order.summary,
                order.budget,
                threshold,
                user_filter.keywords if user_filter else None,
            ):
                continue
            selected.append(order)
        orders = selected[:limit]
    else:
        orders = await Repository.get_recent_orders(
            session,
            categories=categories,
            limit=limit,
            hours=24,
            search=search,
        )
    favorite_ids = await Repository.get_favorite_order_ids(
        session,
        user.id,
        [order.id for order in orders],
    )
    return {
        "orders": [
            _order_response(order, order.id in favorite_ids)
            for order in orders
        ]
    }


@router.get("/favorites")
async def get_favorites(
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    user = await Repository.get_user_by_telegram_id(session, user_data["id"])
    if not user:
        return {"orders": []}
    orders = await Repository.get_user_favorites(session, user.id, limit=100)
    return {"orders": [_order_response(order, True) for order in orders]}


@router.post("/{order_id}/favorite")
async def toggle_favorite(
    order_id: int,
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    user = await Repository.get_user_by_telegram_id(session, user_data["id"])
    if not user:
        user = await Repository.get_or_create_user(
            session,
            user_data["id"],
            user_data.get("username"),
        )

    if not await session.get(Order, order_id):
        raise HTTPException(status_code=404, detail="Order not found")
    added = await Repository.add_favorite(session, user.id, order_id)
    if not added:
        await Repository.remove_favorite(session, user.id, order_id)
    return {"favorited": added}


@router.post("/{order_id}/proposal")
async def generate_proposal(
    order_id: int,
    payload: ProposalRequest,
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        proposal = await ProposalGenerator.generate(
            payload.user_skills.strip(),
            order.title,
            order.summary,
        )
    except ProposalGenerationError as error:
        raise HTTPException(status_code=503, detail="AI proposal service is unavailable") from error
    return {"proposal": proposal}
