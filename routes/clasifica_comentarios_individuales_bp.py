from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity   # Jwt para tokens
from models import AllCommentsWithEvaluation,FilteredExperienceComments   # importar tabla "User" de models
from database import db                                          # importa la db desde database.py
from datetime import timedelta, datetime                         # importa tiempo especifico para rendimiento de token válido
from utils.clasifica_utils import process_missing_sentiment, get_evaluations_of_all, process_negative_comments, comparar_comentarios
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO



clasifica_comentarios_individuales_bp = Blueprint('clasifica_comentarios_individuales_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()

# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@clasifica_comentarios_individuales_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/comparar_comentarios','/evaluate_negative_comments','/test_clasifica_comentarios_individuales_bp','/','/correccion_campos_vacios','/descargar_positividad_corregida','/download_comments_evaluation','/all_comments_evaluation','/download_resume_csv','/create_resumes_of_all','/descargar_excel','/create_resumes', '/reportes_disponibles', '/create_user', '/login', '/users','/update_profile','/update_profile_image','/update_admin']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
# RUTA TEST:

@clasifica_comentarios_individuales_bp.route('/test_clasifica_comentarios_individuales_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, tenemos que ver como manejar el timeout porque los archivos llegan..."}),200



#  ( PASO 1 ) - EVALUACION DE TODOS LOS COMENTARIOS 1 A 1 POR POSITIVIDAD O NEGATIVIDAD ( PASO 1 )

@clasifica_comentarios_individuales_bp.route('/all_comments_evaluation', methods=['POST'])
def get_evaluation_of_all():
    from extensions import executor
    try:
        logger.info("1 - Entró en la ruta all_comments_evaluation")
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

            logger.info("3 - Llamando util get_evaluations_of_all para la creación de resumenes en hilo paralelo...")
            executor.submit(run_get_evaluations_of_all, file_content)

            return jsonify({"message": "El proceso de recuperacion del reporte ha comenzado"}), 200

        else:
            logger.info("Error - El archivo que se proporcionó no es válido. Fijate que sea un .xlsx")
            return jsonify({"error": "El archivo no es válido. Solo se permiten archivos .xlsx"}), 400
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500


def run_get_evaluations_of_all(file_content):
    with current_app.app_context():
        get_evaluations_of_all(file_content)


#  ( PASO 2 ) DESCARGAR PRIMERA EVALUACION DE POSITIVIDAD DE COMENTARIOS TOTALES / DESCARGA UNA VERSIÓN SIN CORRECCIONES de "AllCommentsWithEvaluation"
@clasifica_comentarios_individuales_bp.route('/download_comments_evaluation', methods=['GET'])
def download_comments_evaluation():
    try:
        # Buscar el único archivo en la base de datos
        archivo = AllCommentsWithEvaluation.query.first()  # Como siempre habrá un único registro, usamos .first()

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
            headers={"Content-disposition": "attachment; filename=all_comments_evaluation.csv"}
        )
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error al procesar el archivo: {str(e)}"}), 500


#  ( PASO 3 ) CORRECCIÓN DE CAMPOS VACIOS - Corrige en loop todos los campos vacios (aprox 8 loops )Es necesario enviarle el archivo generado en el paso 1 y decargado en paso 2. 
@clasifica_comentarios_individuales_bp.route('/correccion_campos_vacios', methods=['POST'])
def missing_sentiment():
    from extensions import executor
    try:
        logger.info("1 - Entró en la ruta correccion_campos_vacios")
        if 'file' not in request.files:
            logger.info(f"Error al recuperar el archivo adjunto del request")
            return jsonify({"error": "No se encontró ningún archivo en la solicitud"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400

        if file and file.filename.lower().endswith('.csv'):
            # Leer el archivo CSV directamente desde la memoria (sin decodificar)
            logger.info("2 - Archivo recuperado. Leyendo archivo CSV...")
            file_content = file.read()  # Mantener el archivo como bytes
            
            logger.info("3 - Llamando util process_missing_sentiment para procesar los sentimientos faltantes en hilo paralelo...")
            executor.submit(run_process_missing_sentiment, file_content)

            return jsonify({"message": "El proceso de corrección del reporte ha comenzado"}), 200

        else:
            logger.info("Error - El archivo proporcionado no es válido. Fijate que sea un .csv")
            return jsonify({"error": "El archivo no es válido. Solo se permiten archivos .csv"}), 400
    
    except Exception as e:
        logger.error(f"Error en la ruta correccion_campos_vacios: {str(e)}")
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500

def run_process_missing_sentiment(file_content):
    with current_app.app_context():
        process_missing_sentiment(file_content)



# PASO 4 - CORRECCION DE CAMPOS NEGATIVOS E INVALIDOS

@clasifica_comentarios_individuales_bp.route('/evaluate_negative_comments', methods=['POST'])
def evaluate_negative_comments():
    from extensions import executor
    try:
        logger.info("1 - Entró en la ruta evaluate_negative_comments")
        if 'file' not in request.files:
            logger.info("Error al recuperar el archivo adjunto del request")
            return jsonify({"error": "No se encontró ningún archivo en la solicitud"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
        if file and file.filename.lower().endswith('.csv'):
            # Leer el archivo CSV directamente desde la memoria (sin decodificar)
            logger.info("2 - Archivo recuperado. Leyendo archivo para comentarios negativos...")
            file_content = file.read()  # Mantener el archivo como bytes

            logger.info("3 - Llamando util process_negative_comments para la creación de resumenes en hilo paralelo...")
            executor.submit(run_process_negative_comments, file_content)

            return jsonify({"message": "El proceso de evaluación de comentarios negativos ha comenzado"}), 200

        else:
            logger.info("Error - El archivo que se proporcionó no es válido. Fijate que sea un .xlsx")
            return jsonify({"error": "El archivo no es válido. Solo se permiten archivos .xlsx"}), 400
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500


def run_process_negative_comments(file_content):
    with current_app.app_context():
        process_negative_comments(file_content)


#  ( PASO 5 ) DESCARGAR EVALUACION DE SENTIMIENTO DE COMENTARIOS TOTALES ( CON CORRECCIONES DE: CAMPOS VACIOS / negativos / invalidos )
@clasifica_comentarios_individuales_bp.route('/descargar_positividad_corregida', methods=['GET'])
def descargar_positividad_corregida():
    try:
        # Buscar el único archivo en la base de datos
        archivo = FilteredExperienceComments.query.first()  # Como siempre habrá un único registro, usamos .first()

        if not archivo:
            return jsonify({"error": "No se encontró ningún archivo"}), 404

        # Leer el archivo binario desde la base de datos
        archivo_binario = archivo.archivo_binario

        # Preparar la respuesta con el CSV como descarga
        return Response(
            archivo_binario,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=all_comments_evaluation_fixed.csv"}
        )
    
    except Exception as e:
        return jsonify({"error": f"Se produjo un error al procesar el archivo: {str(e)}"}), 500
    
#---------------------------------------------FIN DEL PROCESO------------------------------------------------



# Comparacion simple evaluacion de sentimiento de jefes de estacion contra evaluacion de sentimiento openai:

@clasifica_comentarios_individuales_bp.route('/comparar_comentarios', methods=['POST'])
def upload_files():
    # Verificar si los archivos fueron enviados en la solicitud
    if 'humanos' not in request.files or 'openai' not in request.files:
        return jsonify({"error": "Faltan archivos 'humanos' y/o 'openai'"}), 400

    humanos_file = request.files['humanos']
    openai_file = request.files['openai']

    # Leer los archivos como objetos en memoria para usarlos con pandas
    humanos_df = pd.read_excel(humanos_file)
    openai_df = pd.read_csv(openai_file, delimiter=',', encoding='ISO-8859-1')
    
    # Llamar a la función de comparación pasándoles los DataFrames
    resultado_df = comparar_comentarios(humanos_df, openai_df)

    # Guardar el resultado en un archivo CSV en memoria
    output = BytesIO()
    resultado_df.to_csv(output, index=False)
    output.seek(0)

    # Enviar el archivo resultante como descarga
    return send_file(output, download_name='resultado_comparacion.csv', as_attachment=True, mimetype='text/csv')