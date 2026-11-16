from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_telegram_user
from src.database.models import ORDER_CATEGORIES
from src.database.repository import Repository
from src.database.session import get_db_session

router = APIRouter(prefix="/api/user", tags=["User"])


class FilterUpdate(BaseModel):
    category: str
    enabled: bool | None = None
    min_budget: float = Field(default=0, ge=0)
    keywords: str | None = Field(default=None, max_length=500)


async def _get_user(session: AsyncSession, user_data: dict):
    user = await Repository.get_user_by_telegram_id(session, user_data["id"])
    if user is None:
        user = await Repository.get_or_create_user(
            session,
            user_data["id"],
            user_data.get("username"),
        )
    return user


@router.get("/profile")
async def get_profile(
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _get_user(session, user_data)
    filters = await Repository.get_user_filters(session, user.id)
    return {
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "language": user.language,
            "trial_used": user.trial_used,
            "subscription_until": user.subscription_until,
        },
        "filters": [
            {
                "category": item.category,
                "enabled": item.enabled,
                "min_budget": item.min_budget,
                "keywords": item.keywords,
            }
            for item in filters
        ],
    }


@router.get("/filters")
async def get_filters(
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _get_user(session, user_data)
    filters = await Repository.get_user_filters(session, user.id)
    return {
        "filters": [
            {
                "category": item.category,
                "enabled": item.enabled,
                "min_budget": item.min_budget,
                "keywords": item.keywords,
            }
            for item in filters
        ]
    }


@router.put("/filters")
async def update_filter(
    payload: FilterUpdate,
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    if payload.category not in ORDER_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    user = await _get_user(session, user_data)
    current = {
        item.category: item
        for item in await Repository.get_user_filters(session, user.id)
    }.get(payload.category)
    updated = await Repository.set_user_filter(
        session,
        user.id,
        payload.category,
        payload.enabled if payload.enabled is not None else (current.enabled if current else True),
        payload.min_budget,
        payload.keywords.strip() if payload.keywords and payload.keywords.strip() else None,
    )
    return {
        "category": updated.category,
        "enabled": updated.enabled,
        "min_budget": updated.min_budget,
        "keywords": updated.keywords,
    }


@router.post("/filters/toggle")
async def toggle_filter(
    payload: FilterUpdate,
    user_data: dict = Depends(require_telegram_user),
    session: AsyncSession = Depends(get_db_session),
):
    if payload.category not in ORDER_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    user = await _get_user(session, user_data)
    new_state = await Repository.toggle_user_filter(session, user.id, payload.category)
    return {"category": payload.category, "enabled": new_state}
