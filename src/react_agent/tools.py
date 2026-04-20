from typing import Any, List, Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
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
async def informacion_fabian(tema: str) -> str:
    """Consulta información específica sobre Fabian Mendez. 
    Argumentos válidos para 'tema': 
    - 'PERFIL': Resumen profesional y especialidades.
    - 'EXPERIENCIA': Proyectos, logros técnicos (RAG, Voicebots, Middleware) e impacto regional.
    - 'CONTACTO': Email, LinkedIn, portafolio y redes.
    """
    # Ruta calculada desde src/react_agent/tools.py hacia la raíz/data/informacion.txt
    path = Path(__file__).parent.parent.parent / "data" / "informacion.txt"
    
    try:
        # Leemos el archivo completo
        contenido = path.read_text(encoding="utf-8")
        
        # Normalizamos el tema a buscar
        tag_inicio = f"[{tema.upper().strip()}]"
        
        if tag_inicio in contenido:
            # Extraemos la sección:
            # 1. Dividimos en el tag de inicio y tomamos lo que sigue
            # 2. Volvemos a dividir en el siguiente '[' (donde empieza otra sección) y tomamos lo anterior
            resultado = contenido.split(tag_inicio)[1].split("[")[0].strip()
            return f"Información sobre {tema.upper()}:\n\n{resultado}"
        else:
            return f"No encontré la sección '{tema}'. Por favor, intenta con: PERFIL, EXPERIENCIA o CONTACTO."
            
    except FileNotFoundError:
        return "Error: El archivo de conocimiento 'informacion.txt' no fue encontrado en la carpeta data/."
    except Exception as e:
        return f"Error al procesar la información: {str(e)}"


# IMPORTANTE: La lista de herramientas actualizada
TOOLS = [informacion_fabian]