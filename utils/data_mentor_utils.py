import os
import time
import requests
import json
from typing import Optional, Tuple
from logging_config import logger
from models import FileDailyID, InstruccionesGenerales, InstruccionesIndividuales
from openai import OpenAI

# ——————————————————————————————————————————
#  CONFIG
# ——————————————————————————————————————————
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Tenés que definir OPENAI_API_KEY en tus env vars")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "assistants=v2"
}

ASSISTANT_ID = os.environ.get("OPENAI_ASSISTANT_ID", "asst_2Y2zysHMQVAObfFs4N6An4Ub")

# Inicializa el cliente de OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def query_assistant_mentor(prompt: str, thread_id: Optional[str] = None) -> Tuple[str, str]:
    logger.info('Entró al util query_assistant_mentor')
    
    # 1. Obtener el ID del Vector Store más reciente desde la DB.
    #    (Ya no necesitamos los file_ids individuales para el chat).
    daily_file_record = FileDailyID.query.first()
    if not daily_file_record or not daily_file_record.current_vector_store_id:
        logger.error("No se encontró el ID del Vector Store en la base de datos.")
        raise RuntimeError("No se encontró una base de conocimiento activa. Por favor, asegúrese de ejecutar la ruta de actualización de archivos.")
    
    current_vector_store_id = daily_file_record.current_vector_store_id
    logger.info(f"Usando Vector Store con ID recuperado de DB: {current_vector_store_id}")
    
    # 2. Asegurar que el Assistant esté configurado con el Vector Store correcto.
    #    Este paso es CRUCIAL para que el asistente sepa dónde buscar.
    try:
        assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
        
        # Verificar si la configuración actual del asistente coincide con el ID de la DB.
        current_vs_ids = assistant.tool_resources.file_search.vector_store_ids if assistant.tool_resources.file_search else []
        if current_vs_ids != [current_vector_store_id]:
            logger.info(f"El Assistant ({ASSISTANT_ID}) NO tiene el Vector Store ({current_vector_store_id}) adjunto. Actualizando...")
            
            client.beta.assistants.update(
                assistant_id=ASSISTANT_ID,
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [current_vector_store_id]
                    }
                }
            )
            logger.info("Assistant actualizado exitosamente con el nuevo Vector Store.")
        else:
            logger.info("Assistant ya está configurado con el Vector Store más reciente. No se requiere actualización.")
            
    except Exception as e:
        logger.error(f"Error al verificar/actualizar el Assistant con el Vector Store: {e}", exc_info=True)
        raise RuntimeError(f"Error al configurar el Assistant con la base de conocimiento: {str(e)}")


    # 3. Construir dinámicamente la guía de uso (sin cambios, tu código está bien aquí)
    try:
        # (Tu código para construir full_guide_text_for_ai va aquí, sin cambios)
        general_instructions = InstruccionesGenerales.query.first()
        if not general_instructions:
            raise RuntimeError("No se encontraron instrucciones generales en la base de datos para la IA. Por favor, cargue los datos iniciales de las instrucciones.")

        individual_instructions_records = InstruccionesIndividuales.query.all()
        if not individual_instructions_records:
            raise RuntimeError("No se encontraron instrucciones individuales en la base de datos para la IA. Por favor, cargue los datos iniciales de las instrucciones.")

        guide_text_parts = ["GUÍA DE USO DE LA BASE DE CONOCIMIENTO:\n"]
        guide_text_parts.append(f"{general_instructions.descripcion_general}\n\n")
        guide_text_parts.append("SECCIONES DISPONIBLES:\n")

        for inst_ind in individual_instructions_records:
            section_name = inst_ind.name
            
            guide_text_parts.append(f"\n- Sección: '{section_name}'")
            guide_text_parts.append(f"  Descripción: {inst_ind.descripcion}")
            
            relaciones = inst_ind.get_relaciones_clave_dict() 
            if relaciones:
                guide_text_parts.append(f"  Relaciones Clave:")
                for rel_key, rel_desc in relaciones.items():
                    guide_text_parts.append(f"    - {rel_key}: {rel_desc}")
            if inst_ind.ejemplo_consulta:
                guide_text_parts.append(f"  Ejemplo de Consulta: {inst_ind.ejemplo_consulta}")

        guide_text_parts.append("\nINSTRUCCIONES ESPECÍFICAS DE BÚSQUEDA PARA LA IA:")
        guide_text_parts.append(general_instructions.instrucciones_especificas_para_ia)

        full_guide_text_for_ai = "\n".join(guide_text_parts)
    except Exception as e:
        logger.error(f"Error al construir la guía de IA desde la base de datos: {e}", exc_info=True)
        raise RuntimeError(f"Error al construir la guía de la IA: {str(e)}")


    # 4. Crear o continuar el Thread (sin adjuntar nada, ya que el Assistant está configurado)
    current_thread_id = thread_id

    try:
        if not current_thread_id:
            logger.info('thread_id vino SIN contenido (charla nueva). Creando un nuevo hilo...')
            thread = client.beta.threads.create(
                messages=[{"role": "user", "content": prompt}]
            )
            current_thread_id = thread.id
            logger.info(f"Nuevo Thread creado con ID: {current_thread_id}")
        else:
            logger.info(f"thread_id vino con contenido. Continuar hilo existente: {current_thread_id}...")
            client.beta.threads.messages.create(
                thread_id=current_thread_id,
                role="user",
                content=prompt,
            )
            logger.info(f"Mensaje añadido al Thread: {current_thread_id}")

        logger.info(f"Creando o continuando run para el Thread: {current_thread_id} con Assistant ID: {ASSISTANT_ID}")
        
        run = client.beta.threads.runs.create(
            thread_id=current_thread_id,
            assistant_id=ASSISTANT_ID,
            additional_instructions=full_guide_text_for_ai
        )
        run_id = run.id
        logger.info(f"Run creado con ID: {run_id}. Estado inicial: {run.status}")

        while run.status in ["queued", "in_progress", "cancelling"]:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(thread_id=current_thread_id, run_id=run_id)
            logger.info(f"Estado del Run: {run.status}")

        if run.status != "completed":
            error_message = f"El asistente no pudo completar la solicitud. Estado: '{run.status}'."
            if run.last_error:
                error_message += f" Código de error: {run.last_error.code}. Mensaje: {run.last_error.message}"
                logger.error(f"Detalles del error del Run: Código={run.last_error.code}, Mensaje='{run.last_error.message}'")
            else:
                logger.error("El Run falló, pero no se encontraron detalles adicionales en 'last_error'.")
            
            raise RuntimeError(error_message)

        messages_page = client.beta.threads.messages.list(
            thread_id=current_thread_id,
            order="desc",
            limit="1"
        )
        
        assistant_response = ""
        for msg in messages_page.data:
            if msg.role == "assistant":
                for content_block in msg.content:
                    if content_block.type == "text":
                        assistant_response += content_block.text.value
                break

        if not assistant_response:
            logger.warning(f"El asistente no devolvió un mensaje de texto. Thread ID: {current_thread_id}")
            assistant_response = "El asistente no pudo generar una respuesta de texto."

        return assistant_response, current_thread_id

    except Exception as e:
        logger.error(f"Error en query_assistant_mentor: {e}", exc_info=True)
        raise