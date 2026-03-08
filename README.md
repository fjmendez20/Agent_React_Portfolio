🤖 ReAct Agent API con LangGraph & FastAPI
Este repositorio contiene un agente inteligente basado en el patrón ReAct (Razonamiento y Acción), construido con LangGraph y expuesto a través de una API moderna con FastAPI. El agente está configurado para utilizar los modelos de Google Gemini por defecto, pero es fácilmente extensible a otros proveedores.

🚀 Características
Flujo de Trabajo Robusto: Implementado con LangGraph para gestionar ciclos de razonamiento y uso de herramientas.

API Lista para Producción: Servidor FastAPI con validación de datos mediante Pydantic.

Memoria de Sesión: Soporte para thread_id permitiendo conversaciones con contexto/memoria.

Configuración Dinámica: Gestión de parámetros (modelo, prompts) mediante variables de entorno y una clase Context centralizada.

🛠️ Requisitos Previos
Python 3.10 o superior.

Una API Key de Google (Gemini).

(Opcional) API Keys para Tavily o Fireworks si deseas usar herramientas de búsqueda adicionales.

📥 Instalación
Clona el repositorio:

Bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
Crea un entorno virtual:

Bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
Instala las dependencias:

Bash
pip install -r requirements.txt
Configura las variables de entorno:
Copia el archivo de ejemplo y añade tus credenciales:

Bash
cp .env.example .env
⚡ Ejecución
Para iniciar el servidor de la API, ejecuta el siguiente comando:

Bash
uvicorn app:app --reload
La API estará disponible en http://localhost:8000. Puedes acceder a la documentación interactiva (Swagger UI) en http://localhost:8000/docs.

📋 Uso de la API
Enviar un mensaje al agente
Endpoint: POST /chat

Cuerpo de la petición (JSON):

JSON
{
  "message": "Hola, ¿puedes ayudarme a organizar mis tareas?",
  "session_id": "usuario_123"
}
Respuesta:

JSON
{
  "response": "¡Hola! Claro que sí, estaré encantado de ayudarte...",
  "session_id": "usuario_123"
}
⚙️ Estructura del Proyecto
app.py: Punto de entrada de FastAPI y configuración de rutas.

react_agent/graph.py: Definición de los nodos y aristas del grafo del agente.

react_agent/context.py: Lógica de configuración y carga de parámetros.

react_agent/state.py: Definición del esquema de estado del agente.

📄 Licencia
Este proyecto está bajo la Licencia MIT.