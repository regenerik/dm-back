from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager                        # Jwt para tokens
from datetime import datetime                         # importa tiempo especifico para rendimiento de token válido
from utils.actividades_utils import  exportar_y_guardar_reporte, obtener_reporte, iniciar_sesion_y_obtener_sesskey
from logging_config import logger
import os                                                        # Para datos .env
from models import Reporte
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pytz
import re
from io import BytesIO
import io
import xlsxwriter
import csv



rescate_actividades_bp = Blueprint('rescate_actividades_bp', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()

# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY


@rescate_actividades_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/test_rescate_reportes_bp','/recuperar_actividades','/obtener_actividades','/descargar_actividad/<int:actividad_id>']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
# RUTA TEST:

@rescate_actividades_bp.route('/test_rescate_reportes_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, rutas de actividades funcionan bien..."}),200



#--------------------------------RUTAS MULTIPLES-----------------------------------------------------------------------------------

#RECUPERAR DE FUENTE>
@rescate_actividades_bp.route('/recuperar_actividades', methods=['POST'])
def exportar_y_guardar_reporte_ruta():
    from extensions import executor
    logger.info("POST > /recuperar_actividades comenzando...")

    data = request.get_json()
    if 'username' not in data or 'password' not in data or 'url' not in data:
        return jsonify({"error": "Falta username, password, url o user_id en el cuerpo JSON"}), 400
    logger.info(f"1 - Url requerida: {data['url']}.")
    username = data['username']
    password = data['password']
    url = data['url']

    # Llamando al inicio de session por separado y recuperando resultados...
    session, sesskey = iniciar_sesion_y_obtener_sesskey(username, password, url)
    if not session or not sesskey:
        logger.info("Error al iniciar sesión o al obtener el sesskey.")
        return jsonify({"error": "Error al iniciar sesión o al obtener el sesskey"}), 500
    
# Lanzar la función de exportar y guardar reporte en un job separado
    executor.submit(run_exportar_y_guardar_reporte, session, sesskey, username, url)

    return jsonify({"message": "El proceso de recuperacion del reporte ha comenzado"}), 200

def run_exportar_y_guardar_reporte(session, sesskey, username, url):
    with current_app.app_context():
        exportar_y_guardar_reporte(session, sesskey, username, url)

    
    
# -----------------------------------------------ACA LO NUEVO---------------------------------------------------------
# 1) Función auxiliar para convertir CSV a XLSX en memoria
def convertir_csv_a_xlsx(csv_bytes):
    # Intentamos decodificar con UTF-8, y si falla, con latin1
    try:
        csv_str = csv_bytes.decode('utf-8')
    except UnicodeDecodeError:
        logger.info("Decoding con utf-8 falló, usando latin1")
        csv_str = csv_bytes.decode('latin1', errors='replace')
    
    # Logueamos los primeros 200 caracteres para confirmar el contenido
    logger.info("Primeros caracteres del CSV: " + csv_str[:200])
    logger.info("Tamaño total del CSV en bytes: " + str(len(csv_bytes)))
    
    # Usamos csv.reader para procesar el CSV
    csv_reader = csv.reader(csv_str.splitlines())
    
    # Creamos el XLSX en memoria
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    
    row_count = 0
    for row in csv_reader:
        for col_count, cell in enumerate(row):
            worksheet.write(row_count, col_count, cell)
        row_count += 1
    
    logger.info(f"Total de filas convertidas: {row_count}")
    workbook.close()
    output.seek(0)
    return output.read()

@rescate_actividades_bp.route('/obtener_actividades', methods=['POST'])
def descargar_reporte():
    logger.info("POST > /obtener_actividades comenzando...")
    data = request.get_json()
    if 'reporte_url' not in data:
        return jsonify({"error": "Falta reporte_id, username o tipo de archivo en el cuerpo JSON"}), 400

    reporte_url = data['reporte_url']
    file_type = data.get('file_type', 'csv')
    logger.info(f"2 - Url requerida para descarga: {reporte_url}")
    
    reporte_data, created_at, title = obtener_reporte(reporte_url)
    if title is None:
        title = "reporte_obtenido"

    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
    safe_title = re.sub(r'\s+', '_', safe_title)

    if reporte_data:
        local_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        created_at_utc = created_at.replace(tzinfo=pytz.utc)
        created_at_local = created_at_utc.astimezone(local_tz)
        timestamp = created_at_local.strftime('%d-%m-%Y_%H-%M')

        # Si se pide XLSX...
        if file_type == 'xlsx':
            # Detectá si el archivo ya es XLSX (firma "PK")
            if reporte_data.startswith(b'PK'):
                logger.info("El reporte ya está en formato XLSX, devolviéndolo directamente")
                filename = f'{safe_title}_{timestamp}.xlsx'
                response = make_response(reporte_data)
                response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'
                return response, 200
            else:
                # Si no empieza con PK, asumimos que es CSV y lo convertimos
                xlsx_data = convertir_csv_a_xlsx(reporte_data)
                filename = f'{safe_title}_{timestamp}.xlsx'
                response = make_response(xlsx_data)
                response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'
                return response, 200

        # Si se pide otro tipo de archivo, tratá de servirlo como venía
        elif file_type == 'json':
            filename = f'{safe_title}_{timestamp}.json'
            response = make_response(reporte_data)
            response.headers['Content-Type'] = 'application/json'
        elif file_type == 'html':
            filename = f'{safe_title}_{timestamp}.html'
            response = make_response(reporte_data)
            response.headers['Content-Type'] = 'text/html'
        elif file_type == 'csv':
            filename = f'{safe_title}_{timestamp}.csv'
            response = make_response(reporte_data)
            response.headers['Content-Type'] = 'text/csv'
        else:
            filename = f'{safe_title}_{timestamp}.csv'
            response = make_response(reporte_data)
            response.headers['Content-Type'] = 'text/csv'

        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response, 200
    else:
        logger.info("El util>obtener_reporte no devolvió la data...Respuesta de server 404")
        return jsonify({"error": "No se encontró el reporte"}), 404



# Descargar reporte especifico por ID----------------------------------

@rescate_actividades_bp.route('/descargar_actividad/<int:actividad_id>', methods=['GET'])
def descargar_reporte_especifico(actividad_id):
    # Buscamos el reporte por id
    report = Reporte.query.get(actividad_id)
    if not report:
        return jsonify({'error': 'Actividad no encontrada'}), 404

    # Creamos un archivo en memoria con el contenido del reporte
    file_data = io.BytesIO(report.data)

    # Armamos un nombre de archivo: "titulo_fecha.csv"
    if report.created_at:
        timestamp = report.created_at.strftime("%Y%m%d_%H%M%S")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{report.title}_{timestamp}.csv"

    response = send_file(
        file_data,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )
    response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response, 200
