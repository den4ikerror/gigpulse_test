# GigPulse

GigPulse aggregates freelance listings from RSS feeds and optional public Telegram channels, classifies them, stores them, and notifies Telegram bot users based on their selected categories.

## Phase 1 status and operation

1. The RSS poller fetches Freelancehunt and DOU feeds every 60 seconds. The optional Telethon user client listens to the channels configured in `TG_CHANNELS`.
2. The batcher groups six posts or flushes after 10 seconds, then persists them in the database before AI processing.
3. A persistent ingestion queue deduplicates posts by normalized text and contact URL. AI and Telegram delivery failures retain posts for exponential-backoff retries instead of dropping them.
4. Gemini is tried with configured keys and models; Groq is the fallback. The classifier can reject unrelated posts instead of forcing them into one of the supported categories; only relevant classifications become orders.
5. The bot creates a user on `/start`, enables category filters, shows recent listings, and sends new matching listings. A cleanup worker deletes orders older than 48 hours.

Payment processing remains Phase 3.

## Phase 2: Telegram Mini App

The Mini App exposes the 24-hour order feed, category/search/budget filters, favorites, profile, and AI proposal generation. API requests require a valid, unexpired Telegram Web App `initData` signature; debug mode does not bypass authentication.

Deploy the static `webapp/` over HTTPS, set `WEBAPP_URL` in `.env`, restart the bot, then open the Mini App using its button in `/start`. Telegram Web Apps require HTTPS; a local `http://localhost` address is not a valid production URL.

The proposal generator uses the configured Gemini models/keys and then Groq. Set `GROQ_MODEL` to a model available to your Groq account. If providers fail, the API reports a service error rather than returning a fabricated proposal.

## Setup

Requires Python 3.12+.

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

- `TELEGRAM_BOT_TOKEN` from @BotFather.
- `WEBAPP_URL` to the public HTTPS address serving `webapp/` (required to display its launch button in the bot).
- At least one of `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, or `GROQ_API_KEY`.
- Optional Telethon user-account settings: `TG_API_ID`, `TG_API_HASH`, and `TG_CHANNELS`. Keep this parser disabled by leaving the API credentials blank if you do not need channel ingestion.

Do not commit `.env`, Telegram session files, or API credentials.

Apply database migrations and run the app:

```bash
./venv/bin/python -m alembic upgrade head
./venv/bin/python main.py
```

If the bot cannot connect to Telegram, verify DNS/network access to `api.telegram.org`. When it reports `Run polling for bot @...`, send `/start` to that exact bot in a private chat. A user must start the bot before Telegram permits the bot to send them notifications.

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## Runtime notes

- The API/static site runs on `http://localhost:8000` by default.
- Database tables are also created at startup for local convenience; Alembic migrations are the schema-change source of truth.
- Gemini model names can change or vary by account. Set `GEMINI_MODEL` and optionally comma-separated `GEMINI_FALLBACK_MODELS` to models enabled for your API key.
- The Groq model shown in `.env.example` may not be enabled for every account; configure `GROQ_MODEL` to an active model shown in your Groq console.
- Telegram channel parsing uses a Telethon user session, not the bot token. The first sign-in should be performed only on a trusted local machine.
