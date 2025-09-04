from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity   # Jwt para tokens
from models import User, Survey, TotalComents, AllApiesResumes, AllCommentsWithEvaluation,FilteredExperienceComments   # importar tabla "User" de models
from database import db                                          # importa la db desde database.py
from datetime import timedelta, datetime                         # importa tiempo especifico para rendimiento de token válido
from utils.encuestas_utils import obtener_y_guardar_survey
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO



encuestas_cursos_bp = Blueprint('encuestas_cursos_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()

# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@encuestas_cursos_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/test_encuestas_cursos_bp','/','/correccion_campos_vacios','/descargar_positividad_corregida','/download_comments_evaluation','/all_comments_evaluation','/download_resume_csv','/create_resumes_of_all','/descargar_excel','/create_resumes', '/reportes_disponibles', '/create_user', '/login', '/users','/update_profile','/update_profile_image','/update_admin']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
# RUTA TEST:

@encuestas_cursos_bp.route('/test_encuestas_cursos_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, tenemos que ver como manejar el timeout porque los archivos llegan..."}),200


# RUTAS SURVEY NUEVAS ( PEDIDO Y RECUPERACION )-------------------------------------------------------------//////////////////////////
@encuestas_cursos_bp.route('/recuperar_survey', methods=['GET'])
def obtener_y_guardar_survey_ruta():
    from extensions import executor
    logger.info("0 - GET > /recuperar_survey a comenzando...")

    
    
# Lanzar la función de exportar y guardar reporte en un job separado
    executor.submit(run_obtener_y_guardar_survey)

    logger.info(f"1 - Hilo de ejecución independiente inicializado, retornando 200...")

    return jsonify({"message": "El proceso de recuperacion de survey ha comenzado"}), 200

def run_obtener_y_guardar_survey():
    with current_app.app_context():
        obtener_y_guardar_survey()

    

@encuestas_cursos_bp.route('/descargar_survey', methods=['GET'])
def descargar_survey():
    try:
        # Obtener el registro más reciente de la base de datos
        survey_record = Survey.query.order_by(Survey.id.desc()).first()

        if not survey_record:
            return jsonify({"message": "No se encontraron encuestas en la base de datos"}), 404

        # Convertir los datos binarios de vuelta a DataFrame
        logger.info("Recuperando archivo binario desde la base de datos...")
        binary_data = survey_record.data
        df_responses = pd.read_pickle(BytesIO(binary_data))

        # Convertir DataFrame a Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_responses.to_excel(writer, index=False, sheet_name='Sheet1')

        # Preparar el archivo Excel para enviarlo
        output.seek(0)
        logger.info("Archivo Excel creado y listo para descargar.")

        return send_file(output, download_name='survey_respuestas.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        logger.error(f"Error al generar el archivo Excel: {str(e)}")
        return jsonify({"message": "Hubo un error al generar el archivo Excel"}), 500


# ----------------------------------------------------------------------------------------------------------//////////////////////////