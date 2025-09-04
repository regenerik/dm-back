import os
import time
import requests
from typing import Optional, Tuple
from logging_config import logger
import json

# Asegurate de tener definida la variable de entorno OPENAI_API_KEY
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Debes definir la variable de entorno OPENAI_API_KEY con tu clave de API.")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "assistants=v2"
}

ASSISTANT_ID = "asst_EJnPM2iiGTaIp8sSTXcC914P"

# def query_assistant(prompt: str, thread_id: Optional[str] = None) -> Tuple[str, str]:
#     """
#     Envía un prompt al asistente con ID ASSISTANT_ID utilizando la API de OpenAI.
#     - Si NO hay thread_id => se crea un nuevo hilo (POST /v1/threads/runs).
#     - Si SÍ hay thread_id => se continúa el hilo existente (POST /v1/threads/{thread_id}/runs).
    
#     Espera a que el run se complete y devuelve (respuesta_del_asistente, thread_id).
#     """

#     # Texto de introducción fijo
#     # instruction_prefix = (
#     #     "Se te va a presentar una pregunta relacionada con MOES o YPF. "
#     #     "Tu tarea es responder exclusivamente utilizando el contenido relacionado con esos temas a los cuales ya tienes acceso.\n\n"
#     #     "Además, si el usuario pregunta quién sos, cómo funcionás o si sos un experto, aclarales que sos un asistente creado por YPF "
#     #     "para asistir en consultas vinculadas al contenido del MOES.\n\n"
#     #     "Es importante que formatees tus respuestas con saltos de línea donde sea necesario para facilitar la lectura.\n\n"
#     #     "A continuación, la consulta del usuario:\n\n"
#     # )

#     full_prompt =  prompt

#     if thread_id:
#         # Continuar hilo existente
#         create_run_url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
#         payload = {
#             "assistant_id": ASSISTANT_ID,
#             "additional_messages": [
#                 {"role": "user", "content": full_prompt}
#             ],
#             "additional_instructions": "Responde siempre con un nuevo mensaje."
#         }
#     else:
#         # Crear hilo nuevo
#         create_run_url = "https://api.openai.com/v1/threads/runs"
#         payload = {
#             "assistant_id": ASSISTANT_ID,
#             "thread": {
#                 "messages": [
#                     {"role": "user", "content": full_prompt}
#                 ]
#             }
#         }

#     # 1. Crear (o continuar) el run
#     response = requests.post(create_run_url, headers=HEADERS, json=payload)
#     response.raise_for_status()
#     run_data = response.json()

#     # Si es nuevo hilo, el thread_id viene de la respuesta
#     # Si es hilo existente, ya lo teníamos, pero la API lo reenvía igual
#     new_thread_id = run_data.get("thread_id") or thread_id
#     run_id = run_data["id"]

#     # 2. Polling: esperar a que el run se complete
#     run_status = run_data["status"]
#     while run_status not in ["completed", "failed", "cancelled"]:
#         time.sleep(1)
#         get_run_url = f"https://api.openai.com/v1/threads/{new_thread_id}/runs/{run_id}"
#         run_response = requests.get(get_run_url, headers=HEADERS)
#         run_response.raise_for_status()
#         run_data = run_response.json()
#         run_status = run_data["status"]

#     if run_status != "completed":
#         raise RuntimeError(f"El run terminó con estado '{run_status}'.")

#     # 3. Recuperar los mensajes del thread
#     messages_url = f"https://api.openai.com/v1/threads/{new_thread_id}/messages"
#     messages_response = requests.get(messages_url, headers=HEADERS)
#     messages_response.raise_for_status()
#     messages_data = messages_response.json()

#     # Agregar un logger o print para ver todo el thread
#     import json
#     # print("Mensajes del thread:", json.dumps(messages_data, indent=2))

#     # 4. Filtrar los mensajes del asistente y elegir el más reciente
#     assistant_messages = [
#         msg for msg in messages_data.get("data", []) if msg.get("role") == "assistant"
#     ]
#     if assistant_messages:
#         last_assistant_msg = max(assistant_messages, key=lambda m: m.get("created_at", 0))
#         assistant_message = ""
#         for part in last_assistant_msg.get("content", []):
#             if part.get("type") == "text":
#                 assistant_message += part.get("text", {}).get("value", "")
#     else:
#         assistant_message = ""

#     return assistant_message, new_thread_id


def query_assistant(prompt: str, thread_id: Optional[str] = None) -> Tuple[str, str]:

    if thread_id:
        # Continuar un hilo existente
        create_run_url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
        payload = {
            "assistant_id": ASSISTANT_ID,
            "additional_messages": [
                {"role": "user", "content": prompt}
            ],
            "tool_choice": "auto"
        }
    else:
        # Crear nuevo hilo y run
        create_run_url = "https://api.openai.com/v1/threads/runs"
        payload = {
            "assistant_id": ASSISTANT_ID,
            "thread": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "tool_choice": "auto"
        }

    # 1. Crear o continuar el run
    response = requests.post(create_run_url, headers=HEADERS, json=payload)
    response.raise_for_status()
    run_data = response.json()

    new_thread_id = run_data.get("thread_id") or thread_id
    run_id = run_data["id"]

    # 2. Esperar a que el run termine
    run_status = run_data["status"]
    while run_status not in ["completed", "failed", "cancelled"]:
        time.sleep(1)
        get_run_url = f"https://api.openai.com/v1/threads/{new_thread_id}/runs/{run_id}"
        run_response = requests.get(get_run_url, headers=HEADERS)
        run_response.raise_for_status()
        run_data = run_response.json()
        run_status = run_data["status"]

    if run_status != "completed":
        raise RuntimeError(f"El run terminó con estado '{run_status}'.")

    # 3. Obtener los mensajes del hilo
    messages_url = f"https://api.openai.com/v1/threads/{new_thread_id}/messages"
    messages_response = requests.get(messages_url, headers=HEADERS)
    messages_response.raise_for_status()
    messages_data = messages_response.json()

    # 4. Buscar el último mensaje del asistente
    assistant_messages = [
        msg for msg in messages_data.get("data", []) if msg.get("role") == "assistant"
    ]
    assistant_message = ""
    if assistant_messages:
        last_assistant_msg = max(assistant_messages, key=lambda m: m.get("created_at", 0))
        for part in last_assistant_msg.get("content", []):
            if part.get("type") == "text":
                assistant_message += part.get("text", {}).get("value", "")

    return assistant_message, new_thread_id