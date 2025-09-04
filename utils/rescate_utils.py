from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
from database import db
from models import Reporte, TodosLosReportes, Usuarios_Sin_ID, ValidaUsuarios,DetalleApies, AvanceCursada, DetallesDeCursos, CursadasAgrupadas, QuintoSurveySql, CuartoSurveySql
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from io import BytesIO
import pytz
from dotenv import load_dotenv
load_dotenv()
import os
from logging_config import logger
import gc
import csv

# Zona horaria de São Paulo/Buenos Aires
tz = pytz.timezone('America/Sao_Paulo')

# - Creando cliente openai
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization="org-cSBk1UaTQMh16D7Xd9wjRUYq"
)


#-----------------------------CAPTURAR REPORTES EXISTENTES-----------------------------------
def compilar_reportes_existentes():
    # Obtener todos los reportes posibles
    todos_los_reportes = TodosLosReportes.query.all()  # Asegúrate de tener un modelo para esta tabla
    titulos_posibles = [reporte.title for reporte in todos_los_reportes]

    logger.info(f"1 - Todos los titulos de reportes posibles son: {titulos_posibles}")
    reportes_disponibles = Reporte.query.all()  # La tabla que ya tenés con reportes disponibles

    # Serializar los reportes disponibles
    reportes_disponibles_serializados = []
    for reporte in reportes_disponibles:
        created_at_utc = reporte.created_at.replace(tzinfo=pytz.utc)
        created_at_local = created_at_utc.astimezone(tz)
        reporte_dict = {
            'id': reporte.id,
            'user_id': reporte.user_id,
            'report_url': reporte.report_url,
            'title': reporte.title,
            'size_megabytes': reporte.size,
            'elapsed_time': reporte.elapsed_time,
            'created_at': created_at_local.strftime("%d/%m/%Y %H:%M:%S")
        }
        reportes_disponibles_serializados.append(reporte_dict)

    # Crear un set de URLs de reportes disponibles
    urls_disponibles = {reporte.report_url for reporte in reportes_disponibles}

    # Filtrar los reportes no disponibles
    reportes_no_disponibles_serializados = []
    for reporte in todos_los_reportes:
        if reporte.report_url not in urls_disponibles:
            reporte_dict = {
                'report_url': reporte.report_url,
                'title': reporte.title,
                'size_megabytes': None,  # Podés dejarlo en None si no tenés el tamaño para los no disponibles
                'created_at': None  # Si no hay fecha para los no disponibles, dejarlo en None
            }
            reportes_no_disponibles_serializados.append(reporte_dict)

    # Devolver ambas listas en un objeto
    return {
        'disponibles': reportes_disponibles_serializados,
        'no_disponibles': reportes_no_disponibles_serializados
    }


# ----------------------------UTILS GENERAL PARA LOGGIN SESSION Y SESSKEY--------------------

def iniciar_sesion_y_obtener_sesskey(username, password, report_url):
    session = requests.Session()
    logger.info("2 - Función Util iniciar_sesion_y_obtener_sesskey iniciando...")

    # Paso 1: Obtener el logintoken
    login_page_url = "https://www.campuscomercialypf.com/login/index.php"
    try:
        login_page_response = session.get(login_page_url, timeout=10)
        login_page_soup = BeautifulSoup(login_page_response.text, 'html.parser')
        logintoken_input = login_page_soup.find('input', {'name': 'logintoken'})
        logintoken = logintoken_input['value'] if logintoken_input else None
        logger.info("3 - Token recuperado. Iniciando log-in...")
    except requests.exceptions.RequestException as e:
        logger.info(f"Error al obtener la página de login: {e}")
        logger.info("Si llegaste a este error, puede ser que la red esté caída o la URL del campus haya cambiado.")
        return None, None

    # Paso 2: Realizar el inicio de sesión
    login_payload = {
        "username": username,
        "password": password,
        "logintoken": logintoken,
        "anchor": ""
    }
    login_headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }


    login_response = session.post(login_page_url, data=login_payload, headers=login_headers)

    if login_response.status_code == 200 and "TotaraSession" in session.cookies:
        logger.info("4 - Inicio de sesión exitoso. Comenzando a capturar el sesskey...")
    else:
        logger.info("Error en el inicio de sesión")
        return None, None

    # Paso 3: Obtener el sesskey dinámicamente desde la página
    dashboard_url = report_url
    dashboard_response = session.get(dashboard_url)
    dashboard_html = dashboard_response.text
    soup = BeautifulSoup(dashboard_html, 'html.parser')
    sesskey_link = soup.find('a', href=re.compile(r'/login/logout.php\?sesskey='))
    if sesskey_link:
        sesskey_url = sesskey_link['href']
        sesskey = re.search(r'sesskey=([a-zA-Z0-9]+)', sesskey_url)
        if sesskey:
            logger.info("5 - Sesskey recuperado.")
            return session, sesskey.group(1)
    logger.info("Error: No se pudo obtener el sesskey")
    return None, None


# -----------------------------------UTILS PARA LLAMADA SIMPLE------------------------------------

def exportar_reporte_json(username, password, report_url):
    session, sesskey = iniciar_sesion_y_obtener_sesskey(username, password, report_url)
    if not session or not sesskey:
        logger.info("Error al iniciar sesión o al obtener el sesskey.")
        return None
    
    logger.info("Recuperando reporte desde la URL...")

    # Paso 4: Traer los datos en excel
    export_payload = {
        "sesskey": sesskey,
        "_qf__report_builder_export_form": "1",
        "format": "excel",
        "export": "Exportar"
    }
    export_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": report_url
    }

    export_response = session.post(report_url, data=export_payload, headers=export_headers)
    logger.info("ESTE ES EL EXPORT RESPONSE: ", export_response)

    if export_response.status_code == 200:
        logger.info("Excel recuperado. Transformando a json...")

        # Leer el archivo Excel y convertir a JSON
        excel_data = BytesIO(export_response.content)
        df = pd.read_excel(excel_data, engine='openpyxl')
        json_data = df.to_json(orient='records')  # Convertir DataFrame a JSON
        logger.info("Enviando json de utils a la ruta...")
        return json_data

    else:
        logger.info("Error en la exportación")
        return None

# -----------------------------------UTILS PARA LLAMADA MULTIPLE------------------------------------



# ---- funciones dedicadas para cada URL “especial” ----
def procesar_usuarios_por_asignacion(csv_bytes_io):
    """
    Ejemplo de función que parsea el CSV y guarda cada fila
    en la tabla InscripcionMarketplace.
    """
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)
    from models import Usuarios_Por_Asignacion  # tu modelo SQLAlchemy

    db.session.query(Usuarios_Por_Asignacion).delete() # Como no es acumulativo borramos todo antes de guardar lo nuevo


    for row in reader:
        fecha_str = row.get('fecha_suspension', '').strip()
        if fecha_str:
            try:
                # ajustá el formato si tu CSV viene con otro (ej: '07/04/2025')
                fecha_susp = datetime.strptime(fecha_str, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"Fecha inválida '{fecha_str}', seteando None")
                fecha_susp = None
        else:
            fecha_susp = None
        insc = Usuarios_Por_Asignacion(
            id_asignacion    = row.get('ID Asignación'),
            dni              = row.get('DNI'),
            nombre_completo  = row.get('Nombre Completo'),
            rol_funcion      = row.get('Rol/Función'),
            id_pertenencia   = row.get('ID Pertenencia'),
            pertenencia      = row.get('Pertenencia'),
            estatus_usuario  = row.get('Estatus del Usuario'),
            fecha_suspension = fecha_susp,
        )
        db.session.add(insc)
    db.session.commit()
    logger.info("✓ Filas de 'Usuarios_por_Asignacion' guardadas en Usuarios_Por_Asignacion.")

def procesar_usuarios_sin_id(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)

    def parse_date(val):
        v = val.strip()
        if not v or v.lower().startswith('hace '):
            return None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        logger.debug(f"parse_date: no pude convertir '{v}', lo dejo None")
        return None


    db.session.query(Usuarios_Sin_ID).delete() 
    for row in reader:
        ultimo_login  = parse_date(row.get('Último inicio de sesión del usuario', ''))
        ultimo_acceso = parse_date(row.get('Último Acceso', ''))
        fecha_ingreso = parse_date(row.get('Fecha de Ingreso', ''))

        usuario = Usuarios_Sin_ID(
            nombre_usuario       = row.get('Nombre del usuario', '').strip(),
            dni                  = row.get('DNI', '').strip(),
            email                = row.get('Email', '').strip(),
            ultimo_inicio_sesion = ultimo_login,
            estatus_usuario      = row.get('Estatus del Usuario', '').strip(),
            ultimo_acceso        = ultimo_acceso,
            fecha_ingreso        = fecha_ingreso,
        )
        db.session.add(usuario)

    db.session.commit()
    logger.info("✓ Filas de 'Usuarios sin ID' guardadas en Usuarios_Sin_ID.")

def procesar_valida_usuarios(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)

    def parse_date(val):
        v = val.strip()
        if not v:
            return None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        logger.debug(f"parse_date: no pude convertir '{v}', lo dejo None")
        return None

    # Limpiar la tabla antes de guardar los nuevos registros
    db.session.query(ValidaUsuarios).delete()

    for row in reader:
        fecha_nac = parse_date(row.get('Fecha de Nacimiento', ''))

        usuario = ValidaUsuarios(
            nombre_completo     = row.get('Nombre completo', '').strip(),
            ciudad              = row.get('Ciudad', '').strip(),
            nivel_estudios      = row.get('Nivel de estudios', '').strip(),
            fecha_nacimiento    = fecha_nac,
            traslado_moto       = row.get('Me traslado en Moto', '').strip(),
            traslado_bicicleta  = row.get('Me traslado en Bicicleta', '').strip(),
            anio_ingreso        = row.get('Año de ingreso a la compañía', '').strip(),
            socio_serviclub     = row.get('Socio ServiClub', '').strip(),
            estatus_usuario     = row.get('Estatus del Usuario', '').strip(),
            dni                 = row.get('DNI', '').strip(),
        )
        db.session.add(usuario)

    db.session.commit()
    logger.info("✓ Filas de 'ValidaUsuarios' cargadas con éxito.")

def procesar_detalle_apies(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)

    # Limpiar la tabla antes de guardar los nuevos registros
    db.session.query(DetalleApies).delete()

    for row in reader:
        detalle = DetalleApies(
            apies               = row.get('APIES', '').strip(),
            apies_razon_social  = row.get('APIES Rz Social', '').strip(),
            cuadro              = row.get('Cuadro', '').strip(),
            numero_id_padre     = row.get('Numero ID del Padre', '').strip(),
            red                 = row.get('RED', '').strip(),
            region              = row.get('Region', '').strip(),
            segmento            = row.get('Segmento', '').strip(),
            zona                = row.get('Zona', '').strip(),
        )
        db.session.add(detalle)

    db.session.commit()
    logger.info("✓ Filas de 'DetalleApies' cargadas correctamente.")

def procesar_ypf_2025_avance_cursada(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)

    def parse_date(val):
        v = val.strip()
        if not v:
            return None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        logger.debug(f"parse_date: no pude convertir '{v}', lo dejo None")
        return None

    # Limpiar la tabla antes de insertar nuevos datos
    db.session.query(AvanceCursada).delete()

    for row in reader:
        fecha_fin = parse_date(row.get('Fecha de Fin del curso', ''))

        curso = AvanceCursada(
            apies                   = row.get('APIES', '').strip(),
            apies_razon_social      = row.get('APIES RzSocial', '').strip(),
            dni                     = row.get('DNI', '').strip(),
            nombre_completo_usuario = row.get('Nombre completo del usuario', '').strip(),
            rol_funcion             = row.get('Rol/Funcion', '').strip(),
            estatus_usuario         = row.get('Estatus del Usuario', '').strip(),
            nombre_programa         = row.get('Nombre del programa', '').strip(),
            nombre_corto_curso      = row.get('Nombre Corto del Curso', '').strip(),
            estatus_curso           = row.get('Estatus del Curso', '').strip(),
            fecha_fin_curso         = fecha_fin,
        )
        db.session.add(curso)

    db.session.commit()
    logger.info("✓ Filas de 'AvanceCursada' cargadas correctamente.")

def procesar_cursos_agrupados(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)

    nuevos_registros = 0
    saltados = 0

    # Traemos todos los id_concat existentes de la tabla
    existentes = set(
        r[0] for r in db.session.query(CursadasAgrupadas.id_concat).all()
    )

    for row in reader:
        dni = row.get('DNI', '').strip()
        id_curso = row.get('ID Curso', '').strip()
        estatus = row.get('Estatus de finalización', '').strip()
        fecha = row.get('La fecha de finalización', '').strip()
        id_concat = f"{dni}{id_curso}"

        if id_concat in existentes:
            logger.debug(f"Registro ya existe, salteado: {id_concat}")
            saltados += 1
            continue

        nuevo = CursadasAgrupadas(
            dni=dni,
            id_curso=id_curso,
            estatus_finalizacion=estatus,
            fecha_finalizacion=fecha,
            id_concat=id_concat
        )
        db.session.add(nuevo)
        existentes.add(id_concat)
        nuevos_registros += 1

    db.session.commit()
    logger.info(f"✓ Se guardaron {nuevos_registros} registros nuevos. {saltados} ya existían y fueron ignorados.")

def procesar_detalles_de_cursos(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    lines = decoded.splitlines()
    reader = csv.DictReader(lines)

    def parse_date(val):
        v = val.strip()
        if not v:
            return None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        logger.debug(f"parse_date: no pude convertir '{v}', lo dejo None")
        return None

    db.session.query(DetallesDeCursos).delete()

    for row in reader:
        fecha_creacion = parse_date(row.get('Fecha de Creacion', ''))

        curso = DetallesDeCursos(
            nombre_curso        = row.get('Nombre del Curso', '').strip(),
            id_curso            = row.get('ID del Curso', '').strip(),
            negocio_solicitante = row.get('Negocio que solicita', '').strip(),
            horas_formacion     = row.get('Horas de Formacion', '').strip(),
            modalidad           = row.get('Modalidad', '').strip(),
            resumen_curso       = row.get('Resumen del Curso', '').strip(),
            fecha_creacion      = fecha_creacion,
            visible_oculto      = row.get('Curso Visible/Oculto', '').strip(),
            capacidad_marco     = row.get('Capacidad marco', '').strip(),
            tematica            = row.get('Temática', '').strip(),
            impacto_negocio     = row.get('Impacto en negocio', '').strip(),
            impacto_segmento    = row.get('Impacto en segmento', '').strip(),
        )
        db.session.add(curso)

    db.session.commit()
    logger.info("✓ Filas de 'DetallesDeCursos' cargadas correctamente.")

def procesar_encuestas_presenciales(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    reader = csv.DictReader(decoded.splitlines())

    # traemos todos los id_concat existentes
    existentes = {row[0] for row in db.session.query(QuintoSurveySql.id_concat).all()}

    nuevos, saltados = 0, 0

    def parse_date(v):
        v = v.strip()
        if not v: return None
        for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'):
            try: return datetime.strptime(v, fmt)
            except: pass
        logger.debug(f"no pude parsear fecha '{v}'")
        return None

    for row in reader:
        dc = row.get('date_created','').strip()
        dm = row.get('date_modified','').strip()
        ga = row.get('GestoresAprendizaje','').strip()
        key = f"{dc}{dm}{ga}"
        if key in existentes:
            saltados += 1
            continue

        record = QuintoSurveySql(
            id_concat             = key,
            date_created          = parse_date(dc),
            gestores_aprendizaje  = ga,
            curso                 = row.get('Curso','').strip(),
            recomendacion_colega  = row.get('¿Qué tan probable es que usted le recomiende este curso a un colega?','').strip(),
            desempeno_instructor  = row.get('De acuerdo a tu experiencia del día de hoy, ¿Cómo calificarías el desempeño del instructor?','').strip(),
            calificacion_general  = row.get('En líneas generales, ¿cómo calificarías a este curso/ actividad?','').strip(),
            duracion_curso        = row.get('Pensando en los contenidos vistos, considerás que la duración del curso fue:','').strip(),
            info_recibida         = row.get('En cuanto a la información recibida, considerás que es:','').strip(),
            claridad_temas        = row.get('Los temas fueron tratados con claridad','').strip(),
            utilidad_contenido    = row.get('El contenido visto es de utilidad para mi tarea','').strip(),
            ayudas_practica       = row.get('Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso','').strip(),
            actividades_refuerzo  = row.get('Las actividades propuestas refuerzan lo aprendido','').strip(),
            experiencia_aprendizaje = row.get('En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:','').strip(),
            sugerencias           = row.get('Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso','').strip()
        )
        db.session.add(record)
        existentes.add(key)
        nuevos += 1

    db.session.commit()
    logger.info(f"✓ Guardé {nuevos} nuevos y salté {saltados} duplicados.")

def procesar_encuestas_ac(csv_bytes_io):
    csv_bytes_io.seek(0)
    decoded = csv_bytes_io.read().decode('utf-8', errors='replace')
    reader = csv.DictReader(decoded.splitlines())

    # Traemos todos los id_concat ya existentes
    existentes = {row[0] for row in db.session.query(CuartoSurveySql.id_concat).all()}

    nuevos, saltados = 0, 0

    def parse_date(v):
        v = v.strip()
        if not v: return ''
        return v  # si no lo parseás a DateTime, lo dejamos string

    for row in reader:
        dm = row.get('date_modified', '').strip()
        ip = row.get('ip_address', '').strip()
        key = f"{dm}{ip}"
        if key in existentes:
            saltados += 1
            continue

        reg = CuartoSurveySql(
            id_code                 = row.get('ID_CODE','').strip(),
            id_concat               = key,
            recomendacion_colega    = row.get('¿Qué tan probable es que usted le recomiende este curso a un colega?','').strip(),
            calificacion_general    = row.get('En líneas generales, ¿cómo calificarías a este curso/ actividad?','').strip(),
            duracion_curso          = row.get('Pensando en los contenidos vistos, considerás que la duración del curso fue:','').strip(),
            info_recibida           = row.get('En cuanto a la información recibida, considerás que es:','').strip(),
            claridad_temas          = row.get('Los temas fueron tratados con claridad','').strip(),
            utilidad_contenido      = row.get('El contenido visto es de utilidad para mi tarea','').strip(),
            ayudas_practica         = row.get('Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso','').strip(),
            actividades_refuerzo    = row.get('Las actividades propuestas refuerzan lo aprendido','').strip(),
            problema_campus         = row.get('Al momento de realizar el curso, ¿tuviste algún problema con el Campus de aprendizaje?','').strip(),
            detalle_problema        = row.get('Si tuviste algún problema, por favor, contanos que sucedió','').strip(),
            experiencia_aprendizaje = row.get('En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:','').strip(),
            sugerencias             = row.get('Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso','').strip(),
        )
        db.session.add(reg)
        existentes.add(key)
        nuevos += 1

    db.session.commit()
    logger.info(f"✓ procesar_encuestas_ac: {nuevos} nuevos, {saltados} duplicados salteados.")

# mapeo de URLs a funciones
SPECIAL_HANDLERS = {
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=133": procesar_usuarios_por_asignacion,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=130": procesar_usuarios_sin_id,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=330": procesar_valida_usuarios,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=205": procesar_detalle_apies,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=249": procesar_ypf_2025_avance_cursada,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=296&sid=713": procesar_cursos_agrupados,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=302&sid=712": procesar_cursos_agrupados,
    "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=248": procesar_detalles_de_cursos,
    "https://repomatic2.onrender.com/recuperar_quinto_survey": procesar_encuestas_presenciales,
    "https://repomatic2.onrender.com/recuperar_cuarto_survey": procesar_encuestas_ac

}


def exportar_y_guardar_reporte(session, sesskey, username, report_url):
    hora_inicio = datetime.now()
    logger.info(f"6 - Recuperando reporte desde la URL. Inicio: {hora_inicio:%d-%m-%Y %H:%M:%S}")

    export_payload = {
        "sesskey": sesskey,
        "_qf__report_builder_export_form": "1",
        "format": "csv",
        "export": "Exportar"
    }
    export_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": report_url
    }

    try:
        # 1) traigo el HTML y saco el título
        html = session.get(report_url)
        html.raise_for_status()
        soup = BeautifulSoup(html.text, 'html.parser')
        titulo = "reporte_solicitado"
        titulos_posibles = [r.title for r in TodosLosReportes.query.all()]
        for h2 in soup.find_all('h2'):
            for span in h2.find_all('span'):
                txt = span.get_text(strip=True)
                if txt in titulos_posibles:
                    titulo = txt
                    break

        # 2) descargo el CSV crudo
        logger.info("8 - Descargando CSV…")
        resp = session.post(report_url, data=export_payload, headers=export_headers)
        resp.raise_for_status()
        csv_data = BytesIO(resp.content)

        # 3) lógica de “Inscripciones Marketplace” (split de APIES)
        if titulo == "Inscripciones Marketplace":
            logger.info("→ Split de APIES en Inscripciones Marketplace…")
            decoded = csv_data.getvalue().decode('utf-8', errors='replace')
            rows = decoded.splitlines()
            reader = csv.DictReader(rows)
            processed = []
            for row in reader:
                apies = re.sub(r'[–—−]', '-', row.get('APIES',''))
                apies = re.sub(r'[\u200B\u200C\u200D\uFEFF]', '', apies)
                uniques = list(dict.fromkeys([a.strip() for a in apies.split('-') if a.strip()]))
                if len(uniques) > 1:
                    for u in uniques:
                        newr = dict(row); newr['APIES'] = u; processed.append(newr)
                else:
                    row['APIES'] = uniques[0] if uniques else ''
                    processed.append(row)
            output = BytesIO()
            writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
            writer.writeheader(); writer.writerows(processed)
            csv_data = BytesIO(output.getvalue())
            logger.info("→ Split de APIES finalizado.")

        # 4) si la URL es “especial”, llamo al handler antes del base64
        if report_url in SPECIAL_HANDLERS:
            logger.info(f"→ URL especial detectada ({report_url}), llamando handler…")
            handler = SPECIAL_HANDLERS[report_url]
            handler(csv_data)            # guarda fila a fila en su tabla
            csv_data.seek(0)             # vuelvo al inicio para el base64

        # 5) controlo cantidad de reportes viejos y los borro manteniendo N
        size_mb = len(csv_data.getvalue()) / 1_048_576
        max_r = 30 if report_url in [
            "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=133",
            "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=306"
        ] else 7
        existing = Reporte.query.filter_by(report_url=report_url).order_by(Reporte.created_at.asc()).all()
        while len(existing) >= max_r:
            db.session.delete(existing[0])
            db.session.commit()
            existing = Reporte.query.filter_by(report_url=report_url).order_by(Reporte.created_at.asc()).all()
            logger.info("→ Eliminé reporte viejo para mantener sólo los últimos.")

        # 6) guardo el reporte completo en base64 como antes
        nuevo = Reporte(
            user_id      = username,
            report_url   = report_url,
            data         = csv_data.read(),
            size         = size_mb,
            elapsed_time = str(datetime.now() - hora_inicio),
            title        = titulo
        )
        db.session.add(nuevo)
        db.session.commit()
        logger.info("13 - Reporte guardado en Reporte (base64).")
        return

    except requests.RequestException as e:
        logger.error(f"Error HTTP al recuperar reporte: {e}")
    except SQLAlchemyError as e:
        logger.error(f"Error BD: {e}")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")



def obtener_reporte(reporte_url):
    report = Reporte.query.filter_by(report_url=reporte_url).order_by(Reporte.created_at.desc()).first()
    if report:
        logger.info("3 - Reporte encontrado en db")
        return report.data, report.created_at, report.title
    else:
        return None, None, None

