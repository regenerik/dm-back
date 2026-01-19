
from flask import Blueprint, request, jsonify, send_file
from reportlab.pdfgen import canvas
from logging_config import logger
from reportlab.lib.pagesizes import letter
import io, os, textwrap
from dotenv import load_dotenv
from models import FormularioNecesidades, DiagnosticoOperadores
from database import db
from utils.form_necesidades_utils import query_assistant
import io
import os
import textwrap
from flask import jsonify, send_file
import json
from datetime import datetime
import pandas as pd
from io import BytesIO
import re

load_dotenv()

form_necesidades_bp = Blueprint('form_necesidades_bp', __name__)

# Clave API para proteger la ruta
API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY


#-----------------DEPRECADO>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
@form_necesidades_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path == '/test_form_necesidades_bp':
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401

@form_necesidades_bp.route('/test_form_necesidades_bp', methods=['GET'])
def test():
    return jsonify({'message': 'Test OK'}), 200

@form_necesidades_bp.route('/form_necesidades', methods=['POST'])
def procesar_formulario_necesidades():
    try:
        payload = request.get_json()

        # 1️⃣ Guardar formulario
        form = FormularioNecesidades(
            provincia=payload.get("provincia"),
            localidad=payload.get("localidad"),
            apies=payload.get("apies"),
            empleados_total=payload.get("empleadosTotal"),
            gestor=payload.get("gestor"),
            email_gestor=payload.get("emailGestor"),
            experiencia_cliente=payload.get("experienciaCliente"),
            liderazgo=payload.get("liderazgo"),
            comentarios=payload.get("comentarios"),
            seguridad_operativa=payload.get("seguridadOperativa"),
        )

        db.session.add(form)
        db.session.commit()

        # 2️⃣ Armar texto del formulario
        seg = payload.get("seguridadOperativa", {})

        form_text = f"""
DATOS DE LA ESTACIÓN
Provincia: {payload.get("provincia")}
Localidad: {payload.get("localidad")}
APIES: {payload.get("apies")}
Cantidad de empleados: {payload.get("empleadosTotal")}
Gestor: {payload.get("gestor")}
Email gestor: {payload.get("emailGestor")}

SEGURIDAD OPERATIVA
Aplicación general:
Puntaje: {seg.get("general", {}).get("score")}
Comentario: {seg.get("general", {}).get("comentario")}

Uso de EPP:
Puntaje: {seg.get("epp", {}).get("score")}
Comentario: {seg.get("epp", {}).get("comentario")}

Procedimientos de emergencia:
Puntaje: {seg.get("emergencias", {}).get("score")}
Comentario: {seg.get("emergencias", {}).get("comentario")}

Manipulación de productos:
Puntaje: {seg.get("manipulacion", {}).get("score")}
Comentario: {seg.get("manipulacion", {}).get("comentario")}

EXPERIENCIA DEL CLIENTE
Puntaje: {payload.get("experienciaCliente")}

LIDERAZGO
Puntaje: {payload.get("liderazgo")}

COMENTARIOS GENERALES
{payload.get("comentarios")}
"""

        # 3️⃣ Prompt final
        evaluation_prompt = f"""
Evaluá la siguiente estación YPF.

Respondé EXCLUSIVAMENTE con este formato:

[EVALUACION_SEGURIDAD]
Aplicacion_general: X
Uso_EPP: X
Emergencias: X
Manipulacion_productos: X

[EVALUACION_CLIENTE]
Experiencia_cliente: X
Liderazgo: X

[DIAGNOSTICO]
Texto.

[CURSOS_RECOMENDADOS]
- Curso 1
- Curso 2

[JUSTIFICACION]
Texto.

DIAGNÓSTICO:
{form_text}
"""

        # 4️⃣ Llamar al assistant (guarda en DB internamente)
        respuesta_ia = query_assistant(evaluation_prompt, form.id)

        # 5️⃣ Responder al frontend
        return jsonify({
            "status": "ok",
            "form_id": form.id,
            "respuesta_ia": respuesta_ia
        }), 200

    except Exception as e:
        logger.exception("Error procesando formulario de necesidades")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@form_necesidades_bp.route("/get_necesidades_form", methods=['GET'])
def get_necesidades_form():
    """Recupera todos los registros de necesidades y los devuelve serializados."""
    registros = FormularioNecesidades.query.all()
    return jsonify([reg.serialize() for reg in registros]), 200

@form_necesidades_bp.route('/get_necesidades_form_pdf/<int:form_id>', methods=['GET'])
def get_necesidades_form_pdf(form_id):
    form = FormularioNecesidades.query.get_or_404(form_id)

    buffer = io.BytesIO()
    width, height = letter
    p = canvas.Canvas(buffer, pagesize=letter)
    
    base_dir = os.path.dirname(__file__)
    bg_path = os.path.join(base_dir, 'background.png')
    logo_path = os.path.join(base_dir, 'logo.png')

    def draw_template(canvas_obj):
        if os.path.exists(bg_path):
            canvas_obj.drawImage(bg_path, 0, 0, width=width, height=height)
        if os.path.exists(logo_path):
            canvas_obj.drawImage(logo_path, width-130, height-70, width=80, height=40, mask='auto')

    # NUEVA LÓGICA: Respeta saltos de línea existentes y ajusta el ancho
    def write_multiline_text(text, current_y, font="Helvetica", size=12, x_pos=60, max_chars=85):
        if not text:
            return current_y
            
        p.setFont(font, size)
        # Dividimos primero por los saltos de línea reales (\n)
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            # Para cada párrafo, aplicamos el wrap si es muy largo
            lines = textwrap.wrap(paragraph, max_chars) if paragraph.strip() else [" "]
            for line in lines:
                if current_y < 60:
                    p.showPage()
                    draw_template(p)
                    current_y = height - 80
                    p.setFont(font, size)
                
                p.drawString(x_pos, current_y, line)
                current_y -= (size + 3)
        return current_y

    draw_template(p)

    # Título
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width/2, height-80, "Informe de Detección de Necesidades")
    y = height - 120

    # --- DATOS GENERALES ---
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Información General")
    y -= 20
    
    datos_header = [
        f"ID: {form.id} | Fecha: {form.created_at.strftime('%d/%m/%Y')}",
        f"APIES: {form.apies}",
        f"Ubicación: {form.provincia}, {form.localidad}",
        f"Gestor: {form.gestor} ({form.email_gestor})",
        f"Empleados Totales: {form.empleados_total}"
    ]
    for item in datos_header:
        y = write_multiline_text(item, y, x_pos=50)
    
    y -= 15

    # --- EVALUACIÓN DE PILARES ---
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Evaluación de Pilares y Scores:")
    y -= 20
    
    pilares = [f"Experiencia Cliente: {form.experiencia_cliente}", f"Liderazgo: {form.liderazgo}"]
    if form.seguridad_operativa:
        try:
            seg_data = form.seguridad_operativa if isinstance(form.seguridad_operativa, dict) else json.loads(form.seguridad_operativa)
            for k, v in seg_data.items():
                pilares.append(f"Seguridad Operativa - {k}: {v}")
        except:
            pilares.append(f"Seguridad Operativa: {form.seguridad_operativa}")

    for pilar in pilares:
        y = write_multiline_text(f"• {pilar}", y, x_pos=60, max_chars=80)

    y -= 15

    # --- COMENTARIOS DEL GESTOR ---
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Comentarios del Gestor:")
    y -= 20
    y = write_multiline_text(form.comentarios or "Sin comentarios.", y, x_pos=60)
    
    y -= 15

    # --- PLAN DE ACCIÓN (IA) - CON RESPETO A FORMATO ORIGINAL ---
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Plan de Acción Sugerido (IA):")
    y -= 20
    # Usamos la nueva función que respeta los saltos de línea de los [TITULOS]
    y = write_multiline_text(form.respuesta_ia, y, x_pos=60, font="Helvetica", max_chars=85)

    # Finalizar
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"informe_{form.apies}_{form.id}.pdf",
        mimetype='application/pdf'
    )


@form_necesidades_bp.route('/download_necesidades_excel', methods=['GET'])
def download_necesidades_excel():
    registros = FormularioNecesidades.query.all()
    data = [r.serialize() for r in registros]
    
    if not data:
        return jsonify({"msg": "No hay datos"}), 404

    df = pd.DataFrame(data)

    # 1. Procesar el JSON de seguridad (igual que antes)
    if 'seguridad_operativa' in df.columns:
        seguridad_df = pd.json_normalize(df['seguridad_operativa'])
        seguridad_df.columns = [f"Seguridad_{col}" for col in seguridad_df.columns]
        df = pd.concat([df.drop(columns=['seguridad_operativa']), seguridad_df], axis=1)

    # 2. FUNCIÓN PARA PARSEAR LA RESPUESTA IA
    def extraer_seccion(texto, titulo):
        if not texto: return ""
        # Buscamos lo que hay entre [TITULO] y el siguiente [ o el final del texto
        pattern = rf"\[{titulo}\](.*?)(?=\[|$)"
        match = re.search(pattern, texto, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    # 3. Crear las nuevas columnas extrayendo la info de 'respuesta_ia'
    secciones = [
        "EVALUACION_SEGURIDAD", 
        "EVALUACION_CLIENTE", 
        "DIAGNOSTICO", 
        "CURSOS_RECOMENDADOS", 
        "JUSTIFICACION"
    ]

    for seccion in secciones:
        df[seccion] = df['respuesta_ia'].apply(lambda x: extraer_seccion(x, seccion))

    # 4. Reordenar Columnas
    columnas_base = [
        'created_at', 'apies', 'provincia', 'localidad', 'gestor', 'email_gestor', 
        'empleados_total', 'experiencia_cliente', 'liderazgo'
    ]
    
    columnas_seguridad = [c for c in df.columns if c.startswith('Seguridad_')]
    
    # Ponemos las nuevas columnas de la IA al final junto con el comentario original
    columnas_ia = secciones + ['comentarios', 'id']
    
    orden_final = [c for c in columnas_base + columnas_seguridad + columnas_ia if c in df.columns]
    df = df[orden_final]

    # 5. Generar Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Necesidades_Detalle')

    output.seek(0)
    hoy = datetime.now()
    nombre = f"Reporte_IA_Detallado_{hoy.strftime('%d_%m_%Y')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=nombre,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@form_necesidades_bp.route('/delete_especific_necesidades_form', methods=['POST'])
def delete_necesidad():
    # 1. Usar silent=True y force=True para evitar el 400 automático de Flask
    data = request.get_json(silent=True, force=True)
    
    # Debug para ver qué llega realmente al servidor de Render
    print(f"DEBUG DATA: {data}") 

    if not data:
        return jsonify({"msg": "El servidor no recibió un JSON válido"}), 400

    form_id = data.get("id")
    email_usuario = data.get("email")

    if not form_id or not email_usuario:
        return jsonify({"msg": "Faltan datos requeridos (id o email)"}), 400

    # Buscar el registro
    formulario = FormularioNecesidades.query.get(form_id)

    if not formulario:
        return jsonify({"msg": "Formulario no encontrado"}), 404

    # VALIDACIÓN: ¿El email del gestor coincide?
    # Usamos .lower() para evitar problemas de mayúsculas/minúsculas
    if formulario.email_gestor.lower() != email_usuario.lower():
        return jsonify({"msg": "No tienes permisos para eliminar este registro. Solo el creador puede hacerlo."}), 403

    try:
        db.session.delete(formulario)
        db.session.commit()
        return jsonify({"msg": f"Formulario {form_id} eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al eliminar", "error": str(e)}), 500
    
#<<<<<<<<<<<<<<<<<<<<<<DEPRECADO----------------------------------------------


#>>>>>>>>>>>NUEVOS >>>>>>>>>>>>>>>>>>>>>>>>>>>

@form_necesidades_bp.route("/diagnostico", methods=["POST"])
def crear_diagnostico():
    data = request.get_json(force=True)

    if not data:
        return jsonify({"error": "No se recibió JSON"}), 400

    nuevo = DiagnosticoOperadores(
        provincia_localidad=data.get("provincia_localidad", ""),
        apies=data.get("apies", ""),
        tipo_estacion=data.get("tipo_estacion", ""),
        empleados_total=data.get("empleados_total", ""),

        playa_personal=data.get("playa_personal", ""),
        tienda_personal=data.get("tienda_personal", ""),
        boxes_personal=data.get("boxes_personal", ""),

        anios_operacion=data.get("anios_operacion", ""),
        capacitaciones_anio=data.get("capacitaciones_anio", ""),
        solo_aprendizaje=data.get("solo_aprendizaje", ""),
        detalle_otras_cap=data.get("detalle_otras_cap", ""),
        gestor_asociado=data.get("gestor_asociado", ""),

        nivel_seguridad=data.get("nivel_seguridad", ""),
        preparacion_emergencia=data.get("preparacion_emergencia", ""),
        mejoras_seguridad=json.dumps(data.get("mejoras_seguridad", [])),

        nivel_bromatologia=data.get("nivel_bromatologia", ""),
        mejoras_bromatologia=json.dumps(data.get("mejoras_bromatologia", [])),

        frecuencia_accidentes=data.get("frecuencia_accidentes", ""),
        situaciones_accidentes=json.dumps(data.get("situaciones_accidentes", [])),

        otro_seguridad_playa=data.get("otro_seguridad_playa", ""),
        otro_seguridad_tienda=data.get("otro_seguridad_tienda", ""),
        otro_seguridad_boxes=data.get("otro_seguridad_boxes", ""),
        otro_bromatologia=data.get("otro_bromatologia", ""),
        otro_accidentes=data.get("otro_accidentes", ""),

        nivel_pilares=data.get("nivel_pilares", ""),
        efectividad_comunicacion=data.get("efectividad_comunicacion", ""),
        actitud_empatica=data.get("actitud_empatica", ""),
        autonomia_reclamos=data.get("autonomia_reclamos", ""),
        adaptacion_estilo=data.get("adaptacion_estilo", ""),

        aspectos_atencion=json.dumps(data.get("aspectos_atencion", [])),
        otro_aspectos_atencion=data.get("otro_aspectos_atencion", ""),

        conoce_playa=data.get("conoce_playa", ""),
        conoce_tienda=data.get("conoce_tienda", ""),
        conoce_boxes=data.get("conoce_boxes", ""),
        conoce_digital=data.get("conoce_digital", ""),

        ranking_temas=json.dumps(data.get("ranking_temas", [])),

        dominio_gestion=data.get("dominio_gestion", ""),
        capacidad_analisis=data.get("capacidad_analisis", ""),
        uso_herramientas_dig=data.get("uso_herramientas_dig", ""),

        ranking_desafios=json.dumps(data.get("ranking_desafios", [])),

        liderazgo_efectivo=data.get("liderazgo_efectivo", ""),
        frecuencia_feedback=data.get("frecuencia_feedback", ""),
        habilidades_org=data.get("habilidades_org", ""),
        estilo_liderazgo=data.get("estilo_liderazgo", ""),

        ranking_fortalecer_lider=json.dumps(data.get("ranking_fortalecer_lider", [])),

        interes_capacitacion=data.get("interes_capacitacion", ""),
        temas_prioritarios=json.dumps(data.get("temas_prioritarios", [])),
        otro_tema_prioritario=data.get("otro_tema_prioritario", ""),
        sugerencias_finales=data.get("sugerencias_finales", "")
    )

    db.session.add(nuevo)
    db.session.commit()

    return jsonify(nuevo.serialize()), 201


@form_necesidades_bp.route("/diagnostico/<int:id>", methods=["GET"])
def obtener_diagnostico(id):
    registro = DiagnosticoOperadores.query.get(id)

    if not registro:
        return jsonify({"error": "Registro no encontrado"}), 404

    return jsonify(registro.serialize()), 200

@form_necesidades_bp.route("/diagnostico", methods=["GET"])
def listar_diagnosticos():
    registros = DiagnosticoOperadores.query.order_by(DiagnosticoOperadores.created_at.desc()).all()
    return jsonify([r.serialize() for r in registros]), 200


@form_necesidades_bp.route("/diagnostico/conclusion", methods=["POST"])
def guardar_conclusion():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibió JSON"}), 400

    registro_id = data.get("id")
    conclucion_final = data.get("conclucion_final")

    if not registro_id:
        return jsonify({"error": "Falta el id del registro"}), 400

    registro = DiagnosticoOperadores.query.get(registro_id)

    if not registro:
        return jsonify({"error": "Registro no encontrado"}), 404

    registro.conclucion_final = conclucion_final
    db.session.commit()

    return jsonify({
        "message": "Conclusión guardada correctamente",
        "registro": registro.serialize()
    }), 200


@form_necesidades_bp.route("/diagnostico/simple", methods=["GET"])
def listar_diagnosticos_simple():
    registros = DiagnosticoOperadores.query.order_by(
        DiagnosticoOperadores.created_at.desc()
    ).all()

    return jsonify([r.serialize_simple() for r in registros]), 200

@form_necesidades_bp.route("/diagnostico/eliminar", methods=["POST"])
def eliminar_diagnostico():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibió JSON"}), 400

    registro_id = data.get("id")
    gestor_request = data.get("gestor_asociado")

    if not registro_id or not gestor_request:
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    registro = DiagnosticoOperadores.query.get(registro_id)

    if not registro:
        return jsonify({"error": "Registro no encontrado"}), 404

    # 1️⃣ Si es el mismo gestor → OK
    if registro.gestor_asociado == gestor_request:
        db.session.delete(registro)
        db.session.commit()
        return jsonify({
            "message": "Registro eliminado correctamente",
            "id": registro_id
        }), 200

    # 2️⃣ Si NO es el gestor, verificamos si es admin
    usuario = User.query.filter_by(name=gestor_request).first()

    if usuario and usuario.admin is True:
        db.session.delete(registro)
        db.session.commit()
        return jsonify({
            "message": "Registro eliminado por administrador",
            "id": registro_id
        }), 200

    # ❌ No es gestor ni admin
    return jsonify({
        "error": "No tenés permisos para eliminar este diagnóstico"
    }), 403


@form_necesidades_bp.route("/diagnostico/ia/evaluar", methods=["POST"])
def evaluar_diagnostico_con_ia():
    try:
        payload = request.get_json()

        if not payload:
            return jsonify({"error": "No se recibió JSON"}), 400

        diagnostico_id = payload.get("id")

        if not diagnostico_id:
            return jsonify({"error": "Falta el id del diagnóstico"}), 400

        # 1️⃣ Buscar diagnóstico
        diagnostico = DiagnosticoOperadores.query.get(diagnostico_id)

        if not diagnostico:
            return jsonify({"error": "Diagnóstico no encontrado"}), 404

        # 2️⃣ Armar texto del formulario
        form_text = f"""
DATOS GENERALES
Provincia / Localidad: {diagnostico.provincia_localidad}
APIES: {diagnostico.apies}
Tipo de estación: {diagnostico.tipo_estacion}
Cantidad total de empleados: {diagnostico.empleados_total}
Gestor asociado: {diagnostico.gestor_asociado}

SEGURIDAD Y CUMPLIMIENTO
Nivel de seguridad general: {diagnostico.nivel_seguridad}
Preparación ante emergencias: {diagnostico.preparacion_emergencia}
Mejoras detectadas en seguridad: {diagnostico.mejoras_seguridad}

BROMATOLOGÍA
Nivel de bromatología: {diagnostico.nivel_bromatologia}
Mejoras detectadas en bromatología: {diagnostico.mejoras_bromatologia}

ACCIDENTES
Frecuencia de accidentes: {diagnostico.frecuencia_accidentes}
Situaciones reportadas: {diagnostico.situaciones_accidentes}

EXPERIENCIA DEL CLIENTE
Pilares de experiencia: {diagnostico.nivel_pilares}
Efectividad de la comunicación: {diagnostico.efectividad_comunicacion}
Actitud empática: {diagnostico.actitud_empatica}
Autonomía en reclamos: {diagnostico.autonomia_reclamos}
Adaptación al estilo del cliente: {diagnostico.adaptacion_estilo}

CONOCIMIENTO
Playa: {diagnostico.conoce_playa}
Tienda: {diagnostico.conoce_tienda}
Boxes: {diagnostico.conoce_boxes}
Digital: {diagnostico.conoce_digital}

GESTIÓN Y LIDERAZGO
Dominio de gestión: {diagnostico.dominio_gestion}
Capacidad de análisis: {diagnostico.capacidad_analisis}
Uso de herramientas digitales: {diagnostico.uso_herramientas_dig}
Liderazgo efectivo: {diagnostico.liderazgo_efectivo}
Frecuencia de feedback: {diagnostico.frecuencia_feedback}
Habilidades organizativas: {diagnostico.habilidades_org}
Estilo de liderazgo: {diagnostico.estilo_liderazgo}

SUGERENCIAS FINALES
{diagnostico.sugerencias_finales}
"""

        # 3️⃣ Prompt final para la IA
        evaluation_prompt = f"""
Evaluá el siguiente diagnóstico de una estación de servicio YPF.

Respondé EXCLUSIVAMENTE con el siguiente formato:

[DIAGNOSTICO_GENERAL]
Texto claro y profesional.

[FORTALEZAS]
- Punto 1
- Punto 2

[DEBILIDADES]
- Punto 1
- Punto 2

[RECOMENDACIONES]
- Recomendación 1
- Recomendación 2

[CAPACITACIONES_SUGERIDAS]
- Curso 1
- Curso 2

INFORMACIÓN DEL FORMULARIO:
{form_text}
"""

        # 4️⃣ Llamar al assistant
        respuesta_ia = query_assistant(evaluation_prompt)

        # 5️⃣ Guardar respuesta IA
        diagnostico.respuesta_ia = respuesta_ia
        db.session.commit()

        # 6️⃣ Responder al frontend
        return jsonify({
            "status": "ok",
            "diagnostico_id": diagnostico.id,
            "conclusion_ia": respuesta_ia
        }), 200

    except Exception as e:
        logger.exception("Error evaluando diagnóstico con IA")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@form_necesidades_bp.route("/diagnostico/<int:id>", methods=["PUT"])
def actualizar_diagnostico(id):
    data = request.get_json(force=True)

    if not data:
        return jsonify({"error": "No se recibió JSON"}), 400

    diagnostico = DiagnosticoOperadores.query.get(id)

    if not diagnostico:
        return jsonify({"error": "Diagnóstico no encontrado"}), 404

    # --- Datos generales ---
    diagnostico.provincia_localidad = data.get("provincia_localidad", "")
    diagnostico.apies = data.get("apies", "")
    diagnostico.tipo_estacion = data.get("tipo_estacion", "")
    diagnostico.empleados_total = data.get("empleados_total", "")

    diagnostico.playa_personal = data.get("playa_personal", "")
    diagnostico.tienda_personal = data.get("tienda_personal", "")
    diagnostico.boxes_personal = data.get("boxes_personal", "")

    diagnostico.anios_operacion = data.get("anios_operacion", "")
    diagnostico.capacitaciones_anio = data.get("capacitaciones_anio", "")
    diagnostico.solo_aprendizaje = data.get("solo_aprendizaje", "")
    diagnostico.detalle_otras_cap = data.get("detalle_otras_cap", "")
    diagnostico.gestor_asociado = data.get("gestor_asociado", "")

    # --- Seguridad ---
    diagnostico.nivel_seguridad = data.get("nivel_seguridad", "")
    diagnostico.preparacion_emergencia = data.get("preparacion_emergencia", "")
    diagnostico.mejoras_seguridad = json.dumps(data.get("mejoras_seguridad", []))

    # --- Bromatología ---
    diagnostico.nivel_bromatologia = data.get("nivel_bromatologia", "")
    diagnostico.mejoras_bromatologia = json.dumps(data.get("mejoras_bromatologia", []))

    # --- Accidentes ---
    diagnostico.frecuencia_accidentes = data.get("frecuencia_accidentes", "")
    diagnostico.situaciones_accidentes = json.dumps(data.get("situaciones_accidentes", []))

    diagnostico.otro_seguridad_playa = data.get("otro_seguridad_playa", "")
    diagnostico.otro_seguridad_tienda = data.get("otro_seguridad_tienda", "")
    diagnostico.otro_seguridad_boxes = data.get("otro_seguridad_boxes", "")
    diagnostico.otro_bromatologia = data.get("otro_bromatologia", "")
    diagnostico.otro_accidentes = data.get("otro_accidentes", "")

    # --- Experiencia cliente ---
    diagnostico.nivel_pilares = data.get("nivel_pilares", "")
    diagnostico.efectividad_comunicacion = data.get("efectividad_comunicacion", "")
    diagnostico.actitud_empatica = data.get("actitud_empatica", "")
    diagnostico.autonomia_reclamos = data.get("autonomia_reclamos", "")
    diagnostico.adaptacion_estilo = data.get("adaptacion_estilo", "")

    diagnostico.aspectos_atencion = json.dumps(data.get("aspectos_atencion", []))
    diagnostico.otro_aspectos_atencion = data.get("otro_aspectos_atencion", "")

    # --- Conocimiento ---
    diagnostico.conoce_playa = data.get("conoce_playa", "")
    diagnostico.conoce_tienda = data.get("conoce_tienda", "")
    diagnostico.conoce_boxes = data.get("conoce_boxes", "")
    diagnostico.conoce_digital = data.get("conoce_digital", "")

    diagnostico.ranking_temas = json.dumps(data.get("ranking_temas", []))

    # --- Gestión ---
    diagnostico.dominio_gestion = data.get("dominio_gestion", "")
    diagnostico.capacidad_analisis = data.get("capacidad_analisis", "")
    diagnostico.uso_herramientas_dig = data.get("uso_herramientas_dig", "")

    diagnostico.ranking_desafios = json.dumps(data.get("ranking_desafios", []))

    # --- Liderazgo ---
    diagnostico.liderazgo_efectivo = data.get("liderazgo_efectivo", "")
    diagnostico.frecuencia_feedback = data.get("frecuencia_feedback", "")
    diagnostico.habilidades_org = data.get("habilidades_org", "")
    diagnostico.estilo_liderazgo = data.get("estilo_liderazgo", "")

    diagnostico.ranking_fortalecer_lider = json.dumps(
        data.get("ranking_fortalecer_lider", [])
    )

    # --- Capacitación futura ---
    diagnostico.interes_capacitacion = data.get("interes_capacitacion", "")
    diagnostico.temas_prioritarios = json.dumps(data.get("temas_prioritarios", []))
    diagnostico.otro_tema_prioritario = data.get("otro_tema_prioritario", "")
    diagnostico.sugerencias_finales = data.get("sugerencias_finales", "")
    diagnostico.respuesta_ia = None

    db.session.commit()

    return jsonify(diagnostico.serialize()), 200
