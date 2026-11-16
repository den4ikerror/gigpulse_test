from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Text, DateTime, Boolean, Float, ForeignKey, Integer, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

ORDER_CATEGORY_LABELS = {
    "graphic_design": "Графічний дизайн",
    "web_uiux_design": "Веб-дизайн та UI/UX",
    "other_design": "Інший дизайн",
    "copywriting": "Копірайтинг і тексти",
    "smm_social": "SMM і соцмережі",
    "video_editing": "Відеомонтаж",
    "frontend_backend": "Frontend / Backend розробка",
    "chatbots": "Створення чат-ботів",
    "3d_visualization": "3D і візуалізація",
    "logo_branding": "Логотипи та брендинг",
    "pr_influencers": "PR і блогери",
    "mobile_apps": "Розробка мобільних застосунків",
    "wordpress_cms": "WordPress та CMS",
    "qa_testing": "QA і тестування",
    "ai_data_automation": "AI, дані й автоматизація",
    "seo": "SEO",
    "targeted_ads": "Таргетована реклама",
    "translation": "Переклад",
    "photo_editing": "Фото та обробка фото",
    "audio_voiceover": "Аудіо та озвучення",
    "virtual_assistance": "Віртуальна допомога та адміністрування",
}
ORDER_CATEGORIES = tuple(ORDER_CATEGORY_LABELS)
ORDER_CATEGORY_DESCRIPTIONS = {
    "graphic_design": "графічні матеріали, ілюстрації, банери та поліграфія",
    "web_uiux_design": "дизайн сайтів і вебзастосунків, UX-дослідження та інтерфейси",
    "other_design": "дизайнерські завдання, що не підходять до інших дизайн-категорій",
    "copywriting": "написання, редагування та підготовка текстів",
    "smm_social": "ведення соцмереж і розвиток спільнот, крім окремих рекламних кампаній",
    "video_editing": "монтаж і постпродакшн відео",
    "frontend_backend": "розробка сайтів, вебзастосунків, frontend, backend та API",
    "chatbots": "розробка або доробка Telegram-ботів та інших чат-ботів",
    "3d_visualization": "3D-моделювання, рендеринг і візуалізація",
    "logo_branding": "розробка логотипів, айдентики та брендингу",
    "pr_influencers": "PR-кампанії, зв'язки з медіа та інтеграції з блогерами",
    "mobile_apps": "розробка застосунків для iOS, Android та кросплатформних мобільних систем",
    "wordpress_cms": "створення та налаштування сайтів на WordPress та інших CMS",
    "qa_testing": "ручне або автоматизоване тестування програмного забезпечення",
    "ai_data_automation": "розробка AI-рішень, обробка даних, скрипти та бізнес-автоматизація",
    "seo": "технічна або контентна SEO-оптимізація та пошукове просування",
    "targeted_ads": "налаштування й оптимізація платної таргетованої реклами",
    "translation": "переклад і локалізація текстів або матеріалів",
    "photo_editing": "фотозйомка, ретуш та обробка фотографій",
    "audio_voiceover": "озвучення, запис голосу, аудіомонтаж і звук",
    "virtual_assistance": "віддалена адміністративна, операційна та віртуальна допомога",
}
EXCLUDED_ORDER_SOURCES = ("dou jobs",)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="uk")
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    filters: Mapped[list["UserFilter"]] = relationship("UserFilter", back_populates="user", cascade="all, delete-orphan")
    favorites: Mapped[list["Favorite"]] = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hash_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_name: Mapped[str] = mapped_column(String(100))
    contact_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    favorites: Mapped[list["Favorite"]] = relationship("Favorite", back_populates="order", cascade="all, delete-orphan")

class UserFilter(Base):
    __tablename__ = "user_filters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(50))
    min_budget: Mapped[float] = mapped_column(Float, default=0.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="filters")

class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="favorites")
    order: Mapped["Order"] = relationship("Order", back_populates="favorites")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan_name: Mapped[str] = mapped_column(String(50)) # e.g. "PRO"
    status: Mapped[str] = mapped_column(String(20), default="active") # active, expired, cancelled
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="UAH")
    provider: Mapped[str] = mapped_column(String(50)) # monobank, wayforpay, telegram_stars
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending, success, failed
    payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="payments")

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(50)) # rss, telegram, reddit
    url: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class IngestedPost(Base):
    __tablename__ = "ingested_posts"
    __table_args__ = (
        Index("ix_ingested_posts_status_next_attempt", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hash_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    contact_url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(100))
    budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
