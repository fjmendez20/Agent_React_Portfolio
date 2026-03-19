"""Define los parámetros configurables del agente."""

from __future__ import annotations
import os
from dataclasses import dataclass, field, fields
from typing import Annotated
from . import prompts
from langchain_core.runnables import RunnableConfig



@dataclass(kw_only=True)
class Context:
    """El contexto del agente."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "El prompt del sistema a usar para las interacciones del agente. "
            "Este prompt establece el contexto y comportamiento del agente."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="google_genai/gemini-2.5-flash-lite",
        metadata={
            "description": "El nombre del modelo de lenguaje a usar para las interacciones principales del agente. "
            "Debe estar en la forma: proveedor/nombre-modelo."
        },
    )

    max_search_results: int = field(
        default=3,
        metadata={
            "description": "El número máximo de resultados de búsqueda a devolver para cada consulta."
        },
    )

    def __post_init__(self) -> None:
        """Obtiene variables de entorno para atributos que no fueron pasados como argumentos."""
        for f in fields(self):
            if not f.init:
                continue

            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
    
    @classmethod
    def from_runnable_config(cls, config: Optional[RunnableConfig] = None) -> Context:
        """Crea una instancia de Context a partir de la configuración del grafo."""
        configurable = (config.get("configurable") or {}) if config else {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})

