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
# Zona horaria de São Paulo/Buenos Aires
tz = pytz.timezone('America/Sao_Paulo')




# - Creando cliente openai
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization="org-cSBk1UaTQMh16D7Xd9wjRUYq"
)

# MODELO FINAL PARA CAPTURA DE EVALUACIÓN DE POSITIVIDAD DE COMENTARIOS

# Captura inicial de sentimientos de la tabla totales:
def get_evaluations_of_all(file_content):
    logger.info("4 - Util get_evaluations_of_all inicializado")
    
    # Leer el archivo Excel desde el contenido en memoria (file_content)
    logger.info("5 - Leyendo excel y agregando ID...")
    df = pd.read_excel(BytesIO(file_content))

    # Agregar columna de ID con un número secuencial para cada comentario
    df['ID'] = range(1, len(df) + 1)

    # Asegurar que la columna de SENTIMIENTO existe
    df['TOPICO'] = ""
    
    # Obtener las APIES únicas
    apies_unicas = df['APIES'].unique()

    logger.info(f"Total de APIES únicas: {len(apies_unicas)}")

    for apies_input in apies_unicas:
        logger.info(f"Procesando APIES {apies_input}...")

        # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
        comentarios_filtrados = df[df['APIES'] == apies_input][['ID', 'COMENTARIO']]
        comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

        # Crear el prompt para OpenAI
        prompt = """
            Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: nombre_del_tópico'. Evalúa el comentario para determinar a cuál de los siguientes 10 tópicos pertenece. No inventes tópicos nuevos, si crees que el comentario no encaja en ningún tópico, clasifícalo como EXPERIENCIA_GENERICA. Aquí están los tópicos:  

            1. Si el comentario menciona temas como TRATO_ACTITUD, ATENCION_GENERAL, SERVICIOS_DE_CORTESIA, CONOCIMIENTO_DEL_VENDEDOR, y solo cuando sea evidente que se esté hablando de la atención al cliente, probablemente se trate del tópico ATENCION_AL_CLIENTE.  
            2. Si el comentario menciona temas como CALIDAD_NAFTA_INFINIA, CALIDAD_CAFE, CALIDAD_HAMBURGUESAS, probablemente se trate del tópico CALIDAD_DE_PRODUCTOS.  
            3. Si el comentario menciona temas como APLICACIONES_DIGITALES, USO_DE_TARJETAS_DIGITALES, probablemente se trate del tópico DIGITAL.  
            4. Si el comentario menciona temas como EXPERIENCIA_POSITIVA, EXPERIENCIA_GENERAL, COSAS_IRRELEVANTES, o es específicamente la palabra 'ok', o contiene las palabras 'bien', 'muy bien', 'mb' sin contexto, y variantes parecidas, o además las evaluaciones con puntajes sin contexto como por ejemplo '10', 'de 10', '10 puntos' o similares, probablemente todos esos ejemplos se traten del tópico EXPERIENCIA_GENERICA.  
            5. Si el comentario menciona temas como IMAGEN_DE_INSTALACIONES, SERVICIOS_GENERALES, probablemente se trate del tópico IMAGEN_INSTALACIONES_Y_SERVICIOS_GENERALES.  
            6. Si el comentario menciona temas como RECLAMOS_SERIOS, PROBLEMAS_CRITICOS, probablemente se trate del tópico PROBLEMATICAS_CRITICAS.  
            7. Si el comentario menciona temas como LIMPIEZA_BAÑOS, HIGIENE_SANITARIOS, probablemente se trate del tópico SANITARIOS.  
            8. Si el comentario menciona temas como FALTA_DE_STOCK, DISPONIBILIDAD_PRODUCTOS, probablemente se trate del tópico STOCK_DE_PRODUCTOS.  
            9. Si el comentario menciona temas como DEMORAS_EN_EL_SERVICIO, RAPIDEZ_ATENCION, probablemente se trate del tópico TIEMPO_DE_ESPERA.  
            10. Si el comentario menciona temas como PRECIOS_ALTOS, USO_DE_TARJETAS_BANCARIAS, probablemente se trate del tópico VARIABLES_ECONOMICAS_Y_BANCOS.  

            Responde SOLO con el formato 'ID-{id}: nombre_del_tópico'. No utilices otros símbolos, comillas o texto adicional. Respuesta ejemplo:  
            123: EXPERIENCIA_GENERICA  

            Aquí están los comentarios:\n
            """
        for comentario_id, comentario in comentarios_dict.items():
            prompt += f"ID-{comentario_id}: {comentario}\n"

        # Hacer el pedido a OpenAI
        try:
            logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un analista que clasifica comentarios por tópico."},
                    {"role": "user", "content": prompt}
                ]
            )

            respuesta = completion.choices[0].message.content
            logger.info(f"Respuesta obtenida para APIES {apies_input}")

            # Guardar la respuesta en el log (COMENTADO)
            # log_file.write(f"APIES {apies_input}:\n{respuesta}\n\n")

            # Parsear la respuesta usando expresiones regulares para extraer el ID y el tópico
            matches = re.findall(
                r'ID-(\d+):\s*(ATENCION_AL_CLIENTE|CALIDAD_DE_PRODUCTOS|DIGITAL|EXPERIENCIA_GENERICA|IMAGEN_INSTALACIONES_Y_SERVICIOS_GENERALES|PROBLEMATICAS_CRITICAS|SANITARIOS|STOCK_DE_PRODUCTOS|TIEMPO_DE_ESPERA|VARIABLES_ECONOMICAS_Y_BANCOS)',respuesta)

            # Actualizar la columna 'TOPICO' usando los IDs
            for match in matches:
                comentario_id, topico = match
                df.loc[df['ID'] == int(comentario_id), 'TOPICO'] = topico


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

# Corrección de campos vacios en TOPICO de forma automatica hasta rellenarlos todos con un while:
# def process_missing_topics(comments_df):

# Version con iteraciones limitadas y guardado por cada iteracion en db:
def process_missing_topics(comments_df):
    logger.info("Iniciando el proceso de corrección de tópicos...")

    MAX_ITERACIONES = 9  # Límite de iteraciones

    for iteracion in range(MAX_ITERACIONES):
        logger.info(f"Iteración {iteracion + 1}/{MAX_ITERACIONES}: Leyendo archivo CSV...")

        # Leer el archivo directamente desde los bytes
        df = pd.read_csv(BytesIO(comments_df), sep=',')
        logger.info(f"DataFrame cargado con {len(df)} registros.")
        logger.info(f"Columnas del DataFrame: {df.columns}")

        # Filtrar los registros que tienen el campo 'TOPICO' vacío
        df_faltante_topico = df[df['TOPICO'].isna() | (df['TOPICO'].str.strip() == "")]
        logger.info(f"Registros con TOPICO vacío: {len(df_faltante_topico)}")

        if df_faltante_topico.empty:
            logger.info("No se encontraron más registros con TOPICO vacío. Deteniendo el proceso.")
            break

        # Procesar las APIES únicas como siempre
        apies_unicas = df_faltante_topico['APIES'].unique()
        logger.info(f"Total de APIES a procesar: {len(apies_unicas)}")

        for apies_input in apies_unicas:
            logger.info(f"Procesando APIES {apies_input}...")

            # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
            comentarios_filtrados = df_faltante_topico[df_faltante_topico['APIES'] == apies_input][['ID', 'COMENTARIO']]
            comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

            # Crear el prompt y pedir respuestas a OpenAI
            prompt = """
            Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: nombre_del_tópico'. Evalúa el comentario para determinar a cuál de los siguientes 10 tópicos pertenece. No inventes tópicos nuevos, si crees que el comentario no encaja en ningún tópico, clasifícalo como EXPERIENCIA_GENERICA. Aquí están los tópicos:  

            1. Si el comentario menciona temas como TRATO_ACTITUD, ATENCION_GENERAL, SERVICIOS_DE_CORTESIA, CONOCIMIENTO_DEL_VENDEDOR, y solo cuando sea evidente que se esté hablando de la atención al cliente, probablemente se trate del tópico ATENCION_AL_CLIENTE.  
            2. Si el comentario menciona temas como CALIDAD_NAFTA_INFINIA, CALIDAD_CAFE, CALIDAD_HAMBURGUESAS, probablemente se trate del tópico CALIDAD_DE_PRODUCTOS.  
            3. Si el comentario menciona temas como APLICACIONES_DIGITALES, USO_DE_TARJETAS_DIGITALES, probablemente se trate del tópico DIGITAL.  
            4. Si el comentario menciona temas como EXPERIENCIA_POSITIVA, EXPERIENCIA_GENERAL, COSAS_IRRELEVANTES, o es específicamente la palabra 'ok', o contiene las palabras 'bien', 'muy bien', 'mb' sin contexto, y variantes parecidas, o además las evaluaciones con puntajes sin contexto como por ejemplo '10', 'de 10', '10 puntos' o similares, probablemente todos esos ejemplos se traten del tópico EXPERIENCIA_GENERICA.  
            5. Si el comentario menciona temas como IMAGEN_DE_INSTALACIONES, SERVICIOS_GENERALES, probablemente se trate del tópico IMAGEN_INSTALACIONES_Y_SERVICIOS_GENERALES.  
            6. Si el comentario menciona temas como RECLAMOS_SERIOS, PROBLEMAS_CRITICOS, probablemente se trate del tópico PROBLEMATICAS_CRITICAS.  
            7. Si el comentario menciona temas como LIMPIEZA_BAÑOS, HIGIENE_SANITARIOS, probablemente se trate del tópico SANITARIOS.  
            8. Si el comentario menciona temas como FALTA_DE_STOCK, DISPONIBILIDAD_PRODUCTOS, probablemente se trate del tópico STOCK_DE_PRODUCTOS.  
            9. Si el comentario menciona temas como DEMORAS_EN_EL_SERVICIO, RAPIDEZ_ATENCION, probablemente se trate del tópico TIEMPO_DE_ESPERA.  
            10. Si el comentario menciona temas como PRECIOS_ALTOS, USO_DE_TARJETAS_BANCARIAS, probablemente se trate del tópico VARIABLES_ECONOMICAS_Y_BANCOS.  

            Responde SOLO con el formato 'ID-{id}: nombre_del_tópico'. No utilices otros símbolos, comillas o texto adicional. Respuesta ejemplo:  
            123: EXPERIENCIA_GENERICA  

            Aquí están los comentarios:\n
            """
            for comentario_id, comentario in comentarios_dict.items():
                prompt += f"ID-{comentario_id}: {comentario}\n"

            try:
                logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Eres un analista que clasifica comentarios por tópico."},
                        {"role": "user", "content": prompt}
                    ]
                )

                respuesta = completion.choices[0].message.content
                logger.info(f"Respuesta obtenida para APIES {apies_input}")

                # Parsear la respuesta y actualizar
                matches = re.findall(r'ID-(\d+):\s*([\w_]+)', respuesta)

                for match in matches:
                    comentario_id, topico = match
                    df_faltante_topico.loc[df_faltante_topico['ID'] == int(comentario_id), 'TOPICO'] = topico

            except Exception as e:
                logger.error(f"Error al procesar el APIES {apies_input}: {e}")

        # Reemplazar las filas actualizadas en el DataFrame original
        logger.info("Reemplazando filas actualizadas en la tabla original...")
        df.update(df_faltante_topico)

        # Guardar el progreso en la base de datos
        logger.info("Guardando progreso actual en la base de datos...")
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
        output.seek(0)
        archivo_binario = output.read()

        # Guardar en la base de datos
        archivo_anterior = FilteredExperienceComments.query.first()
        if archivo_anterior:
            db.session.delete(archivo_anterior)
            db.session.commit()

        nuevo_archivo = FilteredExperienceComments(archivo_binario=archivo_binario)
        db.session.add(nuevo_archivo)
        db.session.commit()
        logger.info("Progreso guardado exitosamente en la base de datos.")

        # Generar un nuevo `comments_df` para la próxima iteración
        comments_df = archivo_binario

    else:
        logger.warning("Se alcanzó el límite máximo de iteraciones. El proceso se detuvo.")
        
    return


#     logger.info("Iniciando el proceso de corrección de topicos...")

#     flag_vacios = True  # Iniciamos el flag en True para entrar en el ciclo while

#     while flag_vacios:
#         logger.info("Leyendo archivo CSV...")

#         # Leer el archivo directamente desde los bytes
#         df = pd.read_csv(BytesIO(comments_df), sep=',')
        
#         logger.info(f"DataFrame cargado con {len(df)} registros.")
#         logger.info(f"Columnas del DataFrame: {df.columns}")

#         # Filtrar los registros que tienen el campo 'TOPICO' vacío
#         df_faltante_topico = df[df['TOPICO'].isna() | (df['TOPICO'].str.strip() == "")]
#         logger.info(f"Registros con TOPICO vacío: {len(df_faltante_topico)}")
        
#         if df_faltante_topico.empty:
#             logger.info("No se encontraron más registros con SENTIMIENTO vacío. Deteniendo el proceso.")
#             flag_vacios = False  # No hay más campos vacíos, salimos del while
#             break  # Rompemos el ciclo del while
        
#         # Obtener las APIES únicas de los registros filtrados
#         apies_unicas = df_faltante_topico['APIES'].unique()

#         logger.info(f"Total de APIES a procesar: {len(apies_unicas)}")

#         for apies_input in apies_unicas:
#             logger.info(f"Procesando APIES {apies_input}...")

#             # Filtrar comentarios por APIES y crear un diccionario {ID: Comentario}
#             comentarios_filtrados = df_faltante_topico[df_faltante_topico['APIES'] == apies_input][['ID', 'COMENTARIO']]
#             comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

#             # Crear el prompt para OpenAI
#             prompt = """
#             Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: nombre_del_tópico'. Evalúa el comentario para determinar a cuál de los siguientes 10 tópicos pertenece. No inventes tópicos nuevos, si crees que el comentario no encaja en ningún tópico, clasifícalo como EXPERIENCIA_GENERICA. Aquí están los tópicos:  

#             1. Si el comentario menciona temas como TRATO_ACTITUD, ATENCION_GENERAL, SERVICIOS_DE_CORTESIA, CONOCIMIENTO_DEL_VENDEDOR, y solo cuando sea evidente que se esté hablando de la atención al cliente, probablemente se trate del tópico ATENCION_AL_CLIENTE.  
#             2. Si el comentario menciona temas como CALIDAD_NAFTA_INFINIA, CALIDAD_CAFE, CALIDAD_HAMBURGUESAS, probablemente se trate del tópico CALIDAD_DE_PRODUCTOS.  
#             3. Si el comentario menciona temas como APLICACIONES_DIGITALES, USO_DE_TARJETAS_DIGITALES, probablemente se trate del tópico DIGITAL.  
#             4. Si el comentario menciona temas como EXPERIENCIA_POSITIVA, EXPERIENCIA_GENERAL, COSAS_IRRELEVANTES, o es específicamente la palabra 'ok', o contiene las palabras 'bien', 'muy bien', 'mb' sin contexto, y variantes parecidas, o además las evaluaciones con puntajes sin contexto como por ejemplo '10', 'de 10', '10 puntos' o similares, probablemente todos esos ejemplos se traten del tópico EXPERIENCIA_GENERICA.  
#             5. Si el comentario menciona temas como IMAGEN_DE_INSTALACIONES, SERVICIOS_GENERALES, probablemente se trate del tópico IMAGEN_INSTALACIONES_Y_SERVICIOS_GENERALES.  
#             6. Si el comentario menciona temas como RECLAMOS_SERIOS, PROBLEMAS_CRITICOS, probablemente se trate del tópico PROBLEMATICAS_CRITICAS.  
#             7. Si el comentario menciona temas como LIMPIEZA_BAÑOS, HIGIENE_SANITARIOS, probablemente se trate del tópico SANITARIOS.  
#             8. Si el comentario menciona temas como FALTA_DE_STOCK, DISPONIBILIDAD_PRODUCTOS, probablemente se trate del tópico STOCK_DE_PRODUCTOS.  
#             9. Si el comentario menciona temas como DEMORAS_EN_EL_SERVICIO, RAPIDEZ_ATENCION, probablemente se trate del tópico TIEMPO_DE_ESPERA.  
#             10. Si el comentario menciona temas como PRECIOS_ALTOS, USO_DE_TARJETAS_BANCARIAS, probablemente se trate del tópico VARIABLES_ECONOMICAS_Y_BANCOS.  

#             Responde SOLO con el formato 'ID-{id}: nombre_del_tópico'. No utilices otros símbolos, comillas o texto adicional. Respuesta ejemplo:  
#             123: EXPERIENCIA_GENERICA  

#             Aquí están los comentarios:\n
#             """
#             for comentario_id, comentario in comentarios_dict.items():
#                 prompt += f"ID-{comentario_id}: {comentario}\n"

#             # Hacer el pedido a OpenAI
#             try:
#                 logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input}...")
#                 completion = client.chat.completions.create(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {"role": "system", "content": "Eres un analista que clasifica comentarios por tópico."},
#                         {"role": "user", "content": prompt}
#                     ]
#                 )

#                 respuesta = completion.choices[0].message.content
#                 logger.info(f"Respuesta obtenida para APIES {apies_input}")

#                 # Parsear la respuesta usando expresiones regulares para extraer el ID y el sentimiento
#                 matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

#                 # Actualizar la columna 'TOPICO' en df_faltante_topico usando los IDs
#                 for match in matches:
#                     comentario_id, topico = match
#                     df_faltante_topico.loc[df_faltante_topico['ID'] == int(comentario_id), 'TOPICO'] = topico

#             except Exception as e:
#                 logger.error(f"Error al procesar el APIES {apies_input}: {e}")

#         # Reemplazar las filas correspondientes en la tabla original
#         logger.info("Reemplazando filas en tabla original...")

#         # Verificar si los objetos df y df_faltante_sentimiento son DataFrames
#         logger.info(f"Tipo de df: {type(df)}")
#         logger.info(f"Tipo de df_faltante_sentimiento: {type(df_faltante_topico)}")

#         # Verificar si los DataFrames están vacíos
#         logger.info(f"df está vacío: {df.empty}")
#         logger.info(f"df_faltante_sentimiento está vacío: {df_faltante_topico.empty}")

#         # Verificar el tamaño de los DataFrames antes de seguir
#         logger.info(f"df tiene {df.shape[0]} filas y {df.shape[1]} columnas")
#         logger.info(f"df_faltante_sentimiento tiene {df_faltante_topico.shape[0]} filas y {df_faltante_topico.shape[1]} columnas")

#         # Verificar si hay valores nulos en la columna 'ID'
#         if df['ID'].isnull().any() or df_faltante_topico['ID'].isnull().any():
#             logger.error("Existen valores nulos en la columna 'ID'. Esto puede causar problemas en el merge.")
#             return
#         else:
#             logger.error("No hay valores nulos en la columna ID")

#         # Verificar si hay duplicados en la columna 'ID'
#         if df['ID'].duplicated().any() or df_faltante_topico['ID'].duplicated().any():
#             logger.error("Existen valores duplicados en la columna 'ID'. Esto puede causar problemas en el merge.")
#             return
#         else:
#             logger.error("No existen duplicados en la columna ID")

#         # Asegurarse de que los tipos de la columna ID coincidan
#         df['ID'] = df['ID'].astype(int)
#         df_faltante_topico['ID'] = df_faltante_topico['ID'].astype(int)
#         logger.error("Se supone que hasta acá hicimos coincidir los tipos de la columna ID para ser int en ambos")

#         # Probar un merge simple para verificar que el merge funcione
#         try:
#             # Hacemos un merge, pero solo actualizamos los valores faltantes en 'TOPICO'
#             df_merged = df.merge(
#                 df_faltante_topico[['ID', 'TOPICO']],
#                 on='ID',
#                 how='left',
#                 suffixes=('', '_nuevo')
#             )

#             # Solo reemplazar los valores de TOPICO que están vacíos
#             df_merged['TOPICO'] = df_merged['TOPICO'].combine_first(df_merged['TOPICO_nuevo'])

#             # Eliminar la columna de los nuevos TOPICOS
#             df_merged = df_merged.drop(columns=['TOPICO_nuevo'])

#             logger.info(f"Primeras filas de df_merged:\n{df_merged.head()}")
#             logger.info(f"Total de filas en df_merged: {len(df_merged)}")

#             logger.info("Filas actualizadas en la tabla original con el merge.")
        
#             # Guardar el DataFrame actualizado como un archivo binario para la siguiente iteración
#             output = BytesIO()
#             df_merged.to_csv(output, index=False, encoding='utf-8', sep=',', quotechar='"', quoting=1)
#             output.seek(0)
#             comments_df = output.read()  # Convertirlo nuevamente en binario para la próxima iteración


#         except Exception as e:
#             logger.error(f"Error durante el merge: {e}")
#             return
    
#     # Guardar el DataFrame actualizado en la base de datos cuando no haya más vacíos
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

# # Corrección de los comentarios negativos para mejorarlos ( pero anexado con el de invalidos en conjutno ):
# def process_negative_comments(file_content):
#     logger.info("Iniciando el proceso de reevaluación de sentimientos negativos...")

#     # Leer el archivo desde los bytes recibidos
#     df = pd.read_csv(BytesIO(file_content))
#     logger.info(f"DataFrame cargado con {len(df)} registros.")
    
#     # Filtrar comentarios con sentimiento negativo
#     df_negativos = df[df['SENTIMIENTO'] == 'negativo']

#     # Cantidad total de registros de la tabla de negativos
#     total_negativos = len(df_negativos)
#     logger.info(f"Total de registros en la tabla de comentarios negativos: {total_negativos}")

#     # Crear el archivo paralelo con todos los comentarios negativos
#     output_negative_comments = BytesIO()
#     df_negativos.to_excel(output_negative_comments, index=False)
#     output_negative_comments.seek(0)
    
#     # Obtener las APIES únicas de los comentarios negativos
#     apies_unicas = df_negativos['APIES'].unique()
#     logger.info(f"Total de APIES a procesar: {len(apies_unicas)}")

#     # Contador para llevar el seguimiento de actualizaciones
#     actualizaciones_realizadas = 0

#     for apies_input in apies_unicas:
#         logger.info(f"Procesando APIES {apies_input}...")

#         # Filtrar comentarios de la APIES actual y crear un diccionario {ID: Comentario}
#         comentarios_filtrados = df_negativos[df_negativos['APIES'] == apies_input][['ID', 'COMENTARIO']]
#         comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

#         # Crear el prompt para OpenAI
#         prompt = "Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: positivo', 'ID-{id}: negativo' o 'ID-{id}: invalido'.Si el comentario solamente tiene la palabra 'no', '0' o 'ne', responde 'invalido'. Si el comentario menciona a 'milei' o 'privaticen', responde 'invalido'. Si el comentario no es claro o no tiene un sentimiento definido, responde 'invalido'.Si el comentario contiene aluciones a positividad como ':)','muy bueno','muy bien',u otros emojis positivos o comentarios que tengan algun tipo de aprovación, serán clasificados como 'positivo'.Necesitamos evitar a toda costa falsos negativos. Aquí están los comentarios:\n"
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

#             # Parsear la respuesta para extraer el ID y el sentimiento
#             matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

#             # Actualizar la columna 'SENTIMIENTO' en df_negativos usando los IDs
#             for comentario_id, sentimiento in matches:
#                 df_negativos.loc[df_negativos['ID'] == int(comentario_id), 'SENTIMIENTO'] = sentimiento
#                 actualizaciones_realizadas += 1  # Incrementamos el contador de actualizaciones

#         except Exception as e:
#             logger.error(f"Error al procesar el APIES {apies_input}: {e}")

#     # Logueamos la cantidad total de actualizaciones realizadas
#     logger.info(f"Total de actualizaciones realizadas en los sentimientos: {actualizaciones_realizadas}, de el total de negativos:{total_negativos}")

#     # Reemplazar las filas correspondientes en la tabla original
#     logger.info("Reemplazando filas en la tabla original con los resultados reevaluados...")
#     df.update(df_negativos[['ID', 'SENTIMIENTO']])

#     # Llamar a la función hermana para procesar los "inválidos"
#     df = process_invalid_comments(df)

#     # Guardar el DataFrame actualizado en la base de datos o como archivo binario
#     logger.info("Guardando DataFrame actualizado en la tabla FilteredExperienceComments...")
#     output = BytesIO()
#     df.to_csv(output, index=False)
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

#     logger.info("Archivo actualizado guardado exitosamente en la tabla FilteredExperienceComments.")
#     return

# # Corrección de los comentarios invalidos para mejorarlos ( es parte del flow del util anterior )
# def process_invalid_comments(df):
#     logger.info("Iniciando el proceso de corrección de comentarios inválidos...")

#     # Filtrar comentarios con sentimiento inválido
#     df_invalidos = df[df['SENTIMIENTO'] == 'invalido']

#     # Cantidad total de registros inválidos
#     total_invalidos = len(df_invalidos)
#     logger.info(f"Total de registros en la tabla de comentarios inválidos: {total_invalidos}")

#     # Obtener las APIES únicas de los comentarios inválidos
#     apies_unicas = df_invalidos['APIES'].unique()
#     logger.info(f"Total de APIES a procesar para comentarios inválidos: {len(apies_unicas)}")

#     # Contador para llevar el seguimiento de actualizaciones
#     actualizaciones_realizadas = 0

#     for apies_input in apies_unicas:
#         logger.info(f"Procesando APIES {apies_input} para comentarios inválidos...")

#         # Filtrar comentarios de la APIES actual y crear un diccionario {ID: Comentario}
#         comentarios_filtrados = df_invalidos[df_invalidos['APIES'] == apies_input][['ID', 'COMENTARIO']]
#         comentarios_dict = dict(zip(comentarios_filtrados['ID'], comentarios_filtrados['COMENTARIO']))

#         # Crear el prompt para OpenAI
#         prompt = "Para cada comentario a continuación, responde SOLO con el formato 'ID-{id}: positivo', 'ID-{id}: negativo' o 'ID-{id}: invalido'. Si el comentario no es claro o no tiene un sentimiento definido, responde 'invalido'.Si el comentario contiene aluciones a positividad como ':)','muy bueno','completo','lujo','todo bien','excelente','muy bien','mb' u otros emojis positivos o comentarios que tengan algun tipo de aprovación, serán clasificados como 'positivo'.El comentario podria encontrarse también despues de uno o dos saltos de linea, revisar bien el texto. Necesitamos evitar a toda costa falsos negativos. Aquí están los comentarios:\n"
#         for comentario_id, comentario in comentarios_dict.items():
#             prompt += f"ID-{comentario_id}: {comentario}\n"

#         # Hacer el pedido a OpenAI
#         try:
#             logger.info(f"Enviando solicitud a OpenAI para APIES {apies_input} (corrección de inválidos)...")
#             completion = client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {"role": "system", "content": "Eres un analista que clasifica comentarios por sentimiento."},
#                     {"role": "user", "content": prompt}
#                 ]
#             )

#             respuesta = completion.choices[0].message.content
#             logger.info(f"Respuesta obtenida para APIES {apies_input} (corrección de inválidos)")

#             # Parsear la respuesta para extraer el ID y el sentimiento
#             matches = re.findall(r'ID-(\d+):\s*(positivo|negativo|invalido)', respuesta)

#             # Actualizar la columna 'SENTIMIENTO' en df_invalidos usando los IDs
#             for comentario_id, sentimiento in matches:
#                 df_invalidos.loc[df_invalidos['ID'] == int(comentario_id), 'SENTIMIENTO'] = sentimiento
#                 actualizaciones_realizadas += 1  # Incrementamos el contador de actualizaciones

#         except Exception as e:
#             logger.error(f"Error al procesar el APIES {apies_input} (corrección de inválidos): {e}")

#     # Logueamos la cantidad total de actualizaciones realizadas
#     logger.info(f"Total de actualizaciones realizadas en los sentimientos inválidos: {actualizaciones_realizadas}, de el total de inválidos: {total_invalidos}")

#     # Reemplazar las filas correspondientes en el DataFrame original
#     df.update(df_invalidos[['ID', 'SENTIMIENTO']])

#     logger.info("Corrección de comentarios inválidos finalizada.")
#     return df
