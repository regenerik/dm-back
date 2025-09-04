from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity   # Jwt para tokens
from models import  TotalComents, AllApiesResumes  # importar tabla "User" de models
from database import db                                          # importa la db desde database.py
from datetime import timedelta, datetime                         # importa tiempo especifico para rendimiento de token válido
from utils.resumen_utils import get_resumes_of_all, get_resumes_for_apies, get_resumes
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO



resumen_comentarios_apies_bp = Blueprint('resumen_comentarios_apies_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()

# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@resumen_comentarios_apies_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/test_resumen_comentarios_apies_bp','/','/correccion_campos_vacios','/descargar_positividad_corregida','/download_comments_evaluation','/all_comments_evaluation','/download_resume_csv','/create_resumes_of_all','/descargar_excel','/create_resumes', '/reportes_disponibles', '/create_user', '/login', '/users','/update_profile','/update_profile_image','/update_admin']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
    
# RUTA TEST:

@resumen_comentarios_apies_bp.route('/test_resumen_comentarios_apies_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, tenemos que ver como manejar el timeout porque los archivos llegan..."}),200

# CREAR RESUMEN INDIVIDUAL ( APIE )

@resumen_comentarios_apies_bp.route('/get_one_resume', methods=['POST'])
def get_one_resume():
    logger.info("1 - Entró en ruta /get_one_resume...")
    request_data = request.json
    apies_input = request_data.get("apies")
    logger.info(f"2 - Recuperando apies: {apies_input}")


    db_data = TotalComents.query.first().data

    if not db_data:
        return jsonify({"error": "No se encontraron datos en la base de datos"}), 404

    # Ahora pasamos los datos binarios al util
    output = get_resumes_for_apies(apies_input, db_data)

    # Aquí verificamos si `output` contiene un mensaje de error en lugar de un archivo
    if isinstance(output, str) and "No se encontraron comentarios" in output:
        logger.info(output)
        return jsonify({"error": output}), 404

    logger.info(f"11 - Devolviendo resultado de apies: {apies_input}. Fin de la ejecución.")
    # Devolver el Excel al frontend si todo va bien
    return send_file(output, download_name=f"resumen_apies_{apies_input}.xlsx", as_attachment=True)

# CREAR RESUMENES DE UN PEQUEÑO GRUPO Y DEVUELVE EN EL MOMENTO 

@resumen_comentarios_apies_bp.route('/create_resumes', methods=['POST'])
def create_resumes():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No se encontró ningún archivo en la solicitud"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400

        if file and file.filename.lower().endswith('.xlsx'):
            # Leer el archivo directamente desde la memoria
            file_content = file.read()

            # Llamamos al util que procesa el contenido del archivo y genera el archivo Excel
            output = get_resumes(file_content)

            # Preparar la respuesta para enviar el archivo Excel
            return send_file(output, download_name="resumenes.xlsx", as_attachment=True)

        else:
            return jsonify({"error": "El archivo no es válido. Solo se permiten archivos .xlsx"}), 400
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500
    

# CREAR RESUMENES DE LAS 1600 ESTACIONES / ( GENERA PERO NO DEVUELVE ) > PARA DESCARGAR USAR LA PROXIMA RUTA

@resumen_comentarios_apies_bp.route('/create_resumes_of_all', methods=['POST'])
def create_resumes_of_all():
    from extensions import executor
    try:
        logger.info("1 - Entró en la ruta create_resumes_of_all")
        if 'file' not in request.files:
            logger.info(f"Error al recuperar el archivo adjunto del request")
            return jsonify({"error": "No se encontró ningún archivo en la solicitud"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400


        if file and file.filename.lower().endswith('.xlsx'):
            # Leer el archivo directamente desde la memoria
            logger.info("2 - Archivo recuperado. Leyendo archivo...")
            file_content = file.read()

            logger.info("3 - Llamando util get_resumes_of_all para la creación de resumenes en hilo paralelo...")
            executor.submit(run_get_resumes_of_all, file_content)

            return jsonify({"message": "El proceso de recuperacion del reporte ha comenzado"}), 200

        else:
            logger.info("Error - El archivo que se proporcionó no es válido. Fijate que sea un .xlsx")
            return jsonify({"error": "El archivo no es válido. Solo se permiten archivos .xlsx"}), 400
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500


def run_get_resumes_of_all(file_content):
    with current_app.app_context():
        get_resumes_of_all(file_content)


# DESCARGAR RESUMEN DE LAS 1600 ESTACIONES
@resumen_comentarios_apies_bp.route('/download_resume_csv', methods=['GET'])
def download_resume_csv():
    try:
        # Buscar el único archivo en la base de datos
        archivo = AllApiesResumes.query.first()  # Como siempre habrá un único registro, usamos .first()

        if not archivo:
            return jsonify({"error": "No se encontró ningún archivo"}), 404

        # Leer el archivo binario desde la base de datos
        archivo_binario = archivo.archivo_binario

        # # Convertir el binario a CSV directamente
        # csv_data = archivo_binario.decode('utf-8') 

        # Preparar la respuesta con el CSV como descarga
        return Response(
            archivo_binario,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=resumen.csv"}
        )
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error al procesar el archivo: {str(e)}"}), 500
    