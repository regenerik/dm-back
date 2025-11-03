from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
import requests
import os
import io
import re
import time
from mailjet_rest import Client
from logging_config import logger

# --- Importaciones de librerías para extracción de texto ---
import PyPDF2
import docx
import mammoth
import pandas as pd

# Carga las variables de entorno del archivo .env
load_dotenv()

presentaciones_bp = Blueprint('presentaciones_bp', __name__)

# URLs de la API pública
GAMMA_API_URL = "https://public-api.gamma.app/v0.2/generations"
GAMMA_API_KEY = os.environ.get("GAMMA_API_KEY")


# --- Funciones de procesamiento de archivos (sin imágenes) ---
def extract_text_from_file(file_stream, mimetype):
    """
    Extrae texto de un archivo y devuelve el contenido.
    Soporta PDF, DOCX, DOC, TXT y Excel (XLSX, XLS).
    """
    try:
        if mimetype == "application/pdf":
            reader = PyPDF2.PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text

        elif mimetype in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]:
            if mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                result = mammoth.convert_to_html(file_stream)
                text = re.sub('<[^>]*>', '', result.value)
                return text.strip()
            else:
                doc = docx.Document(file_stream)
                text = ""
                for para in doc.paragraphs:
                    text += para.text + "\n"
                return text

        elif mimetype in [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]:
            try:
                all_sheets = pd.read_excel(file_stream, sheet_name=None)
                full_text = []
                for sheet_name, df in all_sheets.items():
                    full_text.append(f"Hoja: {sheet_name}")
                    full_text.append(df.to_string(index=False, header=True))
                return "\n\n".join(full_text)
            except Exception as e:
                logger.error(f"Error al procesar archivo Excel: {e}")
                return None

        elif mimetype == "text/plain":
            file_stream.seek(0)
            text = file_stream.read().decode('utf-8', errors='ignore')
            return text

        else:
            return None

    except Exception as e:
        logger.error(f"Error al procesar el archivo {mimetype}: {e}")
        return None


@presentaciones_bp.route('/create-gamma', methods=['POST'])
def create_gamma():
    logger.info("Solicitud POST recibida en /create-gamma.")

    if not GAMMA_API_KEY:
        logger.error("Error: GAMMA_API_KEY no configurada.")
        return jsonify({"message": "GAMMA_API_KEY no configurada en el servidor."}), 500

    titulo = request.form.get('titulo', '')
    descripcion = request.form.get('descripcion', '')
    archivo = request.files.get('file')
    image_url = request.form.get('imageUrl')
    email = request.form.get('email')

    themeName = request.form.get('themeName')
    numCards = request.form.get('numCards')
    tone = request.form.get('tone')
    amount = request.form.get('amount')
    audience = request.form.get('audience')
    language = request.form.get('language')
    exportAs = request.form.get('exportAs')

    logger.info(f"Datos recibidos: Titulo='{titulo}', Descripcion='{descripcion}'")

    prompt_parts = []
    if titulo:
        prompt_parts.append(f"Título: {titulo}")
    if descripcion:
        prompt_parts.append(f"Descripción: {descripcion}")

    prompt = "\n\n".join(prompt_parts)

    if archivo:
        logger.info("Extrayendo texto del archivo...")
        extracted_text = extract_text_from_file(archivo, archivo.mimetype)
        if extracted_text:
            logger.info("Texto del archivo extraído correctamente.")
            prompt += (
                f"\n\nContenido extraído del archivo '{archivo.filename}':\n\n{extracted_text}"
            )
        else:
            logger.warning("No se pudo extraer texto del archivo.")
            prompt += (
                f"\n\nConsidera el contenido del archivo adjunto '{archivo.filename}' "
                f"para la presentación. Nota: el contenido del archivo no pudo ser "
                f"extraído automáticamente."
            )

    if image_url:
        logger.info(f"Incluyendo URL de imagen en el prompt: {image_url}")
        prompt += f"\n\nUtiliza la siguiente imagen para la presentación: {image_url}"

    if not prompt:
        logger.error("Error: El prompt está vacío.")
        return jsonify({"message": "El prompt no puede estar vacío."}), 400

    logger.info("Prompt final preparado. Enviando a la API de Gamma...")

    # Payload de POST (Versión estable sin parámetros opcionales conflictivos)
    payload = {
        "inputText": prompt,
        "textMode": "generate",
        "format": "presentation",
        "exportAs": "pdf",
        "textOptions": {
            "amount": "medium",
            "tone": "string",
            "audience": "string",
            "language": "en"
        },
        "imageOptions": {
            "source": "aiGenerated",
            "style": "profesional, con colores corporativos",
        },
    }

 

    # if themeName:
    #     payload['themeName'] = themeName
    if numCards:
        # La API espera un número, por lo que es mejor convertirlo
        try:
            payload['numCards'] = int(numCards)
        except ValueError:
            pass # Ignora si el valor no es un número válido

    if tone or amount or audience or language or exportAs:
        if 'textOptions' not in payload:
            payload['textOptions'] = {}

        if tone:
            payload['textOptions']['tone'] = tone
        if amount:
            payload['textOptions']['amount'] = amount
        if audience:
            payload['textOptions']['audience'] = audience
        if language:
            payload['textOptions']['language'] = language

    if exportAs:
        payload['exportAs'] = exportAs

    logger.info(payload)

    headers_post = {
        "x-api-key": GAMMA_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        # Paso 1: Llamada inicial para iniciar la generación
        gamma_response = requests.post(GAMMA_API_URL, headers=headers_post, json=payload)
        gamma_response.raise_for_status()
        gamma_data = gamma_response.json()

        generation_id = gamma_data.get('generationId')
        if not generation_id:
            logger.error(
                f"Error: No se recibió 'generationId' de Gamma. Respuesta: {gamma_data}"
            )
            return jsonify({
                "message": "Respuesta inesperada de Gamma (no se recibió 'generationId').",
                "gamma_api_response": gamma_data,
            }), 500

        logger.info(f"Generación iniciada con ID: {generation_id}. Iniciando polling...")

        # Paso 2: Bucle de Polling principal (30 intentos * 10s = 5 minutos)
        for i in range(30):
            time.sleep(10)

            status_url = f"{GAMMA_API_URL}/{generation_id}"

            # Encabezado CORREGIDO para el polling (GET)
            headers_get = {
                "x-api-key": GAMMA_API_KEY,
                "accept": "application/json",
            }

            logger.info(f"Intento {i + 1}: Consultando estado de la generación en {status_url}...")
            # Usamos headers_get para la solicitud de estado
            status_response = requests.get(status_url, headers=headers_get)
            status_response.raise_for_status()
            status_data = status_response.json()

            status = status_data.get('status')
            logger.info(f"Estado de la generación: {status}")

            if status == 'completed':
                logger.info("Generación marcada como 'completed'. Verificando URLs...")

                # Paso 3: Bucle de Polling secundario (mantiene la espera por URLs)
                for j in range(10):
                    # ¡CORRECCIÓN APLICADA AQUÍ!
                    gamma_url = status_data.get('gammaUrl')  # Buscando 'gammaUrl'
                    pdf_url = status_data.get('exportUrl')   # Buscando 'exportUrl' (que es correcto)

                    if gamma_url and pdf_url:
                        logger.info(f"URLs encontradas. Gamma: {gamma_url}, PDF: {pdf_url}")

                        # Si se proporciona un email, enviar el enlace por correo
                        if email:
                            logger.info(f"Enviando enlace de exportación por email a: {email}")
                            
                            subject = f"Presentación Generada - {'PPTX' if exportAs == 'pptx' else 'Archivo'} Disponible"
                            
                            # Usamos f-string para incluir las URLs
                            text = (
                                f"Estimado/a,\n\n"
                                f"Tu presentación ha sido generada correctamente.\n\n"
                                f"Puedes descargar el archivo haciendo click en el siguiente enlace:\n"
                                f"{pdf_url}\n\n"
                                f"También puedes ver y editar la presentación en Gamma (si está disponible):\n"
                                f"{gamma_url}\n\n"
                                f"Gracias por utilizar nuestros servicios."
                            )
                            
                            # Cuerpo HTML opcional, a menudo mejora la entrega y presentación
                            html_part = (
                                f"<h3>Presentación Generada 🚀</h3>"
                                f"<p>Tu presentación ha sido generada correctamente.</p>"
                                f"<p>Puedes descargar el archivo haciendo click en el siguiente enlace:</p>"
                                f'<p><a href="{pdf_url}" target="_blank">Descargar Archivo ({exportAs.upper()})</a></p>'
                                f"<p>También puedes ver y editar la presentación en Gamma:</p>"
                                f'<p><a href="{gamma_url}" target="_blank">{gamma_url}</a></p>'
                                f"<br/>"
                                f"<p>Gracias por utilizar nuestros servicios.</p>"
                            )

                            mailjet = Client(auth=(os.getenv('MJ_APIKEY_PUBLIC'),
                                                os.getenv('MJ_APIKEY_PRIVATE')),
                                            version='v3.1')
                            
                            mail_data = {
                                'Messages': [{
                                    'From': {'Email': os.getenv('MJ_SENDER_EMAIL'), 'Name': 'Generador Gamma'},
                                    'To': [{'Email': email}], # Usamos la variable 'email'
                                    'Subject': subject,
                                    'TextPart': text,
                                    'HTMLPart': html_part,
                                    # NOTA: No incluimos 'Attachments' ya que la URL es un enlace temporal de descarga.
                                }]
                            }

                            try:
                                res = mailjet.send.create(data=mail_data)
                                logger.info(f"Email de presentación enviado a {email} → {res.status_code}")
                            except Exception as e:
                                logger.error(f"Error enviando email de presentación a {email}: {e}")

                        # --- FIN DEL CÓDIGO PARA MANDAR EMAIL ---

                        return jsonify({
                            "status": "completed",
                            "gammaUrl": gamma_url,
                            "exportUrl": pdf_url,  # <-- CAMBIO: Usamos 'exportUrl' como clave en la respuesta final
                            "generationId": generation_id,
                        }), 200

                    logger.warning(f"Intento {j + 1}: URLs aún null. Esperando 10 segundos más...")
                    time.sleep(10)
                    # Vuelve a consultar el estado con el encabezado correcto
                    status_response = requests.get(status_url, headers=headers_get)
                    status_response.raise_for_status()
                    status_data = status_response.json()

                # Si el segundo bucle termina sin URLs
                logger.error("La generación se completó, pero las URLs nunca aparecieron en la respuesta.")
                return jsonify({
                    "status": "completed",
                    "message": "La generación se completó, pero no se recibieron las URLs.",
                    "generationId": generation_id,
                }), 500

            elif status == 'failed':
                logger.error(f"La generación de Gamma falló. Detalles: {status_data.get('error')}")
                return jsonify({
                    "status": "failed",
                    "message": status_data.get('error') or "La generación de la presentación falló.",
                    "generationId": generation_id,
                }), 400

        logger.warning("La generación excedió el tiempo de espera.")
        return jsonify({
            "status": "timeout",
            "message": "La generación de la presentación excedió el tiempo de espera.",
            "generationId": generation_id,
        }), 504

    except requests.exceptions.RequestException as e:
        logger.error(f"Error de solicitud HTTP: {e.response.text if e.response else e}")
        return jsonify({
            "message": "Error en la comunicación con la API de Gamma.",
            "details": str(e),
        }), 500

    except Exception as e:
        logger.error(f"Error inesperado en el servidor: {e}")
        return jsonify({
            "message": "Error interno del servidor.",
            "details": str(e),
        }), 500
