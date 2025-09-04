# DEPRECADO - LO DEJO COMO EJEMPLO PARA ALGUNOS CODIGOS QUE PODRIAN SERVIR.
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
from database import db
from models import Reporte, TodosLosReportes, Survey, AllApiesResumes, AllCommentsWithEvaluation, FilteredExperienceComments
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from io import BytesIO
import pytz
from dotenv import load_dotenv
load_dotenv()
import os
from logging_config import logger
import gc
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

def exportar_y_guardar_reporte(session, sesskey, username, report_url):

    hora_inicio = datetime.now()
    logger.info(f"6 - Recuperando reporte desde la URL. Hora de inicio: {hora_inicio.strftime('%d-%m-%Y %H:%M:%S')}")



        # Paso 4: Traer los datos en csv
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

        # Captura el HTML del report_url
        html_response = session.get(report_url)
        html_response.raise_for_status()  # Lanza una excepción para respuestas de error HTTP

        # # Captura HTML para depuración
        html_content = html_response.text


        # Pre fabrica variable "titulo" por si no lo encuentra
        titulo = "reporte_solicitado"

        # Analiza el HTML con BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Busca todos los <h2> en el HTML
        h2_tags = soup.find_all('h2')
        for h2_tag in h2_tags:
            # Busca todos los <span> dentro del <h2>
            span_tags = h2_tag.find_all('span')
            for span_tag in span_tags:
                # Captura el texto del <span>
                span_text = span_tag.get_text(strip=True)
                if span_text:
                    # Aquí puedes implementar lógica adicional para verificar el texto
                    # Por ejemplo, podrías verificar si contiene ciertas palabras clave
                    logger.info(f"7 - Texto encontrado en <span>: {span_text}")

                    # Lista con los títulos posibles / deprecado , ahora capturo los titulos posibles de la precarga de reportes de app.py
                    # titulos_posibles = [
                    #     "USUARIOS POR ASIGNACION PARA GESTORES",
                    #     "CURSADA+YPFRESPALDO",
                    #     "Cursos con detalle",
                    #     "VERIFICA USUARIOS PARA GESTORES",
                    #     "AVANCE DE PROGRAMAS PBI",
                    # ]

                    # Obtener todos los títulos de la base de datos
                    titulos_posibles = [reporte.title for reporte in TodosLosReportes.query.all()]

                    # Verificamos si span_text está en la lista de títulos posibles
                    if span_text in titulos_posibles:
                        titulo = span_text
                        break

        logger.info(f"8 - Comenzando la captura del archivo csv...")

        # AHORA LA CAPTURA DEL MISMÍSIMO ARCHIVO CSV
        export_response = session.post(report_url, data=export_payload, headers=export_headers)
        export_response.raise_for_status()  # Lanza una excepción para respuestas de error HTTP

        logger.info(f"9 - La respuesta de la captura es: {export_response}")
        

        # Captura la hora de finalización
        hora_descarga_finalizada = datetime.now()

        # Calcula el intervalo de tiempo
        elapsed_time = hora_descarga_finalizada - hora_inicio
        elapsed_time_str = str(elapsed_time)
        logger.info(f"10 - CSV recuperado. Tiempo transcurrido de descarga: {elapsed_time}")

        

        # Si es tabla "usuario por asignacion para gestores", toquetear ( en test de falla ):

        # if "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=133" in report_url:
        #     csv_data_raw = pd.read_csv(BytesIO(export_response.content))
        #     csv_data_raw = csv_data_raw.loc[csv_data_raw['DNI'].str.isnumeric()]
        #     csv_buffer = BytesIO()
        #     csv_data_raw.to_csv(csv_buffer, index=False)
        #     csv_data_raw_bytes = csv_buffer.getvalue()
        #     csv_data = BytesIO(csv_data_raw_bytes)
        # else:
        #     csv_data = BytesIO(export_response.content)
        # Pasamos el csv a binario y rescatamos el peso
        csv_data = BytesIO(export_response.content)

        size_megabytes = (len(csv_data.getvalue())) / 1_048_576
        logger.info("11 - Eliminando reporte anterior de DB...")
        # Elimina registros previos en la tabla que corresponde
        report_to_delete = Reporte.query.filter_by(report_url=report_url).order_by(Reporte.created_at.desc()).first()
        if report_to_delete:
            db.session.delete(report_to_delete)
            db.session.commit()
            logger.info("12 - Reporte previo eliminado >>> guardando el nuevo...")

        # Instancia el nuevo registro a la tabla que corresponde y guarda en db
        report = Reporte(user_id=username, report_url=report_url, data=csv_data.read(),size= size_megabytes, elapsed_time= elapsed_time_str, title=titulo)
        db.session.add(report)
        db.session.commit()
        logger.info("13 - Reporte nuevo guardado en la base de datos. Fin de la ejecución.")
        return

    except requests.RequestException as e:
        logger.info(f"Error en la recuperación del reporte desde el campus. El siguiente error se recuperó: {e}")

    except SQLAlchemyError as e:
        logger.info(f"Error en la base de datos: {e}")

    except Exception as e:
        logger.info(f"Error inesperado: {e}")



def obtener_reporte(reporte_url):
    report = Reporte.query.filter_by(report_url=reporte_url).order_by(Reporte.created_at.desc()).first()
    if report:
        logger.info("3 - Reporte encontrado en db")
        return report.data, report.created_at, report.title
    else:
        return None, None, None



#-------------------------------------------------------UTILS PARA EXPERIENCIA DE USUARIO--------------------

def get_resumes(file_content):
    # Leer el archivo Excel desde el contenido en memoria (file_content)
    df = pd.read_excel(file_content)

    # Crear un diccionario para agrupar los comentarios por APIES
    comentarios_por_apies = {}
    for apies, comentario in zip(df['APIES'], df['COMENTARIO']):
        if apies not in comentarios_por_apies:
            comentarios_por_apies[apies] = []
        comentarios_por_apies[apies].append(comentario)

    # Recorrer cada APIES y crear el prompt para OpenAI
    resultados = []
    pedido = 0
    for apies, comentarios in comentarios_por_apies.items():
        prompt = f"""
        A continuación, tienes una lista de comentarios de clientes sobre la estación de servicio {apies}. Necesito que realices un resumen **sin sesgos** de los comentarios y respondas las siguientes indicaciones:

        1. **Resumen de comentarios sin sesgos**: Proporciona un análisis claro de los comentarios de los clientes. Si se mencionan nombres, citarlos en la respuesta con el motivo.
        
        2. **Temáticas más comentadas**:  Mostrar porcentaje de cada temática mencionada sobre la totalidad. Ordena las temáticas desde la más comentada hasta la menos comentada, identificando las quejas o comentarios más recurrentes. Si se mencionan nombres, citarlos en la respuesta con el motivo.

        3. **Motivos del malestar o quejas**:  Enfócate en el **motivo** que genera el malestar o la queja, no en la queja en sí. Mostrar porcentaje de comentarios de cada motivo de queja sobre la totalidad de los comentarios.  Si se mencionan nombres, citarlos en la respuesta con el motivo.

        4. **Puntaje de tópicos mencionados**: Si se mencionan algunos de los siguientes tópicos, proporciona un puntaje del 1 al 10 basado en el porcentaje de comentarios positivos sobre la totalidad de comentarios en cada uno. Si no hay comentarios sobre un tópico, simplemente coloca "-".
        
        - **A** (Atención al cliente)
        - **T** (Tiempo de espera)
        - **S** (Sanitarios)

        El puntaje se determina de la siguiente forma:
        - Si entre 90% y 99% de los comentarios totales de uno de los 3 tópicos son positivos, el puntaje es 9, en el tópico correspondiente.
        - Si el 100% de los comentarios totales  de uno de los 3 tópicos son positivos, el puntaje es 10, en el tópico correspondiente.
        - Si entre 80% y el 89% de los comentarios totales de uno de los 3 tópicos son positivos, el puntaje es 8, en el tópico correspondiente. y así sucesivamente.

        **Esta es la lista de comentarios para el análisis:**
        {comentarios}

        **Proporción y puntaje para cada tópico mencionado:**
        1. Atención al cliente (A): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.
        2. Tiempo de espera (T): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.
        3. Sanitarios (S): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.

        **Código Resumen**:

        ##APIES {apies}-A:5,T:Y,S:8## ( los puntajes son meramente demostrativos para entender el formato que espero de la respuesta )
        """

        try:
            pedido = pedido + 1
            print(f"El promp numero: {pedido}, está en proceso...")
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un analista que clasifica comentarios sobre eficiencia."},
                    {"role": "user", "content": prompt}
                ]
            )

            # Acceder directamente al mensaje completo como en el código funcional
            resumen = completion.choices[0].message.content
            resultados.append(f"APIES {apies}:\n{resumen}\n")

        except Exception as e:
            resultados.append(f"Ocurrió un error al procesar el APIES {apies}: {e}\n")

    # # Retornar el resultado en lugar de guardar un archivo
    # return "\n".join(resultados)

        # Ahora procesamos los resultados para extraer los puntajes y construir el archivo Excel
    data = []

    for resultado in resultados:
        apies_match = re.search(r"APIES (\d+)", resultado)
        if apies_match:
            apies = apies_match.group(1)

        # Usamos expresiones regulares para extraer los puntajes A, T, S
        a_match = re.search(r"A:(\d+)", resultado)
        t_match = re.search(r"T:(\d+)", resultado)
        s_match = re.search(r"S:(\d+)", resultado)

        a_score = int(a_match.group(1)) if a_match else "-"
        t_score = int(t_match.group(1)) if t_match else "-"
        s_score = int(s_match.group(1)) if s_match else "-"

        # Agregamos una fila a nuestra lista de datos, incluyendo el resumen completo
        data.append({
            "APIES": apies,
            "ATENCION AL CLIENTE": a_score,
            "TIEMPO DE ESPERA": t_score,
            "SANITARIOS": s_score,
            "RESUMEN": resultado
        })

    # Crear un DataFrame con los resultados
    df_resultados = pd.DataFrame(data)

    # Crear un archivo Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_resultados.to_excel(writer, index=False, sheet_name='Resúmenes')

    # Volver al inicio del archivo para que Flask pueda leerlo
    output.seek(0)

    # Retornar el archivo Excel en memoria
    return output

#----------------UTILS PARA OBTENER TODOS LOS RESUMENES>>>>>>>>>>>>>>>>>>>>>>>>>>

def get_resumes_of_all(file_content):
    logger.info("4 - Util get_resumes_of_all inicializado")
    # Leer el archivo Excel desde el contenido en memoria (file_content)

    logger.info("5 - Leyendo excel y transformando fechas...")
    df = pd.read_excel(BytesIO(file_content))

    # Convertir la columna de fechas a tipo datetime
    df['FECHA'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')

    # Obtener la fecha sin hora
    df['FECHA'] = df['FECHA'].dt.date

    # tests
    # logger.info(f"Fechas convertidas: {df['FECHA'].head()}")
    # df_septiembre = df[df['FECHA'] == '2024-09-01']
    # logger.info(f"Registros del 1 de septiembre: {len(df_septiembre)}")


    logger.info("6 - Filtrando comentarios por fecha ( solo aparecen las del ultimo mes cerrado )...")
    # Obtener el primer día del mes actual y restar un mes para el primer día del mes pasado
    hoy = datetime.today()
    primer_dia_mes_actual = hoy.replace(day=1)
    primer_dia_mes_pasado = primer_dia_mes_actual - pd.DateOffset(months=1)

    # Obtener el último día del mes pasado
    ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)

    # Verificar fechas
    logger.info(f"Primer día del mes pasado: {primer_dia_mes_pasado}")
    logger.info(f"Último día del mes pasado: {ultimo_dia_mes_pasado}")
    logger.info(f"Fechas únicas en el archivo: {df['FECHA'].unique()}")

    # Filtrar los comentarios entre el primer y el último día del mes pasado
    df_filtrado = df[(df['FECHA'] >= primer_dia_mes_pasado.date()) & (df['FECHA'] <= ultimo_dia_mes_pasado.date())]

    logger.info(f"Comentarios filtrados: {len(df_filtrado)}")

    logger.info("7 - Agrupando comentarios según APIES...")
    # Crear un diccionario para agrupar los comentarios por APIES
    comentarios_por_apies = {}
    for apies, comentario in zip(df_filtrado['APIES'], df_filtrado['COMENTARIO']):
        if apies not in comentarios_por_apies:
            comentarios_por_apies[apies] = []
        comentarios_por_apies[apies].append(comentario)

    cantidad_apies = len(comentarios_por_apies)
    logger.info(f"8 - La cantidad de Apies a ser procesadas por OPENAI es de : {cantidad_apies}, esto puede tomar un tiempo...")

    # Recorrer cada APIES y crear el prompt para OpenAI
    resultados = []
    pedido = 0
    for apies, comentarios in comentarios_por_apies.items():
        prompt = f"""
        A continuación, tienes una lista de comentarios de clientes sobre la estación de servicio {apies}. Necesito que realices un resumen **sin sesgos** de los comentarios y respondas las siguientes indicaciones:
        (En tu respuesta, respeta los títulos como se encuentran escritos)
        1. **Resumen de comentarios sin sesgos**: Proporciona un análisis claro de los comentarios de los clientes. Si se mencionan nombres, citarlos en la respuesta con el motivo.
        
        2. **Temáticas más comentadas**:  Mostrar porcentaje de cada temática mencionada sobre la totalidad. Ordena las temáticas desde la más comentada hasta la menos comentada, identificando las quejas o comentarios más recurrentes. Si se mencionan nombres, citarlos en la respuesta con el motivo.

        3. **Motivos del malestar o quejas**:  Enfócate en el **motivo** que genera el malestar o la queja, no en la queja en sí. Mostrar porcentaje de comentarios de cada motivo de queja sobre la totalidad de los comentarios.  Si se mencionan nombres, citarlos en la respuesta con el motivo.

        4. **Puntaje de tópicos mencionados**: Si se mencionan algunos de los siguientes tópicos, proporciona un puntaje del 1 al 10 basado en el porcentaje de comentarios positivos sobre la totalidad de comentarios en cada uno. Si no hay comentarios sobre un tópico, coloca exactamente el guion `-`, sin ceros o cualquier otro valor.
        
        - **A** (Atención al cliente)
        - **T** (Tiempo de espera)
        - **S** (Sanitarios)

        El puntaje se determina de la siguiente forma:
        - Si entre 90% y 99% de los comentarios totales de uno de los 3 tópicos son positivos, el puntaje es 9, en el tópico correspondiente.
        - Si el 100% de los comentarios totales  de uno de los 3 tópicos son positivos, el puntaje es 10, en el tópico correspondiente.
        - Si entre 80% y el 89% de los comentarios totales de uno de los 3 tópicos son positivos, el puntaje es 8, en el tópico correspondiente. y así sucesivamente.
        - Si hay un 0% de comentarios de un tópico, coloca exactamente el guion `-`.

        **Esta es la lista de comentarios para el análisis:**
        {comentarios}

        **Proporción y puntaje para cada tópico mencionado:**
        1. Atención al cliente (A): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.
        2. Tiempo de espera (T): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.
        3. Sanitarios (S): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.

        **Código Resumen**:

        ## APIES {apies}-A:5,T:Y,S:8 ## ( los puntajes son meramente demostrativos para entender el formato que espero de la respuesta )
        Este es un ejemplo de formato de respuesta de **Código Resumen** que tiene que ser respetado:  **Código Resumen**:    ## APIES 4-A:10,T:10,S:10 ##

        **Porcentajes totales**:
        Proporciona los porcentajes totales de comentarios positivos, negativos y neutros en el siguiente formato:
        POS:xx%,NEG:xx%,NEU:xx%

        """

        try:
            pedido = pedido + 1
            # print(f"El promp numero: {pedido}, está en proceso...")
            logger.info(f"El promp numero: {pedido}, está en proceso...")
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un analista que clasifica comentarios sobre eficiencia."},
                    {"role": "user", "content": prompt}
                ]
            )

            # Acceder directamente al mensaje completo como en el código funcional
            resumen = completion.choices[0].message.content
            resultados.append(f"APIES {apies}:\n{resumen}\n")

        except Exception as e:
            logger.info(f"Error en el promp numero: {pedido}, {str(e)}")
            resultados.append(f"Ocurrió un error al procesar el APIES {apies}: {e}\n")

    # # Retornar el resultado en lugar de guardar un archivo
    # return "\n".join(resultados)
    logger.info("9 - Proceso de OPENAI finalizado.")
    logger.info("10 - Procesando resultados...")
        # Ahora procesamos los resultados para extraer los puntajes y construir el archivo Excel
    data = []

    for resultado in resultados:
        apies_match = re.search(r"APIES (\d+)", resultado)
        if apies_match:
            apies = apies_match.group(1)
        else:
            apies = "-"
            logger.info(f"No se encontró el puntaje para A en APIES {apies}")

        # Usamos expresiones regulares para extraer los puntajes A, T, S
        a_match = re.search(r"A:(\d+|-)", resultado)
        t_match = re.search(r"T:(\d+|-)", resultado)
        s_match = re.search(r"S:(\d+|-)", resultado)

        # Asegurarse de que los puntajes se busquen después de "APIES"
        regex_puntajes = re.search(r"APIES.*?A:(\d+|[-]),T:(\d+|[-]|0),S:(\d+|[-]|0)", resultado)

        a_score = int(regex_puntajes.group(1)) if regex_puntajes and regex_puntajes.group(1).isdigit() else "-"
        t_score = int(regex_puntajes.group(2)) if regex_puntajes and regex_puntajes.group(2).isdigit() else "-"
        s_score = int(regex_puntajes.group(3)) if regex_puntajes and regex_puntajes.group(3).isdigit() else "-"

        # Expresión regular ajustada para capturar los porcentajes con o sin espacios
        porcentajes_match = re.search(r"POS:\s*(\d+\.?\d*)%.*?NEG:\s*(\d+\.?\d*)%.*?NEU:\s*(\d+\.?\d*)%", resultado)

        positivos = float(porcentajes_match.group(1)) if porcentajes_match else "-"
        negativos = float(porcentajes_match.group(2)) if porcentajes_match else "-"
        neutros = float(porcentajes_match.group(3)) if porcentajes_match else "-"


        # Agregamos una fila a nuestra lista de datos, incluyendo el resumen completo
        resultado_escapado = resultado.replace('"', '""').replace('\n', ' ')

        # Extraer el resumen externo con regex
        resumen_externo_match = re.search(r"(?i)Resumen de comentarios sin sesgos.*?:?\s*(.+?)Temáticas más comentadas", resultado, re.DOTALL)
        resumen_externo = resumen_externo_match.group(1).strip() if resumen_externo_match else ""

        data.append({
            "APIES": apies,
            "RESUMEN EXTERNO": resumen_externo,
            "RESUMEN": resultado_escapado,
            "ATENCION AL CLIENTE": a_score,
            "TIEMPO DE ESPERA": t_score,
            "SANITARIOS": s_score,
            "POSITIVOS": positivos,
            "NEGATIVOS": negativos,
            "NEUTROS": neutros
        })

    logger.info("11 - Creando dataframe...")
    # Crear un DataFrame con los resultados
    df_resultados = pd.DataFrame(data)

    logger.info("12 - Creando archivo CSV")
    output = BytesIO()
    df_resultados.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)  # Guardamos como CSV

    # Volver al inicio del archivo para que Flask pueda leerlo
    output.seek(0)

    logger.info("13 - Transformando a Binario...")
    # Obtener los datos binarios
    archivo_binario = output.read()

    logger.info("14 - Eliminando posibles registros anteriores...")
    # Eliminar el registro anterior si existe
    archivo_anterior = AllApiesResumes.query.first()
    if archivo_anterior:
        db.session.delete(archivo_anterior)
        db.session.commit()

    logger.info("15 - Guardando en database.")
    # Crear una instancia del modelo y guardar el archivo binario en la base de datos
    archivo_resumido = AllApiesResumes(archivo_binario=archivo_binario)
    db.session.add(archivo_resumido)
    db.session.commit()

    logger.info("16 - Tabla lista y guardada. Proceso finalizado.")
    # Finalizar la función
    return

#----------------UTILS PARA SURVEY------------------------///////////////////////

def obtener_y_guardar_survey():

    # Paso 1: Leer keys del .env
    api_key = os.getenv('SURVEYMONKEY_API_KEY')
    access_token = os.getenv('SURVEYMONKEY_ACCESS_TOKEN')
    survey_id = os.getenv('SURVEY_ID')
    
    logger.info("2 - Ya en Utils - Iniciando la recuperación de la encuesta...")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    HOST = "https://api.surveymonkey.com"
    SURVEY_RESPONSES_ENDPOINT = f"/v3/surveys/{survey_id}/responses/bulk"
    SURVEY_DETAILS_ENDPOINT = f"/v3/surveys/{survey_id}/details"

    # Paso 2: Obtener detalles de la encuesta
    hora_inicio = datetime.now()
    logger.info("3 - Obteniendo detalles de la encuesta...")



    survey_details = requests.get(f"{HOST}{SURVEY_DETAILS_ENDPOINT}", headers=headers).json()

    # Crear mapas para preguntas y respuestas
    choice_map = {}
    question_map = {}
    for page in survey_details["pages"]:
        for question in page["questions"]:
            question_map[question["id"]] = question["headings"][0]["heading"]
            if "answers" in question:
                for answer in question["answers"]["choices"]:
                    choice_map[answer["id"]] = answer["text"]

    # Paso 3: Obtener las respuestas
    logger.info("4 - Obteniendo respuestas de la encuesta...")
    page = 1
    per_page = 10000
    all_responses = []

    while True:
        response_data = requests.get(f"{HOST}{SURVEY_RESPONSES_ENDPOINT}?page={page}&per_page={per_page}", headers=headers)
        if response_data.status_code == 200:
            responses_json = response_data.json()["data"]
            if not responses_json:
                break
            all_responses.extend(responses_json)
            page += 1
        else:
            logger.error(f"Error al obtener respuestas: {response_data.status_code}")
            break

    # Paso 4: Procesar respuestas y generar DataFrame
    logger.info("5 - Procesando respuestas...")
    responses_dict = {}

    for response in all_responses:
        respondent_id = response["id"]
        if respondent_id not in responses_dict:
            responses_dict[respondent_id] = {}

        responses_dict[respondent_id]['custom_variables'] = response.get('custom_variables', {}).get('ID_CODE', '')
        responses_dict[respondent_id]['date_created'] = response.get('date_created', '')[:10]
        for page in response["pages"]:
            for question in page["questions"]:
                question_id = question["id"]
                for answer in question["answers"]:
                    if "choice_id" in answer:
                        responses_dict[respondent_id][question_id] = choice_map.get(answer["choice_id"], answer["choice_id"])
                    elif "text" in answer:
                        responses_dict[respondent_id][question_id] = answer["text"]
                    elif "row_id" in answer and "text" in answer:
                        responses_dict[respondent_id][question_id] = answer["text"]

    df_responses = pd.DataFrame.from_dict(responses_dict, orient='index')
    all_responses = []


    # Paso 5: Limpiar columnas con tags HTML
    def extract_text_from_span(html_text):
        return re.sub(r'<[^>]*>', '', html_text)

    if '152421787' in df_responses.columns:
        df_responses['152421787'] = df_responses['152421787'].apply(extract_text_from_span)

    df_responses.rename(columns=question_map, inplace=True)
    df_responses.columns = [extract_text_from_span(col) for col in df_responses.columns]

    logger.info(f"6 - DataFrame con {df_responses.shape[0]} filas y {df_responses.shape[1]} columnas.")


    # Convertir el DataFrame a binario
    logger.info("7 - Convirtiendo DataFrame a binario...")
    #-----------------------Si no funciona vuelvo a habilitar esto>>>
    # output = BytesIO()
    # # df_responses.to_parquet(output, index=False)
    # df_responses.to_pickle(output)  # Cambiamos a pickle
    # binary_data = output.getvalue()
    #-----------------------------------------------------------------
    with BytesIO() as output:
        df_responses.to_pickle(output)  # Cambiamos a pickle
        binary_data = output.getvalue()


    # Paso 6: Guardar en la base de datos
    logger.info("8 - Guardando resultados en la base de datos...")

    # Primero, eliminar cualquier registro anterior
    db.session.query(Survey).delete()
    db.session.flush()
    
    # Crear un nuevo registro
    new_survey = Survey(data=binary_data)
    db.session.add(new_survey)
    db.session.commit()

    logger.info("9 - Datos guardados correctamente.")

    # Captura la hora de finalización
    hora_descarga_finalizada = datetime.now()

    # Calcula el intervalo de tiempo
    elapsed_time = hora_descarga_finalizada - hora_inicio
    elapsed_time_str = str(elapsed_time)
    logger.info(f"10 - Survey recuperado y guardado en db. Tiempo transcurrido de descarga y guardado: {elapsed_time_str}")

    #limpieza
    gc.collect()
    
    return  # Fin de la ejecución en segundo plano


# GET ONE FROM TOTAL RESUMEN OF COMMENTS --------------------------------------------/////


def get_resumes_for_apies(apies_input, db_data):
    logger.info("3 - Ejecutando util get_resumes_for_apies...")
    
    # Leer el archivo Excel desde la DB (binario)
    logger.info("4 - Recuperando excel desde binario...")
    binary_data = BytesIO(db_data)
    df = pd.read_pickle(binary_data)

    apies_input = int(apies_input)

    logger.info("5 - Filtrando comentarios correspondientes a la estación de servicio...")
    # Filtrar los comentarios correspondientes al número de APIES
    comentarios_filtrados = df[df.iloc[:, 1] == apies_input].iloc[:, 2]

    if comentarios_filtrados.empty:
        return f"No se encontraron comentarios para la estación {apies_input}"

    # Crear el prompt de OpenAI con los comentarios filtrados
    prompt = f"""
        A continuación, tienes una lista de comentarios de clientes sobre la estación de servicio {str(apies_input)}. Necesito que realices un resumen **sin sesgos** de los comentarios y respondas las siguientes indicaciones:

        1. **Resumen de comentarios sin sesgos**: Proporciona un análisis claro de los comentarios de los clientes. Si se mencionan nombres, citarlos en la respuesta con el motivo.
        
        2. **Temáticas más comentadas**:  Mostrar porcentaje de cada temática mencionada sobre la totalidad. Ordena las temáticas desde la más comentada hasta la menos comentada, identificando las quejas o comentarios más recurrentes. Si se mencionan nombres, citarlos en la respuesta con el motivo.

        3. **Motivos del malestar o quejas**:  Enfócate en el **motivo** que genera el malestar o la queja, no en la queja en sí. Mostrar porcentaje de comentarios de cada motivo de queja sobre la totalidad de los comentarios.  Si se mencionan nombres, citarlos en la respuesta con el motivo.

        4. **Puntaje de tópicos mencionados**: Si se mencionan algunos de los siguientes tópicos, proporciona un puntaje del 1 al 10 basado en el porcentaje de comentarios positivos sobre la totalidad de comentarios en cada uno. Si no hay comentarios sobre un tópico, simplemente coloca "-".
        
        - **A** (Atención al cliente)
        - **T** (Tiempo de espera)
        - **S** (Sanitarios)

        El puntaje se determina de la siguiente forma:
        - Si entre 90% y 99% de los comentarios totales de uno de los 3 tópicos son positivos, el puntaje es 9, en el tópico correspondiente.
        - Si el 100% de los comentarios totales  de uno de los 3 tópicos son positivos, el puntaje es 10, en el tópico correspondiente.
        - Si entre 80% y el 89% de los comentarios totales de uno de los 3 tópicos son positivos, el puntaje es 8, en el tópico correspondiente. y así sucesivamente.

        **Esta es la lista de comentarios para el análisis:**
        {comentarios_filtrados.tolist()}

        **Proporción y puntaje para cada tópico mencionado:**
        1. Atención al cliente (A): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.
        2. Tiempo de espera (T): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.
        3. Sanitarios (S): \[Porcentaje de comentarios positivos\] — Puntaje del 1 al 10.

        **Código Resumen**:

        ##APIES {str(apies_input)}-A:5,T:Y,S:8## ( los puntajes son meramente demostrativos para entender el formato que espero de la respuesta )
        """
    logger.info("6 - Pidiendo resumen a OPENAI...")
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista que clasifica comentarios sobre eficiencia."},
                {"role": "user", "content": prompt}
            ]
        )
        resumen = completion.choices[0].message.content

    except Exception as e:
        return f"Error al procesar el APIES {apies_input}: {e}"

    logger.info("7 - Extracción de datos importantes del texto resultante...")
    # Extraer puntajes usando regex
    a_match = re.search(r"A:(\d+)", resumen)
    t_match = re.search(r"T:(\d+)", resumen)
    s_match = re.search(r"S:(\d+)", resumen)

    a_score = int(a_match.group(1)) if a_match else "-"
    t_score = int(t_match.group(1)) if t_match else "-"
    s_score = int(s_match.group(1)) if s_match else "-"

    # Preparar datos para el Excel
    logger.info("8 - Preparando matriz para crear el excel de respuesta...")
    data = [{
        "APIES": apies_input,
        "ATENCION AL CLIENTE": a_score,
        "TIEMPO DE ESPERA": t_score,
        "SANITARIOS": s_score,
        "RESUMEN": resumen
    }]

    df_resultados = pd.DataFrame(data)
    logger.info("9 - Creando excel...")
    # Crear un archivo Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_resultados.to_excel(writer, index=False, sheet_name='Resúmenes')

    output.seek(0)
    logger.info("10 - Devolviendo excel a la ruta...")
    return output  # Devuelve el archivo Excel


# MODELO MOMENTANEO PARA CREAR ARCHIVO DE LOGS (RESPUESTAS OPENAI):

# def get_evaluations_of_all(file_content):
#     logger.info("4 - Util get_evaluations_of_all inicializado")
    
#     # Leer el archivo Excel desde el contenido en memoria (file_content)
#     logger.info("5 - Leyendo excel y agregando ID...")
#     df = pd.read_excel(BytesIO(file_content))

#     # Agregar columna de ID con un número secuencial para cada comentario
#     df['ID'] = range(1, len(df) + 1)

#     # Asegurar que la columna de SENTIMIENTO existe
#     df['SENTIMIENTO'] = ""

#     # Crear un archivo para guardar las respuestas de OpenAI
#     with open('openai_responses_log.txt', 'w', encoding='utf-8') as log_file:
#         # Obtener las APIES únicas
#         apies_unicas = df['APIES'].unique()

#         logger.info(f"Total de APIES únicas: {len(apies_unicas)}")

#         for apies_input in apies_unicas:
#             logger.info(f"Procesando APIES {apies_input}...")

#             # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
#             comentarios_filtrados = df[df['APIES'] == apies_input][['ID', 'COMENTARIO']]
#             comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

#             # Crear el prompt para OpenAI
#             prompt = "Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: positivo', 'ID-{id}: negativo' o 'ID-{id}: invalido'. Si el comentario no es claro o no tiene un sentimiento definido, responde 'invalido'. No utilices otras palabras como 'neutro'.Comentarios con solo un 'ok', 'joya','bien','agil' o derivados de ese estilo representando aceptación, son conciderados 'positivos'.Si se habla de rapidez o eficiencia positivamente, tambien será conciderado 'positivo'.Un '10' o un '100' suelto, o acompañado por la palabra 'nota', se concidera positivo.La palabra 'no' suelta se concidera invalida. Si se expresa la falta de algun producto se concidera 'negativo'. Aquí están los comentarios:\n"
#             for comentario_id, comentario in comentarios_dict.items():
#                 prompt += f"ID-{comentario_id}: {comentario}\n"

#             # Hacer el pedido a OpenAI
#             try:
#                 logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
#                 completion = client.chat.completions.create(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {"role": "system", "content": "Eres un analista que clasifica comentarios por sentimiento."},
#                         {"role": "user", "content": prompt}
#                     ]
#                 )

#                 respuesta = completion.choices[0].message.content
#                 logger.info(f"Respuesta obtenida para APIES {apies_input}")

#                 # Guardar la respuesta en el log
#                 log_file.write(f"APIES {apies_input}:\n{respuesta}\n\n")

#                 # Parsear la respuesta usando expresiones regulares para extraer el ID y el sentimiento
#                 matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

#                 # Actualizar la columna 'SENTIMIENTO' usando los IDs
#                 for match in matches:
#                     comentario_id, sentimiento = match
#                     df.loc[df['ID'] == int(comentario_id), 'SENTIMIENTO'] = sentimiento

#             except Exception as e:
#                 logger.error(f"Error al procesar el APIES {apies_input}: {e}")

#     # Guardar el DataFrame actualizado en formato binario (como CSV)
#     logger.info("Guardando DataFrame actualizado con sentimiento...")
#     output = BytesIO()
#     df.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
#     output.seek(0)
#     archivo_binario = output.read()

#     logger.info("Proceso completado. Guardando en base de datos...")

#     # Guardar el archivo en la tabla AllCommentsWithEvaluation
#     archivo_anterior = AllCommentsWithEvaluation.query.first()
#     if archivo_anterior:
#         db.session.delete(archivo_anterior)
#         db.session.commit()

#     # Crear un nuevo registro y guardar el archivo binario
#     archivo_resumido = AllCommentsWithEvaluation(archivo_binario=archivo_binario)
#     db.session.add(archivo_resumido)
#     db.session.commit()

#     logger.info("Archivo guardado exitosamente en la tabla AllCommentsWithEvaluation.")
#     return

# MODELO FINAL PARA CAPTURA DE EVALUACIÓN DE POSITIVIDAD DE COMENTARIOS

def get_evaluations_of_all(file_content):
    logger.info("4 - Util get_evaluations_of_all inicializado")
    
    # Leer el archivo Excel desde el contenido en memoria (file_content)
    logger.info("5 - Leyendo excel y agregando ID...")
    df = pd.read_excel(BytesIO(file_content))

    # Agregar columna de ID con un número secuencial para cada comentario
    df['ID'] = range(1, len(df) + 1)

    # Asegurar que la columna de SENTIMIENTO existe
    df['SENTIMIENTO'] = ""
    
    # Obtener las APIES únicas
    apies_unicas = df['APIES'].unique()

    logger.info(f"Total de APIES únicas: {len(apies_unicas)}")

    for apies_input in apies_unicas:
        logger.info(f"Procesando APIES {apies_input}...")

        # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
        comentarios_filtrados = df[df['APIES'] == apies_input][['ID', 'COMENTARIO']]
        comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

        # Crear el prompt para OpenAI
        prompt = "Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: positivo', 'ID-{id}: negativo' o 'ID-{id}: invalido'. Si el comentario no es claro o no tiene un sentimiento definido, responde 'invalido'. No utilices otras palabras como 'neutro'.Comentarios con solo un 'ok', 'joya','bien','agil' o derivados de ese estilo representando aceptación, son conciderados 'positivos'.Si se habla de rapidez o eficiencia positivamente, tambien será conciderado 'positivo'.Un '10' o un '100' suelto, o acompañado por la palabra 'nota', se concidera positivo.La palabra 'no' suelta se concidera invalida. Si se expresa la falta de algun producto se concidera 'negativo'. Aquí están los comentarios:\n"
        for comentario_id, comentario in comentarios_dict.items():
            prompt += f"ID-{comentario_id}: {comentario}\n"

        # Hacer el pedido a OpenAI
        try:
            logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un analista que clasifica comentarios por sentimiento."},
                    {"role": "user", "content": prompt}
                ]
            )

            respuesta = completion.choices[0].message.content
            logger.info(f"Respuesta obtenida para APIES {apies_input}")

            # Guardar la respuesta en el log (COMENTADO)
            # log_file.write(f"APIES {apies_input}:\n{respuesta}\n\n")

            # Parsear la respuesta usando expresiones regulares para extraer el ID y el sentimiento
            matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

            # Actualizar la columna 'SENTIMIENTO' usando los IDs
            for match in matches:
                comentario_id, sentimiento = match
                df.loc[df['ID'] == int(comentario_id), 'SENTIMIENTO'] = sentimiento

        except Exception as e:
            logger.error(f"Error al procesar el APIES {apies_input}: {e}")

    # Guardar el DataFrame actualizado en formato binario (como CSV)
    logger.info("Guardando DataFrame actualizado con sentimiento...")
    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
    output.seek(0)
    archivo_binario = output.read()

    logger.info("Proceso completado. Guardando en base de datos...")

    # Guardar el archivo en la tabla AllCommentsWithEvaluation
    archivo_anterior = AllCommentsWithEvaluation.query.first()
    if archivo_anterior:
        db.session.delete(archivo_anterior)
        db.session.commit()

    # Crear un nuevo registro y guardar el archivo binario
    archivo_resumido = AllCommentsWithEvaluation(archivo_binario=archivo_binario)
    db.session.add(archivo_resumido)
    db.session.commit()

    logger.info("Archivo guardado exitosamente en la tabla AllCommentsWithEvaluation.")
    return
# Corrección de campos vacios en SENTIMIENTO de forma automatica hasta rellenarlos todos con un while:

def process_missing_sentiment(comments_df):
    logger.info("Iniciando el proceso de corrección de sentimientos...")

    flag_vacios = True  # Iniciamos el flag en True para entrar en el ciclo while

    while flag_vacios:
        logger.info("Leyendo archivo CSV...")

        # Leer el archivo directamente desde los bytes
        df = pd.read_csv(BytesIO(comments_df), sep=',')
        
        logger.info(f"DataFrame cargado con {len(df)} registros.")
        logger.info(f"Columnas del DataFrame: {df.columns}")

        # Filtrar los registros que tienen el campo 'SENTIMIENTO' vacío
        df_faltante_sentimiento = df[df['SENTIMIENTO'].isna() | (df['SENTIMIENTO'].str.strip() == "")]
        logger.info(f"Registros con SENTIMIENTO vacío: {len(df_faltante_sentimiento)}")
        
        if df_faltante_sentimiento.empty:
            logger.info("No se encontraron más registros con SENTIMIENTO vacío. Deteniendo el proceso.")
            flag_vacios = False  # No hay más campos vacíos, salimos del while
            break  # Rompemos el ciclo del while
        
        # Obtener las APIES únicas de los registros filtrados
        apies_unicas = df_faltante_sentimiento['APIES'].unique()

        logger.info(f"Total de APIES a procesar: {len(apies_unicas)}")

        for apies_input in apies_unicas:
            logger.info(f"Procesando APIES {apies_input}...")

            # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
            comentarios_filtrados = df_faltante_sentimiento[df_faltante_sentimiento['APIES'] == apies_input][['ID', 'COMENTARIO']]
            comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

            # Crear el prompt para OpenAI
            prompt = "Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: positivo', 'ID-{id}: negativo' o 'ID-{id}: invalido'. Si el comentario no es claro o no tiene un sentimiento definido, responde 'invalido'. No utilices otras palabras como 'neutro'.Comentarios con solo un 'ok', 'joya','bien','agil' o derivados de ese estilo representando aceptación, son conciderados 'positivos'.Si se habla de rapidez o eficiencia positivamente, tambien será conciderado 'positivo'.Un '10' o un '100' suelto, o acompañado por la palabra 'nota', se concidera positivo.La palabra 'no' suelta se concidera invalida. Si se expresa la falta de algun producto se concidera 'negativo'. Aquí están los comentarios:\n"
            for comentario_id, comentario in comentarios_dict.items():
                prompt += f"ID-{comentario_id}: {comentario}\n"

            # Hacer el pedido a OpenAI
            try:
                logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Eres un analista que clasifica comentarios por sentimiento."},
                        {"role": "user", "content": prompt}
                    ]
                )

                respuesta = completion.choices[0].message.content
                logger.info(f"Respuesta obtenida para APIES {apies_input}")

                # Parsear la respuesta usando expresiones regulares para extraer el ID y el sentimiento
                matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

                # Actualizar la columna 'SENTIMIENTO' en df_faltante_sentimiento usando los IDs
                for match in matches:
                    comentario_id, sentimiento = match
                    df_faltante_sentimiento.loc[df_faltante_sentimiento['ID'] == int(comentario_id), 'SENTIMIENTO'] = sentimiento

            except Exception as e:
                logger.error(f"Error al procesar el APIES {apies_input}: {e}")

        # Reemplazar las filas correspondientes en la tabla original
        logger.info("Reemplazando filas en tabla original...")

        # Verificar si los objetos df y df_faltante_sentimiento son DataFrames
        logger.info(f"Tipo de df: {type(df)}")
        logger.info(f"Tipo de df_faltante_sentimiento: {type(df_faltante_sentimiento)}")

        # Verificar si los DataFrames están vacíos
        logger.info(f"df está vacío: {df.empty}")
        logger.info(f"df_faltante_sentimiento está vacío: {df_faltante_sentimiento.empty}")

        # Verificar el tamaño de los DataFrames antes de seguir
        logger.info(f"df tiene {df.shape[0]} filas y {df.shape[1]} columnas")
        logger.info(f"df_faltante_sentimiento tiene {df_faltante_sentimiento.shape[0]} filas y {df_faltante_sentimiento.shape[1]} columnas")

        # Verificar si hay valores nulos en la columna 'ID'
        if df['ID'].isnull().any() or df_faltante_sentimiento['ID'].isnull().any():
            logger.error("Existen valores nulos en la columna 'ID'. Esto puede causar problemas en el merge.")
            return
        else:
            logger.error("No hay valores nulos en la columna ID")

        # Verificar si hay duplicados en la columna 'ID'
        if df['ID'].duplicated().any() or df_faltante_sentimiento['ID'].duplicated().any():
            logger.error("Existen valores duplicados en la columna 'ID'. Esto puede causar problemas en el merge.")
            return
        else:
            logger.error("No existen duplicados en la columna ID")

        # Asegurarse de que los tipos de la columna ID coincidan
        df['ID'] = df['ID'].astype(int)
        df_faltante_sentimiento['ID'] = df_faltante_sentimiento['ID'].astype(int)
        logger.error("Se supone que hasta acá hicimos coincidir los tipos de la columna ID para ser int en ambos")

        # Probar un merge simple para verificar que el merge funcione
        try:
            # Hacemos un merge, pero solo actualizamos los valores faltantes en 'SENTIMIENTO'
            df_merged = df.merge(
                df_faltante_sentimiento[['ID', 'SENTIMIENTO']],
                on='ID',
                how='left',
                suffixes=('', '_nuevo')
            )

            # Solo reemplazar los valores de SENTIMIENTO que están vacíos
            df_merged['SENTIMIENTO'] = df_merged['SENTIMIENTO'].combine_first(df_merged['SENTIMIENTO_nuevo'])

            # Eliminar la columna de los nuevos sentimientos
            df_merged = df_merged.drop(columns=['SENTIMIENTO_nuevo'])

            logger.info(f"Primeras filas de df_merged:\n{df_merged.head()}")
            logger.info(f"Total de filas en df_merged: {len(df_merged)}")

            logger.info("Filas actualizadas en la tabla original con el merge.")
        
            # Guardar el DataFrame actualizado como un archivo binario para la siguiente iteración
            output = BytesIO()
            df_merged.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
            output.seek(0)
            comments_df = output.read()  # Convertirlo nuevamente en binario para la próxima iteración


        except Exception as e:
            logger.error(f"Error durante el merge: {e}")
            return
    
    # Guardar el DataFrame actualizado en la base de datos cuando no haya más vacíos
    logger.info("Guardando DataFrame actualizado en la tabla FilteredExperienceComments...")
    output = BytesIO()
    df_merged.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
    output.seek(0)
    archivo_binario = output.read()

    # Eliminar cualquier registro anterior en la tabla FilteredExperienceComments
    archivo_anterior = FilteredExperienceComments.query.first()
    if archivo_anterior:
        db.session.delete(archivo_anterior)
        db.session.commit()

    # Crear un nuevo registro y guardar el archivo binario
    archivo_resumido = FilteredExperienceComments(archivo_binario=archivo_binario)
    db.session.add(archivo_resumido)
    db.session.commit()

    logger.info("Archivo guardado exitosamente en la tabla FilteredExperienceComments.")

    return


# Correción de espacios vacios en tabla total de comentarios ( funcional repitiendo el flow 8 veces) CORRE UNA SOLA VEZ

# def process_missing_sentiment(comments_df):
#     logger.info("Iniciando el proceso de corrección de sentimientos...")

#     logger.info("Leyendo archivo CSV...")
    
#     # Leer el archivo directamente desde los bytes
#     df = pd.read_csv(BytesIO(comments_df), sep=',')
    
#     logger.info(f"DataFrame cargado con {len(df)} registros.")
#     logger.info(f"Columnas del DataFrame: {df.columns}")

#     # Filtrar los registros que tienen el campo 'SENTIMIENTO' vacío
#     df_faltante_sentimiento = df[df['SENTIMIENTO'].isna() | (df['SENTIMIENTO'].str.strip() == "")]
#     logger.info(f"Registros con SENTIMIENTO vacío: {len(df_faltante_sentimiento)}")
    
#     if df_faltante_sentimiento.empty:
#         logger.info("No se encontraron registros con SENTIMIENTO vacío.")
#         return comments_df  # No hay registros para procesar, se devuelve el DataFrame original

#     # Obtener las APIES únicas de los registros filtrados
#     apies_unicas = df_faltante_sentimiento['APIES'].unique()

#     logger.info(f"Total de APIES a procesar: {len(apies_unicas)}")

#     for apies_input in apies_unicas:
#         logger.info(f"Procesando APIES {apies_input}...")

#         # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
#         comentarios_filtrados = df_faltante_sentimiento[df_faltante_sentimiento['APIES'] == apies_input][['ID', 'COMENTARIO']]
#         comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

#         # Crear el prompt para OpenAI
#         prompt = "Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: positivo', 'ID-{id}: negativo' o 'ID-{id}: invalido'. Si el comentario no es claro o no tiene un sentimiento definido, responde 'invalido'. No utilices otras palabras como 'neutro'.Comentarios con solo un 'ok', 'joya','bien','agil' o derivados de ese estilo representando aceptación, son conciderados 'positivos'.Si se habla de rapidez o eficiencia positivamente, tambien será conciderado 'positivo'.Un '10' o un '100' suelto, o acompañado por la palabra 'nota', se concidera positivo.La palabra 'no' suelta se concidera invalida. Si se expresa la falta de algun producto se concidera 'negativo'. Aquí están los comentarios:\n"
#         for comentario_id, comentario in comentarios_dict.items():
#             prompt += f"ID-{comentario_id}: {comentario}\n"

#         # Hacer el pedido a OpenAI
#         try:
#             logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
#             completion = client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {"role": "system", "content": "Eres un analista que clasifica comentarios por sentimiento."},
#                     {"role": "user", "content": prompt}
#                 ]
#             )

#             respuesta = completion.choices[0].message.content
#             logger.info(f"Respuesta obtenida para APIES {apies_input}")

#             # Parsear la respuesta usando expresiones regulares para extraer el ID y el sentimiento
#             matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

#             # Actualizar la columna 'SENTIMIENTO' en df_faltante_sentimiento usando los IDs
#             for match in matches:
#                 comentario_id, sentimiento = match
#                 df_faltante_sentimiento.loc[df_faltante_sentimiento['ID'] == int(comentario_id), 'SENTIMIENTO'] = sentimiento

#         except Exception as e:
#             logger.error(f"Error al procesar el APIES {apies_input}: {e}")

#     # Reemplazar las filas correspondientes en la tabla original
#     logger.info("Reemplazando filas en tabla original...")

#     # Verificar si los objetos df y df_faltante_sentimiento son DataFrames
#     logger.info(f"Tipo de df: {type(df)}")
#     logger.info(f"Tipo de df_faltante_sentimiento: {type(df_faltante_sentimiento)}")

#     # Verificar si los DataFrames están vacíos
#     logger.info(f"df está vacío: {df.empty}")
#     logger.info(f"df_faltante_sentimiento está vacío: {df_faltante_sentimiento.empty}")

#     # Verificar el tamaño de los DataFrames antes de seguir
#     logger.info(f"df tiene {df.shape[0]} filas y {df.shape[1]} columnas")
#     logger.info(f"df_faltante_sentimiento tiene {df_faltante_sentimiento.shape[0]} filas y {df_faltante_sentimiento.shape[1]} columnas")

#     # Verificar si hay valores nulos en la columna 'ID'
#     if df['ID'].isnull().any() or df_faltante_sentimiento['ID'].isnull().any():
#         logger.error("Existen valores nulos en la columna 'ID'. Esto puede causar problemas en el merge.")
#         return
#     else:
#         logger.error("No hay valores nulos en la columna ID")

#     # Verificar si hay duplicados en la columna 'ID'
#     if df['ID'].duplicated().any() or df_faltante_sentimiento['ID'].duplicated().any():
#         logger.error("Existen valores duplicados en la columna 'ID'. Esto puede causar problemas en el merge.")
#         return
#     else:
#         logger.error("No existen duplicados en la columna ID")

#     # Asegurarse de que los tipos de la columna ID coincidan
#     df['ID'] = df['ID'].astype(int)
#     df_faltante_sentimiento['ID'] = df_faltante_sentimiento['ID'].astype(int)
#     logger.error("Se supone que hasta acá hicimos coincidir los tipos de la columna ID para ser int en ambos")

#     # Probar un merge simple para verificar que el merge funcione
#     try:
#         # Hacemos un merge, pero solo actualizamos los valores faltantes en 'SENTIMIENTO'
#         df_merged = df.merge(
#             df_faltante_sentimiento[['ID', 'SENTIMIENTO']],
#             on='ID',
#             how='left',
#             suffixes=('', '_nuevo')
#         )

#         # Solo reemplazar los valores de SENTIMIENTO que están vacíos
#         df_merged['SENTIMIENTO'] = df_merged['SENTIMIENTO'].combine_first(df_merged['SENTIMIENTO_nuevo'])

#         # Eliminar la columna de los nuevos sentimientos
#         df_merged = df_merged.drop(columns=['SENTIMIENTO_nuevo'])

#         logger.info(f"Primeras filas de df_merged:\n{df_merged.head()}")
#         logger.info(f"Total de filas en df_merged: {len(df_merged)}")

#         logger.info("Filas actualizadas en la tabla original con el merge.")
#     except Exception as e:
#         logger.error(f"Error durante el merge: {e}")
#         return

#     # Guardar el DataFrame actualizado en formato binario (como CSV)
#     logger.info("Guardando DataFrame actualizado en la tabla FilteredExperienceComments...")
#     output = BytesIO()
#     df_merged.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
#     output.seek(0)
#     archivo_binario = output.read()

#     # Eliminar cualquier registro anterior en la tabla FilteredExperienceComments
#     archivo_anterior = FilteredExperienceComments.query.first()
#     if archivo_anterior:
#         db.session.delete(archivo_anterior)
#         db.session.commit()

#     # Crear un nuevo registro y guardar el archivo binario
#     archivo_resumido = FilteredExperienceComments(archivo_binario=archivo_binario)
#     db.session.add(archivo_resumido)
#     db.session.commit()

#     logger.info("Archivo guardado exitosamente en la tabla FilteredExperienceComments.")
    
#     return

