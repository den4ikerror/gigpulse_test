from dataclasses import dataclass
from datetime import timedelta
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Subscription, User, utc_now


@dataclass(frozen=True)
class WheelPrize:
    key: str
    label: str
    probability_basis_points: int
    contacts: int = 0
    subscription_days: int = 0


WHEEL_PRIZES = (
    WheelPrize("contacts_3", "+3 відкриття контактів", 4500, contacts=3),
    WheelPrize("contacts_5", "+5 відкриттів контактів", 3000, contacts=5),
    WheelPrize("contacts_10", "+10 відкриттів контактів", 1500, contacts=10),
    WheelPrize("subscription_1d", "Безліміт на 1 день", 500, subscription_days=1),
    WheelPrize("subscription_3d", "Безліміт на 3 дні", 300, subscription_days=3),
    WheelPrize("subscription_7d", "Безліміт на 7 днів", 150, subscription_days=7),
    WheelPrize("subscription_30d", "Безліміт на 1 місяць", 49, subscription_days=30),
    WheelPrize("subscription_365d", "Безліміт на 1 рік", 1, subscription_days=365),
)

assert sum(prize.probability_basis_points for prize in WHEEL_PRIZES) == 10_000


def choose_wheel_prize() -> WheelPrize:
    draw = secrets.randbelow(10_000)
    cumulative = 0
    for prize in WHEEL_PRIZES:
        cumulative += prize.probability_basis_points
        if draw < cumulative:
            return prize
    raise RuntimeError("Wheel prize probabilities do not cover the full draw range")


async def spin_wheel(session: AsyncSession, user: User) -> tuple[WheelPrize, int] | None:
    now = utc_now()
    locked_user = await session.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    )
    if locked_user is None:
        raise RuntimeError("User disappeared while spinning the reward wheel")
    if locked_user.wheel_next_spin_at > now:
        await session.rollback()
        return None

    prize = choose_wheel_prize()
    subscription_days_added = 0
    if prize.contacts:
        locked_user.contact_credits += prize.contacts
    elif prize.subscription_days:
        subscription_until = max(locked_user.subscription_until or now, now)
        locked_user.subscription_until = subscription_until + timedelta(days=prize.subscription_days)
        locked_user.trial_used = True
        subscription_days_added = prize.subscription_days
        session.add(Subscription(
            user_id=locked_user.id,
            plan_name=f"wheel_{prize.subscription_days}d",
            status="active",
            expires_at=locked_user.subscription_until,
        ))

    locked_user.wheel_next_spin_at = now + timedelta(days=20)
    await session.commit()
    return prize, subscription_days_added
