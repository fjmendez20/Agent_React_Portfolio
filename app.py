import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from pydantic import BaseModel
from src.react_agent.graph import builder
from langchain_core.messages import HumanMessage
from src.react_agent.context import Context
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

load_dotenv()

# 1. Obtenemos la URL de Supabase desde las variables de entorno
DB_URI = os.getenv("DATABASE_URL")

# 2. Creamos un pool de conexiones (esto es más profesional)
connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": None,
}

@asynccontextmanager
async def get_checkpointer():
    # Usamos la conexión a Supabase
    async with AsyncConnectionPool(conninfo=DB_URI, max_size=20, kwargs=connection_kwargs) as pool:
        async with pool.connection() as conn:
            checkpointer = AsyncPostgresSaver(conn)
            # La primera vez, esto crea las tablas necesarias en Supabase
            await checkpointer.setup() 
            yield checkpointer

app = FastAPI()

# Definimos cómo se llama el encabezado que buscaremos
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Función para validar la llave
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
            async with get_checkpointer() as memory:
                graph = builder.compile(name="ReAct Agent", checkpointer=memory)
                final_state = await graph.ainvoke(input_state, config=config)
                
                # --- LÓGICA DE EXTRACCIÓN MEJORADA ---
                ai_response = ""
                # Recorremos los mensajes de atrás hacia adelante
                for m in reversed(final_state["messages"]):
                    # Buscamos un mensaje de AI que tenga contenido y NO sea una simple llamada a tool
                    if m.type == "ai" and m.content:
                        raw_content = m.content
                        
                        # Manejamos si el contenido viene como string o como lista de bloques (formato Gemini/Claude)
                        if isinstance(raw_content, str):
                            ai_response = raw_content
                        elif isinstance(raw_content, list):
                            ai_response = "\n".join(
                                block.get("text", "") for block in raw_content 
                                if isinstance(block, dict) and "text" in block
                            )
                        
                        # Si encontramos texto válido, dejamos de buscar
                        if ai_response.strip():
                            break

                # Si después de buscar no hay nada, damos un mensaje de respaldo
                if not ai_response:
                    ai_response = "Lo siento, tuve un problema procesando esa consulta. ¿Podrías repetirla?"

                return ChatResponse(
                    response=ai_response,
                    session_id=request.session_id
                )
            
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error en el grafo: {str(e)}")
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)