from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required
from utils.comentarios_necesidades_final_utils import process_file_and_identify_needs
from logging_config import logger
from models import ComentarioNecesidad, TopicoNecesidad, ProcesoNecesidadesEstado
from database import db
from io import BytesIO
import pandas as pd

comentarios_necesidades_final_bp = Blueprint('comentarios_necesidades_final_bp', __name__)

@comentarios_necesidades_final_bp.route('/comentarios_necesidades_final', methods=['POST'])
def iniciar_proceso_comentarios_necesidades():
    """
    Encola el proceso de identificación de necesidades.
    Recibe un .xlsx con columnas FECHA, APIES, COMENTARIO, CANAL, SENTIMIENTO,
    y opcionalmente parámetros de filtro: fecha_desde, fecha_hasta,
    sentimiento, apies, canal, topico, min_caracteres.
    Devuelve el count de filas que se van a procesar y el ID del proceso.
    """
    from extensions import executor

    try:
        # 1) Validaciones básicas del file
        if 'file' not in request.files:
            return jsonify({"error": "No se encontró ningún archivo en la solicitud"}), 400
        file = request.files['file']
        if not file.filename.lower().endswith('.xlsx'):
            return jsonify({"error": "Solo archivos .xlsx permitidos"}), 400

        # 2) Leemos el Excel en un DataFrame
        contenido = file.read()
        df = pd.read_excel(BytesIO(contenido), parse_dates=['FECHA'])

        # 3) Tomamos los parámetros de filtro (si vienen)
        fecha_desde    = request.form.get('fecha_desde')
        fecha_hasta    = request.form.get('fecha_hasta')
        sentimiento    = request.form.get('sentimiento')
        apies          = request.form.get('apies')
        canal          = request.form.get('canal')
        topico         = request.form.get('topico')
        min_caracteres = request.form.get('min_caracteres')
        user_id = request.form.get('user_id', type=int)

        if not user_id:
            return jsonify({"error": "Falta user_id"}), 400

        # 4) Aplicamos cada filtro si fue enviado
        if fecha_desde:
            df = df[df['FECHA'] >= pd.to_datetime(fecha_desde)]
        if fecha_hasta:
            df = df[df['FECHA'] <= pd.to_datetime(fecha_hasta)]
        if sentimiento:
            df = df[df['SENTIMIENTO'].str.lower() == sentimiento.lower()]
        if apies:
            lista = [int(x.strip()) for x in apies.split(',')]
            df = df[df['APIES'].isin(lista)]
        if canal:
            df = df[df['CANAL'].str.lower() == canal.lower()]
        if topico:
            df = df[df['TOPICO'] == topico]
        if min_caracteres:
            mc = int(min_caracteres)
            df = df[df['COMENTARIO'].str.len() >= mc]

        # 5) Contamos cuántas filas quedaron
        count = len(df)

        # 6) Guardamos estado del proceso en la tabla
        estado = ProcesoNecesidadesEstado(total=count, done=0, finish=False)
        db.session.add(estado)
        db.session.commit()
        proceso_id = estado.id  # este es el ID que vamos a devolver y usar

        # 7) Preparamos un nuevo Excel con solo los filtrados
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        filtered_content = buffer.getvalue()

        # 8) Encolamos el proceso en background
        executor.submit(process_file_and_identify_needs, filtered_content, proceso_id, user_id)

        # 9) Devolvemos info al frontend
        return jsonify({
            "message": "Proceso iniciado. Recordá que la cantidad de comentarios filtrados no es la cantidad de registros de devolución, ya que todavía falta determinar cuáles son necesidades.",
            "comentarios_filtrados_a_procesar": count,
            "proceso_id": proceso_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@comentarios_necesidades_final_bp.route('/progreso/<proceso_id>', methods=['GET'])
def obtener_estado_proceso(proceso_id):
    estado = ProcesoNecesidadesEstado.query.get(proceso_id)
    if not estado:
        return jsonify({"error": "Proceso no encontrado"}), 404

    porcentaje = int((estado.done / estado.total) * 100) if estado.total else 0
    return jsonify({
        "total": estado.total,
        "procesados": estado.done,
        "porcentaje": porcentaje,
        "finalizado": estado.finish
    })

@comentarios_necesidades_final_bp.route('/comentarios_resultado/<int:user_id>', methods=['GET'])
def descargar_resultado_para_usuario(user_id):
    """
    Descarga un archivo Excel con los comentarios marcados como necesidades
    y su tópico asociado (solo para un usuario específico).
    """
    try:
        stmt = (
            db.session.query(
                ComentarioNecesidad.id_unico,
                ComentarioNecesidad.fecha,
                ComentarioNecesidad.api_es,
                ComentarioNecesidad.comentario,
                ComentarioNecesidad.canal,
                ComentarioNecesidad.sentimiento,
                ComentarioNecesidad.topico.label('topico_original'),
                TopicoNecesidad.nombre_topico.label('topico_necesidad')
            )
            .join(TopicoNecesidad, ComentarioNecesidad.topico_necesidad_id == TopicoNecesidad.id)
            .filter(ComentarioNecesidad.user_id == user_id)
            .statement
        )

        result = db.session.execute(stmt).mappings().all()

        if not result:
            return jsonify({"error": "No hay comentarios procesados para este usuario"}), 404

        df = pd.DataFrame(result)

        output = BytesIO()
        df.to_excel(output, index=False, sheet_name='Necesidades')
        output.seek(0)

        return Response(
            output.read(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename=comentarios_usuario_{user_id}.xlsx'}
        )

    except Exception as e:
        logger.error(f"Error al descargar comentarios necesidades para user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500

@comentarios_necesidades_final_bp.route('/comentarios_necesidades_borrar/<int:user_id>', methods=['DELETE'])
def borrar_comentarios_usuario(user_id):
    ComentarioNecesidad.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"message": f"Comentarios eliminados para user_id {user_id}"}), 200

@comentarios_necesidades_final_bp.route('/topicos_necesidad_final', methods=['GET'])
def listar_topicos_necesidad():
    """
    Devuelve en JSON todos los registros de TopicoNecesidad.
    """
    try:
        topicos = TopicoNecesidad.query.order_by(TopicoNecesidad.id).all()
        resultado = [
            {"id": t.id, "nombre_topico": t.nombre_topico}
            for t in topicos
        ]
        return jsonify(resultado), 200
    except Exception as e:
        logger.error(f"Error al listar tópicos de necesidad: {e}")
        return jsonify({"error": str(e)}), 500
    
@comentarios_necesidades_final_bp.route('/topicos_necesidad_final', methods=['POST'])
def crear_topico_necesidad():
    """
    Crea un nuevo tópico de necesidad.
    JSON esperado: { "nombre_topico": "NOMBRE" }
    """
    try:
        data = request.get_json(force=True)
        nombre = data.get('nombre_topico', '').strip()
        if not nombre:
            return jsonify({'error': 'El campo nombre_topico es requerido.'}), 400
        existe = TopicoNecesidad.query.filter_by(nombre_topico=nombre).first()
        if existe:
            return jsonify({'error': 'El tópico ya existe.'}), 409
        top = TopicoNecesidad(nombre_topico=nombre)
        db.session.add(top)
        db.session.commit()
        return jsonify({'id': top.id, 'nombre_topico': top.nombre_topico}), 201
    except Exception as e:
        logger.error(f"Error al crear tópico: {e}")
        return jsonify({'error': str(e)}), 500

@comentarios_necesidades_final_bp.route('/topicos_necesidad_final/<int:id>', methods=['DELETE'])
def eliminar_topico_necesidad(id):
    """
    Elimina un tópico de necesidad por su ID.
    """
    try:
        top = TopicoNecesidad.query.get(id)
        if not top:
            return jsonify({'error': 'Tópico no encontrado.'}), 404
        db.session.delete(top)
        db.session.commit()
        return jsonify({'message': 'Tópico eliminado correctamente.'}), 200
    except Exception as e:
        logger.error(f"Error al eliminar tópico: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    

@comentarios_necesidades_final_bp.route('/topicos_necesidad_final', methods=['DELETE'])
def eliminar_todos_topicos():
    """
    Elimina todos los tópicos de necesidad.
    """
    try:
        deleted = db.session.query(TopicoNecesidad).delete()
        db.session.commit()
        return jsonify({'message': f'Se eliminaron {deleted} tópicos.'}), 200
    except Exception as e:
        logger.error(f"Error al eliminar todos los tópicos: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@comentarios_necesidades_final_bp.route('/topicos_necesidad_final/bulk', methods=['POST'])
def crear_topicos_bulk():
    """
    Crea múltiples tópicos de necesidad.
    JSON esperado: { "topicos": ["NOMBRE1", "NOMBRE2", ...] }
    """
    try:
        data = request.get_json(force=True)
        names = data.get('topicos', [])
        if not isinstance(names, list) or not names:
            return jsonify({'error': 'El campo topicos debe ser una lista no vacía.'}), 400
        created = []
        for name in names:
            nombre = name.strip()
            if not nombre:
                continue
            if not TopicoNecesidad.query.filter_by(nombre_topico=nombre).first():
                top = TopicoNecesidad(nombre_topico=nombre)
                db.session.add(top)
                db.session.commit()
                created.append(nombre)
        return jsonify({'created': created}), 201
    except Exception as e:
        logger.error(f"Error al crear tópicos bulk: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error al eliminar tópico: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500