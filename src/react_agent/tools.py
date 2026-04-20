import os
import requests
from typing import Any, List, Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_community.tools.tavily_search import TavilySearchResults
from src.react_agent.context import Context
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv


load_dotenv()  

#@tool
#async def search(query: str, config: RunnableConfig) -> Any:
#    """Busca resultados generales de la web.
#    Es particularmente útil para responder preguntas sobre eventos actuales.
#    """
#    context = Context.from_runnable_config(config)
#    
#    # Esta es la forma más estándar de invocarla
#    tool = TavilySearchResults(max_results=context.max_search_results)
#    return await tool.ainvoke({"query": query})



# 1. Definimos el esquema estricto. Esto obliga al LLM a tener estos 3 datos.
class CapturarLeadInput(BaseModel):
    nombre: str = Field(description="Nombre completo, nombre de la empresa o nombre de pila del cliente potencial.")
    email: str = Field(description="Correo electrónico válido del cliente.")
    descripcion: str = Field(description="Breve descripción del proyecto, problema o necesidad por la que contactan.")

# 2. Creamos la herramienta
@tool("capturar_lead", args_schema=CapturarLeadInput, return_direct=False)
def capturar_lead(nombre: str, email: str, descripcion: str) -> str:
    """
    Usa esta herramienta ÚNICAMENTE cuando el usuario haya confirmado su interés en trabajar con Fabian 
    y te haya proporcionado su nombre, email y descripción del proyecto.
    """

    api_url = os.getenv("LEAD_API_URL")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; font-family: 'helvetica neue', helvetica, arial, sans-serif; background-color: #f4f7f9;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <tr>
                <td style="padding: 40px 20px; text-align: center; background-color: #000000;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 22px; letter-spacing: 1px;">NOTIFICACIÓN AGENTE AI</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 30px;">
                    <p style="font-size: 16px; color: #444444; line-height: 1.5;">Hola, se ha capturado nueva información a través del agente:</p>
                    <table width="100%" style="margin-top: 20px; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee;">
                                <span style="font-size: 12px; color: #999999; text-transform: uppercase; font-weight: bold;">Nombre</span><br>
                                <span style="font-size: 16px; color: #333333;">{nombre}</span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee;">
                                <span style="font-size: 12px; color: #999999; text-transform: uppercase; font-weight: bold;">Email de contacto</span><br>
                                <span style="font-size: 16px; color: #007bff;">{email}</span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0;">
                                <span style="font-size: 12px; color: #999999; text-transform: uppercase; font-weight: bold;">Descripción</span><br>
                                <p style="font-size: 16px; color: #333333; margin: 5px 0 0 0;">{descripcion}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    payload = {
        "from": "onboarding@resend.dev",
        "to": "thefome18@gmail.com",
        "subject": "Lead Generado",
        "html": html_content
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}"
    }

    try:
        # Hacemos la petición POST a tu API
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        
        # Verificamos que la petición fue exitosa (código 200-299)
        response.raise_for_status()
        
        return "ÉXITO: El lead fue guardado. Agradece al usuario por su interés y dile que Fabian lo contactará en breve."
    
    except requests.exceptions.RequestException as e:
        # Si tu backend falla, le decimos al agente cómo reaccionar
        print(f"Error al enviar lead: {e}")
        return "ERROR: El sistema de leads falló. Pídele disculpas al usuario y dile que escriba directamente al correo de contacto de Fabian."



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