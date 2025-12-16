import requests
import time
import os
from typing import Optional, Tuple
from models import FormularioNecesidades
from database import db

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Debes definir OPENAI_API_KEY")

ASSISTANT_ID = "asst_PhXLvGOUUMa7vxNdidkfdxP4"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "assistants=v2"
}

def query_assistant(prompt: str, form_id: int, thread_id: Optional[str] = None) -> str:
    """
    Envía un prompt al assistant, espera la respuesta,
    la guarda en FormularioNecesidades.respuesta_ia
    y devuelve el texto.
    """

    if thread_id:
        url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
        payload = {
            "assistant_id": ASSISTANT_ID,
            "additional_messages": [
                {"role": "user", "content": prompt}
            ]
        }
    else:
        url = "https://api.openai.com/v1/threads/runs"
        payload = {
            "assistant_id": ASSISTANT_ID,
            "thread": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        }

    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    run_data = response.json()

    run_id = run_data["id"]
    thread_id = run_data.get("thread_id")

    status = run_data["status"]
    while status not in ["completed", "failed", "cancelled"]:
        time.sleep(1)
        poll = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
            headers=HEADERS
        )
        poll.raise_for_status()
        run_data = poll.json()
        status = run_data["status"]

    if status != "completed":
        raise RuntimeError(f"Run terminó en estado {status}")

    messages = requests.get(
        f"https://api.openai.com/v1/threads/{thread_id}/messages",
        headers=HEADERS
    )
    messages.raise_for_status()
    data = messages.json().get("data", [])

    assistant_msgs = [m for m in data if m.get("role") == "assistant"]
    if not assistant_msgs:
        return ""

    last_msg = max(assistant_msgs, key=lambda m: m.get("created_at", 0))

    respuesta = ""
    for part in last_msg.get("content", []):
        if part.get("type") == "text":
            respuesta += part.get("text", {}).get("value", "")

    # 👉 Guardar respuesta en el registro
    form = FormularioNecesidades.query.get(form_id)
    if form:
        form.respuesta_ia = respuesta.strip()
        db.session.commit()

    return respuesta.strip()
