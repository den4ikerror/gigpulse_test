import asyncio
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.ai.batcher import Batcher
from src.ai.groq_chat import create_chat_completion
from src.ai.llm_router import ClassificationError, LLMRouter
from src.ai.prefilter import PreFilter
from src.database.models import Base, IngestedPost, ORDER_CATEGORIES, utc_now
from src.database.repository import Repository


class PrefilterTests(unittest.TestCase):
    def test_hash_is_normalized_and_spam_is_filtered(self):
        prefilter = PreFilter()
        self.assertEqual(
            prefilter.get_hash("  Need   a WEB site ", "HTTPS://example.com"),
            prefilter.get_hash("need a web site", "https://example.com"),
        )
        self.assertTrue(prefilter.is_spam("Шукаю роботу frontend developer"))
        self.assertFalse(prefilter.is_spam("Потрібно розробити frontend сайт"))


class ClassificationTests(unittest.TestCase):
    def test_parses_valid_array_and_object_responses(self):
        expected = [{
            "index": 0,
            "category": "web_dev",
            "cleaned_title": "Website",
            "summary": "Build a website",
            "budget": None,
        }]
        array = LLMRouter._parse_json_response(
            '[{"index":0,"category":"web_dev","cleaned_title":"Website","summary":"Build a website","budget":null}]',
            1,
        )
        wrapped = LLMRouter._parse_json_response(
            '{"orders":[{"index":0,"category":"web_dev","cleaned_title":"Website","summary":"Build a website","budget":null}]}',
            1,
        )
        self.assertEqual(array, expected)
        self.assertEqual(wrapped, expected)

    def test_accepts_irrelevant_items_without_fabricating_a_category(self):
        parsed = LLMRouter._parse_json_response(
            '{"orders":[{"index":0,"category":"irrelevant"}]}',
            1,
        )
        self.assertEqual(parsed, [{"index": 0, "category": "irrelevant"}])

    def test_rejects_incomplete_or_invalid_classifications(self):
        with self.assertRaises(ClassificationError):
            LLMRouter._parse_json_response(
                '[{"index":0,"category":"not-a-category","cleaned_title":"x","summary":"y"}]',
                1,
            )
        with self.assertRaises(ClassificationError):
            LLMRouter._parse_json_response("[]", 1)


class GroqModelSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_available_models_and_skips_non_chat_models(self):
        response = object()
        client = SimpleNamespace(
            models=SimpleNamespace(list=AsyncMock(return_value=SimpleNamespace(data=[
                SimpleNamespace(id="whisper-large-v3"),
                SimpleNamespace(id="openai/gpt-oss-20b"),
            ]))),
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=response),
            )),
        )

        result = await create_chat_completion(
            client,
            messages=[{"role": "user", "content": "test"}],
        )

        self.assertIs(result, response)
        client.chat.completions.create.assert_awaited_once_with(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": "test"}],
        )

    async def test_tries_another_available_model_when_first_is_rejected(self):
        response = object()

        async def complete(*, model, **kwargs):
            if model == "model-a":
                raise RuntimeError("model unavailable")
            return response

        client = SimpleNamespace(
            models=SimpleNamespace(list=AsyncMock(return_value=SimpleNamespace(data=[
                SimpleNamespace(id="model-a"),
                SimpleNamespace(id="model-b"),
            ]))),
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(side_effect=complete),
            )),
        )

        result = await create_chat_completion(client, messages=[])

        self.assertIs(result, response)
        self.assertEqual(client.chat.completions.create.await_count, 2)


class BatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_flushes_partial_batch(self):
        batches = []
        batcher = Batcher(callback=lambda batch: self._capture(batches, batch), batch_size=3)
        await batcher.add({"id": 1})
        await batcher.add({"id": 2})
        await batcher.close()
        self.assertEqual(batches, [[{"id": 1}, {"id": 2}]])

    async def test_persistence_callback_retries(self):
        calls = 0
        persisted = []

        async def persist(batch):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("temporary database failure")
            persisted.extend(batch)

        batcher = Batcher(callback=persist, batch_size=1)
        await batcher.add({"id": 1})
        await asyncio.sleep(1.05)
        await batcher.close()
        self.assertEqual(calls, 2)
        self.assertEqual(persisted, [{"id": 1}])

    @staticmethod
    async def _capture(destination, batch):
        destination.append(batch)


class IngestionRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_queue_is_deduplicated_and_completion_is_atomic(self):
        post = {
            "hash_id": "a" * 64,
            "title": "Project",
            "summary": "Original summary",
            "raw_text": "Original task",
            "contact_url": "https://example.com/task",
            "source_name": "Test",
            "budget": None,
        }
        async with self.session_maker() as session:
            self.assertEqual(await Repository.enqueue_posts(session, [post, post]), 1)
            self.assertEqual(await Repository.enqueue_posts(session, [post]), 0)
            pending = await Repository.get_pending_posts(session)

        async with self.session_maker() as session:
            orders = await Repository.complete_ingested_posts(
                session,
                pending,
                {
                    pending[0].id: {
                        "index": 0,
                        "category": "web_dev",
                        "cleaned_title": "Website build",
                        "summary": "Build a website",
                        "budget": None,
                    }
                },
            )
            self.assertEqual(len(orders), 1)
            self.assertEqual(orders[0].category, "web_dev")
            self.assertEqual(await Repository.get_pending_posts(session), [])

        async with self.session_maker() as session:
            pending_notifications = await Repository.get_pending_notifications(session)
            self.assertEqual(len(pending_notifications), 1)
            self.assertEqual(pending_notifications[0][1].id, orders[0].id)
            post_id = pending_notifications[0][0].id
            await Repository.defer_ingested_posts_by_ids(
                session,
                [post_id],
                "temporary delivery failure",
            )
            self.assertEqual(await Repository.get_pending_notifications(session), [])
            queued_post = await session.get(IngestedPost, post_id)
            self.assertEqual(queued_post.status, "notifying")
            self.assertGreater(queued_post.next_attempt_at, utc_now())
            queued_post.next_attempt_at = utc_now() - timedelta(seconds=1)
            await session.commit()
            pending_notifications = await Repository.get_pending_notifications(session)
            self.assertEqual(len(pending_notifications), 1)
            await Repository.mark_ingested_posts_notified(
                session,
                [post_id],
            )
            self.assertEqual(await Repository.get_pending_notifications(session), [])

    async def test_excluded_source_posts_are_not_processed_or_shown(self):
        async with self.session_maker() as session:
            await Repository.enqueue_posts(session, [{
                "hash_id": "c" * 64,
                "title": "Оператор БПЛА",
                "summary": "Ведення повітряної розвідки",
                "raw_text": "Оператор БПЛА",
                "contact_url": "https://jobs.dou.ua/vacancies/1/",
                "source_name": "DOU Jobs",
                "budget": None,
            }])
            self.assertEqual(await Repository.get_pending_posts(session), [])
            result = await session.execute(
                select(IngestedPost).where(IngestedPost.hash_id == "c" * 64)
            )
            self.assertEqual(result.scalar_one().status, "processed")

            order = await Repository.create_order(
                session,
                hash_id="d" * 64,
                category="dev_bots",
                title="Оператор БПЛА",
                summary="Ведення повітряної розвідки",
                budget=None,
                source_name="DOU Jobs",
                contact_url="https://jobs.dou.ua/vacancies/1/",
            )
            self.assertEqual(
