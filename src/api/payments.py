from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db_session
from src.database.repository import Repository
from src.database.models import Subscription, Payment
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/payments", tags=["Payments"])

@router.post("/webhook/monobank")
async def monobank_webhook(request: Request, session: AsyncSession = Depends(get_db_session)):
    body = await request.json()
    # Handle Monobank webhook event
    return {"status": "ok"}

@router.post("/webhook/wayforpay")
async def wayforpay_webhook(request: Request, session: AsyncSession = Depends(get_db_session)):
    body = await request.json()
    # Handle WayForPay webhook event
    return {"status": "ok"}
