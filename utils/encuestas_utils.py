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