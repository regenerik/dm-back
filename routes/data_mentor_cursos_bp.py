from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity   # Jwt para tokens
from database import db                                          # importa la db desde database.py
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO
from utils.data_mentor_cursos_utils import query_assistant
import urllib.request
import urllib.error
import json
from models import HistoryUserCourses, User
from werkzeug.utils import secure_filename
from mailjet_rest import Client
import os, json, base64

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Debes definir la variable de entorno OPENAI_API_KEY con tu clave de API.")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "assistants=v2"
}

data_mentor_cursos_bp = Blueprint('data_mentor_cursos_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()

# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@data_mentor_cursos_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/delete-individual-chat','/test_clasifica_data_mentor_cursos_bp']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
# RUTA TEST:

@data_mentor_cursos_bp.route('/test_clasifica_data_mentor_cursos_bp', methods=['GET'])
def test():
    logger.info("data_mentor_cursos bp rutas funcionando ok segun test.")
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, data mentor cursos rutas funcionan bien..."}),200

@data_mentor_cursos_bp.route("/chat_mentor_cursos", methods=["POST"])
def chat():
    """
    Recibe prompt y opcionalmente thread_id.
    """
    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "Falta el prompt en el cuerpo de la solicitud"}), 400

    prompt = data["prompt"]
    thread_id = data.get("thread_id")  # puede ser None

    try:
        response_text, current_thread = query_assistant(prompt, thread_id)
        return jsonify({"response": response_text, "thread_id": current_thread}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@data_mentor_cursos_bp.route("/close_chat_cursos", methods=["POST"])
def close_chat():
    """
    Ruta para cerrar el thread del chat.
    Se espera recibir un JSON con la clave "thread_id".
    Llama al endpoint DELETE de la API para cerrar el hilo usando urllib.
    """
    data = request.get_json()
    if not data or "thread_id" not in data:
        return jsonify({"error": "Falta el thread_id en el cuerpo de la solicitud"}), 400

    thread_id = data["thread_id"]
    delete_url = f"https://api.openai.com/v1/threads/{thread_id}"

    try:
        req = urllib.request.Request(delete_url, headers=HEADERS, method="DELETE")
        with urllib.request.urlopen(req) as response:
            result_data = response.read().decode("utf-8")
            result = json.loads(result_data)
        return jsonify(result), 200
    except urllib.error.HTTPError as e:
        error_message = e.read().decode("utf-8")
        return jsonify({"error": f"HTTPError {e.code}: {error_message}"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_mentor_cursos_bp.route("/history-user-add", methods=['POST'])
def add_user_history():
    # Se extrae la autorización y se valida
    auth_header = request.headers.get('Authorization')
    if auth_header != "1803-1989-1803-1989":
        return jsonify({"resultado": "no guardado", "error": "Unauthorized"}), 401

    # Se obtienen los datos del cuerpo de la solicitud JSON
    data = request.get_json()
    if not data:
        return jsonify({"resultado": "no guardado", "error": "No JSON data received"}), 400

    titulo = data.get('titulo')
    email = data.get('email')
    texto = data.get('texto')

    # Validación de datos básicos
    if not all([titulo, email, texto]):
        return jsonify({"resultado": "no guardado", "error": "Missing data: titulo, email, or texto"}), 400

    # 1. Verifica si el usuario existe en la base de datos
    user_exists = User.query.filter_by(email=email).first()
    if not user_exists:
        return jsonify({"resultado": "no guardado", "error": "User with this email does not exist"}), 404
        
    try:
        # 2. Crea una nueva instancia de HistoryUserCourses
        new_history = HistoryUserCourses(
            titulo=titulo,
            email=email,
            texto=texto
        )
        
        # 3. Agrega y guarda en la base de datos
        db.session.add(new_history)
        db.session.commit()

        return jsonify({"resultado": "guardado"}), 201
    
    except Exception as e:
        # En caso de cualquier error, se revierte la transacción de la base de datos
        db.session.rollback()
        print(f"Error al guardar el historial: {e}")
        return jsonify({"resultado": "no guardado", "error": str(e)}), 500
    
@data_mentor_cursos_bp.route("/get-history-by-user", methods=['POST'])
def get_user_history():
    # Extraer el email del usuario de la solicitud JSON
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({"error": "Email no proporcionado en el cuerpo de la solicitud"}), 400

    user_email = data.get('email')

    # Verificar si el usuario existe antes de buscar su historial
    user_exists = User.query.filter_by(email=user_email).first()
    if not user_exists:
        return jsonify({"error": "Usuario con este email no existe"}), 404

    try:
        # Buscar todas las entradas de historial para el email del usuario
        history_records = HistoryUserCourses.query.filter_by(email=user_email).order_by(HistoryUserCourses.created_at.desc()).all()
        
        # Serializar cada registro
        serialized_history = [record.serialize() for record in history_records]

        return jsonify(serialized_history), 200
    
    except Exception as e:
        print(f"Error al obtener el historial del usuario: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500
       
@data_mentor_cursos_bp.route("/delete-individual-chat", methods=['POST'])
def delete_individual_chat():
    # Extrae la autorización y la valida
    auth_header = request.headers.get('Authorization')
    if auth_header != "1803-1989-1803-1989":
        return jsonify({"resultado": "no borrado", "error": "Unauthorized"}), 401

    # Obtiene el ID del chat del cuerpo de la solicitud JSON
    data = request.get_json()
    chat_id = data.get('id')

    if not chat_id:
        return jsonify({"resultado": "no borrado", "error": "ID del chat no proporcionado"}), 400
    
    try:
        # Busca el chat por ID
        chat_to_delete = HistoryUserCourses.query.get(chat_id)
        
        if not chat_to_delete:
            return jsonify({"resultado": "no borrado", "error": "Chat no encontrado"}), 404
            
        # Elimina el chat de la sesión y guarda los cambios
        db.session.delete(chat_to_delete)
        db.session.commit()

        return jsonify({"resultado": "borrado"}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error al intentar borrar el chat: {e}")
        return jsonify({"resultado": "no borrado", "error": "Error interno del servidor"}), 500
    


# Envio de emails : 

def _chunk(lst, n):
    """Parte una lista en bloques de n elementos."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _safe_resp_payload(resp):
    """Intenta parsear JSON; si no, devuelve un recorte de texto."""
    try:
        return resp.json()
    except Exception:
        try:
            txt = resp.text
        except Exception:
            txt = None
        return {"non_json_body": (txt[:1000] if txt else None)}

# --- ruta ------------------------------------------------------------------

@data_mentor_cursos_bp.route("/send-course-pdf", methods=["POST"])
def send_course_pdf():
    """
    Recibe:
      - FormData 'file': el PDF a enviar
      - FormData 'emails': lista JSON de emails  (o CSV/separado por ; )
      - opcional: 'subject', 'text', 'html'
    Envía el PDF a todos los destinatarios usando Mailjet.
    """
    try:
        # --- credenciales ---
        api_key = os.getenv("MJ_APIKEY_PUBLIC")
        api_secret = os.getenv("MJ_APIKEY_PRIVATE")
        sender_email = os.getenv("MJ_SENDER_EMAIL")
        if not (api_key and api_secret and sender_email):
            return jsonify({"ok": False, "error": "Faltan variables de entorno de Mailjet"}), 500

        # --- archivo ---
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "Falta 'file' en FormData"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"ok": False, "error": "Archivo sin nombre"}), 400

        filename = secure_filename(f.filename)
        file_bytes = f.read()
        if not file_bytes:
            return jsonify({"ok": False, "error": "Archivo vacío"}), 400

        # tamaño base64 = 4 * ceil(n/3)  =>  4 * ((n + 2) // 3)  (sin math)
        base64_len = 4 * ((len(file_bytes) + 2) // 3)
        # margen por headers/cuerpo → tope ~14.5MB
        if base64_len > int(14.5 * 1024 * 1024):
            return jsonify({
                "ok": False,
                "error": "Adjunto demasiado grande para enviar por email (base64). "
                         "Reducí el peso del PDF o exportalo con menor calidad.",
                "raw_size_mb": round(len(file_bytes) / 1024 / 1024, 2),
                "estimated_base64_mb": round(base64_len / 1024 / 1024, 2),
                "limit_mb": 14.5
            }), 413

        content_type = f.mimetype or "application/pdf"
        b64 = base64.b64encode(file_bytes).decode("utf-8")

        # --- emails ---
        emails = []
        emails += [e.strip() for e in request.form.getlist("emails[]") if e.strip()]
        raw_emails = (request.form.get("emails") or "").strip()
        if raw_emails:
            try:
                parsed = json.loads(raw_emails)
                if isinstance(parsed, list):
                    emails += [str(e).strip() for e in parsed if str(e).strip()]
                elif isinstance(parsed, str) and parsed.strip():
                    emails.append(parsed.strip())
            except Exception:
                emails += [e.strip() for e in raw_emails.replace(";", ",").split(",") if e.strip()]

        emails = sorted(set([e for e in emails if e]))
        if not emails:
            return jsonify({"ok": False, "error": "No se recibieron emails"}), 400

        # --- contenido del correo (opcionales) ---
        subject = request.form.get("subject") or f"Curso: {os.path.splitext(filename)[0]}"
        text_part = request.form.get("text") or "Te comparto el curso adjunto."
        html_part = request.form.get("html") or "<p>Te comparto el curso adjunto.</p>"

        # --- Mailjet ---
        mailjet = Client(auth=(api_key, api_secret), version="v3.1")
        results, errors = [], 0

        for batch in _chunk(emails, 50):  # 50 por tanda es prudente
            data = {
                "Messages": [{
                    "From": {"Email": sender_email, "Name": "Cursos Data Mentor"},
                    "To": [{"Email": sender_email}],              # Mailjet exige al menos un To
                    "Bcc": [{"Email": e} for e in batch],         # destinatarios reales en Bcc
                    "Subject": subject,
                    "TextPart": text_part,
                    "HTMLPart": html_part,
                    "Attachments": [{
                        "ContentType": content_type,
                        "Filename": filename,
                        "Base64Content": b64,
                    }],
                }]
            }

            resp = mailjet.send.create(data=data)
            payload = _safe_resp_payload(resp)
            ok_batch = 200 <= resp.status_code < 300
            if not ok_batch:
                errors += 1
                # logueo liviano para debug
                current_app.logger.warning(
                    "Mailjet non-2xx",
                    extra={"status": resp.status_code, "payload": payload}
                )

            results.append({
                "status": resp.status_code,
                "ok": ok_batch,
                "payload": payload,
                "batch_size": len(batch),
                "recipients": batch,
            })

        status_code = 200 if errors == 0 else 502
        return jsonify({
            "ok": errors == 0,
            "filename": filename,
            "email_count": len(emails),
            "batches": len(results),
            "sent_batches": sum(1 for r in results if r["ok"]),
            "results": results,
        }), status_code

    except Exception as e:
        current_app.logger.exception("send_course_pdf failed")
        return jsonify({"ok": False, "error": str(e)}), 500