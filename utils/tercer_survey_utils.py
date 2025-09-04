from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
from database import db
from models import TercerSurvey
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from io import BytesIO
import pytz
from dotenv import load_dotenv
load_dotenv()
import os
from logging_config import logger
import gc
from datetime import datetime
# Zona horaria de São Paulo/Buenos Aires
tz = pytz.timezone('America/Sao_Paulo')

# - Creando cliente openai
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization="org-cSBk1UaTQMh16D7Xd9wjRUYq"
)


#----------------UTILS PARA TERCER SURVEY------------------------///////////////////////

def obtener_y_guardar_survey():


    # Paso 1: Leer las variables de entorno
    api_key = os.getenv('SURVEYMONKEY_API_KEY')
    access_token = os.getenv('SURVEYMONKEY_ACCESS_TOKEN')

    survey_id =  '416779463'
    
    logger.info("Arrancando con el tercer survey ... vamos que esta sale a la primera..")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    HOST = "https://api.surveymonkey.com"
    SURVEY_RESPONSES_ENDPOINT = f"/v3/surveys/{survey_id}/responses/bulk"
    SURVEY_DETAILS_ENDPOINT = f"/v3/surveys/{survey_id}/details"
    
    # Paso 2: Obtener los detalles de la encuesta
    hora_inicio = datetime.now()
    logger.info("Recuperando detalles del survey nuevo...")
    
    survey_details = requests.get(f"{HOST}{SURVEY_DETAILS_ENDPOINT}", headers=headers).json()
    
    # Crear mapas para preguntas y opciones
    choice_map = {}
    question_map = {}
    for page in survey_details.get("pages", []):
        for question in page.get("questions", []):
            # Guardamos el texto de la pregunta
            question_map[question["id"]] = question["headings"][0]["heading"]
            # Si la pregunta tiene opciones, mapeamos cada una
            if "answers" in question and "choices" in question["answers"]:
                for answer in question["answers"]["choices"]:
                    choice_map[answer["id"]] = answer["text"]
    
    # Paso 3: Obtener las respuestas
    logger.info("Bajando respuestas... ¡aguantá que esto se pone copado!")
    page = 1
    per_page = 10000
    all_responses = []
    
    while True:
        response_data = requests.get(
            f"{HOST}{SURVEY_RESPONSES_ENDPOINT}?page={page}&per_page={per_page}",
            headers=headers
        )
        if response_data.status_code == 200:
            responses_json = response_data.json().get("data", [])
            if not responses_json:
                break
            all_responses.extend(responses_json)
            page += 1
        else:
            logger.error(f"Error al obtener respuestas: {response_data.status_code}")
            break
    
    # Paso 4: Procesar las respuestas y armar un DataFrame
    logger.info("Procesando respuestas... que no se nos escape nada")
    responses_dict = {}
    
    for response in all_responses:
        respondent_id = response["id"]
        if respondent_id not in responses_dict:
            responses_dict[respondent_id] = {}
        
        # Extraer custom variable "Boca" y fecha de creación
        responses_dict[respondent_id]['Boca'] = response.get('custom_variables', {}).get('Boca', '')
        responses_dict[respondent_id]['date_created'] = response.get('date_created', '')[:10]
    
        # Recorremos cada página y pregunta para volcar la respuesta
        for page_data in response.get("pages", []):
            for question in page_data.get("questions", []):
                question_id = question["id"]
                for answer in question.get("answers", []):
                    if "choice_id" in answer:
                        responses_dict[respondent_id][question_id] = choice_map.get(answer["choice_id"], answer["choice_id"])
                    elif "text" in answer:
                        responses_dict[respondent_id][question_id] = answer["text"]
                    elif "row_id" in answer and "text" in answer:
                        responses_dict[respondent_id][question_id] = answer["text"]
    
    df_responses = pd.DataFrame.from_dict(responses_dict, orient='index')
    all_responses = []  # Liberamos la lista gigante para no sobrecargar la memoria
    
    # Paso 5: Limpiar columnas con tags HTML
    def extract_text_from_span(html_text):
        if not isinstance(html_text, str):
            return html_text
        return re.sub(r'<[^>]*>', '', html_text)
    
    if '152421787' in df_responses.columns:
        df_responses['152421787'] = df_responses['152421787'].apply(extract_text_from_span)
    
    # Renombrar columnas usando el question_map y limpiar posibles tags HTML
    df_responses.rename(columns=question_map, inplace=True)
    df_responses.columns = [extract_text_from_span(col) for col in df_responses.columns]
    
    logger.info(f"DataFrame armado: {df_responses.shape[0]} filas y {df_responses.shape[1]} columnas.")
    
    # Paso 6: Convertir el DataFrame a binario (pickle)
    logger.info("Serializando DataFrame para guardarlo en la DB...")
    with BytesIO() as output:
        df_responses.to_pickle(output)
        binary_data = output.getvalue()
    
    # Paso 7: Guardar en la base de datos
    logger.info("Guardando el survey nuevo en la DB... a meterle garra")
    # Eliminar registros anteriores (si corresponde)
    db.session.query(TercerSurvey).delete()
    db.session.flush()
    
    new_survey = TercerSurvey(data=binary_data)
    db.session.add(new_survey)
    db.session.commit()
    
    hora_fin = datetime.now()
    elapsed_time = hora_fin - hora_inicio
    logger.info(f"Survey nuevo guardado. Tiempo transcurrido: {elapsed_time}")
    
    gc.collect()
    return
