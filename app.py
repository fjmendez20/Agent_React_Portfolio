import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
#from typing import List, Optional
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
    "prepare_threshold": 0,
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

app = FastAPI(title="Agente ReAct API")

class ChatRequest(BaseModel):
    message: str 
    session_id: str 

class ChatResponse(BaseModel):
    response: str
    session_id: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
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
            
            # 1. Obtenemos el contenido crudo del último mensaje
            raw_content = final_state["messages"][-1].content
            
            # 2. Manejamos los diferentes formatos que puede devolver el LLM
            if isinstance(raw_content, str):
                # Si ya es texto, lo dejamos igual
                ai_response = raw_content
            elif isinstance(raw_content, list):
                # Si es una lista, extraemos el valor "text" de cada bloque y lo unimos
                ai_response = "\n".join(
                    block.get("text", "") for block in raw_content if isinstance(block, dict) and "text" in block
                )
            else:
                # Por si acaso llega en algún otro formato raro
                ai_response = str(raw_content)
            
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