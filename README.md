# 🤖 ReAct Agent API con LangGraph & FastAPI
Este repositorio contiene un agente inteligente basado en el patrón ReAct (Razonamiento y Acción), construido con LangGraph y expuesto a través de una API moderna con FastAPI. El agente está configurado para utilizar los modelos de Google Gemini por defecto, pero es fácilmente extensible a otros proveedores.

## 🚀 Características
- **Flujo de Trabajo Robusto:** Implementado con LangGraph para gestionar ciclos de razonamiento y uso de herramientas.
- **API Lista para Producción:** Servidor FastAPI con validación de datos mediante Pydantic.
- **Memoria de Sesión en Memoria:** Soporte para `thread_id` permitiendo conversaciones con contexto/memoria usando `MemorySaver` de LangGraph (sin base de datos).
- **Configuración Dinámica:** Gestión de parámetros (modelo, prompts) mediante variables de entorno y una clase `Context` centralizada.
- **Listo para Docker:** Incluye `Dockerfile` y `docker-compose.yml`.

## 🛠️ Requisitos Previos
- Python 3.10 o superior (o Docker).
- Una API Key de Google (Gemini).
- (Opcional) API Keys para la captura de leads (Resend) si deseas usar la herramienta `capturar_lead`.

## 📥 Instalación
Clona el repositorio:

```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
```

Crea un entorno virtual:

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

Configura las variables de entorno: copia el archivo de ejemplo y añade tus credenciales:

```bash
cp .env.example .env
```

## 🐳 Ejecución con Docker (recomendado)
Asegúrate de tener `.env` configurado y ejecuta:

```bash
docker compose up --build
```

La API estará disponible en http://localhost:8000.

## ⚡ Ejecución local
Para iniciar el servidor de la API, ejecuta:

```bash
uvicorn app:app --reload
```

La API estará disponible en http://localhost:8000. Puedes acceder a la documentación interactiva (Swagger UI) en http://localhost:8000/docs.

> **Nota:** Como la memoria es en memoria (RAM), cada reinicio del contenedor/proceso borra las conversaciones activas. Esto es intencional para máxima velocidad y cero dependencias externas.

## 📋 Uso de la API

### Enviar un mensaje al agente (respuesta completa)
**Endpoint:** `POST /chat`

**Cuerpo de la petición (JSON):**

```json
{
  "message": "Hola, ¿puedes ayudarme a organizar mis tareas?",
  "session_id": "usuario_123"
}
```

**Respuesta:**

```json
{
  "response": "¡Hola! Claro que sí, estaré encantado de ayudarte...",
  "session_id": "usuario_123"
}
```

**Autenticación:** envía tu API Key en el header `X-API-KEY`.

### Enviar un mensaje al agente (streaming)
**Endpoint:** `POST /chat/stream` — mismo cuerpo y misma autenticación.

Devuelve `text/event-stream` con cuatro tipos de evento:

| Evento   | Payload                              | Cuándo llega |
|----------|--------------------------------------|--------------|
| `status` | `{"stage": "thinking"}`              | inmediato, antes de llamar al modelo |
| `delta`  | `{"text": "..."}`                    | token a token |
| `done`   | `{"response": "texto final", "session_id": "..."}` | al terminar |
| `error`  | `{"message": "..."}`                 | si el modelo no pudo responder |

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "X-API-KEY: $CHAT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hola","session_id":"demo"}'
```

Este endpoint **nunca devuelve un 5xx**: una vez enviada la cabecera, los errores
viajan dentro del propio stream para que la interfaz nunca se rompa.

### Health check
**Endpoint:** `GET /health` → sesiones activas y límite de concurrencia.

## ⚙️ Estructura del Proyecto
- `app.py`: Punto de entrada de FastAPI, rutas `/chat`, `/chat/stream` y `/health`.
- `src/react_agent/graph.py`: Definición de los nodos y aristas del grafo del agente.
- `src/react_agent/context.py`: Lógica de configuración y carga de parámetros.
- `src/react_agent/state.py`: Definición del esquema de estado.
- `src/react_agent/tools.py`: Herramientas disponibles (solo `capturar_lead`).
- `src/react_agent/prompts.py`: Prompt del sistema con la base de conocimiento inline.
- `src/react_agent/utils.py`: Carga de modelos con caché y cadena de respaldo.
- `data/informacion.txt`: Base de conocimiento sobre Fabian Mendez.
- `Dockerfile` / `docker-compose.yml`: Despliegue contenerizado.

## 🔧 Configuración del free tier

El free tier de Gemini da ~15 RPM y responde `503 UNAVAILABLE` cuando el modelo
se satura. Estas variables (ver `.env.example`) controlan cómo se degrada:

| Variable | Default | Para qué sirve |
|----------|---------|----------------|
| `MODEL` | `google_genai/gemini-3.1-flash-lite` | Modelo principal |
| `FALLBACK_MODELS` | `gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-flash-latest` | Respaldos que se prueban en orden si el principal falla |
| `LLM_MAX_RETRIES` | `2` | Reintentos por llamada. El default de google-genai es **5** con backoff 1+2+4+8s, que hace que un request tarde 25s antes de fallar |
| `LLM_TIMEOUT` | `30` | Timeout de una llamada, en segundos |
| `LLM_TOTAL_TIMEOUT` | `45` | Timeout de un turno completo |
| `MAX_CONCURRENCY` | `3` | Conversaciones simultáneas (protege cuota y RAM) |
| `QUEUE_TIMEOUT` | `60` | Espera máxima en cola antes de devolver 503 |
| `SESSION_TTL_SECONDS` | `7200` | Inactividad tras la cual se libera la memoria de la sesión |

> **Usa alias `-latest` en los respaldos.** Google retira los modelos concretos:
> `gemini-2.5-flash` y `gemini-2.5-flash-lite` ya devuelven
> `404 NOT_FOUND` ("no longer available to new users"), así que una cadena de
> respaldos con nombres fijos se queda sin brazos que probar.

## ⚡ Solución de Rendimiento
- El grafo se compila **una sola vez** al iniciar (antes se recompilaba en cada request).
- El cliente del modelo LLM se **cachea en memoria** (antes se reinicializaba en cada paso del agente).
- Los chats viven **en memoria** (`MemorySaver`), eliminando la latencia de ida y vuelta a la base de datos (antes Supabase/Postgres). Las sesiones inactivas se purgan para no agotar la RAM.
- La base de conocimiento va **inline en el system prompt**, así cada mensaje cuesta
  **una sola llamada** al modelo en vez de dos (antes el ciclo ReAct era
  modelo → tool → modelo). Medido: 25.99s → 1.2-2.0s de respuesta.
- `/chat/stream` entrega tokens a medida que se generan en lugar de esperar al turno completo.


## 📄 Licencia
Este proyecto está bajo la Licencia MIT.