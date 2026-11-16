import logging

from groq import AsyncGroq

from src.config import settings

logger = logging.getLogger("gigpulse.groq_chat")

_INCOMPATIBLE_MODEL_MARKERS = (
    "whisper",
    "orpheus",
    "tts",
    "speech",
    "transcription",
    "prompt-guard",
    "safeguard",
    "embedding",
)


async def create_chat_completion(client: AsyncGroq, **request_options):
    """Use a configured Groq chat model, falling back to models available to this API key."""
    model_response = await client.models.list()
    available_models = [
        model.id
        for model in model_response.data
        if not any(marker in model.id.casefold() for marker in _INCOMPATIBLE_MODEL_MARKERS)
    ]

    preferred_model = settings.GROQ_MODEL.strip()
    candidates = []
    if preferred_model in available_models:
        candidates.append(preferred_model)
    candidates.extend(model for model in available_models if model not in candidates)

    if not candidates:
        raise RuntimeError("Groq returned no chat-capable text models for this API key")

    errors = []
    for model in candidates[:5]:
        try:
            completion = await client.chat.completions.create(model=model, **request_options)
            logger.info("Using available Groq model %s", model)
            return completion
        except Exception as error:
            errors.append(f"{model}: {error}")
            logger.warning("Groq chat request failed for model %s: %s", model, error)

    raise RuntimeError(
        "All available Groq chat models failed: " + "; ".join(errors)
    )
