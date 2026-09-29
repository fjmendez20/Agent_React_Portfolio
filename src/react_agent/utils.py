"""Funciones de utilidad y ayuda."""

import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


DEFAULT_FALLBACK_MODELS = (
    "google_genai/gemini-flash-lite-latest,google_genai/gemini-3.5-flash-lite,google_genai/gemini-flash-latest"
)

DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT = 30.0


def get_message_text(msg: BaseMessage) -> str:
    """Obtiene el contenido de texto de un mensaje."""
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


_model_cache: dict[tuple, list[BaseChatModel]] = {}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def load_chat_models(
    fully_specified_name: str, fallback_names: str | None = None
) -> list[BaseChatModel]:
    """Carga el modelo principal junto con sus modelos de respaldo.

    El free tier de Gemini responde con ``503 UNAVAILABLE`` cuando el modelo
    está saturado. Mantener una lista permite que el agente siga respondiendo
    con otro modelo en vez de exponer el error al usuario.

    Los clientes se cachean en memoria: inicializar el cliente del LLM en cada
    paso del grafo era una de las principales fuentes de latencia.

    Args:
        fully_specified_name (str): Cadena en el formato 'proveedor/modelo'.
        fallback_names (str | None): Modelos de respaldo separados por coma.
            Si es ``None`` se usa :data:`DEFAULT_FALLBACK_MODELS`.

    Returns:
        list[BaseChatModel]: Modelo principal seguido de los de respaldo.
    """
    names = [fully_specified_name]
    raw_fallbacks = (
        fallback_names if fallback_names is not None else DEFAULT_FALLBACK_MODELS
    )
    for raw_name in (raw_fallbacks or "").split(","):
        name = raw_name.strip()
        if name and name not in names:
            names.append(name)

    max_retries = int(_env_float("LLM_MAX_RETRIES", DEFAULT_MAX_RETRIES))
    timeout = _env_float("LLM_TIMEOUT", DEFAULT_TIMEOUT)
    cache_key = (tuple(names), max_retries, timeout)

    if cache_key not in _model_cache:
        models = []
        for name in names:
            provider, model = name.split("/", maxsplit=1)
            models.append(
                init_chat_model(
                    model,
                    model_provider=provider,
                    max_retries=max_retries,
                    timeout=timeout,
                )
            )
        _model_cache[cache_key] = models
    return _model_cache[cache_key]
