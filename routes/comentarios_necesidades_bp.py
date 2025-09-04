from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required
from utils.comentarios_necesidades_final_utils import process_file_and_identify_needs
from logging_config import logger
from models import ComentarioNecesidad, TopicoNecesidad
from database import db
from io import BytesIO
import pandas as pd

comentarios_necesidades_bp = Blueprint('comentarios_necesidades_bp', __name__)

@comentarios_necesidades_bp.route('/comentarios_necesidades', methods=['POST'])
def iniciar_proceso_comentarios_necesidades():
    """
    Encola el proceso de identificación de necesidades.
    Recibe un .xlsx con columnas FECHA, APIES, COMENTARIO, CANAL, SENTIMIENTO,
    y opcionalmente parámetros de filtro: fecha_desde, fecha_hasta,
    sentimiento, apies, canal, topico, min_caracteres.
    Devuelve el count de filas que se van a procesar.
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
        fecha_desde    = request.form.get('fecha_desde')    # 'YYYY-MM-DD'
        fecha_hasta    = request.form.get('fecha_hasta')
        sentimiento    = request.form.get('sentimiento')    # 'positivo','negativo','invalido'
        apies          = request.form.get('apies')          # '123,456'
        canal          = request.form.get('canal')          # 'APP','otros'
        topico         = request.form.get('topico')         # 'EJEMPLO_TOPICO'
        min_caracteres = request.form.get('min_caracteres') # '50'

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
        count = len(df) - 1

        # 6) Preparamos un nuevo Excel con sólo los filtrados
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        filtered_content = buffer.getvalue()

        # 7) Encolamos el proceso con el Excel filtrado
        executor.submit(process_file_and_identify_needs, filtered_content)

        # 8) Respondemos con el count mientras el proceso sigue atrás
        return jsonify({
            "message": "Proceso iniciado. Recordá que la cantidad de comentarios filtrados no es la cantidad de registros de devolución, ya que todavia falta determinar cuales son necesidades.",
            "comentarios_filtrados_a_procesar": count
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@comentarios_necesidades_bp.route('/descargar_comentarios_necesidades', methods=['GET'])
def descargar_comentarios_necesidades():
    """
    Descarga un archivo Excel con todos los comentarios marcados como necesidades
    y su tópico asociado (nombre).
    """
    try:
        # Consulta SQLAlchemy
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
            .statement
        )
        result = db.session.execute(stmt).mappings().all()
        df = pd.DataFrame(result)

        output = BytesIO()
        df.to_excel(output, index=False, sheet_name='Necesidades')
        output.seek(0)
        return Response(
            output.read(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=comentarios_necesidades.xlsx'}
        )
    except Exception as e:
        logger.error(f"Error al descargar comentarios necesidades: {e}")
        return jsonify({"error": str(e)}), 500


@comentarios_necesidades_bp.route('/topicos_necesidad', methods=['GET'])
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
    

@comentarios_necesidades_bp.route('/topicos_necesidad', methods=['POST'])
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

@comentarios_necesidades_bp.route('/topicos_necesidad/<int:id>', methods=['DELETE'])
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
    

@comentarios_necesidades_bp.route('/topicos_necesidad', methods=['DELETE'])
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

@comentarios_necesidades_bp.route('/topicos_necesidad/bulk', methods=['POST'])
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