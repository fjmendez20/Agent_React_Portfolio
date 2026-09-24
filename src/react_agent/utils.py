"""Funciones de utilidad y ayuda."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


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


_model_cache: dict = {}


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Carga un modelo de chat a partir de un nombre completamente especificado.

    Args:
        fully_specified_name (str): Cadena en el formato 'proveedor/modelo'.

    El modelo se cachea en memoria: inicializar el cliente del LLM en cada
    paso del grafo era una de las principales fuentes de latencia.
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    if fully_specified_name not in _model_cache:
        _model_cache[fully_specified_name] = init_chat_model(
            model, model_provider=provider
        )
    return _model_cache[fully_specified_name]
