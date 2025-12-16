
from flask import Blueprint, request, jsonify, current_app, send_file
from reportlab.pdfgen import canvas
from logging_config import logger
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import io, os, base64, textwrap
from mailjet_rest import Client
from dotenv import load_dotenv
from models import FormularioNecesidades
from datetime import datetime
from database import db
import pandas as pd
from io import BytesIO
from utils.form_necesidades_utils import query_assistant


load_dotenv()

form_necesidades_bp = Blueprint('form_necesidades_bp', __name__)

# Clave API para proteger la ruta
API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@form_necesidades_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path == '/test_form_necesidades_bp':
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401

@form_necesidades_bp.route('/test_form_necesidades_bp', methods=['GET'])
def test():
    return jsonify({'message': 'Test OK'}), 200

@form_necesidades_bp.route('/form_necesidades', methods=['POST'])
def procesar_formulario_necesidades():
    try:
        payload = request.get_json()

        # 1️⃣ Guardar formulario
        form = FormularioNecesidades(
            provincia=payload.get("provincia"),
            localidad=payload.get("localidad"),
            apies=payload.get("apies"),
            empleados_total=payload.get("empleadosTotal"),
            gestor=payload.get("gestor"),
            email_gestor=payload.get("emailGestor"),
            experiencia_cliente=payload.get("experienciaCliente"),
            liderazgo=payload.get("liderazgo"),
            comentarios=payload.get("comentarios"),
            seguridad_operativa=payload.get("seguridadOperativa"),
        )

        db.session.add(form)
        db.session.commit()

        # 2️⃣ Armar texto del formulario
        seg = payload.get("seguridadOperativa", {})

        form_text = f"""
DATOS DE LA ESTACIÓN
Provincia: {payload.get("provincia")}
Localidad: {payload.get("localidad")}
APIES: {payload.get("apies")}
Cantidad de empleados: {payload.get("empleadosTotal")}
Gestor: {payload.get("gestor")}
Email gestor: {payload.get("emailGestor")}

SEGURIDAD OPERATIVA
Aplicación general:
Puntaje: {seg.get("general", {}).get("score")}
Comentario: {seg.get("general", {}).get("comentario")}

Uso de EPP:
Puntaje: {seg.get("epp", {}).get("score")}
Comentario: {seg.get("epp", {}).get("comentario")}

Procedimientos de emergencia:
Puntaje: {seg.get("emergencias", {}).get("score")}
Comentario: {seg.get("emergencias", {}).get("comentario")}

Manipulación de productos:
Puntaje: {seg.get("manipulacion", {}).get("score")}
Comentario: {seg.get("manipulacion", {}).get("comentario")}

EXPERIENCIA DEL CLIENTE
Puntaje: {payload.get("experienciaCliente")}

LIDERAZGO
Puntaje: {payload.get("liderazgo")}

COMENTARIOS GENERALES
{payload.get("comentarios")}
"""

        # 3️⃣ Prompt final
        evaluation_prompt = f"""
Evaluá la siguiente estación YPF.

Respondé EXCLUSIVAMENTE con este formato:

[EVALUACION_SEGURIDAD]
Aplicacion_general: X
Uso_EPP: X
Emergencias: X
Manipulacion_productos: X

[EVALUACION_CLIENTE]
Experiencia_cliente: X
Liderazgo: X

[DIAGNOSTICO]
Texto.

[CURSOS_RECOMENDADOS]
- Curso 1
- Curso 2

[JUSTIFICACION]
Texto.

DIAGNÓSTICO:
{form_text}
"""

        # 4️⃣ Llamar al assistant (guarda en DB internamente)
        respuesta_ia = query_assistant(evaluation_prompt, form.id)

        # 5️⃣ Responder al frontend
        return jsonify({
            "status": "ok",
            "form_id": form.id,
            "respuesta_ia": respuesta_ia
        }), 200

    except Exception as e:
        logger.exception("Error procesando formulario de necesidades")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
