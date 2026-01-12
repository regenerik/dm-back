from database import db
from datetime import datetime
import hashlib
import uuid
import json
from logging_config import logger
from sqlalchemy.dialects.postgresql import JSON


class User(db.Model):
    dni = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.Integer)
    name = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    url_image = db.Column(db.String(255))
    admin = db.Column(db.Boolean)
    status = db.Column(db.Boolean, default=True) # Agrega esta línea

class Permitido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.Integer, db.ForeignKey('user.id'))


class Reporte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_url = db.Column(db.String(255), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    size = db.Column(db.Float, nullable=False)
    elapsed_time = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # revisar si .UTC va o si cambiamos a .utcnow

class TodosLosReportes(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Primary Key
    report_url = db.Column(db.String(255), unique=True, nullable=False)  # La URL del reporte
    title = db.Column(db.String(255), nullable=False)  # El título del reporte
    size_megabytes = db.Column(db.Float, nullable=True)  # El tamaño del reporte en megabytes, puede ser NULL si no está disponible
    created_at = db.Column(db.DateTime, nullable=True)  # La fecha de creación, puede ser NULL si no está disponible

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)

class SegundoSurvey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)

class TercerSurvey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)

class CuartoSurvey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)

class QuintoSurvey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)

class SextoSurvey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)


class TotalComents(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class AllApiesResumes(db.Model):
    __tablename__ = 'archivo_resumido'
    id = db.Column(db.Integer, primary_key=True)
    archivo_binario = db.Column(db.LargeBinary)

class AllCommentsWithEvaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo_binario = db.Column(db.LargeBinary)

class FilteredExperienceComments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo_binario = db.Column(db.LargeBinary)

class DailyCommentsWithEvaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo_binario = db.Column(db.LargeBinary)

# TABLAS PARA GUARDAR NECESIDADES>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

class TopicoNecesidad(db.Model):
    __tablename__ = 'topico_necesidad'
    id = db.Column(db.Integer, primary_key=True)
    nombre_topico = db.Column(db.String(255), unique=True, nullable=False)

class ComentarioNecesidad(db.Model):
    __tablename__ = 'comentario_necesidad'
    id = db.Column(db.Integer, primary_key=True)
    id_unico = db.Column(db.String(255), unique=True, nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    api_es = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text, nullable=False)
    canal = db.Column(db.String(50), nullable=False)
    sentimiento = db.Column(db.String(50), nullable=False)
    topico = db.Column(db.String(255), nullable=True)
    topico_necesidad_id = db.Column(db.Integer, db.ForeignKey('topico_necesidad.id'))
    topico_rel = db.relationship('TopicoNecesidad')
    user_id = db.Column(db.Integer, nullable=False) 

class ProcesoNecesidadesEstado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Integer, nullable=False)
    done = db.Column(db.Integer, default=0)
    finish = db.Column(db.Boolean, default=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

# TABLAS PARA GUARDAR REPORTES EN SQL>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>


class Usuarios_Por_Asignacion(db.Model):
    __tablename__ = 'usuarios_por_asignacion'

    id = db.Column(db.Integer, primary_key=True)
    id_asignacion    = db.Column(db.String(50),  nullable=True, default="")
    dni              = db.Column(db.String(20),  nullable=True, default="")
    nombre_completo  = db.Column(db.String(255), nullable=True, default="")
    rol_funcion      = db.Column(db.String(255), nullable=True, default="")
    id_pertenencia   = db.Column(db.String(50),  nullable=True, default="")
    pertenencia      = db.Column(db.String(255), nullable=True, default="")
    estatus_usuario  = db.Column(db.String(100), nullable=True, default="")
    fecha_suspension = db.Column(db.DateTime,   nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            'id': self.id,
            'id_asignacion': self.id_asignacion,
            'dni': self.dni,
            'nombre_completo': self.nombre_completo,
            'rol_funcion': self.rol_funcion,
            'id_pertenencia': self.id_pertenencia,
            'pertenencia': self.pertenencia,
            'estatus_usuario': self.estatus_usuario,
            'fecha_suspension': self.fecha_suspension.isoformat() if self.fecha_suspension else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<Usuarios_Por_Asignacion(id={self.id}, asignacion={self.id_asignacion})>"
    
class Usuarios_Sin_ID(db.Model):
    __tablename__ = 'usuarios_sin_id'

    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario            = db.Column(db.String(255), nullable=True, default="")
    dni                       = db.Column(db.String(20), nullable=True, default="")
    email                     = db.Column(db.String(255), nullable=True, default="")
    ultimo_inicio_sesion      = db.Column(db.DateTime, nullable=True)
    estatus_usuario           = db.Column(db.String(100), nullable=True, default="")
    ultimo_acceso             = db.Column(db.DateTime, nullable=True)
    fecha_ingreso             = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            'id': self.id,
            'nombre_usuario': self.nombre_usuario,
            'dni': self.dni,
            'email': self.email,
            'ultimo_inicio_sesion': self.ultimo_inicio_sesion.isoformat() if self.ultimo_inicio_sesion else None,
            'estatus_usuario': self.estatus_usuario,
            'ultimo_acceso': self.ultimo_acceso.isoformat() if self.ultimo_acceso else None,
            'fecha_ingreso': self.fecha_ingreso.isoformat() if self.fecha_ingreso else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<Usuarios_Sin_ID(id={self.id}, nombre_usuario={self.nombre_usuario})>"
    
class ValidaUsuarios(db.Model):
    __tablename__ = 'valida_usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo       = db.Column(db.String(255), nullable=True, default="")
    ciudad                = db.Column(db.String(100), nullable=True, default="")
    nivel_estudios        = db.Column(db.String(100), nullable=True, default="")
    fecha_nacimiento      = db.Column(db.DateTime, nullable=True)
    traslado_moto         = db.Column(db.String(10), nullable=True, default="")  # puede ser Sí / No
    traslado_bicicleta    = db.Column(db.String(10), nullable=True, default="")  # puede ser Sí / No
    anio_ingreso          = db.Column(db.String(10), nullable=True, default="")
    socio_serviclub       = db.Column(db.String(10), nullable=True, default="")  # puede ser Sí / No
    estatus_usuario       = db.Column(db.String(100), nullable=True, default="")
    dni                   = db.Column(db.String(20), nullable=True, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "nombre_completo": self.nombre_completo,
            "ciudad": self.ciudad,
            "nivel_estudios": self.nivel_estudios,
            "fecha_nacimiento": self.fecha_nacimiento.isoformat() if self.fecha_nacimiento else None,
            "traslado_moto": self.traslado_moto,
            "traslado_bicicleta": self.traslado_bicicleta,
            "anio_ingreso": self.anio_ingreso,
            "socio_serviclub": self.socio_serviclub,
            "estatus_usuario": self.estatus_usuario,
            "dni": self.dni,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<ValidaUsuarios(id={self.id}, nombre_completo={self.nombre_completo})>"
    
class DetalleApies(db.Model):
    __tablename__ = 'detalle_apies'

    id = db.Column(db.Integer, primary_key=True)
    apies              = db.Column(db.String(100), nullable=True, default="")
    apies_razon_social = db.Column(db.String(255), nullable=True, default="")
    cuadro             = db.Column(db.String(100), nullable=True, default="")
    numero_id_padre    = db.Column(db.String(100), nullable=True, default="")
    red                = db.Column(db.String(100), nullable=True, default="")
    region             = db.Column(db.String(100), nullable=True, default="")
    segmento           = db.Column(db.String(100), nullable=True, default="")
    zona               = db.Column(db.String(100), nullable=True, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "apies": self.apies,
            "apies_razon_social": self.apies_razon_social,
            "cuadro": self.cuadro,
            "numero_id_padre": self.numero_id_padre,
            "red": self.red,
            "region": self.region,
            "segmento": self.segmento,
            "zona": self.zona,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<DetalleApies(id={self.id}, apies={self.apies})>"
    
class AvanceCursada(db.Model):
    __tablename__ = 'avance_cursada'

    id = db.Column(db.Integer, primary_key=True)
    apies                    = db.Column(db.String(100), nullable=True, default="")
    apies_razon_social       = db.Column(db.String(255), nullable=True, default="")
    dni                      = db.Column(db.String(20), nullable=True, default="")
    nombre_completo_usuario  = db.Column(db.String(255), nullable=True, default="")
    rol_funcion              = db.Column(db.String(100), nullable=True, default="")
    estatus_usuario          = db.Column(db.String(100), nullable=True, default="")
    nombre_programa          = db.Column(db.String(255), nullable=True, default="")
    nombre_corto_curso       = db.Column(db.String(255), nullable=True, default="")
    estatus_curso            = db.Column(db.String(100), nullable=True, default="")
    fecha_fin_curso          = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "apies": self.apies,
            "apies_razon_social": self.apies_razon_social,
            "dni": self.dni,
            "nombre_completo_usuario": self.nombre_completo_usuario,
            "rol_funcion": self.rol_funcion,
            "estatus_usuario": self.estatus_usuario,
            "nombre_programa": self.nombre_programa,
            "nombre_corto_curso": self.nombre_corto_curso,
            "estatus_curso": self.estatus_curso,
            "fecha_fin_curso": self.fecha_fin_curso.isoformat() if self.fecha_fin_curso else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<AvanceCursada(id={self.id}, usuario={self.nombre_completo_usuario})>"
    
class CursadasAgrupadas(db.Model):
    __tablename__ = 'cursadas_agrupadas'

    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(20), nullable=False)
    id_curso = db.Column(db.String(100), nullable=False)
    estatus_finalizacion = db.Column(db.String(100), nullable=True, default="")
    fecha_finalizacion = db.Column(db.String(50), nullable=True, default="")
    id_concat = db.Column(db.String(120), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "dni": self.dni,
            "id_curso": self.id_curso,
            "estatus_finalizacion": self.estatus_finalizacion,
            "fecha_finalizacion": self.fecha_finalizacion,
            "id_concat": self.id_concat,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<CursosNoRetail2025(id={self.id}, id_concat={self.id_concat})>"

class DetallesDeCursos(db.Model):
    __tablename__ = 'detalles_de_cursos'

    id = db.Column(db.Integer, primary_key=True)
    nombre_curso           = db.Column(db.String(255), nullable=True, default="")
    id_curso               = db.Column(db.String(100), nullable=True, default="")
    negocio_solicitante    = db.Column(db.String(255), nullable=True, default="")
    horas_formacion        = db.Column(db.String(50), nullable=True, default="")
    modalidad              = db.Column(db.String(100), nullable=True, default="")
    resumen_curso          = db.Column(db.Text, nullable=True, default="")
    fecha_creacion         = db.Column(db.DateTime, nullable=True)
    visible_oculto         = db.Column(db.String(50), nullable=True, default="")
    capacidad_marco        = db.Column(db.String(100), nullable=True, default="")
    tematica               = db.Column(db.String(100), nullable=True, default="")
    impacto_negocio        = db.Column(db.String(255), nullable=True, default="")
    impacto_segmento       = db.Column(db.String(255), nullable=True, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "nombre_curso": self.nombre_curso,
            "id_curso": self.id_curso,
            "negocio_solicitante": self.negocio_solicitante,
            "horas_formacion": self.horas_formacion,
            "modalidad": self.modalidad,
            "resumen_curso": self.resumen_curso,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "visible_oculto": self.visible_oculto,
            "capacidad_marco": self.capacidad_marco,
            "tematica": self.tematica,
            "impacto_negocio": self.impacto_negocio,
            "impacto_segmento": self.impacto_segmento,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<DetallesDeCursos(id={self.id}, curso={self.nombre_curso})>"
    
class FormularioGestor(db.Model):
    __tablename__ = 'formulario_gestor'

    id = db.Column(db.Integer, primary_key=True)
    apies = db.Column(db.String(50), nullable=False)
    curso = db.Column(db.String(100), nullable=False)
    fecha_usuario = db.Column(db.Date, nullable=False)
    gestor = db.Column(db.String(100), nullable=False)
    duracion_horas = db.Column(db.Integer, nullable=False)
    objetivo = db.Column(db.Text, nullable=True)
    contenido_desarrollado = db.Column(db.Text, nullable=True)
    ausentes = db.Column(db.Integer, nullable=False)
    presentes = db.Column(db.Integer, nullable=False)
    resultados_logros = db.Column(db.Text, nullable=True)
    compromiso = db.Column(db.String(20), nullable=True)
    participacion_actividades = db.Column(db.String(20), nullable=True)
    concentracion = db.Column(db.String(20), nullable=True)
    cansancio = db.Column(db.String(20), nullable=True)
    interes_temas = db.Column(db.String(20), nullable=True)
    recomendaciones = db.Column(db.Text, nullable=True)
    otros_aspectos = db.Column(db.Text, nullable=True)
    jornada = db.Column(db.String(20), nullable=False)
    dotacion_real_estacion = db.Column(db.Integer, nullable=True)
    dotacion_en_campus = db.Column(db.Integer, nullable=True)
    dotacion_dni_faltantes = db.Column(db.Text, nullable=True)
    firma_file = db.Column(db.LargeBinary, nullable=True)
    nombre_firma = db.Column(db.String(100), nullable=True)
    email_gestor = db.Column(db.String(120), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def serialize(self):
        return {
            "id": self.id,
            "apies": self.apies,
            "curso": self.curso,
            "fecha_usuario": self.fecha_usuario.isoformat(),
            "gestor": self.gestor,
            "duracion_horas": self.duracion_horas,
            "objetivo": self.objetivo,
            "contenido_desarrollado": self.contenido_desarrollado,
            "ausentes": self.ausentes,
            "presentes": self.presentes,
            "resultados_logros": self.resultados_logros,
            "compromiso": self.compromiso,
            "participacion_actividades": self.participacion_actividades,
            "concentracion": self.concentracion,
            "cansancio": self.cansancio,
            "interes_temas": self.interes_temas,
            "recomendaciones": self.recomendaciones,
            "otros_aspectos": self.otros_aspectos,
            "jornada": self.jornada,
            "dotacion_real_estacion": self.dotacion_real_estacion,
            "dotacion_dni_faltantes": self.dotacion_dni_faltantes,
            "nombre_firma": self.nombre_firma,
            "email_gestor": self.email_gestor,
            "creado_en": self.creado_en.isoformat()
        }
    
class QuintoSurveySql(db.Model):
    __tablename__ = 'quinto_survey_sql'

    id = db.Column(db.Integer, primary_key=True)
    id_concat = db.Column(db.String(255), unique=True, nullable=False)
    date_created = db.Column(db.DateTime, nullable=True)
    gestores_aprendizaje = db.Column('GestoresAprendizaje', db.String(255), nullable=True, default="")
    curso = db.Column('Curso', db.String(255), nullable=True, default="")
    recomendacion_colega = db.Column('¿Qué tan probable es que usted le recomiende este curso a un colega?', db.String(255), nullable=True, default="")
    desempeno_instructor = db.Column('De acuerdo a tu experiencia del día de hoy, ¿Cómo calificarías el desempeño del instructor?', db.String(255), nullable=True, default="")
    calificacion_general = db.Column('En líneas generales, ¿cómo calificarías a este curso/ actividad?', db.String(255), nullable=True, default="")
    duracion_curso = db.Column('Pensando en los contenidos vistos, considerás que la duración del curso fue:', db.String(255), nullable=True, default="")
    info_recibida = db.Column('En cuanto a la información recibida, considerás que es:', db.String(255), nullable=True, default="")
    claridad_temas = db.Column('Los temas fueron tratados con claridad', db.String(255), nullable=True, default="")
    utilidad_contenido = db.Column('El contenido visto es de utilidad para mi tarea', db.String(255), nullable=True, default="")
    ayudas_practica = db.Column('Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso', db.String(255), nullable=True, default="")
    actividades_refuerzo = db.Column('Las actividades propuestas refuerzan lo aprendido', db.String(255), nullable=True, default="")
    experiencia_aprendizaje = db.Column('En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:', db.String(255), nullable=True, default="")
    sugerencias = db.Column('Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso', db.Text, nullable=True, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            'id': self.id,
            'id_concat': self.id_concat,
            'date_created': self.date_created.isoformat() if self.date_created else None,
            'gestores_aprendizaje': self.gestores_aprendizaje,
            'curso': self.curso,
            'recomendacion_colega': self.recomendacion_colega,
            'desempeno_instructor': self.desempeno_instructor,
            'calificacion_general': self.calificacion_general,
            'duracion_curso': self.duracion_curso,
            'info_recibida': self.info_recibida,
            'claridad_temas': self.claridad_temas,
            'utilidad_contenido': self.utilidad_contenido,
            'ayudas_practica': self.ayudas_practica,
            'actividades_refuerzo': self.actividades_refuerzo,
            'experiencia_aprendizaje': self.experiencia_aprendizaje,
            'sugerencias': self.sugerencias,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<QuintoSurveySql(id_concat={self.id_concat}, curso={self.curso})>"
    
class CuartoSurveySql(db.Model):
    __tablename__ = 'cuarto_survey_sql'

    id         = db.Column(db.Integer, primary_key=True)
    id_code    = db.Column('ID_CODE', db.String(255), nullable=True)
    id_concat  = db.Column(db.String(512), unique=True, nullable=False)

    recomendacion_colega    = db.Column('¿Qué tan probable es que usted le recomiende este curso a un colega?', db.String(255), nullable=True, default="")
    calificacion_general    = db.Column('En líneas generales, ¿cómo calificarías a este curso/ actividad?', db.String(255), nullable=True, default="")
    duracion_curso          = db.Column('Pensando en los contenidos vistos, considerás que la duración del curso fue:', db.String(255), nullable=True, default="")
    info_recibida           = db.Column('En cuanto a la información recibida, considerás que es:', db.String(255), nullable=True, default="")
    claridad_temas          = db.Column('Los temas fueron tratados con claridad', db.String(255), nullable=True, default="")
    utilidad_contenido      = db.Column('El contenido visto es de utilidad para mi tarea', db.String(255), nullable=True, default="")
    ayudas_practica         = db.Column('Las explicaciones, guías, videos, etc. ayudan a poner en práctica lo visto en el curso', db.String(255), nullable=True, default="")
    actividades_refuerzo    = db.Column('Las actividades propuestas refuerzan lo aprendido', db.String(255), nullable=True, default="")
    problema_campus         = db.Column('Al momento de realizar el curso, ¿tuviste algún problema con el Campus de aprendizaje?', db.String(255), nullable=True, default="")
    detalle_problema        = db.Column('Si tuviste algún problema, por favor, contanos que sucedió', db.Text, nullable=True, default="")
    experiencia_aprendizaje = db.Column('En líneas generales dirías que tu experiencia de aprendizaje con este curso fue:', db.String(255), nullable=True, default="")
    sugerencias             = db.Column('Para finalizar dejamos este espacio para que nos dejes tus sugerencias o comentarios relacionados a este curso', db.Text, nullable=True, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            'id': self.id,
            'id_code': self.id_code,
            'id_concat': self.id_concat,
            'recomendacion_colega': self.recomendacion_colega,
            'calificacion_general': self.calificacion_general,
            'duracion_curso': self.duracion_curso,
            'info_recibida': self.info_recibida,
            'claridad_temas': self.claridad_temas,
            'utilidad_contenido': self.utilidad_contenido,
            'ayudas_practica': self.ayudas_practica,
            'actividades_refuerzo': self.actividades_refuerzo,
            'problema_campus': self.problema_campus,
            'detalle_problema': self.detalle_problema,
            'experiencia_aprendizaje': self.experiencia_aprendizaje,
            'sugerencias': self.sugerencias,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<CuartoSurveySql(id_concat={self.id_concat})>"
    

# TABLAS EXPERIENCIA DE CLIENTE

class Comentarios2023(db.Model):
    __tablename__ = 'comentarios_encuesta_2023'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=True)
    apies = db.Column(db.String(255), nullable=True, default="")
    comentario = db.Column(db.Text, nullable=True, default="")
    canal = db.Column(db.String(255), nullable=True, default="")
    topico = db.Column(db.String(255), nullable=True, default="")
    sentiment = db.Column(db.String(50), nullable=True, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            'id': self.id,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'apies': self.apies,
            'comentario': self.comentario,
            'canal': self.canal,
            'topico': self.topico,
            'sentiment': self.sentiment,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<ComentarioEncuesta id={self.id} apies={self.apies}>"
    
class Comentarios2024(db.Model):
    __tablename__ = 'comentarios_encuesta_2024'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=True)
    apies = db.Column(db.String(255), nullable=True, default="")
    comentario = db.Column(db.Text, nullable=True, default="")
    canal = db.Column(db.String(255), nullable=True, default="")
    topico = db.Column(db.String(255), nullable=True, default="")
    sentiment = db.Column(db.String(50), nullable=True, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            'id': self.id,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'apies': self.apies,
            'comentario': self.comentario,
            'canal': self.canal,
            'topico': self.topico,
            'sentiment': self.sentiment,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<ComentarioEncuesta id={self.id} apies={self.apies}>"

class Comentarios2025(db.Model):
    __tablename__ = 'comentarios_encuesta_2025'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=True)
    apies = db.Column(db.String(255), nullable=True, default="")
    comentario = db.Column(db.Text, nullable=True, default="")
    canal = db.Column(db.String(255), nullable=True, default="")
    topico = db.Column(db.String(255), nullable=True, default="")
    sentiment = db.Column(db.String(50), nullable=True, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hash_id = db.Column(db.String(64), unique=True, index=True)

    def serialize(self):
        return {
            'id': self.id,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'apies': self.apies,
            'comentario': self.comentario,
            'canal': self.canal,
            'topico': self.topico,
            'sentiment': self.sentiment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'hash_id': self.hash_id
        }

    def __repr__(self):
        return f"<ComentarioEncuesta id={self.id} apies={self.apies}>"

    @staticmethod
    def generar_hash(fecha, apies, comentario, canal, topico, sentiment): # ¡Nuevos parámetros!
        """
        Método auxiliar para generar hash_id a partir de todos los campos clave
        que definen un comentario único.
        Asegura que la representación de la fecha sea consistente para el hash.
        """
        # Convertir fecha a un string consistente para hashing
        fecha_str = fecha.isoformat() if isinstance(fecha, datetime) else str(fecha)
        
        # Asegurarse de que todos los componentes sean strings antes de concatenar y codificar
        # Incluimos topico y sentiment aquí
        data_string = f"{fecha_str}|{str(apies)}|{str(comentario)}|{str(canal)}|{str(topico)}|{str(sentiment)}"
        
        return hashlib.md5(data_string.encode('utf-8')).hexdigest() # Puedes seguir usando MD5 o SHA256 (64 caracteres)
    
class BaseLoopEstaciones(db.Model):
    __tablename__ = 'base_loop_estaciones'

    uid = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id = db.Column('Id', db.String(255))
    apies = db.Column('Apies', db.String(255))
    inscripcion = db.Column('Inscripcion', db.String(255))
    operador = db.Column('Operador', db.String(255))
    estado_boca = db.Column('Estado Boca', db.String(255))
    bandera = db.Column('Bandera', db.String(255))
    direccion_admin = db.Column('Direccion Admin.', db.String(255))
    localidad_geo = db.Column('Localidad Geo.', db.String(255))
    provincia_geo = db.Column('Provincia Geo.', db.String(255))
    region_geo = db.Column('Region Geo.', db.String(255))
    zona_com_geo = db.Column('Zona Com. Geo.', db.String(255))
    tipo_establecimiento = db.Column('Tipo Establecimiento', db.String(255))
    tipo_operador = db.Column('Tipo Operador', db.String(255))
    tipo_despacho = db.Column('Tipo Despacho', db.String(255))
    tipo_ubicacion = db.Column('Tipo Ubicacion', db.String(255))
    region_admin = db.Column('Region Admin.', db.String(255))
    zona_com_admin = db.Column('Zona Com. Admin.', db.String(255))
    rrcc = db.Column('RRCC', db.String(255))
    opera_aca = db.Column('Opera ACA', db.String(255))
    bandera_aca = db.Column('Bandera ACA', db.String(255))
    contrato_gn = db.Column('Contrato GN', db.String(255))
    tipo_operacion = db.Column('Tipo Operacion', db.String(255))
    inicio_actividad_cuenta = db.Column('Inicio actividad cuenta', db.String(255))
    tipo_imagen = db.Column('Tipo Imagen', db.String(255))
    tipo_tienda = db.Column('Tipo Tienda', db.String(255))
    tipo_lubricentro = db.Column('Tipo Lubricentro', db.String(255))
    serviclub = db.Column('Serviclub', db.String(255))
    ypf_ruta = db.Column('YPF Ruta', db.String(255))
    azul_32 = db.Column('Azul 32', db.String(255))
    punto_eléctrico = db.Column('Punto Eléctrico', db.String(255))
    cant_imagenes = db.Column('Cant. Imagenes', db.String(255))
    cant_surtidores = db.Column('Cant. Surtidores', db.String(255))
    cant_tanques = db.Column('Cant. Tanques', db.String(255))
    cant_bombas = db.Column('Cant. Bombas', db.String(255))
    cant_conectores = db.Column('Cant. Conectores', db.String(255))
    vol_prom_total_n2_m3 = db.Column('Vol. prom. total N2 (m3)', db.String(255))
    vol_prom_total_n3_m3 = db.Column('Vol. prom. total N3 (m3)', db.String(255))
    vol_prom_total_nafta_m3 = db.Column('Vol. prom. total Nafta (m3)', db.String(255))
    vol_prom_total_go_m3 = db.Column('Vol. prom. total GO (m3)', db.String(255))
    vol_prom_total_go2_m3 = db.Column('Vol. prom. total GO2 (m3)', db.String(255))
    vol_prom_total_go3_m3 = db.Column('Vol. prom. total GO3 (m3)', db.String(255))
    volumen_promedio_liquidos_m3 = db.Column('Volumen Promedio Liquidos (m3)', db.String(255))
    vol_prom_gnc_m3 = db.Column('Vol. prom. GNC (m3)', db.String(255))
    volumen_promedio_lubricantes_m3 = db.Column('Volumen Promedio Lubricantes (m3)', db.String(255))
    cantidad_cambios_de_lubricantes = db.Column('Cantidad Cambios de Lubricantes', db.String(255))
    facturacion_bruta_promedio_tienda_ars = db.Column('Facturacion Bruta Promedio Tienda (ARS)', db.String(255))
    despacho_liq_prom_n2 = db.Column('Despacho_Liq_Prom_N2', db.String(255))
    despacho_liq_prom_n3 = db.Column('Despacho_Liq_Prom_N3', db.String(255))
    despacho_liq_prom_nafta = db.Column('Despacho_Liq_Prom_Nafta', db.String(255))
    despacho_liq_prom_go2 = db.Column('Despacho_Liq_Prom_GO2', db.String(255))
    despacho_liq_prom_go3 = db.Column('Despacho_Liq_Prom_GO3', db.String(255))
    despacho_liq_prom_gasoil = db.Column('Despacho_Liq_Prom_Gasoil', db.String(255))
    despacho_liq_prom_total = db.Column('Despacho_Liq_Prom_Total', db.String(255))
    despacho_cnt_prom_n3 = db.Column('Despacho_Cnt_Prom_N3', db.String(255))
    despacho_cnt_prom_nafta = db.Column('Despacho_Cnt_Prom_Nafta', db.String(255))
    despacho_cnt_prom_go2 = db.Column('Despacho_Cnt_Prom_GO2', db.String(255))
    despacho_cnt_prom_go3 = db.Column('Despacho_Cnt_Prom_GO3', db.String(255))
    despacho_cnt_prom_gasoil = db.Column('Despacho_Cnt_Prom_Gasoil', db.String(255))
    despacho_cnt_prom_total = db.Column('Despacho_Cnt_Prom_Total', db.String(255))
    despacho_vol_prom_n2 = db.Column('Despacho_Vol_Prom_N2', db.String(255))
    despacho_vol_prom_n3 = db.Column('Despacho_Vol_Prom_N3', db.String(255))
    despacho_vol_prom_nafta = db.Column('Despacho_Vol_Prom_Nafta', db.String(255))
    despacho_vol_prom_go2 = db.Column('Despacho_Vol_Prom_GO2', db.String(255))
    despacho_vol_prom_go3 = db.Column('Despacho_Vol_Prom_GO3', db.String(255))
    despacho_vol_prom_gasoil = db.Column('Despacho_Vol_Prom_Gasoil', db.String(255))
    despacho_vol_prom_total = db.Column('Despacho_Vol_Prom_Total', db.String(255))
    ypf_ruta_credito_vol_prom_n2 = db.Column('YPF Ruta Credito_Vol_Prom_N2', db.String(255))
    ypf_ruta_credito_vol_prom_n3 = db.Column('YPF Ruta Credito_Vol_Prom_N3', db.String(255))
    ypf_ruta_credito_vol_prom_nafta = db.Column('YPF Ruta Credito_Vol_Prom_Nafta', db.String(255))
    ypf_ruta_credito_vol_prom_go2 = db.Column('YPF Ruta Credito_Vol_Prom_GO2', db.String(255))
    ypf_ruta_credito_vol_prom_go3 = db.Column('YPF Ruta Credito_Vol_Prom_GO3', db.String(255))
    ypf_ruta_credito_vol_prom_gasoil = db.Column('YPF Ruta Credito_Vol_Prom_Gasoil', db.String(255))
    ypf_ruta_credito_vol_prom_total = db.Column('YPF Ruta Credito_Vol_Prom_Total', db.String(255))
    ypf_ruta_contado_vol_prom_n2 = db.Column('YPF Ruta Contado_Vol_Prom_N2', db.String(255))
    ypf_ruta_contado_vol_prom_n3 = db.Column('YPF Ruta Contado_Vol_Prom_N3', db.String(255))
    ypf_ruta_contado_vol_prom_nafta = db.Column('YPF Ruta Contado_Vol_Prom_Nafta', db.String(255))
    ypf_ruta_contado_vol_prom_go2 = db.Column('YPF Ruta Contado_Vol_Prom_GO2', db.String(255))
    ypf_ruta_contado_vol_prom_go3 = db.Column('YPF Ruta Contado_Vol_Prom_GO3', db.String(255))
    ypf_ruta_contado_vol_prom_gasoil = db.Column('YPF Ruta Contado_Vol_Prom_Gasoil', db.String(255))
    ypf_ruta_contado_vol_prom_total = db.Column('YPF Ruta Contado_Vol_Prom_Total', db.String(255))
    serviclub_penetracion_por_n2 = db.Column('Serviclub_Penetracion_Por_N2', db.String(255))
    serviclub_penetracion_por_n3 = db.Column('Serviclub_Penetracion_Por_N3', db.String(255))
    serviclub_penetracion_por_nafta = db.Column('Serviclub_Penetracion_Por_Nafta', db.String(255))
    serviclub_penetracion_por_go2 = db.Column('Serviclub_Penetracion_Por_GO2', db.String(255))
    serviclub_penetracion_por_go3 = db.Column('Serviclub_Penetracion_Por_GO3', db.String(255))
    serviclub_penetracion_por_gasoil = db.Column('Serviclub_Penetracion_Por_Gasoil', db.String(255))
    serviclub_penetracion_por_total = db.Column('Serviclub_Penetracion_Por_Total', db.String(255))
    serviclub_vol_base_n2 = db.Column('Serviclub_Vol_Base_N2', db.String(255))
    serviclub_vol_base_n3 = db.Column('Serviclub_Vol_Base_N3', db.String(255))
    serviclub_vol_base_nafta = db.Column('Serviclub_Vol_Base_Nafta', db.String(255))
    serviclub_vol_base_go2 = db.Column('Serviclub_Vol_Base_GO2', db.String(255))
    serviclub_vol_base_go3 = db.Column('Serviclub_Vol_Base_GO3', db.String(255))
    serviclub_vol_base_gasoil = db.Column('Serviclub_Vol_Base_Gasoil', db.String(255))
    serviclub_vol_base_total = db.Column('Serviclub_Vol_Base_Total', db.String(255))
    dotacion_actual_total = db.Column('Dotación Actual_Total', db.String(255))
    dotacion_actual_jefes_de_estacion = db.Column('Dotación Actual_Jefes de Estación', db.String(255))
    dotacion_actual_jefes_trainee = db.Column('Dotación Actual_Jefes Trainee', db.String(255))
    dotacion_actual_responsables_de_turno = db.Column('Dotación Actual_Responsables de Turno', db.String(255))
    dotacion_actual_vendedor_dual = db.Column('Dotación Actual_Vendedor Dual', db.String(255))
    dotacion_actual_vendedor_sr = db.Column('Dotación Actual_Vendedor SR', db.String(255))
    dotacion_actual_lubriexperto = db.Column('Dotación Actual_Lubriexperto', db.String(255))
    dotacion_actual_lubriplaya = db.Column('Dotación Actual_Lubriplaya', db.String(255))
    descripcion_tramo_1 = db.Column('Descripción Tramo 1', db.String(255))
    porcentaje_tramo_1 = db.Column('Porcentaje Tramo 1', db.String(255))
    descripcion_tramo_2 = db.Column('Descripción Tramo 2', db.String(255))
    porcentaje_tramo_2 = db.Column('Porcentaje Tramo 2', db.String(255))
    cuit = db.Column('CUIT', db.String(255))
    red_propia = db.Column('Red Propia', db.String(255))
    zona_exclusion = db.Column('Zona Exclusión', db.String(255))
    nivel_socio_economico = db.Column('Nivel Socio Económico', db.String(255))
    densidad_poblacional_hab_por_km2 = db.Column('Densidad Poblacional (Hab/km2)', db.String(255))
    latitud = db.Column('Latitud', db.String(255))
    longitud = db.Column('Longitud', db.String(255))

    def serialize(self):
        data = {}
        for col in self.__table__.columns:
            # Convierte el nombre de la columna DB a un formato de atributo Python (snake_case)
            # Ej: 'Id' -> 'id', 'Direccion Admin.' -> 'direccion_admin'
            attr_name = col.name.replace(" ", "_").replace(".", "").lower()

            # Caso especial para 'uid' (siempre debe ser 'uid')
            if col.name == 'uid':
                attr_name = 'uid'
            
            # Intenta obtener el valor del atributo usando el nombre del atributo Python
            if hasattr(self, attr_name):
                data[col.name] = getattr(self, attr_name)
            else:
                # Si el mapeo automático falla (ej. por alguna columna con un nombre muy particular),
                # intenta usar el nombre de la columna de la DB directamente como atributo (menos común)
                # O puedes decidir no incluirlo o asignar None
                if hasattr(self, col.name):
                    data[col.name] = getattr(self, col.name)
                else:
                    # Si no se encuentra el atributo por ninguna convención, se asigna None
                    data[col.name] = None 
        return data

    def __repr__(self):
        # Asegúrate de usar self.id (el atributo Python) aquí.
        return f"<BaseLoopEstaciones id={self.id}>"
    
class FichasGoogleCompetencia(db.Model):
    __tablename__ = 'fichas_google_competencia'

    id = db.Column(db.Integer, primary_key=True)
    id_loop = db.Column('idLoop', db.String(255), nullable=True)
    total_review_count = db.Column('totalReviewCount', db.String(255), nullable=True)
    average_rating = db.Column('averageRating', db.String(255), nullable=True)
    hash_id = db.Column(db.String(64), unique=True, index=True)

    @staticmethod
    def generar_hash(id_loop, total_review_count, average_rating):
        texto = f"{id_loop}|{total_review_count}|{average_rating}"
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

    def serialize(self):
        return {
            'id': self.id,
            'id_loop': self.id_loop,
            'total_review_count': self.total_review_count,
            'average_rating': self.average_rating,
            'hash_id': self.hash_id
        }

    def __repr__(self):
        return f"<FichasGoogleCompetencia id={self.id} id_loop={self.id_loop}>"
    
class FichasGoogle(db.Model):
    __tablename__ = 'fichas_google'

    id = db.Column(db.Integer, primary_key=True)
    store_code = db.Column('Store Code', db.String(255), nullable=True)
    cantidad_de_calificaciones = db.Column('Cantidad de calificaciones', db.String(255), nullable=True)
    start_rating = db.Column('Star Rating', db.String(255), nullable=True)
    hash_id = db.Column(db.String(64), unique=True, index=True)

    @staticmethod
    def generar_hash(store_code, cantidad_de_calificaciones, start_rating):
        texto = f"{store_code}|{cantidad_de_calificaciones}|{start_rating}"
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

    def serialize(self):
        return {
            'id': self.id,
            'store_code': self.store_code,
            'cantidad_de_calificaciones': self.cantidad_de_calificaciones,
            'start_rating': self.start_rating,
            'hash_id': self.hash_id
        }

    def __repr__(self):
        return f"<FichasGoogle id={self.id} store_code={self.store_code}>"
    
class SalesForce(db.Model):
    __tablename__ = 'salesforce'

    id = db.Column(db.Integer, primary_key=True)
    estacion_servicio_zona = db.Column('Estacion de Servicio: Zona', db.String(255))
    numero_de_caso = db.Column('Número del caso', db.String(255))
    estado = db.Column('Estado', db.String(255))
    tipificacion_caso = db.Column('Tipificación Caso', db.String(255))
    asunto = db.Column('Asunto', db.String(255))
    fecha_apertura = db.Column('Fecha/Hora de apertura', db.String(255))
    cantidad_reclamos = db.Column('Cantidad de Reclamos', db.String(255))
    defensa_consumidor = db.Column('Defensa al Consumidor', db.String(255))
    ggrr_cola_asignado = db.Column('GGRR/COLA Asignado', db.String(255))
    propietario_nombre = db.Column('Propietario del caso: Nombre completo', db.String(255))
    descripcion = db.Column('Descripción', db.Text)
    contacto_nombre = db.Column('Nombre del contacto: Nombre completo', db.String(255))
    comentarios = db.Column('Comentarios', db.Text)
    razon_social = db.Column('Estacion de Servicio: Razón Social', db.String(255))
    red = db.Column('Estacion de Servicio: Red', db.String(255))
    regional = db.Column('Estacion de Servicio: Regional', db.String(255))
    hash_id = db.Column(db.String(64), unique=True, index=True)

    @staticmethod
    def generar_hash(*args):
        texto = '|'.join(str(arg).strip() for arg in args)
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

    def serialize(self):
        return {
            'id': self.id,
            'estacion_servicio_zona': self.estacion_servicio_zona,
            'numero_de_caso': self.numero_de_caso,
            'estado': self.estado,
            'tipificacion_caso': self.tipificacion_caso,
            'asunto': self.asunto,
            'fecha_apertura': self.fecha_apertura,
            'cantidad_reclamos': self.cantidad_reclamos,
            'defensa_consumidor': self.defensa_consumidor,
            'ggrr_cola_asignado': self.ggrr_cola_asignado,
            'propietario_nombre': self.propietario_nombre,
            'descripcion': self.descripcion,
            'contacto_nombre': self.contacto_nombre,
            'comentarios': self.comentarios,
            'razon_social': self.razon_social,
            'red': self.red,
            'regional': self.regional,
            'hash_id': self.hash_id
        }

    def __repr__(self):
        return f"<SalesForce id={self.id} numero_de_caso={self.numero_de_caso}>"
    
class ComentariosCompetencia(db.Model):
    __tablename__ = 'comentarios_competencia'

    id = db.Column(db.Integer, primary_key=True)
    id_original = db.Column('ID_ORIGINAL', db.String(255))
    fecha = db.Column('FECHA', db.String(255))
    id_loop = db.Column('IDLOOP', db.String(255))
    comentario = db.Column('COMENTARIO', db.Text)
    rating = db.Column('RATING', db.String(255))
    sentimiento = db.Column('SENTIMIENTO', db.String(255))
    topico = db.Column('TÓPICO', db.String(255))
    hash_id = db.Column(db.String(64), unique=True, index=True)

    @staticmethod
    def generar_hash(id_original, fecha, id_loop, comentario, rating, sentimiento, topico):
        texto = f"{id_original}|{fecha}|{id_loop}|{comentario}|{rating}|{sentimiento}|{topico}"
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

    def serialize(self):
        return {
            'id': self.id,
            'id_original': self.id_original,
            'fecha': self.fecha,
            'id_loop': self.id_loop,
            'comentario': self.comentario,
            'rating': self.rating,
            'sentimiento': self.sentimiento,
            'topico': self.topico,
            'hash_id': self.hash_id
        }

    def __repr__(self):
        return f"<ComentarioCompetencia id={self.id} id_loop={self.id_loop}>"
    


    # ---------------------------------------------------ACTUALIZAR DATOS DE THREAD---------------------------------------->

# CLASES PARA QUE FUNCIONE DATA MENTOR Y EL CHAT EN GENERAL >>  Y los modificables de la info extra que recibe la IA>>>>>

class FileDailyID(db.Model):
    __tablename__ = 'file_daily_id' 

    id = db.Column(db.Integer, primary_key=True)
    current_file_id = db.Column(db.String(255), unique=True, nullable=False)
    
    # ¡ESTA ES LA COLUMNA QUE NECESITAS AÑADIR!
    current_vector_store_id = db.Column(db.String(255), nullable=True) 
    
    # Buenas prácticas para timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        # Incluye el vector_store_id para mejor visibilidad en la representación
        return f"<FileDailyID id={self.id}, file_id={self.current_file_id}, vs_id={self.current_vector_store_id}>"

    # Puedes añadir un método serialize si necesitas exponer esta tabla vía API
    def serialize(self):
        return {
            'id': self.id,
            'current_file_id': self.current_file_id,
            'current_vector_store_id': self.current_vector_store_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class InstruccionesGenerales(db.Model):
    __tablename__ = 'instrucciones_generales'
    id = db.Column(db.Integer, primary_key=True)
    descripcion_general = db.Column(db.Text, nullable=False)
    instrucciones_especificas_para_ia = db.Column(db.Text, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<InstruccionesGenerales id={self.id}>"

class InstruccionesIndividuales(db.Model):
    __tablename__ = 'instrucciones_individuales'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False) # ej: "comentarios_2025", "base_loop_estaciones"
    descripcion = db.Column(db.Text, nullable=False)
    ejemplo_consulta = db.Column(db.Text, nullable=True) # Puede ser opcional
    relaciones_clave = db.Column(db.Text, nullable=True) # Guardaremos esto como un JSON string
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<InstruccionesIndividuales name='{self.name}'>"

    def get_relaciones_clave_dict(self):
        """Convierte el texto de relaciones_clave a un diccionario."""
        if self.relaciones_clave:
            try:
                return json.loads(self.relaciones_clave)
            except json.JSONDecodeError:
                logger.error(f"Error al decodificar relaciones_clave para {self.name}: {self.relaciones_clave}")
                return {}
        return {}

    def set_relaciones_clave_dict(self, data_dict):
        """Convierte un diccionario a texto para guardar en relaciones_clave."""
        self.relaciones_clave = json.dumps(data_dict, ensure_ascii=False)


class HistoryUserCourses(db.Model):
    __tablename__ = 'history_user_courses'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), db.ForeignKey('user.email'), nullable=False) # Clave foránea al email del usuario
    texto = db.Column(db.Text, nullable=False) # Usamos Text para texto largo
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HistoryUserCourses id={self.id}, titulo={self.titulo}, email={self.email}>"

    def serialize(self):
        return {
            'id': self.id,
            'titulo': self.titulo,
            'email': self.email,
            'texto': self.texto,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    


class ReportesDataMentor(db.Model):
    __tablename__ = 'reportes_data_mentor'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(255), nullable=False)
    user_dni = db.Column(db.String(50), nullable=True)
    question = db.Column(db.Text, nullable=False)
    failed_answer = db.Column(db.Text, nullable=False)
    sql_query = db.Column(db.Text, nullable=True)
    resolved = db.Column(db.Boolean, default=False)
    solution = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    modified_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "user": self.user,
            "user_dni": self.user_dni,
            "question": self.question,
            "failed_answer": self.failed_answer,
            "sql_query": self.sql_query,
            "resolved": self.resolved,
            "solution": self.solution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }
    

class Instructions(db.Model):
    __tablename__ = 'instructions'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(255), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "user": self.user,
            "instructions": self.instructions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    

# MODELOS PARA RECURSOS HUMANOS

class JobDescription(db.Model):
    __tablename__ = "job_description"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def serialize_min(self):
        return {"job_description_id": self.id, "titulo": self.titulo}


class Curriculos(db.Model):
    __tablename__ = "curriculos"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    file_name = db.Column(db.String(512), nullable=False)
    puntaje = db.Column(db.Float, nullable=True)
    comentario_ia = db.Column(db.Text, nullable=True)
    validez = db.Column(db.String(16), nullable=False)          # "VALIDO" | "INVALIDO"
    recomendado = db.Column(db.String(8), nullable=False)       # "SI" | "NO"
    formato_original = db.Column(db.String(16), nullable=False) # "pdf" | "docx" | "txt" | "doc"
    job_description_id = db.Column(db.Integer, db.ForeignKey("job_description.id"), nullable=False)

    job_description = db.relationship("JobDescription", backref=db.backref("curriculos", lazy=True))

    def serialize(self):
        return {
            "id": self.id,
            "email": self.email,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "file_name": self.file_name,
            "puntaje": self.puntaje,
            "comentario_ia": self.comentario_ia,
            "validez": self.validez,
            "recomendado": self.recomendado,
            "formato_original": self.formato_original,
            "job_description_id": self.job_description_id,
        }
    

class FormularioNecesidades(db.Model):
    __tablename__ = "formulario_necesidades"

    id = db.Column(db.Integer, primary_key=True)

    provincia = db.Column(db.String(100), nullable=False)
    localidad = db.Column(db.String(100), nullable=False)
    apies = db.Column(db.String(50), nullable=False)

    empleados_total = db.Column(db.Integer)

    gestor = db.Column(db.String(150))
    email_gestor = db.Column(db.String(150))

    experiencia_cliente = db.Column(db.String(10))
    liderazgo = db.Column(db.String(10))

    comentarios = db.Column(db.Text)

    seguridad_operativa = db.Column(JSON)

    # 👉 Respuesta del Assistant
    respuesta_ia = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "provincia": self.provincia,
            "localidad": self.localidad,
            "apies": self.apies,
            "empleados_total": self.empleados_total,
            "gestor": self.gestor,
            "email_gestor": self.email_gestor,
            "experiencia_cliente": self.experiencia_cliente,
            "liderazgo": self.liderazgo,
            "comentarios": self.comentarios,
            "seguridad_operativa": self.seguridad_operativa,
            "respuesta_ia": self.respuesta_ia,
            "created_at": self.created_at.isoformat()
        }


class DiagnosticoOperadores(db.Model):
    __tablename__ = "diagnostico_operadores"

    id = db.Column(db.Integer, primary_key=True)

    # -------------------
    # SECCIÓN 1 - DATOS GENERALES
    # -------------------
    provincia_localidad = db.Column(db.String(255), nullable=True, default="")
    apies               = db.Column(db.String(50), nullable=True, default="")
    tipo_estacion       = db.Column(db.String(50), nullable=True, default="")
    empleados_total     = db.Column(db.String(20), nullable=True, default="")

    playa_personal  = db.Column(db.String(20), nullable=True, default="")
    tienda_personal = db.Column(db.String(20), nullable=True, default="")
    boxes_personal  = db.Column(db.String(20), nullable=True, default="")

    anios_operacion      = db.Column(db.String(50), nullable=True, default="")
    capacitaciones_anio  = db.Column(db.String(50), nullable=True, default="")
    solo_aprendizaje     = db.Column(db.String(10), nullable=True, default="")
    detalle_otras_cap    = db.Column(db.Text, nullable=True, default="")
    gestor_asociado      = db.Column(db.String(150), nullable=True, default="")

    # -------------------
    # SECCIÓN 2 - SEGURIDAD Y CUMPLIMIENTO
    # -------------------
    nivel_seguridad          = db.Column(db.String(5), nullable=True, default="")
    preparacion_emergencia   = db.Column(db.String(5), nullable=True, default="")
    mejoras_seguridad        = db.Column(db.Text, nullable=True, default="")  # JSON array

    nivel_bromatologia       = db.Column(db.String(5), nullable=True, default="")
    mejoras_bromatologia     = db.Column(db.Text, nullable=True, default="")  # JSON array

    frecuencia_accidentes    = db.Column(db.String(50), nullable=True, default="")
    situaciones_accidentes   = db.Column(db.Text, nullable=True, default="")  # JSON array

    otro_seguridad_playa     = db.Column(db.String(255), nullable=True, default="")
    otro_seguridad_tienda    = db.Column(db.String(255), nullable=True, default="")
    otro_seguridad_boxes     = db.Column(db.String(255), nullable=True, default="")
    otro_bromatologia        = db.Column(db.String(255), nullable=True, default="")
    otro_accidentes          = db.Column(db.String(255), nullable=True, default="")

    # -------------------
    # SECCIÓN 3 - EXPERIENCIA DEL CLIENTE
    # -------------------
    nivel_pilares            = db.Column(db.String(5), nullable=True, default="")
    efectividad_comunicacion = db.Column(db.String(5), nullable=True, default="")
    actitud_empatica         = db.Column(db.String(5), nullable=True, default="")
    autonomia_reclamos       = db.Column(db.String(5), nullable=True, default="")
    adaptacion_estilo        = db.Column(db.String(5), nullable=True, default="")

    aspectos_atencion        = db.Column(db.Text, nullable=True, default="")  # JSON array
    otro_aspectos_atencion   = db.Column(db.String(255), nullable=True, default="")

    # -------------------
    # SECCIÓN 4 - CONOCIMIENTO Y RANKING
    # -------------------
    conoce_playa   = db.Column(db.String(5), nullable=True, default="")
    conoce_tienda  = db.Column(db.String(5), nullable=True, default="")
    conoce_boxes   = db.Column(db.String(5), nullable=True, default="")
    conoce_digital = db.Column(db.String(5), nullable=True, default="")

    ranking_temas  = db.Column(db.Text, nullable=True, default="")  # JSON array

    # -------------------
    # SECCIÓN 5 - GESTIÓN Y REPUTACIÓN
    # -------------------
    dominio_gestion        = db.Column(db.String(5), nullable=True, default="")
    capacidad_analisis     = db.Column(db.String(5), nullable=True, default="")
    uso_herramientas_dig   = db.Column(db.String(5), nullable=True, default="")

    ranking_desafios       = db.Column(db.Text, nullable=True, default="")  # JSON array

    # -------------------
    # SECCIÓN 6 - LIDERAZGO
    # -------------------
    liderazgo_efectivo      = db.Column(db.String(5), nullable=True, default="")
    frecuencia_feedback     = db.Column(db.String(50), nullable=True, default="")
    habilidades_org         = db.Column(db.String(5), nullable=True, default="")
    estilo_liderazgo        = db.Column(db.String(50), nullable=True, default="")

    ranking_fortalecer_lider = db.Column(db.Text, nullable=True, default="")  # JSON array

    interes_capacitacion    = db.Column(db.String(5), nullable=True, default="")
    temas_prioritarios      = db.Column(db.Text, nullable=True, default="")  # JSON array
    otro_tema_prioritario   = db.Column(db.String(255), nullable=True, default="")
    sugerencias_finales     = db.Column(db.Text, nullable=True, default="")

    # -------------------
    # CAMPO EXTRA PEDIDO
    # -------------------
    conclucion_final = db.Column(db.Text, nullable=True, default=None)
    respuesta_ia = db.Column(db.Text, nullable=True, default=None)
    # -------------------
    # METADATA
    # -------------------
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def serialize_simple(self):
        return {
            "id": self.id,
            "gestor_asociado": self.gestor_asociado,
            "apies": self.apies,
            "tipo_estacion": self.tipo_estacion,
            "conclucion_final": self.conclucion_final,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "respuesta_ia": self.respuesta_ia
        }
    def serialize(self):
        return {
            "id": self.id,

            # SECCIÓN 1
            "provincia_localidad": self.provincia_localidad,
            "apies": self.apies,
            "tipo_estacion": self.tipo_estacion,
            "empleados_total": self.empleados_total,
            "playa_personal": self.playa_personal,
            "tienda_personal": self.tienda_personal,
            "boxes_personal": self.boxes_personal,
            "anios_operacion": self.anios_operacion,
            "capacitaciones_anio": self.capacitaciones_anio,
            "solo_aprendizaje": self.solo_aprendizaje,
            "detalle_otras_cap": self.detalle_otras_cap,
            "gestor_asociado": self.gestor_asociado,

            # SECCIÓN 2
            "nivel_seguridad": self.nivel_seguridad,
            "preparacion_emergencia": self.preparacion_emergencia,
            "mejoras_seguridad": self.mejoras_seguridad,
            "nivel_bromatologia": self.nivel_bromatologia,
            "mejoras_bromatologia": self.mejoras_bromatologia,
            "frecuencia_accidentes": self.frecuencia_accidentes,
            "situaciones_accidentes": self.situaciones_accidentes,
            "otro_seguridad_playa": self.otro_seguridad_playa,
            "otro_seguridad_tienda": self.otro_seguridad_tienda,
            "otro_seguridad_boxes": self.otro_seguridad_boxes,
            "otro_bromatologia": self.otro_bromatologia,
            "otro_accidentes": self.otro_accidentes,

            # SECCIÓN 3
            "nivel_pilares": self.nivel_pilares,
            "efectividad_comunicacion": self.efectividad_comunicacion,
            "actitud_empatica": self.actitud_empatica,
            "autonomia_reclamos": self.autonomia_reclamos,
            "adaptacion_estilo": self.adaptacion_estilo,
            "aspectos_atencion": self.aspectos_atencion,
            "otro_aspectos_atencion": self.otro_aspectos_atencion,

            # SECCIÓN 4
            "conoce_playa": self.conoce_playa,
            "conoce_tienda": self.conoce_tienda,
            "conoce_boxes": self.conoce_boxes,
            "conoce_digital": self.conoce_digital,
            "ranking_temas": self.ranking_temas,

            # SECCIÓN 5
            "dominio_gestion": self.dominio_gestion,
            "capacidad_analisis": self.capacidad_analisis,
            "uso_herramientas_dig": self.uso_herramientas_dig,
            "ranking_desafios": self.ranking_desafios,

            # SECCIÓN 6
            "liderazgo_efectivo": self.liderazgo_efectivo,
            "frecuencia_feedback": self.frecuencia_feedback,
            "habilidades_org": self.habilidades_org,
            "estilo_liderazgo": self.estilo_liderazgo,
            "ranking_fortalecer_lider": self.ranking_fortalecer_lider,
            "interes_capacitacion": self.interes_capacitacion,
            "temas_prioritarios": self.temas_prioritarios,
            "otro_tema_prioritario": self.otro_tema_prioritario,
            "sugerencias_finales": self.sugerencias_finales,

            # EXTRA
            "conclucion_final": self.conclucion_final,
            "respuesta_ia": self.respuesta_ia,
            # METADATA
            "created_at": self.created_at.isoformat() if self.created_at else None
        }