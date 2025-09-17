from flask import Blueprint, request, jsonify, send_file
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from database import db
from logging_config import logger
import os
from dotenv import load_dotenv
load_dotenv()
import pandas as pd
from io import BytesIO
from werkzeug.utils import secure_filename
from datetime import datetime
import re

# === Importaciones de librerías para extracción de texto ===
# Estas importaciones ahora estarán disponibles si instalas los nuevos requisitos
from pdfminer.high_level import extract_text
import PyPDF2
import docx
import pydocx
from pdfminer.high_level import extract_text
import PyPDF2
import docx  # Mantendremos esta como respaldo por si falla mammoth
import mammoth
import re

# === OpenAI (tu forma) ===
from openai import OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Debes definir la variable de entorno OPENAI_API_KEY con tu clave de API.")
client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

from models import JobDescription, Curriculos

recursos_bp = Blueprint('recursos_bp', __name__)
bcrypt = Bcrypt()
jwt = JWTManager()

# --- API KEY guard ---
API_KEY = os.getenv('API_KEY')
def check_api_key(api_key): return api_key == API_KEY

@recursos_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/test_clasifica_recursos_bp']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401

@recursos_bp.route('/test_clasifica_recursos_bp', methods=['GET'])
def test():
    logger.info("recursos_bp rutas funcionando ok segun test.")
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, recursos rutas funcionan bien..."}),200

# ================== Helpers ==================

_PAQUETE_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
def _parse_paquete(paquete: str):
    if not paquete: return None, None
    m = _PAQUETE_RE.match(paquete)
    if not m: return None, None
    try:
        return int(m.group(1)), int(m.group(2))
    except Exception:
        return None, None

def _ext_from_filename(filename: str) -> str:
    return (filename.rsplit(".", 1)[-1].lower() if "." in filename else "").strip()

def _extract_text_from_docx(file_bytes: bytes) -> str:
    # Intentar con mammoth primero, ya que es más robusto
    try:
        with BytesIO(file_bytes) as bio:
            logger.info("Intentando extraer texto de DOCX con la librería 'mammoth'...")
            result = mammoth.convert_to_html(bio)
            # Quitar tags HTML y limpiar el texto
            text = re.sub('<[^>]*>', '', result.value)
            
            if text:
                logger.info("Extracción de DOCX con 'mammoth' exitosa.")
                return text.strip()
            else:
                logger.warning("Extracción de DOCX con 'mammoth' no devolvió texto.")
                return ""
    except Exception as e:
        logger.exception(f"Error fatal con la librería 'mammoth' al extraer DOCX: {e}")
        
    # Fallback a python-docx si mammoth falla
    try:
        import docx
        with BytesIO(file_bytes) as bio:
            logger.info("Intentando extraer texto de DOCX con la librería 'python-docx'...")
            doc = docx.Document(bio)
            text = "\n".join(p.text for p in doc.paragraphs if p.text).strip()
            
            if text:
                logger.info("Extracción de DOCX con 'python-docx' exitosa.")
                return text
            else:
                logger.warning("Extracción de DOCX con 'python-docx' no devolvió texto.")
                return ""
    except Exception as e:
        logger.exception(f"Error fatal con la librería 'python-docx' al extraer DOCX: {e}")
        return ""

def _extract_text_from_doc_rtf(file_bytes: bytes) -> str:
    # Manejar archivos RTF que a veces se confunden con .doc
    try:
        text = file_bytes.decode("utf-8", errors="ignore")
        # Quitar los códigos de formato RTF
        clean_text = re.sub(r'\{.*?\}|\\[a-z0-9]+|\\\'[0-9a-f]{2}|\\["\'\s]', '', text, flags=re.DOTALL)
        return clean_text.strip()
    except Exception:
        return ""

def _extract_text_from_doc(file_bytes: bytes) -> str:
    # Pydocx no funcionó; simplemente intentamos el manejo RTF
    return _extract_text_from_doc_rtf(file_bytes)

def _extract_text_by_ext(ext: str, file_bytes: bytes) -> str:
    if ext == "pdf":  return _extract_text_from_pdf(file_bytes)
    if ext == "docx": return _extract_text_from_docx(file_bytes)
    if ext == "doc":  return _extract_text_from_doc(file_bytes)
    if ext == "txt":  return _extract_text_from_txt(file_bytes)
    return ""

def _extract_text_from_pdf(file_bytes: bytes) -> str:
    # pdfminer → PyPDF2 fallback
    try:
        from pdfminer.high_level import extract_text
        with BytesIO(file_bytes) as bio:
            return extract_text(bio) or ""
    except Exception:
        pass
    try:
        import PyPDF2
        with BytesIO(file_bytes) as bio:
            reader = PyPDF2.PdfReader(bio)
            texts = []
            for page in reader.pages:
                try: texts.append(page.extract_text() or "")
                except Exception: continue
            return "\n".join(texts).strip()
    except Exception:
        pass
    return ""

def _extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""

# Instrucciones y prompt (en tu formato de chat.completions)
_LLM_INSTRUCTIONS = (
    'Vas a recibir dos bloques: un CV y un job description.\n'
    'Respondé **SOLO** con este formato exacto, sin texto extra:\n'
    'PUNTAJE: <float con 2 decimales entre 0.00 y 10.00>\n'
    'COMENTARIO: "<justificación breve en español>"\n'
    'NOMBRE_ARCHIVO: "<nombre del archivo evaluado>"\n'
    'VALIDEZ: "VALIDO" o "INVALIDO"\n'
    'RECOMENDADO: "SI" o "NO"\n'
    '\n'
    'Reglas:\n'
    '- Si el CV es ilegible/vacío, VALIDEZ="INVALIDO", PUNTAJE=0.00 y RECOMENDADO="NO".\n'
    '- Mantené las claves y comillas exactamente como están.\n'
)

_LLM_PROMPT_TEMPLATE = (
    "CV TEXT:\n{cv}\n\n"
    "JOB DESCRIPTION:\n{jd}\n\n"
    "Ahora producí la salida en el formato indicado, estrictamente."
)

_RE_PUNTAJE = re.compile(r"PUNTAJE\s*:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_RE_COMENT = re.compile(r'COMENTARIO\s*:\s*"(.*?)"', re.IGNORECASE | re.DOTALL)
_RE_VALID = re.compile(r'VALIDEZ\s*:\s*"?\b(VALIDO|INVALIDO)\b"?', re.IGNORECASE)
_RE_RECO = re.compile(r'RECOMENDADO\s*:\s*"?\b(SI|NO)\b"?', re.IGNORECASE)

def _safe_parse_llm(raw: str) -> dict:
    puntaje, comentario, validez, recomendado = 0.0, "", "INVALIDO", "NO"
    try:
        m = _RE_PUNTAJE.search(raw)
        if m: puntaje = float(m.group(1))
    except Exception: puntaje = 0.0

    m = _RE_COMENT.search(raw)
    if m: comentario = m.group(1).strip()

    m = _RE_VALID.search(raw)
    if m: validez = "VALIDO" if m.group(1).upper()=="VALIDO" else "INVALIDO"

    m = _RE_RECO.search(raw)
    if m: recomendado = "SI" if m.group(1).upper()=="SI" else "NO"

    if validez == "INVALIDO":
        puntaje = 0.0
        recomendado = "NO"

    try:
        puntaje = max(0.0, min(10.0, float(puntaje)))
    except Exception:
        puntaje = 0.0

    return {
        "puntaje": round(puntaje, 2),
        "comentario": comentario,
        "validez": validez,
        "recomendado": recomendado,
    }

def _call_llm(filename: str, cv_text: str, jd_text: str) -> dict:
    # si no hay texto, devolvé INVALIDO sin llamar
    if not cv_text or len(cv_text.strip()) < 20:
        return {"puntaje": 0.0, "comentario": "Texto ilegible o insuficiente.", "validez": "INVALIDO", "recomendado": "NO"}

    prompt = _LLM_PROMPT_TEMPLATE.format(cv=cv_text[:12000], jd=jd_text[:8000])
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _LLM_INSTRUCTIONS},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
    except Exception as e:
        logger.exception(f"OpenAI error con {filename}: {e}")
        return {"puntaje": 0.0, "comentario": "Error al contactar a la IA.", "validez": "INVALIDO", "recomendado": "NO"}

    parsed = _safe_parse_llm(content)
    if parsed["validez"] == "INVALIDO":
        parsed["puntaje"] = 0.0
        parsed["recomendado"] = "NO"
    return parsed

# ================== /upload_cvs ==================

@recursos_bp.route("/upload_cvs", methods=["POST"])
def upload_cvs():
    """
    form-data:
      - email (str)
      - archivos (file[])  -> múltiples
      - job_description (str)
      - titulo (str)
      - paquete (str "n/x")
      - job_description_id (str|int)  [opcional: solo de 2/x en adelante]
    """
    logger.info("Iniciando procesamiento de /upload_cvs.")
    try:
        email = (request.form.get("email") or "").strip()
        jd_text = (request.form.get("job_description") or "").strip()
        titulo = (request.form.get("titulo") or "").strip()
        paquete = (request.form.get("paquete") or "").strip()
        jd_id_form = (request.form.get("job_description_id") or "").strip()

        logger.info(f"Datos recibidos: email={email}, titulo={titulo}, paquete={paquete}")

        if not email or not jd_text or not titulo or not paquete:
            logger.warning("Faltan campos requeridos en la solicitud.")
            return jsonify({"ok": False, "error": "Campos requeridos: email, job_description, titulo, paquete"}), 400

        n, x = _parse_paquete(paquete)
        if n is None or x is None or x < 1:
            logger.warning(f"Formato de paquete inválido: {paquete}")
            return jsonify({"ok": False, "error": "Formato de 'paquete' inválido (esperado n/x)"}), 400
        
        files = request.files.getlist("archivos")
        if not files:
            logger.warning("No se recibieron archivos.")
            return jsonify({"ok": False, "error": "No se recibieron archivos"}), 400

        job_description_obj = None
        job_description_id = None
        
        # Lógica para manejar JD existente o crear uno nuevo
        if jd_id_form:
            try:
                job_description_id = int(jd_id_form)
                job_description_obj = db.session.get(JobDescription, job_description_id)
                if not job_description_obj:
                    logger.warning(f"job_description_id inválido: {jd_id_form}")
                    return jsonify({"ok": False, "error": "job_description_id inválido"}), 400
                logger.info(f"Usando JD existente con ID: {job_description_id}")
            except Exception:
                logger.warning(f"Fallo al convertir job_description_id a entero o al buscar en DB: {jd_id_form}")
                return jsonify({"ok": False, "error": "job_description_id inválido"}), 400
        else:
            if n == 1:
                # Lógica para crear un nuevo JD
                dup = JobDescription.query.filter(JobDescription.email == email, JobDescription.titulo == titulo).order_by(JobDescription.id.desc()).first()
                if dup and (datetime.utcnow() - (dup.created_date or datetime.utcnow())).total_seconds() < 600:
                    job_description_obj = dup
                    job_description_id = dup.id
                    logger.info(f"Reutilizando JD reciente id={job_description_id} para {email}/{titulo}")
                else:
                    job_description_obj = JobDescription(titulo=titulo, job_description=jd_text, email=email, created_date=datetime.utcnow())
                    db.session.add(job_description_obj)
                    db.session.flush()
                    job_description_id = job_description_obj.id
                    logger.info(f"Creado nuevo JD con ID: {job_description_id}")
            else:
                logger.warning("Se espera un job_description_id para paquetes no iniciales.")
                return jsonify({"ok": False, "error": "Falta job_description_id para paquete no inicial"}), 400

        created_count = invalid_count = error_count = 0

        for fs in files:
            filename = secure_filename(fs.filename or "").strip() or "sin_nombre"
            logger.info(f"Procesando archivo: {filename}")
            try:
                ext = _ext_from_filename(filename) or "file"
                raw = fs.read() or b""
                
                logger.info(f"Extrayendo texto de '{filename}' con extensión '.{ext}'...")
                txt = _extract_text_by_ext(ext, raw)
                
                # Log del texto extraído
                if not txt:
                    logger.warning(f"No se pudo extraer texto de '{filename}'.")
                else:
                    logger.info(f"Texto extraído de '{filename}': {txt[:100]}...") # Loguea solo los primeros 100 caracteres

                parsed = _call_llm(filename, txt, jd_text) if txt else {
                    "puntaje": 0.0,
                    "comentario": "Texto ilegible o no soportado.",
                    "validez": "INVALIDO",
                    "recomendado": "NO",
                }
                logger.info(f"Resultado de la IA para '{filename}': {parsed}")

                cur = Curriculos(
                    email=email,
                    created_date=datetime.utcnow(),
                    file_name=filename,
                    puntaje=float(parsed.get("puntaje") or 0.0),
                    comentario_ia=(parsed.get("comentario") or "")[:10000],
                    validez=(parsed.get("validez") or "INVALIDO").upper(),
                    recomendado=(parsed.get("recomendado") or "NO").upper(),
                    formato_original=ext,
                    job_description_id=job_description_id,
                )
                db.session.add(cur)

                if cur.validez == "INVALIDO":
                    invalid_count += 1
                else:
                    created_count += 1

            except Exception as e:
                logger.exception(f"Error procesando archivo '{filename}' en paquete {paquete}: {e}")
                error_count += 1
                continue

        db.session.commit()
        logger.info(f"Procesamiento del paquete '{paquete}' finalizado. Creados: {created_count}, Inválidos: {invalid_count}, Errores: {error_count}")

        return jsonify({
            "ok": True,
            "job_description_id": job_description_id,
            "paquete": paquete,
            "created": created_count,
            "invalid": invalid_count,
            "errors": error_count,
        }), 200

    except Exception as e:
        logger.exception(f"/upload_cvs fatal error: {e}")
        db.session.rollback()
        return jsonify({"ok": False, "error": "Internal server error"}), 500


# --- Nuevas rutas ---
@recursos_bp.route("/get_my_job_descriptions", methods=["POST"])
def get_my_job_descriptions():
    """
    POST:
      - email (str)
    """
    try:
        data = request.get_json()
        email = (data.get("email") or "").strip()

        if not email:
            return jsonify({"ok": False, "error": "Email is required."}), 400

        jds = JobDescription.query.filter_by(email=email).order_by(JobDescription.created_date.desc()).all()
        
        list_jobs = [{
            "job_description_id": jd.id,
            "titulo": jd.titulo,
            "created_at": jd.created_date.isoformat() if jd.created_date else None,
        } for jd in jds]
        
        return jsonify({"ok": True, "list_jobs": list_jobs}), 200

    except Exception as e:
        logger.exception(f"/get_my_job_descriptions fatal error: {e}")
        return jsonify({"ok": False, "error": "Internal server error"}), 500
    

# --- Paginación ---
@recursos_bp.route("/get_cv_list/", methods=["GET", "POST"])
def get_cv_list():
    """
    POST:
      - email (str)
      - job_description_id (int)
    GET:
      - page (int) [de la paginación]
      - email (str) [de la paginación]
      - job_description_id (int) [de la paginación]
    """
    per_page = 50
    try:
        is_get = request.method == "GET"
        if is_get:
            email = request.args.get("email")
            jd_id = request.args.get("job_description_id", type=int)
            page = request.args.get("page", 1, type=int)
        else:
            data = request.get_json()
            email = data.get("email")
            jd_id = data.get("job_description_id")
            page = 1

        if not email or not jd_id:
            return jsonify({"ok": False, "error": "Email and job_description_id are required."}), 400

        # CAMBIO: Ordenar por puntaje (descendente) y luego por fecha (descendente)
        pagination = Curriculos.query.filter_by(
            email=email,
            job_description_id=jd_id
        ).order_by(
            Curriculos.puntaje.desc(),
            Curriculos.created_date.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )

        cvs_data = [{
            "id": c.id,
            "email": c.email,
            "file_name": c.file_name,
            "puntaje": c.puntaje,
            "comentario_ia": c.comentario_ia,
            "validez": c.validez,
            "recomendado": c.recomendado,
            "formato_original": c.formato_original,
            "created_date": c.created_date.isoformat() if c.created_date else None,
        } for c in pagination.items]

        next_url = f"{request.path}?page={pagination.next_num}&email={email}&job_description_id={jd_id}" if pagination.has_next else None
        prev_url = f"{request.path}?page={pagination.prev_num}&email={email}&job_description_id={jd_id}" if pagination.has_prev else None

        return jsonify({
            "ok": True,
            "curriculos": cvs_data,
            "next_50": next_url,
            "prev_50": prev_url,
            "user_email": email,
            "job_description_id": jd_id,
            "current_url": request.url
        }), 200

    except Exception as e:
        logger.exception(f"/get_cv_list fatal error: {e}")
        return jsonify({"ok": False, "error": "Internal server error"}), 500
    

@recursos_bp.route("/download_my_job_description", methods=["POST"])
def download_my_job_description():
    """
    POST:
      - job_description_id (int)
    """
    try:
        data = request.get_json()
        jd_id = data.get("job_description_id")

        if not jd_id:
            return jsonify({"ok": False, "error": "job_description_id is required."}), 400

        jd = db.session.get(JobDescription, jd_id)
        if not jd:
            return jsonify({"ok": False, "error": "Job description not found."}), 404

        # CAMBIO: Ordenar por puntaje (descendente) antes de crear el DataFrame
        curriculos = Curriculos.query.filter_by(job_description_id=jd_id).order_by(
            Curriculos.puntaje.desc(),
            Curriculos.created_date.desc()
        ).all()

        if not curriculos:
            return jsonify({"ok": False, "error": "No curricula found for this job description."}), 404

        data_list = [{
            "ID_Curriculo": c.id,
            "Nombre_Archivo": c.file_name,
            "Puntaje": c.puntaje,
            "Recomendado": c.recomendado,
            "Validez": c.validez,
            "Comentario_IA": c.comentario_ia,
            "Email_Usuario": c.email,
            "Fecha_Creacion": c.created_date.isoformat() if c.created_date else None,
        } for c in curriculos]

        df = pd.DataFrame(data_list)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Resultados CV')
            workbook = writer.book
            worksheet = writer.sheets['Resultados CV']
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.set_column(i, i, column_len)

        output.seek(0)

        return send_file(output, as_attachment=True, download_name=f"job_description_{jd_id}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        logger.exception(f"/download_my_job_description fatal error: {e}")
        return jsonify({"ok": False, "error": "Internal server error"}), 500