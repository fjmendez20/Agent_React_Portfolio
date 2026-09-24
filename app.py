import os
import uvicorn
import re
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from src.react_agent.context import Context
from src.react_agent.graph import builder

load_dotenv()

# --- OPTIMIZACIÓN: Checkpointer EN MEMORIA (sin base de datos) ---
# Los chats se guardan en RAM por proceso; al reiniciar se pierden.
memory_saver = MemorySaver()

# --- OPTIMIZACIÓN: El grafo se compila UNA SOLA VEZ al importar ---
# Antes se compilaba dentro de cada request, lo cual era lento.
graph = builder.compile(name="ReAct Agent", checkpointer=memory_saver)

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

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    api_key: str = Depends(get_api_key)
):
    # Iniciamos el cronómetro
    start_time = time.time()

    user_message = HumanMessage(content=request.message)
    defaults = Context()

    config = {
        "configurable": {
            "thread_id": request.session_id,
            "model": defaults.model,
            "system_prompt": defaults.system_prompt,
            "max_search_results": defaults.max_search_results
        }
    }

    input_state = {"messages": [user_message]}

    try:
        # El grafo ya está compilado y el checkpointer es en memoria.
        final_state = await graph.ainvoke(input_state, config=config)

        # --- LOG DE DETECCIÓN DE TOOLS ---
        for m in final_state["messages"]:
            if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
                for tool_call in m.tool_calls:
                    print(f"🎯 EL AGENTE LLAMÓ A: {tool_call['name']}")
                    print(f"📦 ARGUMENTOS: {tool_call['args']}")
        # ----------------------------------------

        # --- LÓGICA DE EXTRACCIÓN Y LIMPIEZA ---
        ai_response = ""
        for m in reversed(final_state["messages"]):
            if m.type == "ai" and m.content:
                raw_content = m.content

                if isinstance(raw_content, str):
                    ai_response = raw_content
                elif isinstance(raw_content, list):
                    ai_response = "\n".join(
                        block.get("text", "") for block in raw_content
                        if isinstance(block, dict) and "text" in block
                    )

                # --- LIMPIEZA (Regex) ---
                ai_response = re.sub(r'<tool_code.*?>.*?</tool_code>', '', ai_response, flags=re.DOTALL)
                ai_response = re.sub(r'<tool_code.*?>', '', ai_response, flags=re.DOTALL)
                ai_response = re.sub(r'print\(default_api\..*?\)', '', ai_response)
                ai_response = ai_response.replace('</tool_code>', '').strip()
                # --------------------------------

                if ai_response.strip():
                    break

        if not ai_response:
            ai_response = "Lo siento, tuve un problema procesando esa consulta. ¿Podrías repetirla?"

        # Paramos el cronómetro y mostramos el tiempo
        end_time = time.time()
        print(f"⏱️ TIEMPO TOTAL DE RESPUESTA: {end_time - start_time:.2f} segundos")

        return ChatResponse(
            response=ai_response,
            session_id=request.session_id
        )

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error en el grafo: {str(e)}")


@app.get("/")
async def root():
    return {"status": "online", "message": "Agente de Fabian operando"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)