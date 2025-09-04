from flask import Blueprint, send_file, request, jsonify, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager
from models import CuartoSurvey
from database import db                                          # importa la db desde database.py
from utils.cuarto_survey_utils import obtener_y_guardar_cuarto_survey
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO
import requests
import json




cuarto_survey_bp = Blueprint('cuarto_survey_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()

# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@cuarto_survey_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/recuperar_cuarto_survey','/test_cuarto_survey_bp','/descargar_cuarto_survey','/recuperar_segundo_survey','/test_encuestas_cursos_bp','/','/correccion_campos_vacios','/descargar_positividad_corregida','/download_comments_evaluation','/all_comments_evaluation','/download_resume_csv','/create_resumes_of_all','/descargar_excel','/create_resumes', '/reportes_disponibles', '/create_user', '/login', '/users','/update_profile','/update_profile_image','/update_admin']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
# RUTA TEST:

@cuarto_survey_bp.route('/test_cuarto_survey_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, las rutas de cuarto_survey funciona okkk..."}),200


# RUTAS SURVEY NUEVAS ( PEDIDO Y RECUPERACION )-------------------------------------------------------------//////////////////////////
# @cuarto_survey_bp.route('/recuperar_cuarto_survey', methods=['GET'])
# def obtener_y_guardar_survey_ruta():
#     from extensions import executor
#     logger.info("0 - GET > /recuperar_cuarto_survey a comenzando...")
    
#     # Lanzar la función de exportar y guardar reporte en un job separado
#     executor.submit(run_obtener_y_guardar_survey)

#     logger.info(f"1 - Hilo de ejecución independiente inicializado, retornando 200...")

#     return jsonify({"message": "El proceso de recuperacion del cuarto survey ha comenzado"}), 200

# def run_obtener_y_guardar_survey():
#     with current_app.app_context():
#         obtener_y_guardar_survey()

    

# @cuarto_survey_bp.route('/descargar_cuarto_survey', methods=['GET'])
# def descargar_segundo_survey():
#     try:
#         # Obtener el registro más reciente de la base de datos
#         survey_record = CuartoSurvey.query.order_by(CuartoSurvey.id.desc()).first()

#         if not survey_record:
#             return jsonify({"message": "No se encontraron encuestas en la base de datos"}), 404

#         # Convertir los datos binarios de vuelta a DataFrame
#         logger.info("Recuperando archivo binario desde la base de datos...")
#         binary_data = survey_record.data
#         df_responses = pd.read_pickle(BytesIO(binary_data))

#         # Convertir DataFrame a Excel en memoria
#         output = BytesIO()
#         with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
#             df_responses.to_excel(writer, index=False, sheet_name='Sheet1')

#         # Preparar el archivo Excel para enviarlo
#         output.seek(0)
#         logger.info("Archivo Excel creado y listo para descargar.")

#         return send_file(output, download_name='cuarto_survey_respuestas.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

#     except Exception as e:
#         logger.error(f"Error al generar el archivo Excel: {str(e)}")
#         return jsonify({"message": "Hubo un error al generar el archivo Excel"}), 500


# ----------------------------------------------------------------------------------------------------------//////////////////////////


@cuarto_survey_bp.route('/recuperar_cuarto_survey', methods=['GET'])
def iniciar_recuperacion_cuarto():
    from extensions import executor
    current_app.logger.info("🔔 Iniciando recuperación del cuarto survey...")
    executor.submit(run_obtener_y_guardar_cuarto)
    return jsonify({"message": "Proceso de recuperación del cuarto survey iniciado"}), 200

def run_obtener_y_guardar_cuarto():
    with current_app.app_context():
        obtener_y_guardar_cuarto_survey()


@cuarto_survey_bp.route('/descargar_cuarto_survey', methods=['GET'])
def descargar_cuarto():
    try:
        registro = CuartoSurvey.query.order_by(CuartoSurvey.id.desc()).first()
        if not registro:
            return jsonify({"message": "No hay datos del cuarto survey en la DB"}), 404

        # deserializo el pickle a DataFrame
        binary = registro.data
        df = pd.read_pickle(BytesIO(binary))

        # armo el Excel en memoria
        salida = BytesIO()
        with pd.ExcelWriter(salida, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        salida.seek(0)

        current_app.logger.info("✅ Excel del cuarto survey listo para descargar")
        return send_file(
            salida,
            download_name='cuarto_survey_respuestas.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        current_app.logger.error(f"💣 Error al generar Excel del cuarto survey: {e}")
        return jsonify({"message": "Error al generar el Excel"}), 500
    


    # -------------------------------Recupero survey crudo

@cuarto_survey_bp.route('/descargar_raw_cuarto_survey', methods=['GET'])
def descargar_raw_cuarto_survey():
    """
    Baja las respuestas bulk del cuarto survey en crudo y las devuelve
    como un .json descargable (sin renombrar columnas, sin Excel, sin DB).
    """
    try:
        access_token = os.getenv('SURVEYMONKEY_ACCESS_TOKEN')
        survey_id    = '514508354'
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        HOST     = "https://api.surveymonkey.com"
        endpoint = f"/v3/surveys/{survey_id}/responses/bulk"
        
        all_data = []
        url = f"{HOST}{endpoint}?per_page=1000"
        current_app.logger.info("🚀 Bajando respuestas bulk en crudo...")
        while url:
            r = requests.get(url, headers=headers)
            if r.status_code != 200:
                current_app.logger.error(f"Error {r.status_code} al bajar página: {r.text}")
                break
            js = r.json()
            all_data.extend(js.get("data", []))
            url = js.get("links", {}).get("next")
        
        # armo el JSON en memoria
        buf = BytesIO()
        buf.write(json.dumps(all_data, ensure_ascii=False, indent=2).encode('utf-8'))
        buf.seek(0)
        
        return send_file(
            buf,
            download_name='raw_cuarto_survey.json',
            as_attachment=True,
            mimetype='application/json'
        )
    
    except Exception as e:
        current_app.logger.error(f"💥 Falló descarga raw: {e}")
        return {"message": "Error bajando raw survey"}, 500