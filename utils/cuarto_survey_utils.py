from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
from database import db
from models import CuartoSurvey
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



# -----------------------------------En esta versión J , K y T tiene valores, pero N, O, P y Q no : 

# def clean_html(raw_html):
#     """
#     Elimina tags HTML de un string y devuelve texto limpio.
#     Sólo analiza con BeautifulSoup si detecta etiquetas '<' o '>'.
#     """
#     if not isinstance(raw_html, str):
#         return raw_html
#     if '<' not in raw_html and '>' not in raw_html:
#         return raw_html
#     return BeautifulSoup(raw_html, "html.parser").get_text()


# def obtener_y_guardar_cuarto_survey():
#     """
#     Descarga respuestas de SurveyMonkey, procesa datos y guarda resultado en DB.
#     Identifica directamente por qid las columnas J, K y T para asegurar valores correctos.
#     """
#     print("[0] Inicio de obtener_y_guardar_cuarto_survey")
#     access_token = os.getenv('SURVEYMONKEY_ACCESS_TOKEN')
#     survey_id    = '514508354'
#     headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
#     HOST = "https://api.surveymonkey.com"
#     DETS = f"/v3/surveys/{survey_id}/details"
#     BULK = f"/v3/surveys/{survey_id}/responses/bulk"
#     t0 = datetime.now()

#     # Paso 1: detalles
#     print("[1] Obteniendo detalles...")
#     det = requests.get(f"{HOST}{DETS}", headers=headers).json()
#     print(f"[1] {len(det.get('pages', []))} páginas de preguntas")

#     # Paso 2: construir maps
#     question_map = {}  # qid -> heading
#     choice_map = {}    # choice_id -> texto
#     for page in det.get('pages', []):
#         for q in page.get('questions', []):
#             qid = q['id']
#             heading = clean_html(q['headings'][0]['heading'])
#             question_map[qid] = heading
#             for ch in q.get('answers', {}).get('choices', []):
#                 choice_map[ch['id']] = clean_html(ch['text'])
#     print(f"[2] question_map={len(question_map)}, choice_map={len(choice_map)}")

#     # Identificar qids de J, K, T por contenido en heading
#     j_qid = next((qid for qid,h in question_map.items() if 'recomiende este curso' in h), None)
#     k_qid = next((qid for qid,h in question_map.items() if 'calificarías a este curso' in h), None)
#     t_qid = next((qid for qid,h in question_map.items() if 'experiencia de aprendizaje' in h), None)
#     print(f"[2] J_qid={j_qid}, K_qid={k_qid}, T_qid={t_qid}")

#     # Paso 3: descargar respuestas
#     print("[3] Descargando respuestas...")
#     all_resp = []
#     url = f"{HOST}{BULK}?per_page=1000"
#     pg = 1
#     while url:
#         batch = requests.get(url, headers=headers).json()
#         data = batch.get('data', [])
#         all_resp.extend(data)
#         print(f"[3] página {pg}: {len(data)} respuestas, total={len(all_resp)}")
#         url = batch.get('links', {}).get('next')
#         pg += 1
#     print(f"[3] Total respuestas={len(all_resp)}")

#     # Paso 4: preparar registros
#     print("[4] Procesando respuestas...")
#     desired_cols = [
#         'respondent_id','collector_id','date_created','date_modified','ip_address',
#         'email_address','first_name','last_name','custom_1',
#         '¿Qué tan probable es que usted le recomiende este curso a un colega?',
#         'En líneas generales, ¿cómo calificarías a este curso/ actividad?',
#         'Pensando en los contenidos vistos, considerás que la duración del curso fue:',
#         'En cuanto a la información recibida, considerás que es:',
#         'Los temas fueron tratados con claridad',
#         'El contenido visto es de utilidad para mi tarea',
#         'Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso',
#         'Las actividades propuestas refuerzan lo aprendido',
#         'Al momento de realizar el curso, ¿tuviste algún problema con el Campus de aprendizaje?',
#         'Si tuviste algún problema, por favor, contanos que sucedió',
#         'En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:',
#         'Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso',
#         'ID_CODE'
#     ]
#     records = []

#     for resp in all_resp:
#         # base
#         cv = resp.get('custom_variables', {})
#         base = {
#             'respondent_id': resp.get('id'),
#             'collector_id': resp.get('collector_id'),
#             'date_created': resp.get('date_created','')[:10],
#             'date_modified': resp.get('date_modified'),
#             'ip_address': resp.get('ip_address'),
#             'email_address': resp.get('email_address'),
#             'first_name': resp.get('first_name'),
#             'last_name': resp.get('last_name'),
#             'custom_1': cv.get('1',''),
#             'ID_CODE': cv.get('ID_CODE','')
#         }
#         # iniciar record con base
#         rec = {col: base.get(col) for col in desired_cols}
#         # llenar J, K, T desde qids directos
#         for page in resp.get('pages', []):
#             for q in page.get('questions', []):
#                 qid = q.get('id')
#                 for ans in q.get('answers', []):
#                     # J: likelihood
#                     if qid == j_qid:
#                         rec['¿Qué tan probable es que usted le recomiende este curso a un colega?'] = choice_map.get(ans.get('choice_id'), clean_html(ans.get('text','')))
#                     # K: general rating
#                     elif qid == k_qid:
#                         rec['En líneas generales, ¿cómo calificarías a este curso/ actividad?'] = choice_map.get(ans.get('choice_id'), clean_html(ans.get('text','')))
#                     # T: learning experience
#                     elif qid == t_qid:
#                         rec['En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:'] = choice_map.get(ans.get('choice_id'), clean_html(ans.get('text','')))
#                     # luego matrices y resto (ya tenías implementado)
#         # procesar matrices y otras simples
#         for page in resp.get('pages', []):
#             for q in page.get('questions', []):
#                 qid = q.get('id')
#                 if qid not in {j_qid, k_qid, t_qid}:
#                     heading = question_map.get(qid)
#                     # matrix
#                     if heading not in desired_cols:
#                         continue
#                     for ans in q.get('answers', []):
#                         rec[heading] = choice_map.get(ans.get('choice_id'), clean_html(ans.get('text','')))
#         records.append(rec)
#     print(f"[4] Records preparados={len(records)}")

#     # Paso 5: DataFrame y guardado
#     print("[5] Creando DataFrame...")
#     df = pd.DataFrame.from_records(records, columns=desired_cols)
#     print(f"[5] DataFrame shape={df.shape}")

#     print("[6] Guardando en DB...")
#     with BytesIO() as buf:
#         df.to_pickle(buf)
#         data_blob = buf.getvalue()
#     db.session.query(CuartoSurvey).delete()
#     db.session.add(CuartoSurvey(data=data_blob))
#     db.session.commit()

#     gc.collect()
#     print(f"[7] Completado en {datetime.now() - t0}")


# ------------------------En esta versión N, O, P y Q tiene valores, pero J , Q y T no : 

# def clean_html(raw_html):
#     """
#     Elimina tags HTML de un string y devuelve texto limpio.
#     Sólo analiza con BeautifulSoup si detecta etiquetas '<' o '>'.
#     """
#     if not isinstance(raw_html, str):
#         return raw_html
#     if '<' not in raw_html and '>' not in raw_html:
#         return raw_html
#     return BeautifulSoup(raw_html, "html.parser").get_text()


# def obtener_y_guardar_cuarto_survey():
#     """
#     Descarga respuestas de SurveyMonkey, procesa datos y guarda resultado en DB.
#     Llena correctamente columnas J, K, T (simples) y N-Q (subpreguntas de matriz).
#     """
#     print("[0] Inicio de obtener_y_guardar_cuarto_survey")
#     access_token = os.getenv('SURVEYMONKEY_ACCESS_TOKEN')
#     survey_id    = '514508354'
#     headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
#     base_url = "https://api.surveymonkey.com"
#     dets_url = f"{base_url}/v3/surveys/{survey_id}/details"
#     bulk_url = f"{base_url}/v3/surveys/{survey_id}/responses/bulk"
#     t0 = datetime.now()

#     # 1) Obtener detalles y construir mapas
#     print("[1] Obteniendo detalles...")
#     det = requests.get(dets_url, headers=headers).json()
#     question_map = {}   # qid -> heading (para simples)
#     matrix_map   = {}   # qid -> { row_id: row_text }
#     choice_map   = {}   # choice_id -> texto

#     for page in det.get('pages', []):
#         for q in page.get('questions', []):
#             qid = q['id']
#             heading = clean_html(q['headings'][0]['heading'])
#             # mapear options
#             for ch in q.get('answers', {}).get('choices', []):
#                 choice_map[ch['id']] = clean_html(ch['text'])
#             # filas de matriz
#             rows = q.get('answers', {}).get('rows', [])
#             if rows:
#                 matrix_map[qid] = {r['id']: clean_html(r['text']) for r in rows}
#             else:
#                 question_map[qid] = heading
#     print(f"[1] question_map={len(question_map)}, matrix_map={len(matrix_map)}, choice_map={len(choice_map)}")

#     # detectar qids de columnas simples J, K, T
#     inv_qmap = {v:k for k,v in question_map.items()}
#     j_heading = '¿Qué tan probable es que usted le recomiende este curso a un colega?'
#     k_heading = 'En líneas generales, ¿cómo calificarías a este curso/ actividad?'
#     t_heading = 'En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:'
#     j_qid = inv_qmap.get(j_heading)
#     k_qid = inv_qmap.get(k_heading)
#     t_qid = inv_qmap.get(t_heading)
#     print(f"[1] J_qid={j_qid}, K_qid={k_qid}, T_qid={t_qid}")

#     # columnas deseadas
#     desired_cols = [
#         'respondent_id','collector_id','date_created','date_modified','ip_address',
#         'email_address','first_name','last_name','custom_1',
#         j_heading, k_heading,
#         'Pensando en los contenidos vistos, considerás que la duración del curso fue:',
#         'En cuanto a la información recibida, considerás que es:',
#         'Los temas fueron tratados con claridad',
#         'El contenido visto es de utilidad para mi tarea',
#         'Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso',
#         'Las actividades propuestas refuerzan lo aprendido',
#         'Al momento de realizar el curso, ¿tuviste algún problema con el Campus de aprendizaje?',
#         'Si tuviste algún problema, por favor, contanos que sucedió',
#         t_heading,
#         'Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso',
#         'ID_CODE'
#     ]

#     # 2) Descargar respuestas
#     print("[2] Descargando respuestas...")
#     all_resp = []
#     url = f"{bulk_url}?per_page=1000"
#     page = 1
#     while url:
#         batch = requests.get(url, headers=headers).json()
#         data = batch.get('data', [])
#         all_resp.extend(data)
#         print(f"[2] página {page}: {len(data)} respuestas")
#         url = batch.get('links', {}).get('next')
#         page += 1
#     print(f"[2] Total respuestas={len(all_resp)}")

#     # 3) Procesar registros
#     print("[3] Procesando registros...")
#     records = []
#     for resp in all_resp:
#         cv = resp.get('custom_variables', {})
#         base = {
#             'respondent_id': resp.get('id'),
#             'collector_id': resp.get('collector_id'),
#             'date_created': resp.get('date_created','')[:10],
#             'date_modified': resp.get('date_modified'),
#             'ip_address': resp.get('ip_address'),
#             'email_address': resp.get('email_address'),
#             'first_name': resp.get('first_name'),
#             'last_name': resp.get('last_name'),
#             'custom_1': cv.get('1',''),
#             'ID_CODE': cv.get('ID_CODE','')
#         }
#         rec = {col: base.get(col) for col in desired_cols}
#         # Lectura de respuestas
#         for pg_obj in resp.get('pages', []):
#             for q in pg_obj.get('questions', []):
#                 qid = q.get('id')
#                 # preguntas simples J,K,T y otras simples
#                 if qid in question_map:
#                     heading = question_map[qid]
#                     if heading in desired_cols:
#                         for ans in q.get('answers', []):
#                             rec[heading] = choice_map.get(ans.get('choice_id'), clean_html(ans.get('text','')))
#                 # matrix N/Q
#                 elif qid in matrix_map:
#                     for ans in q.get('answers', []):
#                         row_id = ans.get('row_id')
#                         colname = matrix_map[qid].get(row_id)
#                         if colname in desired_cols:
#                             rec[colname] = choice_map.get(ans.get('choice_id'), clean_html(ans.get('text','')))
#         records.append(rec)
#     print(f"[3] Registros procesados={len(records)}")

#     # 4) Crear DataFrame y guardar
#     print("[4] Creando DataFrame...")
#     df = pd.DataFrame.from_records(records, columns=desired_cols)
#     print(f"[4] DataFrame shape={df.shape}")

#     print("[5] Serializando y guardando en DB...")
#     with BytesIO() as buf:
#         df.to_pickle(buf)
#         data_blob = buf.getvalue()
#     db.session.query(CuartoSurvey).delete()
#     db.session.add(CuartoSurvey(data=data_blob))
#     db.session.commit()

#     gc.collect()
#     print(f"[6] Completado en {datetime.now() - t0}")


    # ----------------------------------nuevo test :

def clean_html(raw_html):
    """
    Elimina tags HTML de un string y devuelve texto limpio.
    Sólo analiza con BeautifulSoup si detecta tags HTML.
    """
    if not isinstance(raw_html, str):
        return raw_html
    if '<' not in raw_html and '>' not in raw_html:
        return raw_html
    return BeautifulSoup(raw_html, 'html.parser').get_text()


def obtener_y_guardar_cuarto_survey():
    """
    Descarga respuestas de SurveyMonkey, procesa y garantiza que todas las columnas
    (J, K, T, N-Q) queden pobladas correctamente, luego guarda en DB.
    """
    print('[0] Inicio de obtener_y_guardar_cuarto_survey')
    token = os.getenv('SURVEYMONKEY_ACCESS_TOKEN')
    survey_id = '514508354'
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    base_url = 'https://api.surveymonkey.com'
    details_url = f'{base_url}/v3/surveys/{survey_id}/details'
    bulk_url = f'{base_url}/v3/surveys/{survey_id}/responses/bulk'
    start = datetime.now()

    # Definir encabezados y orden de columnas
    hdr_j = '¿Qué tan probable es que usted le recomiende este curso a un colega?'
    hdr_k = 'En líneas generales, ¿cómo calificarías a este curso/ actividad?'
    hdr_dur = 'Pensando en los contenidos vistos, considerás que la duración del curso fue:'
    hdr_inf = 'En cuanto a la información recibida, considerás que es:'
    hdr_n = 'Los temas fueron tratados con claridad'
    hdr_o = 'El contenido visto es de utilidad para mi tarea'
    hdr_p = 'Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso'
    hdr_q = 'Las actividades propuestas refuerzan lo aprendido'
    hdr_t = 'En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:'
    cols = [
        'respondent_id','collector_id','date_created','date_modified','ip_address',
        'email_address','first_name','last_name','custom_1',
        hdr_j, hdr_k, hdr_dur, hdr_inf,
        hdr_n, hdr_o, hdr_p, hdr_q,
        'Al momento de realizar el curso, ¿tuviste algún problema con el Campus de aprendizaje?',
        'Si tuviste algún problema, por favor, contanos que sucedió',
        hdr_t,
        'Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso',
        'ID_CODE'
    ]

    # 1) Obtener detalles y construir mapas
    print('[1] Obteniendo detalles de preguntas')
    det = requests.get(details_url, headers=headers).json()
    question_map = {}    # qid -> heading (preguntas simples)
    matrix_map = {}      # qid -> {row_id: row_text} (subpreguntas)
    choice_map = {}      # choice_id -> texto
    # conjunto de preguntas simples forzadas
    forced_simple = {hdr_j, hdr_k, hdr_t}
    for page in det.get('pages', []):
        for q in page.get('questions', []):
            qid = q['id']
            heading = clean_html(q['headings'][0]['heading'])
            # registrar opciones
            for ch in q.get('answers', {}).get('choices', []):
                choice_map[ch['id']] = clean_html(ch['text'])
            # detectar matriz vs simple, pero forzar simples para J, K, T
            rows = q.get('answers', {}).get('rows', [])
            if rows and heading not in forced_simple:
                matrix_map[qid] = {r['id']: clean_html(r['text']) for r in rows}
            else:
                question_map[qid] = heading
    print(f"[1] Mapas: {len(question_map)} simples, {len(matrix_map)} matrices, {len(choice_map)} opciones")
    hdr_j = '¿Qué tan probable es que usted le recomiende este curso a un colega?'
    hdr_k = 'En líneas generales, ¿cómo calificarías a este curso/ actividad?'
    hdr_dur = 'Pensando en los contenidos vistos, considerás que la duración del curso fue:'
    hdr_inf = 'En cuanto a la información recibida, considerás que es:'
    hdr_n = 'Los temas fueron tratados con claridad'
    hdr_o = 'El contenido visto es de utilidad para mi tarea'
    hdr_p = 'Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso'
    hdr_q = 'Las actividades propuestas refuerzan lo aprendido'
    hdr_t = 'En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:'
    cols = [
        'respondent_id','collector_id','date_created','date_modified','ip_address',
        'email_address','first_name','last_name','custom_1',
        hdr_j, hdr_k, hdr_dur, hdr_inf,
        hdr_n, hdr_o, hdr_p, hdr_q,
        'Al momento de realizar el curso, ¿tuviste algún problema con el Campus de aprendizaje?',
        'Si tuviste algún problema, por favor, contanos que sucedió',
        hdr_t,
        'Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso',
        'ID_CODE'
    ]

    # 2) Descargar respuestas bulk
    print('[2] Descargando respuestas')
    all_resp = []
    url = f'{bulk_url}?per_page=1000'
    page_num = 1
    while url:
        batch = requests.get(url, headers=headers).json()
        data = batch.get('data', [])
        print(f"[2] Página {page_num}: {len(data)} items")
        all_resp.extend(data)
        url = batch.get('links', {}).get('next')
        page_num += 1
    print(f"[2] Total respuestas: {len(all_resp)}")

    # 3) Procesar respuestas en registros
    print('[3] Procesando registros')
    records = []
    for resp in all_resp:
        cv = resp.get('custom_variables', {})
        base = {
            'respondent_id': resp.get('id'),
            'collector_id': resp.get('collector_id'),
            'date_created': resp.get('date_created','')[:10],
            'date_modified': resp.get('date_modified'),
            'ip_address': resp.get('ip_address'),
            'email_address': resp.get('email_address'),
            'first_name': resp.get('first_name'),
            'last_name': resp.get('last_name'),
            'custom_1': cv.get('1',''),
            'ID_CODE': cv.get('ID_CODE','')
        }
        rec = {c: base.get(c) for c in cols}
        # Completar respuestas
        for page_obj in resp.get('pages', []):
            for question_item in page_obj.get('questions', []):
                qid = question_item.get('id')
                # Pregunta simple (incluyendo j, k, t)
                if qid in question_map:
                    hd = question_map[qid]
                    if hd in rec:
                        for ans in question_item.get('answers', []):
                            if 'choice_id' in ans:
                                rec[hd] = choice_map.get(ans['choice_id'], '')
                            elif 'text' in ans:
                                rec[hd] = clean_html(ans['text'])
                # Subpregunta matriz (n, o, p, q)
                if qid in matrix_map:
                    for ans in question_item.get('answers', []):
                        row_id = ans.get('row_id')
                        hd = matrix_map[qid].get(row_id)
                        if hd in rec:
                            if 'choice_id' in ans:
                                rec[hd] = choice_map.get(ans['choice_id'], '')
                            elif 'text' in ans:
                                rec[hd] = clean_html(ans['text'])
        records.append(rec)
    print(f"[3] Registros preparados: {len(records)}")

    # 4) Crear DataFrame y guardar en DB
    print('[4] Creando DataFrame y guardando en DB')
    df = pd.DataFrame.from_records(records, columns=cols)

    # ————— Aquí metés tu llamada —————
    import io
    from utils.rescate_utils import procesar_encuestas_ac

    # Convertimos el df a CSV en un BytesIO y lo pasamos a procesar_encuestas_ac
    csv_buffer = io.BytesIO()
    csv_buffer.write(df.to_csv(index=False).encode('utf-8'))
    csv_buffer.seek(0)
    procesar_encuestas_ac(csv_buffer)
    logger.info("🔌 procesar_encuestas_ac terminó correctamente")
    # ————————————————————————————

    with BytesIO() as buf:
        df.to_pickle(buf)
        blob = buf.getvalue()
    db.session.query(CuartoSurvey).delete()
    db.session.add(CuartoSurvey(data=blob))
    db.session.commit()

    gc.collect()
    print(f"[5] Finalizado en {datetime.now() - start}")