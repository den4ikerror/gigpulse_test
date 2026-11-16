import json
import logging

from src.config import settings
from src.database.models import ORDER_CATEGORIES

logger = logging.getLogger("gigpulse.llm_router")

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class ClassificationError(RuntimeError):
    pass


class LLMRouter:
    def __init__(self):
        self.gemini_keys = [key for key in (settings.GEMINI_API_KEY_1, settings.GEMINI_API_KEY_2) if key]
        self.gemini_models = list(dict.fromkeys(
            [settings.GEMINI_MODEL]
            + [model.strip() for model in settings.GEMINI_FALLBACK_MODELS.split(",") if model.strip()]
        ))
        self.current_key_idx = 0
        self.groq_key = settings.GROQ_API_KEY

    async def classify_batch(self, posts: list[dict]) -> list[dict]:
        if not posts:
            return []

        prompt = f"""
Ти професійний AI-класифікатор фриланс-замовлень. Для кожного замовлення визнач:
1. `category`: одне зі значень: {", ".join(ORDER_CATEGORIES)}.
2. `cleaned_title`: коротка і зрозуміла назва.
3. `summary`: стислий опис завдання до 300 символів.
4. `budget`: бюджет або null, якщо його не вказано.

Поверни лише JSON-об'єкт у форматі {{"orders": [{{"index": 0, "category": "...", "cleaned_title": "...", "summary": "...", "budget": null}}]}}.
Не вигадуй бюджет і збережи index кожного вхідного елемента.

Замовлення:
{json.dumps([{"index": index, "text": post.get("raw_text", "")[:500]} for index, post in enumerate(posts)], ensure_ascii=False)}
"""
        errors: list[str] = []

        if GENAI_AVAILABLE and self.gemini_keys:
            start_idx = self.current_key_idx % len(self.gemini_keys)
            self.current_key_idx = (self.current_key_idx + 1) % len(self.gemini_keys)
            ordered_keys = self.gemini_keys[start_idx:] + self.gemini_keys[:start_idx]
            for key in ordered_keys:
                client = None
                try:
                    client = genai.Client(api_key=key)
                    for model in self.gemini_models:
                        try:
                            response = await client.aio.models.generate_content(
                                model=model,
                                contents=prompt,
                            )
                            return self._parse_json_response(response.text, len(posts))
                        except ClassificationError as error:
                            errors.append(f"Gemini {model}: {error}")
                        except Exception as error:
                            errors.append(f"Gemini {model}: {error}")
                            logger.warning("Gemini request failed for model %s: %s", model, error)
                except Exception as error:
                    errors.append(f"Gemini client: {error}")
                    logger.exception("Could not initialize Gemini client")
                finally:
                    if client:
                        try:
                            await client.aio.aclose()
                        except Exception:
                            logger.exception("Could not close Gemini client")

        if GROQ_AVAILABLE and self.groq_key:
            groq_client = None
            try:
                groq_client = AsyncGroq(api_key=self.groq_key)
                completion = await groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                text = completion.choices[0].message.content
                return self._parse_json_response(text, len(posts))
            except Exception as error:
                errors.append(f"Groq: {error}")
                logger.exception("Groq classification request failed")
            finally:
                if groq_client:
                    try:
                        await groq_client.close()
                    except Exception:
                        logger.exception("Could not close Groq client")

        detail = "; ".join(errors[-4:]) or "No AI provider is configured or available"
        raise ClassificationError(detail)

    @staticmethod
    def _parse_json_response(text: str | None, expected_count: int) -> list[dict]:
        if not text:
            raise ClassificationError("AI provider returned an empty response")
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[-1]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
        try:
            data = json.loads(clean_text.strip())
        except json.JSONDecodeError as error:
            raise ClassificationError(f"AI response is not valid JSON: {error}") from error

        if isinstance(data, dict):
            data = data.get("orders")
        if not isinstance(data, list):
            raise ClassificationError("AI response must be a JSON array")

        parsed: dict[int, dict] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ClassificationError("AI response contains a non-object item")
            index = item.get("index")
            if not isinstance(index, int) or not 0 <= index < expected_count or index in parsed:
                raise ClassificationError("AI response contains an invalid or duplicate index")
            category = item.get("category")
            title = item.get("cleaned_title")
            summary = item.get("summary")
            budget = item.get("budget")
            if category not in ORDER_CATEGORIES or not isinstance(title, str) or not isinstance(summary, str):
                raise ClassificationError(f"AI response has invalid fields for item {index}")
            if budget is not None and not isinstance(budget, str):
                budget = str(budget)
            parsed[index] = {
                "index": index,
                "category": category,
                "cleaned_title": title.strip()[:500],
                "summary": summary.strip()[:300],
                "budget": budget,
            }

        if set(parsed) != set(range(expected_count)):
            raise ClassificationError("AI response did not classify every input item")
        return [parsed[index] for index in range(expected_count)]
