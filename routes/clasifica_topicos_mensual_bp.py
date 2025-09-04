from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity   # Jwt para tokens
from models import AllCommentsWithEvaluation,FilteredExperienceComments   # importar tabla "User" de models
from database import db                                          # importa la db desde database.py
from datetime import timedelta, datetime                         # importa tiempo especifico para rendimiento de token válido
from utils.clas_topicos_utils import process_missing_topics, get_evaluations_of_all
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO



clasifica_topicos_mensual_bp = Blueprint('clasifica_topicos_mensual_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()


    
# RUTA TEST:

@clasifica_topicos_mensual_bp.route('/test_clasifica_utils_mensuales_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, funcionan rutas utils mensuales"}),200



#  ( PASO 1 ) - EVALUACION DE TODOS LOS COMENTARIOS 1 A 1 POR POSITIVIDAD O NEGATIVIDAD ( PASO 1 )

@clasifica_topicos_mensual_bp.route('/all_comments_evaluation_topics', methods=['POST'])
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
@clasifica_topicos_mensual_bp.route('/download_comments_evaluation_topics', methods=['GET'])
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
@clasifica_topicos_mensual_bp.route('/correccion_campos_vacios_topics', methods=['POST'])
def missing_sentiment():
    from extensions import executor
    try:
        logger.info("1 - Entró en la ruta correccion_campos_vacios_topics")
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
            
            logger.info("3 - Llamando util process_missing_topics para procesar los topicos faltantes en hilo paralelo...")
            executor.submit(run_process_missing_topics, file_content)

            return jsonify({"message": "El proceso de corrección del reporte ha comenzado"}), 200

        else:
            logger.info("Error - El archivo proporcionado no es válido. Fijate que sea un .csv")
            return jsonify({"error": "El archivo no es válido. Solo se permiten archivos .csv"}), 400
    
    except Exception as e:
        logger.error(f"Error en la ruta correccion_campos_vacios: {str(e)}")
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500

def run_process_missing_topics(file_content):
    with current_app.app_context():
        process_missing_topics(file_content)



#  ( PASO 4 ) DESCARGAR EVALUACION DE TOPICO DE COMENTARIOS TOTALES ( CON CORRECCIONES DE: CAMPOS VACIOS)
@clasifica_topicos_mensual_bp.route('/descargar_positividad_corregida_topics', methods=['GET'])
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