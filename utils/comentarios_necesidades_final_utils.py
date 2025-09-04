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


def process_file_and_identify_needs(file_content: bytes, proceso_id: str, user_id: int) -> None:
    from models import ProcesoNecesidadesEstado
    raw_df = pd.read_excel(BytesIO(file_content))
    logger.info(f"Columnas recibidas: {raw_df.columns.tolist()}")
    logger.info(f"Total registros en Excel: {len(raw_df)}")

    df = raw_df.copy()
    df.columns = [c.strip().upper() for c in df.columns]
    df['FECHA'] = pd.to_datetime(df['FECHA']).dt.date
    if 'COMENTARIO' not in df.columns:
        logger.error("Falta columna 'COMENTARIO'. No se puede procesar.")
        return
    df['ORIG_ROW'] = raw_df.index[df.index] + 1
    df['ID'] = df.index + 1

    estado = ProcesoNecesidadesEstado.query.get(proceso_id)
    if not estado:
        logger.error(f"No se encontró proceso con ID {proceso_id}")
        return

    total_registros = len(df)
    estado.total = total_registros
    estado.done = 0
    estado.finish = False
    db.session.commit()

    db.session.query(ComentarioNecesidad).filter_by(user_id=user_id).delete()
    db.session.commit()

    pendientes = set(df['ID'])
    necesidades = {}
    topicos_asignados = {}
    topicos_existentes = [t.nombre_topico for t in TopicoNecesidad.query.all()]
    max_intentos = 8
    procesados_unicos = set()

    for intento in range(1, max_intentos + 1):
        if not pendientes:
            logger.info("✔ No quedan pendientes, saliendo del loop")
            break
        logger.info(f"🔁 Iteración {intento} con {len(pendientes)} pendientes")

        for apies in df[df['ID'].isin(pendientes)]['APIES'].unique():
            ids_grupo = [i for i in pendientes if df.loc[df['ID'] == i, 'APIES'].iloc[0] == apies]
            subset = df[df['ID'].isin(ids_grupo)]
            prompt = '\n'.join(f"ID-{int(r['ID'])}: {r['COMENTARIO']}" for _, r in subset.iterrows())

            instrucciones = (
                f"TOPICOS_PERMITIDOS: {topicos_existentes}\n"
                "Para cada comentario recibido, responde en el siguiente formato:\n"
                "ID-123: SI <TOPICONECESIDAD:NOMBRE_EXISTENTE>\n"
                "o\n"
                "ID-123: NO\n\n"
                "NO clasifiques elogios como necesidades. Ejemplos:\n"
                "- 'Muy buena atención' → NO\n"
                "- 'Excelente servicio' → NO\n"
                "Ejemplo SI:\n"
                "- 'El baño estaba sucio' → SI <TOPICONECESIDAD:MEJORAR_INFRAESTRUCTURA_BAÑOS>\n"
            )

            try:
                respuesta = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Sos un clasificador de necesidades y tópicos. Respondé en formato estricto como se indica."},
                        {"role": "user", "content": instrucciones + "\n\n" + prompt}
                    ]
                ).choices[0].message.content
                logger.info(f"📦 Respuesta OpenAI para APIES {apies}:\n{respuesta}")
            except Exception as e:
                logger.error(f"❌ Error al pedir a OpenAI para APIES {apies}: {e}")
                continue

            procesados_iter = set()
            for line in respuesta.splitlines():
                logger.debug(f"📜 Analizando línea: {line}")
                match = re.match(r'ID-(\d+):\s*(SI|NO)(?:\s*<TOPICONECESIDAD:([^>]+)>)?', line.strip(), flags=re.IGNORECASE)
                if match:
                    idx = int(match.group(1))
                    es_necesidad = match.group(2).upper() == 'SI'
                    necesidades[idx] = es_necesidad
                    if es_necesidad:
                        topico_raw = match.group(3)
                        if topico_raw:
                            topico = topico_raw.strip().upper().replace(' ', '_')
                            if topico in topicos_existentes:
                                topicos_asignados[idx] = topico
                            else:
                                logger.warning(f"⚠️ Tópico inválido para ID-{idx}: {topico}")
                    procesados_iter.add(idx)
                else:
                    logger.warning(f"❌ Línea no matcheada: {line}")

            nuevos_procesados = procesados_iter - procesados_unicos
            procesados_unicos.update(nuevos_procesados)

            estado.done = len(procesados_unicos)
            estado.finish = False
            db.session.commit()
            logger.info(f"📊 Avance: {estado.done} / {estado.total} ({int((estado.done / estado.total) * 100)}%)")

            if not nuevos_procesados:
                logger.warning(f"🛑 No se procesó nada nuevo en el intento {intento}. Cortando.")
                break

            pendientes -= nuevos_procesados

    df['ES_NECESIDAD'] = df['ID'].map(necesidades)
    guardados = 0

    for _, r in df[df['ES_NECESIDAD']].iterrows():
        uid = f"{r['FECHA']}_{r['APIES']}_{r['ORIG_ROW']}"
        try:
            cm = ComentarioNecesidad(
                id_unico=uid,
                fecha=r['FECHA'],
                api_es=int(r['APIES']),
                comentario=r['COMENTARIO'],
                canal=r.get('CANAL', ''),
                sentimiento=r.get('SENTIMIENTO', ''),
                topico=r.get('TOPICO', ''),
                user_id=user_id
            )
            topico_nom = topicos_asignados.get(r['ID'])
            if topico_nom:
                top = TopicoNecesidad.query.filter_by(nombre_topico=topico_nom).first()
                if top:
                    cm.topico_necesidad_id = top.id
            db.session.add(cm)
            db.session.commit()
            guardados += 1
        except Exception as e:
            db.session.rollback()
            logger.error(f"💥 Error guardando {uid}: {e}")

    estado.done = estado.total
    estado.finish = True
    db.session.commit()

    logger.info(f"🎉 Proceso completado. Total guardados: {guardados}")
