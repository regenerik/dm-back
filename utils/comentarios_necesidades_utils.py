import pandas as pd
import re
from io import BytesIO
from database import db
from models import TopicoNecesidad, ComentarioNecesidad
from openai import OpenAI
import os
from logging_config import logger

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization="org-cSBk1UaTQMh16D7Xd9wjRUYq"
)

def process_file_and_identify_needs(file_content: bytes) -> None:
    # 0. Leer Excel y debug inicial
    raw_df = pd.read_excel(BytesIO(file_content))
    logger.info(f"Columnas recibidas: {raw_df.columns.tolist()}")
    logger.info(f"Total registros en Excel: {len(raw_df)}")

    # 1. Preparar DataFrame y filtrar
    df = raw_df.copy()
    # Convertir columna FECHA a date
    df['FECHA'] = pd.to_datetime(df['FECHA']).dt.date
    # Normalizar nombres de columna
    df.columns = [c.strip().upper() for c in df.columns]
    if 'COMENTARIO' not in df.columns:
        logger.error("Falta columna 'COMENTARIO'. No se puede procesar.")
        return
    # df = df[df['COMENTARIO'].astype(str).str.len() >= 20].reset_index(drop=True)
    # logger.info(f"Registros tras filtro COMENTARIO>=20: {len(df)}")
    df['ORIG_ROW'] = raw_df.index[df.index] + 1  # conservar fila original
    df['ID'] = df.index + 1

    # 2. Limpiar tabla previa
    db.session.query(ComentarioNecesidad).delete()
    db.session.commit()

    # 3. Bulk detección con reintentos
    pendientes = set(df['ID'])
    necesidades = {}
    max_intentos = 8
    for intento in range(1, max_intentos+1):
        if not pendientes:
            break
        logger.info(f"Intento {intento}: pendientes={len(pendientes)}")
        procesados_iter = set()
        for apies in df[df['ID'].isin(pendientes)]['APIES'].unique():
            ids_grupo = [i for i in pendientes if df.loc[df['ID']==i, 'APIES'].iloc[0] == apies]
            subset = df[df['ID'].isin(ids_grupo)]
            prompt = build_need_prompt(subset)
            try:
                respuesta = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role":"system","content":"Detecta si cada comentario del cliente es una necesidad constructiva y/o sugerencia que pueda mostrarnos como mejorar: responde 'ID-{id}: SI' o 'ID-{id}: NO' por línea. No consideres saludos, elogios o comentarios de atención rápida como necesidades (ej: 'rápida y buena atención', 'excelente y rápida atención').Algunos ejemplos de sugerencias o necesidades constructivas son:'Me encantaria que tengan un lugar para las mascotas', 'el sistema de cobro va lento, podrian mejorarlo?','el empleado no supo decirme que aceite colocar en mi auto'"},
                        {"role":"user","content":prompt}
                    ]
                ).choices[0].message.content
                logger.info(f"Resp RAW APIES {apies}: {respuesta}")
            except Exception as e:
                logger.error(f"Error OpenAI APIES {apies}: {e}")
                continue
            for m in re.findall(r'ID-(\d+):\s*(SI|NO)', respuesta, flags=re.IGNORECASE):
                idx, flag = int(m[0]), m[1].upper()
                necesidades[idx] = (flag == 'SI')
                procesados_iter.add(idx)
        pendientes -= procesados_iter
    for idx in pendientes:
        necesidades[idx] = False

    # 4. Asignar y guardar comentarios
    df['ES_NECESIDAD'] = df['ID'].map(necesidades)
    total_necesidades = df['ES_NECESIDAD'].sum()
    logger.info(f"Total marcados como necesidad: {total_necesidades}")
    guardados = 0
    for _, r in df[df['ES_NECESIDAD']].iterrows():
        uid = f"{r['FECHA']}_{r['APIES']}_{r['ORIG_ROW']}"
        logger.info(f"Intentando guardar {uid}")
        try:
            cm = ComentarioNecesidad(
                id_unico=uid,
                fecha=r['FECHA'].date() if hasattr(r['FECHA'], 'date') else r['FECHA'],
                api_es=int(r['APIES']),
                comentario=r['COMENTARIO'],
                canal=r.get('CANAL', ''),
                sentimiento=r.get('SENTIMIENTO', ''),
                topico=r.get('TOPICO', '')
            )
            db.session.add(cm)
            db.session.commit()
            guardados += 1
            logger.info(f"Guardado OK: {uid}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error guardando {uid}: {e}")
    logger.info(f"Comentarios de necesidad guardados: {guardados}")

    # 5. Clasificación de tópicos uno-a-uno con detección de existentes o nuevos
    logger.info("Iniciando clasificación de tópicos")
    # Obtener lista inicial de nombres de tópicos existentes
    def refrescar_topicos():
        return [t.nombre_topico for t in TopicoNecesidad.query.all()]

    for cm in ComentarioNecesidad.query.all():
        logger.info(f"Clasificando comentario {cm.id_unico}")
        topicos_existentes = refrescar_topicos()
        # Construir prompt más explícito
        prompt = (
            f"TOPICOS_EXISTENTES: {topicos_existentes}"
            f"COMENTARIO: {cm.comentario}"
            "No incluyas saludos, elogios generales ni comentarios de atención rápida como necesidades (ej: 'rápida y buena atención', 'excelente y rápida atención'). "
            "Si el comentario encaja en uno de los tópicos existentes, responde '<TOPICONECESIDAD:NOMBRE_EXISTENTE>'. "
            "Si se trata de un nuevo tópico, crea un nombre descriptivo en mayúsculas y guiones bajos y responde '<TOPICONECESIDAD:NOMBRE_NUEVO>'."
        )
        logger.info(f"Prompt tópico IA para {cm.id_unico}: {prompt}")
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"Eres un analista que etiqueta comentarios con tópicos. Usa el formato <TOPICONECESIDAD:...>."},
                    {"role":"user","content":prompt}
                ]
            ).choices[0].message.content.strip()
            logger.info(f"Respuesta tópico IA para {cm.id_unico}: {resp}")
        except Exception as e:
            logger.error(f"Error topic API {cm.id_unico}: {e}")
            continue
        # Extraer nombre de tópico
        m = re.search(r'<TOPICONECESIDAD:([^>]+)>', resp)
        if m:
            nombre_topico = m.group(1).strip().upper().replace(' ', '_')
            # Buscar o crear tópico
            top = TopicoNecesidad.query.filter_by(nombre_topico=nombre_topico).first()
            if not top:
                top = TopicoNecesidad(nombre_topico=nombre_topico)
                db.session.add(top)
                db.session.commit()
                logger.info(f"Nuevo tópico creado: {nombre_topico}")
            # Asignar fk
            cm.topico_necesidad_id = top.id
            db.session.commit()
            logger.info(f"Comentario {cm.id_unico} asignado a tópico '{nombre_topico}'")
    # 6. Finalización
    logger.info("Proceso de identificación de necesidades completado")

def build_need_prompt(df_sub: pd.DataFrame) -> str:
    return '\n'.join(f"ID-{int(r['ID'])}: {r['COMENTARIO']}" for _, r in df_sub.iterrows())
