from datetime import timedelta
from sqlalchemy import select, delete, desc, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, Order, Favorite, UserFilter, IngestedPost, ORDER_CATEGORIES, utc_now

class Repository:
    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None = None) -> User:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            trial_end = utc_now() + timedelta(days=3)
            user = User(
                telegram_id=telegram_id,
                username=username,
                trial_used=True,
                subscription_until=trial_end
            )
            session.add(user)
            try:
                await session.flush()
                session.add_all(
                    UserFilter(user_id=user.id, category=category, enabled=True)
                    for category in ORDER_CATEGORIES
                )
                await session.commit()
                await session.refresh(user)
            except IntegrityError:
                await session.rollback()
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = result.scalar_one_or_none()
                if user is None:
                    raise
        if user:
            result = await session.execute(
                select(UserFilter.category).where(UserFilter.user_id == user.id)
            )
            existing_categories = set(result.scalars())
            missing_categories = [category for category in ORDER_CATEGORIES if category not in existing_categories]
            if missing_categories:
                session.add_all(
                    UserFilter(user_id=user.id, category=category, enabled=True)
                    for category in missing_categories
                )
                await session.commit()
        return user

    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def order_exists(session: AsyncSession, hash_id: str) -> bool:
        result = await session.execute(select(Order.id).where(Order.hash_id == hash_id))
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def create_order(
        session: AsyncSession,
        hash_id: str,
        category: str,
        title: str,
        summary: str,
        budget: str | None,
        source_name: str,
        contact_url: str
    ) -> Order | None:
        if await Repository.order_exists(session, hash_id):
            return None

        order = Order(
            hash_id=hash_id,
            category=category,
            title=title,
            summary=summary,
            budget=budget,
            source_name=source_name,
            contact_url=contact_url
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order

    @staticmethod
    async def enqueue_posts(session: AsyncSession, posts: list[dict]) -> int:
        if not posts:
            return 0

        hash_ids = [post["hash_id"] for post in posts]
        existing_orders = await session.execute(
            select(Order.hash_id).where(Order.hash_id.in_(hash_ids))
        )
        existing_ingested = await session.execute(
            select(IngestedPost.hash_id).where(IngestedPost.hash_id.in_(hash_ids))
        )
        known_hashes = set(existing_orders.scalars()) | set(existing_ingested.scalars())
        values = [
            {
                "hash_id": post["hash_id"],
                "title": post.get("title", "")[:500],
                "summary": post.get("summary", ""),
                "raw_text": post.get("raw_text", ""),
                "contact_url": post.get("contact_url", ""),
                "source_name": post.get("source_name", "")[:100],
                "budget": post.get("budget"),
                "status": "pending",
                "attempts": 0,
                "next_attempt_at": utc_now(),
                "created_at": utc_now(),
            }
            for post in posts
            if post["hash_id"] not in known_hashes
        ]
        if not values:
            return 0

        dialect_name = session.get_bind().dialect.name
        if dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        elif dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            raise RuntimeError(f"Unsupported database dialect for ingestion: {dialect_name}")

        statement = insert(IngestedPost).values(values).on_conflict_do_nothing(
            index_elements=[IngestedPost.hash_id]
        )
        result = await session.execute(statement)
        await session.commit()
        return result.rowcount or 0

    @staticmethod
    async def get_pending_posts(
        session: AsyncSession,
        limit: int = 6,
    ) -> list[IngestedPost]:
        result = await session.execute(
            select(IngestedPost)
            .where(
                IngestedPost.status == "pending",
                IngestedPost.next_attempt_at <= utc_now(),
            )
            .order_by(IngestedPost.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def complete_ingested_posts(
        session: AsyncSession,
        posts: list[IngestedPost],
        classifications: dict[int, dict],
    ) -> list[Order]:
        post_ids = [post.id for post in posts]
        result = await session.execute(
            select(IngestedPost)
            .where(IngestedPost.id.in_(post_ids), IngestedPost.status == "pending")
            .with_for_update()
        )
        current_posts = list(result.scalars())
        if len(current_posts) != len(post_ids):
            raise RuntimeError("One or more ingested posts are no longer pending")

        created_orders = []
        for post in current_posts:
            classification = classifications[post.id]
            if classification["category"] == "irrelevant":
                post.status = "processed"
                post.processed_at = utc_now()
                post.last_error = None
                continue
            order = Order(
                hash_id=post.hash_id,
                category=classification["category"],
                title=classification["cleaned_title"][:500],
                summary=classification["summary"],
                budget=classification.get("budget") or post.budget,
                source_name=post.source_name,
                contact_url=post.contact_url,
            )
            session.add(order)
            post.status = "notifying"
            post.last_error = None
            created_orders.append(order)
        await session.commit()
        return created_orders

    @staticmethod
    async def get_pending_notifications(
        session: AsyncSession,
        limit: int = 20,
    ) -> list[tuple[IngestedPost, Order]]:
        result = await session.execute(
            select(IngestedPost, Order)
            .join(Order, Order.hash_id == IngestedPost.hash_id)
            .where(
                IngestedPost.status == "notifying",
                IngestedPost.next_attempt_at <= utc_now(),
            )
            .order_by(IngestedPost.created_at)
            .limit(limit)
        )
        return list(result.all())

    @staticmethod
    async def mark_ingested_posts_notified(session: AsyncSession, post_ids: list[int]) -> None:
        if not post_ids:
            return
        result = await session.execute(
            select(IngestedPost).where(
                IngestedPost.id.in_(post_ids),
                IngestedPost.status == "notifying",
            )
        )
        now = utc_now()
        for post in result.scalars():
            post.status = "processed"
            post.processed_at = now
        await session.commit()

    @staticmethod
    async def defer_ingested_posts(
        session: AsyncSession,
        posts: list[IngestedPost],
        error: str,
    ) -> None:
        now = utc_now()
        for post in posts:
            post.attempts += 1
            delay_seconds = min(3600, 30 * (2 ** min(post.attempts - 1, 7)))
            post.next_attempt_at = now + timedelta(seconds=delay_seconds)
            post.last_error = error[:2000]
        await session.commit()

    @staticmethod
    async def defer_ingested_posts_by_ids(
        session: AsyncSession,
        post_ids: list[int],
        error: str,
    ) -> None:
        if not post_ids:
            return
        result = await session.execute(
            select(IngestedPost).where(
                IngestedPost.id.in_(post_ids),
                IngestedPost.status.in_(("pending", "notifying")),
            )
        )
        await Repository.defer_ingested_posts(session, list(result.scalars()), error)

    @staticmethod
    async def get_recent_orders(
        session: AsyncSession,
        categories: list[str] | None = None,
        limit: int = 5,
        hours: int = 24,
        search: str | None = None,
    ) -> list[Order]:
        since = utc_now() - timedelta(hours=hours)
        stmt = select(Order).where(Order.created_at >= since)
        if categories is not None:
            stmt = stmt.where(Order.category.in_(categories))
        if search:
            term = f"%{search}%"
            stmt = stmt.where(or_(Order.title.ilike(term), Order.summary.ilike(term)))
        stmt = stmt.order_by(desc(Order.created_at)).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_user_filters(session: AsyncSession, user_id: int) -> list[UserFilter]:
        result = await session.execute(select(UserFilter).where(UserFilter.user_id == user_id))
        return list(result.scalars().all())

    @staticmethod
    async def toggle_user_filter(session: AsyncSession, user_id: int, category: str) -> bool:
        result = await session.execute(
            select(UserFilter).where(UserFilter.user_id == user_id, UserFilter.category == category)
        )
        f = result.scalar_one_or_none()
        if f:
            f.enabled = not f.enabled
            await session.commit()
            return f.enabled
        return False

    @staticmethod
    async def set_user_filter(
        session: AsyncSession,
        user_id: int,
        category: str,
        enabled: bool,
        min_budget: float,
        keywords: str | None,
    ) -> UserFilter:
        result = await session.execute(
            select(UserFilter).where(
                UserFilter.user_id == user_id,
                UserFilter.category == category,
            )
        )
        user_filter = result.scalar_one_or_none()
        if user_filter is None:
            user_filter = UserFilter(user_id=user_id, category=category)
            session.add(user_filter)
        user_filter.enabled = enabled
        user_filter.min_budget = min_budget
        user_filter.keywords = keywords
        await session.commit()
        await session.refresh(user_filter)
        return user_filter

    @staticmethod
    async def add_favorite(session: AsyncSession, user_id: int, order_id: int) -> bool:
        existing = await session.execute(
            select(Favorite).where(Favorite.user_id == user_id, Favorite.order_id == order_id)
        )
        if existing.scalar_one_or_none():
            return False
        fav = Favorite(user_id=user_id, order_id=order_id)
        session.add(fav)
        await session.commit()
        return True

    @staticmethod
    async def remove_favorite(session: AsyncSession, user_id: int, order_id: int) -> bool:
        result = await session.execute(
            select(Favorite).where(Favorite.user_id == user_id, Favorite.order_id == order_id)
        )
        fav = result.scalar_one_or_none()
        if fav:
            await session.delete(fav)
            await session.commit()
            return True
        return False

    @staticmethod
    async def get_user_favorites(session: AsyncSession, user_id: int, limit: int = 20) -> list[Order]:
        stmt = (
            select(Order)
            .join(Favorite, Favorite.order_id == Order.id)
            .where(Favorite.user_id == user_id)
            .order_by(desc(Favorite.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_favorite_order_ids(
        session: AsyncSession,
        user_id: int,
        order_ids: list[int],
    ) -> set[int]:
        if not order_ids:
            return set()
        result = await session.execute(
            select(Favorite.order_id).where(
                Favorite.user_id == user_id,
                Favorite.order_id.in_(order_ids),
            )
        )
        return set(result.scalars())

    @staticmethod
    async def delete_old_orders(session: AsyncSession, hours: int = 48) -> int:
        cutoff = utc_now() - timedelta(hours=hours)
        result = await session.execute(delete(Order).where(Order.created_at < cutoff))
        await session.commit()
        return result.rowcount

    @staticmethod
    async def delete_old_ingested_posts(session: AsyncSession, days: int = 7) -> int:
        cutoff = utc_now() - timedelta(days=days)
        result = await session.execute(
            delete(IngestedPost).where(
                or_(
                    and_(
                        IngestedPost.status == "processed",
                        IngestedPost.processed_at < cutoff,
                    ),
                    and_(
                        IngestedPost.status == "notifying",
                        IngestedPost.created_at < cutoff,
                    ),
                )
            )
        )
        await session.commit()
        return result.rowcount or 0
