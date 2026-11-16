from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./gigpulse.db"
    DEBUG: bool = False
    PORT: int = 8000

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_INIT_DATA_MAX_AGE_SECONDS: int = Field(default=86400, gt=0)
    WEBAPP_URL: str | None = None

    TG_API_ID: int | None = None
    TG_API_HASH: str | None = None
    TG_SESSION_NAME: str = "gigpulse_userbot"
    TG_CHANNELS: str = "freelance_ukraine,it_jobs_ua,freelance_cabin"

    GEMINI_API_KEY_1: str | None = None
    GEMINI_API_KEY_2: str | None = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_FALLBACK_MODELS: str = ""
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    MONOBANK_TOKEN: str | None = None
    WAYFORPAY_MERCHANT_LOGIN: str | None = None
    WAYFORPAY_MERCHANT_SECRET: str | None = None
    TELEGRAM_PROVIDER_TOKEN: str | None = None

    @field_validator("TG_API_ID", mode="before")
    @classmethod
    def parse_tg_api_id(cls, v):
        if v == "" or v is None:
            return None
        return int(v)

    @field_validator("WEBAPP_URL")
    @classmethod
    def validate_webapp_url(cls, value):
        if value:
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("WEBAPP_URL must be an absolute HTTPS URL")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
