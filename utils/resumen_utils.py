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
        prompt = fr"""
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