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
### Enviar un mensaje al agente
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

## ⚙️ Estructura del Proyecto
- `app.py`: Punto de entrada de FastAPI y configuración de rutas.
- `src/react_agent/graph.py`: Definición de los nodos y aristas del grafo del agente.
- `src/react_agent/context.py`: Lógica de configuración y carga de parámetros.
- `src/react_agent/state.py`: Definición del esquema de estado del agente.
- `src/react_agent/tools.py`: Herramientas disponibles para el agente.
- `src/react_agent/utils.py`: Utilidades (carga del modelo con caché).
- `data/informacion.txt`: Base de conocimiento sobre Fabian Mendez.
- `Dockerfile` / `docker-compose.yml`: Despliegue contenerizado.

## ⚡ Solución de Rendimiento
- El grafo se compila **una sola vez** al iniciar (antes se recompilaba en cada request).
- El cliente del modelo LLM se **cachea en memoria** (antes se reinicializaba en cada paso del agente).
- Los chats viven **en memoria** (`MemorySaver`), eliminando la latencia de ida y vuelta a la base de datos (antes Supabase/Postgres).

## 📄 Licencia
Este proyecto está bajo la Licencia MIT.