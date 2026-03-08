"""Define las estructuras de estado del agente."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from typing_extensions import Annotated


@dataclass
class InputState:
    """Define el estado de entrada del agente, representando una interfaz más estrecha hacia el mundo exterior.

    Esta clase se usa para definir el estado inicial y la estructura de los datos entrantes.
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    Mensajes que rastrean el estado de ejecución principal del agente.

    Típicamente acumula un patrón de:
    1. HumanMessage - entrada del usuario
    2. AIMessage con .tool_calls - agente eligiendo herramientas a utilizar para recopilar información
    3. ToolMessage(s) - las respuestas (o errores) de las herramientas ejecutadas
    4. AIMessage sin .tool_calls - agente respondiendo en formato no estructurado al usuario
    5. HumanMessage - usuario responde con el siguiente turno conversacional

    Los pasos 2-5 pueden repetirse según sea necesario.

    La anotación `add_messages` asegura que los nuevos mensajes se fusionen con los existentes,
    actualizando por ID para mantener un estado "append-only" a menos que se proporcione un mensaje con el mismo ID.
    """


@dataclass
class State(InputState):
    """Representa el estado completo del agente, extendiendo InputState con atributos adicionales.

    Esta clase se puede usar para almacenar cualquier información necesaria a lo largo del ciclo de vida del agente.
    """

    is_last_step: IsLastStep = field(default=False)
    """
    Indica si el paso actual es el último antes de que el grafo lance un error.

    Esta es una variable 'gestionada', controlada por el gestor de estado en lugar del código del usuario.
    Se establece en 'True' cuando el conteo de pasos alcanza recursion_limit - 1.
    """

    # Se pueden agregar atributos adicionales aquí según sea necesario.
    # Los ejemplos comunes incluyen:
    # retrieved_documents: List[Document] = field(default_factory=list)
    # extracted_entities: Dict[str, Any] = field(default_factory=dict)
    # api_connections: Dict[str, Any] = field(default_factory=dict)
