from openai import OpenAI
import requests
import pandas as pd
from database import db
from models import QuintoSurvey
import time
import pickle
import pytz
from dotenv import load_dotenv
load_dotenv()
import os
from logging_config import logger

# Zona horaria de São Paulo/Buenos Aires
tz = pytz.timezone('America/Sao_Paulo')

# - Creando cliente openai
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization="org-cSBk1UaTQMh16D7Xd9wjRUYq"
)



# ===================== MAPPING MANUAL PARA EL QUINTO SURVEY =====================
hardcoded_question_text = {
    "240286181": "¿Qué tan probable es que usted le recomiende este curso a un colega?",
    "213556722": "De acuerdo a tu experiencia del día de hoy, ¿Cómo calificarías el desempeño del instructor?",
    "213556725": "En líneas generales, ¿cómo calificarías a este curso/ actividad?",
    "213556723": "Pensando en los contenidos vistos, considerás que la duración del curso fue:",
    "240267012": "En cuanto a la información recibida, considerás que es:",
    "240267144": "A continuación te presentamos una serie de frases, en cada caso decinos cuán de acuerdo estás:",
    "240267640": "En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:",
    "213556724": "Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso"
}

# ===================== CONFIGURACIÓN =====================
access_token = '2wYqIfOC-NMjGsZY1cNmbJgQ8T1vbEkIpn.dV-DyAIxDVDLsWCFrb-OyZEZwZJh63trqhqzLTUoWi69XN3ksCA5RdMAElrXi5nd7vZ-hheS4clX12YP97SY1MxdlQn-e'
survey_id = '520546031'
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}


def get_survey_details(session):
    logger.info("🔍 Obteniendo detalles de la encuesta %s", survey_id)
    details_url = f"https://api.surveymonkey.com/v3/surveys/{survey_id}/details"
    r = session.get(details_url, timeout=15)
    if r.status_code != 200:
       logger.info(
            "❌ Error al obtener detalles: %s %s", r.status_code, r.text
       )
       return {}, {}

    details = r.json()
    question_text_mapping = {}
    choice_mapping = {}

    for page in details.get("pages", []):
        for question in page.get("questions", []):
            q_id = question.get("id")
            heading = None
            if "headings" in question and question["headings"]:
                heading = question["headings"][0].get("heading")
            if not heading:
                heading = hardcoded_question_text.get(q_id, str(q_id))
            question_text_mapping[q_id] = heading

            choice_mapping[q_id] = {}
            answers_info = question.get("answers", {})
            for choice in answers_info.get("choices", []):
                cid = choice.get("id")
                choice_mapping[q_id][cid] = choice.get("text")
    logger.info(
        "✅ Mapeos obtenidos: %s preguntas, mapeos de opciones generados", 
        len(question_text_mapping)
    )
    return question_text_mapping, choice_mapping


def flatten_response(response_json, question_text_mapping, choice_mapping):
    flat = {}
    flat["respondent_id"] = response_json.get("id")
    flat["collector_id"] = response_json.get("collector_id")
    flat["date_created"] = response_json.get("date_created")
    flat["date_modified"] = response_json.get("date_modified")

    meta = response_json.get("metadata", {})
    if meta:
        flat.update({
            "ip_address": meta.get("ip_address"),
            "email_address": meta.get("email_address"),
            "first_name": meta.get("first_name"),
            "last_name": meta.get("last_name"),
            "custom_1": meta.get("custom_1")
        })

    for key, val in response_json.get("custom_variables", {}).items():
        flat[key] = val

    for page in response_json.get("pages", []):
        for question in page.get("questions", []):
            q_id = question.get("id")
            text = question_text_mapping.get(q_id, str(q_id))
            answers = question.get("answers", [])
            texts = []
            if not answers:
                texts.append("Sin respuesta")
            else:
                for ans in answers:
                    if ans.get("text"):
                        texts.append(ans.get("text"))
                    elif ans.get("choice_id"):
                        cid = ans.get("choice_id")
                        texts.append(choice_mapping.get(q_id, {}).get(cid, f"[ID:{cid}]") )
                    elif ans.get("row") and ans.get("column"):
                        texts.append(f"Fila:{ans['row']} Col:{ans['column']}")
                    else:
                        texts.append(str(ans))
            flat[text] = ", ".join(texts)
    return flat


def get_detail_response(session, response_id, question_text_mapping, choice_mapping,
                        max_retries=3, wait=2):
    url = f"https://api.surveymonkey.com/v3/surveys/{survey_id}/responses/{response_id}/details"
    for attempt in range(1, max_retries+1):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                return flatten_response(r.json(), question_text_mapping, choice_mapping)
            logger.info(
                "⚠️ Intento %s: Error %s al obtener detalle %s",
                attempt, r.status_code, response_id
            )
        except Exception as e:
            logger.info(
                "⚠️ Excepción %s en intento %s para %s", e, attempt, response_id
            )
        time.sleep(wait * attempt)
    logger.info(
        "❌ Falló al obtener el detalle de respuesta %s tras %s intentos",
        response_id, max_retries
    )
    return None


def obtener_y_guardar_quinto_survey():
    try:
        logger.info("🚀 Iniciando obtención y guardado del quinto survey")
        with requests.Session() as session:
            session.headers.update(headers)

            q_map, c_map = get_survey_details(session)
            if not q_map:
                logger.info("Aborto: no se pudieron obtener mapeos de encuesta")
                return

            all_responses = []
            bulk_url = f"https://api.surveymonkey.com/v3/surveys/{survey_id}/responses/bulk"
            params = {"per_page": 1000, "page": 1}

            while True:
                logger.info(
                    "📄 Solicitando página %s de respuestas", params["page"]
                )
                r_bulk = session.get(bulk_url, params=params, timeout=15)
                if r_bulk.status_code != 200:
                    logger.info(
                        "❌ Error bulk %s %s", r_bulk.status_code, r_bulk.text
                    )
                    break

                data = r_bulk.json().get("data", [])
                if not data:
                    logger.info("✅ No quedan más respuestas. Fin del bucle.")
                    break

                for resp in data:
                    rid = resp.get("id")
                    logger.info("🔗 Obteniendo detalle para respuesta %s", rid)
                    detail = get_detail_response(session, rid, q_map, c_map)
                    if detail:
                        all_responses.append(detail)

                params["page"] += 1

            logger.info(
                "📊 Total de respuestas procesadas: %s", len(all_responses)
            )

            df = pd.DataFrame(all_responses)
            logger.info("✅ DataFrame creado con %s filas", len(df))

            frases_col = "A continuación te presentamos una serie de frases, en cada caso decinos cuán de acuerdo estás:"
            if frases_col in df.columns:
                logger.info("🔄 Separando columna de matriz en columnas individuales")
                split = df[frases_col].str.split(",", expand=True)
                split = split.rename(columns={
                    0: "Los temas fueron tratados con claridad",
                    1: "El contenido visto es de utilidad para mi tarea",
                    2: "Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso",
                    3: "Las actividades propuestas refuerzan lo aprendido"
                })
                df = df.join(split)
                df.drop(columns=[frases_col], inplace=True)

            column_order = [
                "respondent_id", "collector_id", "date_created", "date_modified",
                "ip_address", "email_address", "first_name", "last_name", "custom_1",
                "GestoresAprendizaje", "Curso",
                "¿Qué tan probable es que usted le recomiende este curso a un colega?",
                "De acuerdo a tu experiencia del día de hoy, ¿Cómo calificarías el desempeño del instructor?",
                "En líneas generales, ¿cómo calificarías a este curso/ actividad?",
                "Pensando en los contenidos vistos, considerás que la duración del curso fue:",
                "En cuanto a la información recibida, considerás que es:",
                "Los temas fueron tratados con claridad",
                "El contenido visto es de utilidad para mi tarea",
                "Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso",
                "Las actividades propuestas refuerzan lo aprendido",
                "En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:",
                "Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso"
            ]
            existing = [col for col in column_order if col in df.columns]
            df = df[existing]
            logger.info("🔢 Columnas ordenadas según schema final")

            import io
            from utils.rescate_utils import procesar_encuestas_presenciales

            # --- INTERCEPCIÓN PARA procesar_encuestas_presenciales ---
            logger.info("🔌 Envío del DataFrame a procesar_encuestas_presenciales")

            # Convertimos el df a CSV en un BytesIO
            csv_buffer = io.BytesIO()
            # Index=False para no incluir la columna de índice en el CSV
            csv_buffer.write(df.to_csv(index=False).encode('utf-8'))
            csv_buffer.seek(0)

            # Llamamos a tu función que procesa encuestas presenciales
            procesar_encuestas_presenciales(csv_buffer)

            logger.info("✅ procesar_encuestas_presenciales terminó correctamente")
            # --- FIN DE LA INTERCEPCIÓN ------------------------------

            logger.info("💾 Serializando DataFrame a binario pickle")
            binary = pickle.dumps(df)

            logger.info("🗄️ Guardando registro en la base de datos")
            record = QuintoSurvey(data=binary)
            db.session.add(record)
            db.session.commit()
            logger.info("✅ Registro guardado con id %s", record.id)

        logger.info("🎉 Proceso de recuperación del quinto survey completado")
    except Exception as e:
        logger.info(
            f"💣 Error en obtener_y_guardar_quinto_survey: {e}", exc_info=True
        )
