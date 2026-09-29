"""Define un agente personalizado de Razonamiento y Acción.

Funciona con un modelo de chat que soporta llamadas a herramientas.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from src.react_agent.context import Context
from src.react_agent.state import InputState, State
from src.react_agent.tools import TOOLS
from src.react_agent.utils import load_chat_models
from langchain_core.runnables import RunnableConfig
#from langgraph.checkpoint.memory import MemorySaver 



def build_model(context: Context):
    """Construye el modelo con sus herramientas y una cadena de modelos de respaldo.

    ``RunnableWithFallbacks`` no expone ``bind_tools``, así que las herramientas
    se enlazan a cada modelo ANTES de encadenar los respaldos. Si el modelo
    principal devuelve 503 o 429, LangChain prueba el siguiente de la lista.
    """
    models = load_chat_models(context.model, context.fallback_models)
    primary = models[0].bind_tools(TOOLS)
    if len(models) == 1:
        return primary
    return primary.with_fallbacks([m.bind_tools(TOOLS) for m in models[1:]])


async def call_model(state: State, config: RunnableConfig) -> Dict[str, List[AIMessage]]:
    # Extraemos el contexto correctamente usando el método que creamos
    context = Context.from_runnable_config(config)

    model = build_model(context)

    system_message = context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    response = await model.ainvoke(
        [{"role": "system", "content": system_message}, *state.messages]
    )

    # Maneja el caso cuando es el último paso y el modelo aún quiere usar una herramienta
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Lo siento, no pude encontrar una respuesta a su pregunta en el número de pasos especificado.",
                )
            ]
        }

    # Devuelve la respuesta del modelo como una lista para agregarse a los mensajes existentes
    return {"messages": [response]}





def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determina el siguiente nodo basado en la salida del modelo.

    Esta función verifica si el último mensaje del modelo contiene llamadas a herramientas.

    Args:
        state (State): El estado actual de la conversación.

    Returns:
        str: El nombre del siguiente nodo a llamar ("__end__" o "tools").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # Si no hay llamadas a herramientas, entonces terminamos
    if not last_message.tool_calls:
        return "__end__"
    # De lo contrario, ejecutamos las acciones solicitadas
    return "tools"

# Cambiamos context_schema por config_schema
builder = StateGraph(State, input_schema=InputState, config_schema=Context)

builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge("__start__", "call_model")
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")


#memory = #MemorySaver(memory_key="agent_memory", save_on_exit=True)  # Guarda el estado del agente en cada paso

#graph = builder.compile(name="ReAct Agent", checkpointer=memory)