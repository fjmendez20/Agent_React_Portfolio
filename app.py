import asyncio
import json
import os
import re
import sys
import time

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from starlette.status import HTTP_403_FORBIDDEN

from src.react_agent.context import Context
from src.react_agent.graph import builder

load_dotenv()

# Los logs llevan emojis. Si la consola no usa UTF-8 (cp1252 en Windows) el
# print lanza UnicodeEncodeError DESPUÉS de tener la respuesta ya generada y
# el cliente recibe un 500 sin motivo. Forzamos UTF-8 tolerante a fallos.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


TOTAL_TIMEOUT = _env_float("LLM_TOTAL_TIMEOUT", 45.0)
MAX_CONCURRENCY = _env_int("MAX_CONCURRENCY", 3)
SESSION_TTL_SECONDS = _env_float("SESSION_TTL_SECONDS", 7200.0)
QUEUE_TIMEOUT = _env_float("QUEUE_TIMEOUT", 60.0)

FALLBACK_MESSAGE = (
    "Estoy recibiendo mucha demanda en este momento. "
    "¿Podrías intentar de nuevo en unos segundos?"
)

# --- OPTIMIZACIÓN: Checkpointer EN MEMORIA (sin base de datos) ---
# Los chats se guardan en RAM por proceso; al reiniciar se pierden.
memory_saver = MemorySaver()

# --- OPTIMIZACIÓN: El grafo se compila UNA SOLA VEZ al importar ---
# Antes se compilaba dentro de cada request, lo cual era lento.
graph = builder.compile(name="ReAct Agent", checkpointer=memory_saver)

# --- PROTECCIÓN DE FREE TIER ---
# El free tier de Gemini da ~15 RPM y devuelve 503 cuando el modelo se satura.
# El semáforo evita que un pico de visitas desborde la cuota y el TTL evita que
# el MemorySaver agote los 512 MB de RAM de Render free.
_slots = asyncio.Semaphore(MAX_CONCURRENCY)
_thread_last_seen: dict[str, float] = {}

app = FastAPI(title="ReAct Agent API")

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == os.getenv("CHAT_API_KEY"):
        return api_key_header
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="No se pudo validar la API Key"
        )


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    response: str
    session_id: str


# --- Helpers de limpieza y extracción ---

_TAG_RE = re.compile(r"<tool_code.*?>.*?</tool_code>", re.DOTALL)
_OPEN_TAG_RE = re.compile(r"<tool_code.*?>", re.DOTALL)
_PRINT_RE = re.compile(r"print\(default_api\..*?\)")


def _clean(text: str) -> str:
    """Elimina de la respuesta las marcas técnicas que el modelo no debe emitir."""
    text = _TAG_RE.sub("", text)
    text = _OPEN_TAG_RE.sub("", text)
    text = _PRINT_RE.sub("", text)
    return text.replace("</tool_code>", "").strip()


def _strip_tags(text: str) -> str:
    """Versión ligera para aplicar token a token mientras se transmite."""
    text = _OPEN_TAG_RE.sub("", text)
    text = _PRINT_RE.sub("", text)
    return text.replace("</tool_code>", "")


def _message_text(message: BaseMessage) -> str:
    """Normaliza el contenido de un mensaje o fragmento a texto plano."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content.get("text", "")
    return "".join(
        block if isinstance(block, str) else (block.get("text") or "")
        for block in content
    )


def _extract_answer(messages: list[BaseMessage]) -> str:
    """Recorre los mensajes en reversa y devuelve el último texto del asistente."""
    for message in reversed(messages):
        if message.type != "ai":
            continue
        text = _clean(_message_text(message))
        if text:
            return text
    return ""


def _is_saturation_error(exc: BaseException) -> bool:
    """Detecta los errores transitorios de cuota/saturación del proveedor."""
    text = f"{type(exc).__name__} {exc}".upper()
    markers = (
        "503",
        "UNAVAILABLE",
        "429",
        "RESOURCE_EXHAUSTED",
        "RATE LIMIT",
        "DEADLINE EXCEEDED",
    )
    return any(marker in text for marker in markers)


def _purge_stale_sessions() -> None:
    """Libera la memoria de las conversaciones inactivas."""
    now = time.time()
    stale = [
        thread_id
        for thread_id, seen in _thread_last_seen.items()
        if now - seen > SESSION_TTL_SECONDS
    ]
    for thread_id in stale:
        _thread_last_seen.pop(thread_id, None)
        memory_saver.storage.pop(thread_id, None)
        for store in (memory_saver.writes, memory_saver.blobs):
            for key in [k for k in store if k[0] == thread_id]:
                store.pop(key, None)


def _build_config(request: ChatRequest) -> dict:
    defaults = Context()
    return {
        "configurable": {
            "thread_id": request.session_id,
            "model": defaults.model,
            "fallback_models": defaults.fallback_models,
            "system_prompt": defaults.system_prompt,
            "max_search_results": defaults.max_search_results,
        }
    }


def _register_session(session_id: str) -> None:
    _purge_stale_sessions()
    _thread_last_seen[session_id] = time.time()


def _log_tools(state: dict) -> None:
    for message in state.get("messages", []):
        if message.type == "ai" and getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                print(f"🎯 EL AGENTE LLAMÓ A: {tool_call['name']}")
                print(f"📦 ARGUMENTOS: {tool_call['args']}")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _acquire_slot() -> None:
    try:
        await asyncio.wait_for(_slots.acquire(), timeout=QUEUE_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503, detail="Servidor saturado", headers={"Retry-After": "5"}
        )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    api_key: str = Depends(get_api_key),
):
    start_time = time.time()
    _register_session(request.session_id)

    input_state = {"messages": [HumanMessage(content=request.message)]}

    await _acquire_slot()
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT):
            final_state = await graph.ainvoke(
                input_state, config=_build_config(request)
            )
    except Exception as exc:
        print(f"Error: {exc}")
        if _is_saturation_error(exc):
            raise HTTPException(
                status_code=503,
                detail=FALLBACK_MESSAGE,
                headers={"Retry-After": "5"},
            )
        raise HTTPException(status_code=500, detail=f"Error en el grafo: {str(exc)}")
    finally:
        _slots.release()

    _log_tools(final_state)

    ai_response = _extract_answer(final_state["messages"])
    if not ai_response:
        ai_response = "Lo siento, tuve un problema procesando esa consulta. ¿Podrías repetirla?"

    print(f"⏱️ TIEMPO TOTAL DE RESPUESTA: {time.time() - start_time:.2f} segundos")

    return ChatResponse(response=ai_response, session_id=request.session_id)


@app.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    api_key: str = Depends(get_api_key),
):
    """Versión en streaming (SSE) de /chat.

    Emite cuatro tipos de evento: ``status`` (de inmediato, para que el widget
    pueda mostrar un indicador), ``delta`` (token a token), ``done`` (texto
    final ya limpiado) y ``error``. Nunca devuelve un 5xx: una vez enviada la
    cabecera los errores viajan dentro del propio stream para no romper la UI.
    """
    start_time = time.time()
    _register_session(request.session_id)

    input_state = {"messages": [HumanMessage(content=request.message)]}
    config = _build_config(request)
    await _acquire_slot()

    async def event_source():
        yield _sse("status", {"stage": "thinking"})
        streamed: list[str] = []
        final_state: dict = {}

        try:
            async with asyncio.timeout(TOTAL_TIMEOUT):
                async for mode, chunk in graph.astream(
                    input_state, config=config, stream_mode=["messages", "values"]
                ):
                    if mode == "messages":
                        message_chunk, metadata = chunk
                        if metadata.get("langgraph_node") != "call_model":
                            continue
                        text = _strip_tags(_message_text(message_chunk))
                        if not text:
                            continue
                        streamed.append(text)
                        yield _sse("delta", {"text": text})
                    elif mode == "values":
                        final_state = chunk
        except asyncio.TimeoutError:
            print("Error: timeout esperando al modelo")
            yield _sse("error", {"message": FALLBACK_MESSAGE})
            return
        except Exception as exc:
            print(f"Error: {exc}")
            message = (
                FALLBACK_MESSAGE
                if _is_saturation_error(exc)
                else "Lo siento, tuve un problema procesando esa consulta. ¿Podrías repetirla?"
            )
            if not streamed:
                yield _sse("error", {"message": message})
            return
        finally:
            _slots.release()

        if final_state:
            _log_tools(final_state)

        final_text = (
            _extract_answer(final_state.get("messages", [])) or "".join(streamed)
        )
        if not final_text:
            final_text = "Lo siento, tuve un problema procesando esa consulta. ¿Podrías repetirla?"

        print(f"⏱️ TIEMPO TOTAL DE RESPUESTA: {time.time() - start_time:.2f} segundos")
        yield _sse(
            "done", {"response": final_text, "session_id": request.session_id}
        )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def root():
    return {"status": "online", "message": "Agente de Fabian operando"}


@app.get("/health")
async def health():
    return {
        "status": "online",
        "sessions": len(_thread_last_seen),
        "max_concurrency": MAX_CONCURRENCY,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
