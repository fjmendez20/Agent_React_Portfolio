from typing import Any, List
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
# Cambiamos la importación a la clase base que suele ser más estable
from langchain_community.tools.tavily_search import TavilySearchResults
from src.react_agent.context import Context
from pathlib import Path
@tool
async def search(query: str, config: RunnableConfig) -> Any:
    """Busca resultados generales de la web.
    Es particularmente útil para responder preguntas sobre eventos actuales.
    """
    context = Context.from_runnable_config(config)
    
    # Esta es la forma más estándar de invocarla
    tool = TavilySearchResults(max_results=context.max_search_results)
    return await tool.ainvoke({"query": query})


@tool
async def informacion_fabian() -> str:
    """Devuelve información personal y profesional sobre Fabian.
    Consulta esta herramienta si el usuario pregunta quién es Fabian o detalles sobre él.
    """
    # Ruta relativa al directorio raíz del proyecto
    # Ajustada para que funcione desde la raíz donde está app.py
    path = Path(__file__).parent.parent.parent / "data" / "informacion.txt"
    
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "Lo siento, no pude encontrar el archivo de información sobre Fabian."


# IMPORTANTE: La lista de herramientas ahora usa las funciones decoradas
TOOLS = [search, informacion_fabian]