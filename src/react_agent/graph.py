"""Define un agente personalizado de Razonamiento y Acción.

Funciona con un modelo de chat que soporta llamadas a herramientas.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model
from langchain_core.runnables import RunnableConfig
#from langgraph.checkpoint.memory import MemorySaver 



async def call_model(state: State, config: RunnableConfig) -> Dict[str, List[AIMessage]]:
    # Extraemos el contexto correctamente usando el método que creamos
    context = Context.from_runnable_config(config)
    
    # Ahora context.model ya no será None
    model = load_chat_model(context.model).bind_tools(TOOLS)

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