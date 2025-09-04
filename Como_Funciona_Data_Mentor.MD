Aquí tienes un resumen conciso de todo lo que hemos trabajado, consolidado en un único archivo Markdown para facilitar su digestión y preservar el formato.

Puedes copiar este contenido y guardarlo como un archivo `.md` (por ejemplo, `sistema_ia_repomatic_turbo_guia.md`).

```markdown
# Guía Completa del Sistema de IA para YPF - Repomatic Turbo

Este documento consolida la configuración y el código para el sistema de Asistente de IA de YPF, cubriendo la gestión de archivos de conocimiento, la configuración de la IA y el flujo de chat.

---

## 1. Estructura de Proyectos y Archivos

Asegúrate de que tus archivos estén organizados de manera similar:

```

tu\_proyecto/
├── app.py
├── your\_app\_name/
│   ├── **init**.py
│   ├── models.py
│   ├── routes/
│   │   ├── **init**.py
│   │   └── data\_mentor\_bp.py
│   └── utils/
│       ├── **init**.py
│       └── data\_mentor\_utils.py
├── initial\_data\_setup.py
└── logging\_config.py \# Archivo para tu configuración de logger

````

---

## 2. Modelos de Base de Datos (`your_app_name/models.py`)

Asegúrate de que estos modelos (y los de tus datos `Comentarios2025`, `BaseLoopEstaciones`, etc.) estén correctamente definidos y que tu base de datos haya sido migrada/creada.

```python
# your_app_name/models.py

import uuid
from datetime import datetime
import json # Asegúrate de importar json aquí

from flask_sqlalchemy import SQLAlchemy # O tu ORM, por ejemplo, SQLAlchemy


db = SQLAlchemy() # Inicializa tu objeto db aquí si usas Flask-SQLAlchemy

# --- Modelo para el ID del archivo diario de OpenAI ---
class FileDailyID(db.Model):
    __tablename__ = 'file_daily_id'
    id = db.Column(db.Integer, primary_key=True)
    current_file_id = db.Column(db.String, unique=True, nullable=False)
    usage_guide_text = db.Column(db.Text, nullable=True) # Para la guía de IA
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FileDailyID id={self.id}>"

# --- Modelos para las Instrucciones de la IA (configurables) ---
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
    name = db.Column(db.String(255), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    ejemplo_consulta = db.Column(db.Text, nullable=True)
    relaciones_clave = db.Column(db.Text, nullable=True) # Guardado como JSON string
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<InstruccionesIndividuales name='{self.name}'>"

    def get_relaciones_clave_dict(self):
        if self.relaciones_clave:
            try:
                return json.loads(self.relaciones_clave)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_relaciones_clave_dict(self, data_dict):
        self.relaciones_clave = json.dumps(data_dict, ensure_ascii=False)


# --- Tus modelos de datos (ejemplos, asegúrate de que todos tienen .serialize()) ---
# Nota: La columna 'id' en BaseLoopEstaciones se ha renombrado a 'uid' para evitar conflicto
# con el atributo 'id' si la columna DB es 'Id' mayúscula.
# El método serialize() debe estar adaptado para manejar los nombres de columnas de DB vs atributos Python.

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
        return {col.name: getattr(self, col.name) for col in self.__table__.columns} # Asume nombres de columnas coinciden con atributos

    @staticmethod
    def generar_hash(fecha, apies, comentario, canal):
        import hashlib
        texto = f"{fecha}|{apies}|{comentario}|{canal}"
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

class BaseLoopEstaciones(db.Model):
    __tablename__ = 'base_loop_estaciones'
    uid = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id = db.Column('Id', db.String(255)) # Columna 'Id' en DB, atributo 'id' en Python
    apies = db.Column('Apies', db.String(255))
    # ... otras columnas ...

    def serialize(self):
        data = {}
        for col in self.__table__.columns:
            attr_name = col.name.replace(" ", "_").replace(".", "").lower()
            if col.name == 'uid': attr_name = 'uid' # Caso específico para uid
            elif col.name == 'Id': attr_name = 'id' # Caso específico para Id
            
            if hasattr(self, attr_name):
                data[col.name] = getattr(self, attr_name)
            else:
                data[col.name] = None # O manejar el error según convenga
        return data

    def __repr__(self):
        return f"<BaseLoopEstaciones id={self.id}>" # Usar self.id (atributo Python)


# Incluir aquí el resto de tus modelos de datos como FichasGoogle, FichasGoogleCompetencia, etc.
# Asegúrate de que todos tengan un método .serialize() similar, adaptado a sus nombres de columnas.
````

-----

## 3\. Carga Inicial de Instrucciones (`initial_data_setup.py`)

Este script se ejecuta al inicio de la aplicación para asegurar que las tablas de instrucciones de la IA estén pobladas con los datos predefinidos.

**Archivo: `initial_data_setup.py`**

```python
import json
from datetime import datetime
# Asegúrate de que los modelos estén importados desde tu archivo de modelos
from your_app_name.models import db, InstruccionesGenerales, InstruccionesIndividuales
# Asume que tu logger está configurado en logging_config.py
from logging_config import logger


def carga_base_instrucciones_ia_data_mentor():
    """
    Carga las instrucciones iniciales para el Assistant de IA en la base de datos.
    Verifica si los registros ya existen para evitar duplicados.
    """
    logger.info("Iniciando carga de instrucciones de IA para Data Mentor...")

    try:
        # --- Cargar Instrucciones Generales ---
        inst_gen = InstruccionesGenerales.query.first()
        if not inst_gen:
            logger.info("No se encontraron Instrucciones Generales. Creando registro inicial...")
            inst_gen = InstruccionesGenerales(
                descripcion_general="Este archivo contiene una base de conocimiento integral sobre las operaciones, experiencia del cliente y aprendizaje comercial de nuestra empresa. El objetivo es proporcionar información detallada para análisis, resolución de consultas y comparación con la competencia. La tabla 'base_loop_estaciones' es central para la mayoría de las relaciones. Cada sección de datos ahora incluye un campo 'total_registros' para facilitar conteos directos, y los datos reales están bajo la clave 'datos'.",
                instrucciones_especificas_para_ia="Cuando un usuario haga una pregunta, primero identifica la sección más relevante usando 'secciones_disponibles'. Cada sección de datos contiene un campo 'total_registros' con la cantidad total de entradas en esa sección, y los datos detallados se encuentran bajo la clave 'datos'. Si la pregunta requiere combinar información de diferentes secciones (ej. 'comentarios' con 'base_loop_estaciones'), utiliza las 'relaciones_clave' indicadas para vincularlas. Por ejemplo, para obtener comentarios de una estación específica, usa el campo 'APIES' de los comentarios y de 'base_loop_estaciones'. Siempre correlaciona la pregunta del usuario con la sección del JSON que contenga la información más probable. Si la información no está disponible en una sección o en la mezcla de dos o más secciones por medio de joins de tablas, indícalo claramente. Proporciona respuestas claras, concisas y directas, citando la sección del documento de donde proviene la información si es necesario."
            )
            db.session.add(inst_gen)
            db.session.commit()
            logger.info("Instrucciones Generales cargadas exitosamente.")
        else:
            logger.info("Instrucciones Generales ya existen en la base de datos. No se realizaron cambios.")

        # --- Cargar Instrucciones Individuales ---
        # Datos para las Instrucciones Individuales (asegúrate de que estén completos para TODAS tus 19 secciones)
        secciones_data = [
            {
                "name": "base_loop_estaciones",
                "descripcion": "Tabla PRINCIPAL. Detalle de estaciones (operativa, geográfica, administrativa). Campos 'APIES' e 'Id' claves para relaciones. Los datos reales están en 'datos' y el conteo total en 'total_registros'.",
                "relaciones_clave": {
                    "BaseLoopEstaciones.APIES": "Relaciona con 'comentarios_2023.APIES', 'comentarios_2024.APIES', 'comentarios_2025.APIES'.",
                    "BaseLoopEstaciones.Id": "Relaciona con 'fichas_google.Store_Code', 'fichas_google_competencia.Idloop', 'comentarios_competencia.Idloop', 'usuarios_por_asignacion.ID_Pertenencia'."
                },
                "ejemplo_consulta": "Para la estación con ID 1234, ¿cuál es su volumen promedio de Nafta y qué comentarios de clientes tiene de 2025?"
            },
            {
                "name": "comentarios_2023",
                "descripcion": "Comentarios de encuestas de clientes recibidos en 2023. Incluye 'fecha', 'apies' (ID de estación), 'comentario' (texto libre), 'canal', 'topico', 'sentiment'. Los datos reales están en 'datos' y el conteo total en 'total_registros'.",
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'APIES'."},
                "ejemplo_consulta": "¿Qué comentarios positivos hubo en la estación 5678 en 2023 sobre la atención?"
            },
            {
                "name": "comentarios_2024",
                "descripcion": "Comentarios de encuestas de clientes recibidos en 2024. Formato y campos similares a 2023. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'APIES'."},
                "ejemplo_consulta": "Dame los tópicos más frecuentes en los comentarios negativos de 2024 para la región 'Norte'."
            },
            {
                "name": "comentarios_2025",
                "descripcion": "Comentarios de encuestas de clientes recibidos en 2025. Formato y campos similares a 2023 y 2024. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'APIES'."},
                "ejemplo_consulta": "¿Cuáles son los comentarios recientes (2025) sobre el 'precio' en estaciones de Capital Federal?"
            },
            {
                "name": "fichas_google",
                "descripcion": "Datos de nuestras fichas de Google (reseñas, valoraciones, información de la estación). Contiene 'Store_Code' que es el ID de la estación. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'Store_Code' (que es igual a BaseLoopEstaciones.Id)."},
                "ejemplo_consulta": "¿Cuál es la valoración promedio de las fichas de Google para las estaciones de Buenos Aires?"
            },
            {
                "name": "fichas_google_competencia",
                "descripcion": "Datos de fichas de Google de la competencia. Permite analizar y comparar métricas y comentarios de nuestros rivales. Contiene 'Idloop' que es el ID de la estación asociada. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'Idloop' (que es igual a BaseLoopEstaciones.Id)."},
                "ejemplo_consulta": "¿Qué comentarios negativos hay en las fichas de Google de la competencia sobre la 'velocidad de servicio'?"
            },
            {
                "name": "comentarios_competencia",
                "descripcion": "**¡ATENCIÓN!** Esta sección contiene **comentarios textuales de clientes específicamente sobre nuestros competidores.** Busca aquí para analizar el tipo de feedback que reciben nuestros rivales en temas como precio, atención, calidad de producto, etc. Los campos incluyen 'competidor', 'comentario', 'sentimiento'. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'Idloop' (que es igual a BaseLoopEstaciones.Id)."},
                "ejemplo_consulta": "Dame los comentarios negativos de la competencia sobre el precio en el último mes."
            },
            {
                "name": "usuarios_por_asignacion",
                "descripcion": "Detalles sobre la asignación de usuarios a estaciones. 'ID_Pertenencia' corresponde al ID de la estación en BaseLoopEstaciones. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Relacionado con 'base_loop_estaciones' mediante 'ID_Pertenencia' (que es igual a BaseLoopEstaciones.Id)."},
                "ejemplo_consulta": "¿Cuántos usuarios están asignados a la estación con ID 1234 y cuál es su tipo de operador?"
            },
            {
                "name": "usuarios_sin_id",
                "descripcion": "Información sobre usuarios que no tienen un ID de sistema asignado. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "valida_usuarios",
                "descripcion": "Datos utilizados para la validación de usuarios. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "detalle_apies",
                "descripcion": "Detalle de identificadores de APIES. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "Contiene IDs de APIES, que pueden ser usados para correlacionar con BaseLoopEstaciones."}
            },
            {
                "name": "avance_cursada",
                "descripcion": "Seguimiento del progreso de los usuarios en cursos específicos. Contiene 'ID_Usuario' y 'ID_Curso'. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "detalles_de_cursos",
                "descripcion": "Información detallada sobre los cursos disponibles, como nombre del curso, duración, etc. 'ID_Curso' es la clave. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "cursadas_agrupadas",
                "descripcion": "Resumen o agrupación de datos de cursadas. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "formulario_gestor",
                "descripcion": "Datos recopilados de formularios gestionados. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "cuarto_survey_sql",
                "descripcion": "Resultados de la Cuarta Encuesta SQL. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "quinto_survey_sql",
                "descripcion": "Resultados de la Quinta Encuesta SQL. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            },
            {
                "name": "sales_force",
                "descripcion": "Datos provenientes de SalesForce, relacionados con ventas o gestión de relaciones con clientes. Los datos reales están en 'datos' y el conteo total en 'total_registros'." ,
                "relaciones_clave": {"nota": "No hay una relación directa con BaseLoopEstaciones basada en IDs de estación."}
            }
        ]

        for item_data in secciones_data:
            inst_ind = InstruccionesIndividuales.query.filter_by(name=item_data['name']).first()
            if not inst_ind:
                logger.info(f"No se encontró Instrucción Individual para '{item_data['name']}'. Creando registro inicial...")
                
                new_inst_ind = InstruccionesIndividuales(
                    name=item_data['name'],
                    descripcion=item_data['descripcion'],
                    ejemplo_consulta=item_data.get('ejemplo_consulta'),
                    relaciones_clave=json.dumps(item_data.get('relaciones_clave', {}), ensure_ascii=False)
                )
                db.session.add(new_inst_ind)
            else:
                logger.info(f"Instrucción Individual para '{item_data['name']}' ya existe. No se realizaron cambios.")
        
        db.session.commit()
        logger.info("Carga de instrucciones de IA para Data Mentor completada.")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error durante la carga de instrucciones de IA: {e}", exc_info=True)
```

-----

## 4\. Orquestación Principal (`app.py`)

Así es como tu aplicación Flask inicializa la base de datos y ejecuta la carga de datos iniciales.

**Archivo: `app.py`**

```python
# app.py

import os
from flask import Flask, jsonify, request
from your_app_name.models import db # Asegúrate de importar tu objeto db
# Importa tus blueprints si los usas
from your_app_name.routes.data_mentor_bp import data_mentor_bp
# Importa la función de carga inicial
from initial_data_setup import carga_base_instrucciones_ia_data_mentor
# Asegúrate de importar y configurar tu logger global
from logging_config import logger # Si tienes un logger global

app = Flask(__name__)

# --- Configuración de la base de datos ---
# Ejemplo para SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Configuración de Flask-CORS si lo usas ---
# from flask_cors import CORS
# CORS(app)

# Registra tus Blueprints
app.register_blueprint(data_mentor_bp)

# --- Punto de entrada para la inicialización y carga de datos ---
if __name__ == '__main__':
    with app.app_context():
        db.init_app(app) # Inicializa db con la app
        db.create_all() # Crea todas las tablas (¡ejecuta migraciones si no quieres perder datos!)

        # Cargas iniciales de datos (ejemplos)
        # cargar_todos_los_reportes_iniciales()
        # cargar_usuarios_iniciales()
        # cargar_topicos_iniciales_si_no_existen()

        # --- Llama a la nueva función para cargar las instrucciones de la IA ---
        carga_base_instrucciones_ia_data_mentor()

        logger.info("Proceso de inicio de la aplicación completado.")

    app.run(debug=True, port=10000) # O el puerto que uses
```

-----

## 5\. Ruta de Actualización de Archivos (`routes/data_mentor_bp.py`)

Esta ruta se encarga de recopilar datos de tu DB, estructurarlos con la guía de uso (leída desde la DB), subir el JSON a OpenAI y gestionar el `file_id` para optimizar costos y disponibilidad.

**Archivo: `routes/data_mentor_bp.py`**

```python
import os
import json
import logging
from flask import Blueprint, jsonify, request
from openai import OpenAI
from tempfile import NamedTemporaryFile
import httpx 

# Asegúrate de que todos estos modelos existan y estén importados correctamente.
from your_app_name.models import (
    db,
    Comentarios2025, FichasGoogle, FichasGoogleCompetencia, FileDailyID,
    Usuarios_Por_Asignacion, Usuarios_Sin_ID, ValidaUsuarios, DetalleApies,
    AvanceCursada, DetallesDeCursos, CursadasAgrupadas, FormularioGestor,
    CuartoSurveySql, QuintoSurveySql, Comentarios2023, Comentarios2024,
    BaseLoopEstaciones, SalesForce, ComentariosCompetencia,
    InstruccionesGenerales, InstruccionesIndividuales # <-- Importa los nuevos modelos
)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

data_mentor_bp = Blueprint('data_mentor_bp', __name__)

@data_mentor_bp.route("/actualizar-archivos-asistente", methods=["POST"])
def actualizar_archivos_asistente():
    tmpfile_path = None
    try:
        logger.info("Iniciando el proceso de actualización del archivo de conocimiento diario para OpenAI.")
        logger.info("Recopilando datos de todas las tablas...")

        # --- 1. Recopilar datos de todas las tablas ---
        comentarios_2025_data = Comentarios2025.query.all()
        fichas_google_data = FichasGoogle.query.all()
        fichas_google_competencia_data = FichasGoogleCompetencia.query.all()
        usuarios_por_asignacion_data = Usuarios_Por_Asignacion.query.all()
        usuarios_sin_id_data = Usuarios_Sin_ID.query.all()
        valida_usuarios_data = ValidaUsuarios.query.all()
        detalle_apies_data = DetalleApies.query.all()
        avance_cursada_data = AvanceCursada.query.all()
        detalles_de_cursos_data = DetallesDeCursos.query.all()
        cursadas_agrupadas_data = CursadasAgrupadas.query.all()
        formulario_gestor_data = FormularioGestor.query.all()
        cuarto_survey_sql_data = CuartoSurveySql.query.all()
        quinto_survey_sql_data = QuintoSurveySql.query.all()
        comentarios_2023_data = Comentarios2023.query.all()
        comentarios_2024_data = Comentarios2024.query.all()
        base_loop_estaciones_data = BaseLoopEstaciones.query.all()
        sales_force_data = SalesForce.query.all()
        comentarios_competencia_data = ComentariosCompetencia.query.all()

        # --- CONSTRUCCIÓN DINÁMICA DE LA GUÍA DE USO DE DATOS DESDE LA DB ---
        general_instructions = InstruccionesGenerales.query.first()
        if not general_instructions:
            raise RuntimeError("No se encontraron instrucciones generales en la base de datos. Por favor, cargue los datos en la tabla 'instrucciones_generales' ejecutando la carga inicial.")

        individual_instructions_records = InstruccionesIndividuales.query.all()
        if not individual_instructions_records:
            raise RuntimeError("No se encontraron instrucciones individuales en la base de datos. Por favor, cargue los datos en la tabla 'instrucciones_individuales' ejecutando la carga inicial.")

        secciones_disponibles_guide = {}
        guide_text_parts = ["GUÍA DE USO DE LA BASE DE CONOCIMIENTO:\n"]
        guide_text_parts.append(f"{general_instructions.descripcion_general}\n\n")
        guide_text_parts.append("SECCIONES DISPONIBLES:\n")

        # Mapeo de nombres de modelos a los nombres de claves en el JSON para InstruccionesIndividuales
        section_data_map = {
            "comentarios_2025": comentarios_2025_data,
            "fichas_google": fichas_google_data,
            "fichas_google_competencia": fichas_google_competencia_data,
            "usuarios_por_asignacion": usuarios_por_asignacion_data,
            "usuarios_sin_id": usuarios_sin_id_data,
            "valida_usuarios": valida_usuarios_data,
            "detalle_apies": detalle_apies_data,
            "avance_cursada": avance_cursada_data,
            "detalles_de_cursos": detalles_de_cursos_data,
            "cursadas_agrupadas": cursadas_agrupadas_data,
            "formulario_gestor": formulario_gestor_data,
            "cuarto_survey_sql": cuarto_survey_sql_data,
            "quinto_survey_sql": quinto_survey_sql_data,
            "comentarios_2023": comentarios_2023_data,
            "comentarios_2024": comentarios_2024_data,
            "base_loop_estaciones": base_loop_estaciones_data,
            "sales_force": sales_force_data,
            "comentarios_competencia": comentarios_competencia_data
        }

        for inst_ind in individual_instructions_records:
            section_name = inst_ind.name
            section_data_list = section_data_map.get(section_name, [])
            
            section_info_dict = {
                "descripcion": inst_ind.descripcion,
                "ejemplo_consulta": inst_ind.ejemplo_consulta
            }
            
            relaciones = inst_ind.get_relaciones_clave_dict() # Usa el método para obtener el dict
            if relaciones:
                section_info_dict["relaciones_clave"] = relaciones
            
            # Ajustar la descripción para el texto de la guía si incluye total_registros/datos
            if section_data_list is not None and hasattr(section_data_list, '__len__'):
                section_info_dict["descripcion"] += " Los datos reales están en 'datos' y el conteo total en 'total_registros'."
                
            secciones_disponibles_guide[section_name] = section_info_dict

            # Construir la parte de texto para full_guide_text_for_ai
            guide_text_parts.append(f"\n- Sección: '{section_name}'")
            guide_text_parts.append(f"  Descripción: {section_info_dict['descripcion']}")
            if relaciones:
                guide_text_parts.append(f"  Relaciones Clave:")
                for rel_key, rel_desc in relaciones.items():
                    guide_text_parts.append(f"    - {rel_key}: {rel_desc}")
            if inst_ind.ejemplo_consulta:
                guide_text_parts.append(f"  Ejemplo de Consulta: {inst_ind.ejemplo_consulta}")

        guide_text_parts.append("\nINSTRUCCIONES ESPECÍFICAS DE BÚSQUEDA PARA LA IA:")
        guide_text_parts.append(general_instructions.instrucciones_especificas_para_ia)

        full_guide_text_for_ai = "\n".join(guide_text_parts)
        # FIN DE LA CONSTRUCCIÓN DE LA GUÍA DINÁMICA

        # --- Creación del diccionario JSON final ---
        data_json = {
            "guia_de_uso_de_datos": {
                "descripcion_general": general_instructions.descripcion_general,
                "secciones_disponibles": secciones_disponibles_guide, # Usamos la guía construida dinámicamente
                "instrucciones_especificas_para_ia": full_guide_text_for_ai # Usamos el texto de la guía construida
            },
            # --- Aquí aplicamos el nuevo formato {"total_registros": X, "datos": [...]} a TODAS las secciones de datos ---
            "comentarios_2025": {
                "total_registros": len(comentarios_2025_data),
                "datos": [c.serialize() for c in comentarios_2025_data]
            },
            "fichas_google": {
                "total_registros": len(fichas_google_data),
                "datos": [f.serialize() for f in fichas_google_data]
            },
            "fichas_google_competencia": {
                "total_registros": len(fichas_google_competencia_data),
                "datos": [f.serialize() for f in fichas_google_competencia_data]
            },
            "usuarios_por_asignacion": {
                "total_registros": len(usuarios_por_asignacion_data),
                "datos": [u.serialize() for u in usuarios_por_asignacion_data]
            },
            "usuarios_sin_id": {
                "total_registros": len(usuarios_sin_id_data),
                "datos": [u.serialize() for u in usuarios_sin_id_data]
            },
            "valida_usuarios": {
                "total_registros": len(valida_usuarios_data),
                "datos": [v.serialize() for v in valida_usuarios_data]
            },
            "detalle_apies": {
                "total_registros": len(detalle_apies_data),
                "datos": [d.serialize() for d in detalle_apies_data]
            },
            "avance_cursada": {
                "total_registros": len(avance_cursada_data),
                "datos": [a.serialize() for a in avance_cursada_data]
            },
            "detalles_de_cursos": {
                "total_registros": len(detalles_de_cursos_data),
                "datos": [d.serialize() for d in detalles_de_cursos_data]
            },
            "cursadas_agrupadas": {
                "total_registros": len(cursadas_agrupadas_data),
                "datos": [c.serialize() for c in cursadas_agrupadas_data]
            },
            "formulario_gestor": {
                "total_registros": len(formulario_gestor_data),
                "datos": [f.serialize() for f in formulario_gestor_data]
            },
            "cuarto_survey_sql": {
                "total_registros": len(cuarto_survey_sql_data),
                "datos": [c.serialize() for c in cuarto_survey_sql_data]
            },
            "quinto_survey_sql": {
                "total_registros": len(quinto_survey_sql_data),
                "datos": [q.serialize() for q in quinto_survey_sql_data]
            },
            "comentarios_2023": {
                "total_registros": len(comentarios_2023_data),
                "datos": [c.serialize() for c in comentarios_2023_data]
            },
            "comentarios_2024": {
                "total_registros": len(comentarios_2024_data),
                "datos": [c.serialize() for c in comentarios_2024_data]
            },
            "base_loop_estaciones": {
                "total_registros": len(base_loop_estaciones_data),
                "datos": [b.serialize() for b in base_loop_estaciones_data]
            },
            "sales_force": {
                "total_registros": len(sales_force_data),
                "datos": [s.serialize() for s in sales_force_data]
            },
            "comentarios_competencia": {
                "total_registros": len(comentarios_competencia_data),
                "datos": [c.serialize() for c in comentarios_competencia_data]
            }
        }

        with NamedTemporaryFile(mode="w+", delete=False, suffix=".json", encoding="utf-8") as tmpfile:
            json.dump(data_json, tmpfile, indent=2, ensure_ascii=False)
            tmpfile.flush()
            tmpfile_path = tmpfile.name
        
        file_size = os.path.getsize(tmpfile_path) / (1024 * 1024)
        logger.info(f"Tamaño final del archivo JSON temporal: {file_size:.2f} MB")

        logger.info("Subiendo el nuevo archivo JSON a OpenAI...")
        with open(tmpfile_path, "rb") as file_to_upload:
            uploaded_file = client.files.create(
                file=file_to_upload,
                purpose="assistants"
            )
        new_file_id = uploaded_file.id
        logger.info(f"Nuevo archivo JSON subido con éxito. File ID: {new_file_id}")

        existing_file_record = FileDailyID.query.first()

        if existing_file_record:
            old_file_id = existing_file_record.current_file_id
            logger.info(f"Se encontró un archivo antiguo para eliminar con ID: {old_file_id}")
            try:
                client.files.delete(old_file_id)
                logger.info(f"Archivo antiguo '{old_file_id}' eliminado exitosamente de OpenAI.")
            except Exception as e:
                logger.warning(f"No se pudo eliminar el archivo antiguo '{old_file_id}' de OpenAI. Causa: {e}")
            
            existing_file_record.current_file_id = new_file_id
            existing_file_record.usage_guide_text = full_guide_text_for_ai
            db.session.add(existing_file_record)
            db.session.commit()
            logger.info(f"ID de archivo y guía de uso actualizados en la base de datos a: {new_file_id}")
        else:
            logger.info("No se encontró un archivo anterior registrado en la base de datos.")
            new_record = FileDailyID(
                current_file_id=new_file_id,
                usage_guide_text=full_guide_text_for_ai
            )
            db.session.add(new_record)
            db.session.commit()
            logger.info(f"Nuevo registro de ID de archivo y guía de uso creado en la base de datos: {new_file_id}")

        return jsonify({
            "success": True,
            "message": "Archivo de conocimiento diario actualizado y gestionado exitosamente.",
            "new_file_id": new_file_id
        }), 200

    except Exception as e:
        logger.error("Error en la gestión del archivo de conocimiento diario para OpenAI", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        if tmpfile_path and os.path.exists(tmpfile_path):
            try:
                os.remove(tmpfile_path)
                logger.info(f"Archivo temporal '{tmpfile_path}' eliminado.")
            except PermissionError as pe:
                logger.error(f"Error de permiso al intentar eliminar el archivo temporal en el finally block: {pe}")
            except Exception as final_e:
                logger.error(f"Error inesperado al eliminar el archivo temporal en el finally block: {final_e}")
```

-----

## 6\. Función de Chat (`utils/data_mentor_utils.py`)

Esta función maneja la interacción con el Assistant de OpenAI, recuperando la guía y el archivo más reciente para cada conversación.

**Archivo: `utils/data_mentor_utils.py`**

```python
import os
import time
import json
import logging
from typing import Optional, Tuple
from openai import OpenAI
from your_app_name.models import db, FileDailyID 
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID", "asst_Gy0OKzAqKGqXiU25q9Z89Ifs") 

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def query_assistant_mentor(prompt: str, thread_id: Optional[str] = None) -> Tuple[str, str]:
    logger.info('Entró al util query_assistant_mentor')
    
    # 1. Obtener el ID del archivo de conocimiento diario más reciente Y LA GUÍA DE USO
    daily_file_record = FileDailyID.query.first()
    if not daily_file_record:
        logger.error("No se encontró el ID del archivo de conocimiento diario en la base de datos.")
        raise RuntimeError("No se encontró la base de conocimiento diaria. Por favor, asegúrese de ejecutar la ruta de actualización de archivos.")
    
    current_knowledge_file_id = daily_file_record.current_file_id
    full_guide_text_for_ai = daily_file_record.usage_guide_text # <-- Recupera la guía desde la DB
    
    if not full_guide_text_for_ai:
        logger.error("La guía de uso de datos no se encontró en la base de datos para el archivo actual.")
        raise RuntimeError("La guía de uso de datos para el asistente no está disponible. Ejecute la ruta de actualización de archivos.")

    logger.info(f"Usando archivo de conocimiento con ID recuperado de DB: {current_knowledge_file_id}")

    # --- Verificación del estado de procesamiento del archivo ---
    try:
        file_status_check_limit = 10 
        file_is_processed = False
        
        for _ in range(file_status_check_limit):
            file_obj = client.files.retrieve(current_knowledge_file_id)
            logger.info(f"Estado de procesamiento del archivo {current_knowledge_file_id}: {file_obj.status}")
            
            if file_obj.status == "processed":
                file_is_processed = True
                break
            elif file_obj.status == "failed":
                logger.error(f"El archivo {current_knowledge_file_id} falló su procesamiento en OpenAI. Detalles: {file_obj.error}")
                raise RuntimeError(f"El archivo de conocimiento ({current_knowledge_file_id}) falló su procesamiento en OpenAI. Por favor, revise el archivo o contacte a soporte si persiste.")
            
            time.sleep(2) 

        if not file_is_processed:
            logger.warning(f"El archivo {current_knowledge_file_id} aún no está 'processed' después de {file_status_check_limit} intentos. Estado actual: {file_obj.status}")
            raise RuntimeError("La base de conocimiento aún se está procesando. Por favor, inténtelo de nuevo en unos minutos.")

    except Exception as e:
        logger.error(f"Error al verificar el estado del archivo {current_knowledge_file_id}: {e}", exc_info=True)
        raise RuntimeError(f"Error al verificar la disponibilidad de la base de conocimiento: {str(e)}")


    # Configuración de los adjuntos para el mensaje
    attachments = [
        {
            "file_id": current_knowledge_file_id,
            "tools": [{"type": "file_search"}]
        }
    ]

    current_thread_id = thread_id

    try:
        if not current_thread_id:
            logger.info('thread_id vino SIN contenido (charla nueva). Creando un nuevo hilo...')
            logger.info(f"DEBUG: Creando nuevo Thread. Adjuntando file_id: {current_knowledge_file_id}")
            
            thread = client.beta.threads.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "attachments": attachments
                    }
                ]
            )
            current_thread_id = thread.id
            logger.info(f"Nuevo Thread creado con ID: {current_thread_id}")
        else:
            logger.info(f"thread_id vino con contenido. Continuar hilo existente: {current_thread_id}...")
            logger.info(f"DEBUG: Añadiendo mensaje a Thread existente. Adjuntando file_id: {current_knowledge_file_id}")
            
            client.beta.threads.messages.create(
                thread_id=current_thread_id,
                role="user",
                content=prompt,
                attachments=attachments
            )
            logger.info(f"Mensaje y archivo adjunto al Thread: {current_thread_id}")

        logger.info(f"Creando o continuando run para el Thread: {current_thread_id} con Assistant ID: {ASSISTANT_ID}")
        
        run = client.beta.threads.runs.create(
            thread_id=current_thread_id,
            assistant_id=ASSISTANT_ID,
            additional_instructions=full_guide_text_for_ai # <-- ¡Guía inyectada desde la DB!
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
```

-----

## 7\. System Instructions del Assistant en OpenAI Dashboard

Estas son las instrucciones que configuras directamente en la interfaz de usuario de OpenAI para tu Assistant.

```
Eres un asistente experto en análisis de datos operativos para YPF. Tu objetivo principal es responder preguntas de los usuarios utilizando **exclusivamente** la información detallada que se te proporciona en un **archivo JSON adjunto**.

**Instrucciones Clave para la Interpretación y Uso de Datos:**

1.  **Prioridad de Información:** Siempre basa tus respuestas en los datos más recientes y relevantes disponibles. No utilices conocimiento externo.
2.  **Guía de Estructura y Contenido (Crucial):**
    * **Recibirás una "GUÍA DE USO DE LA BASE DE CONOCIMIENTO" directamente como instrucciones adicionales en cada Run.** Esta guía describe la estructura de los datos del JSON adjunto (qué contiene cada categoría de datos como "comentarios_2025", "comentarios_competencia", "base_loop_estaciones", y cómo usarlos).
    * **Presta especial atención a cómo las secciones de datos incluyen un campo 'total_registros' y los datos detallados bajo la clave 'datos'.**
    * **La tabla "base_loop_estaciones" es el NÚCLEO central.** La mayoría de los demás datos se relacionan con las estaciones a través de los campos indicados en la guía (ej., `APIES`, `Id`).
3.  **Estrategia de Búsqueda y Correlación:**
    * Utiliza la herramienta 'File Search' de manera **precisa e inteligente** para buscar en el JSON adjunto.
    * Si una consulta implica información de múltiples secciones, **identifica las relaciones clave (`relaciones_clave`) descritas en la guía** para correlacionar la información.
    * Para preguntas que solicitan **conteos, totales o resúmenes cuantitativos (ej., 'cuántos registros', 'número total', 'volumen promedio')**, utiliza el campo `total_registros` de la sección relevante. Si no está disponible, intenta contar los elementos de la lista en `datos`.
4.  **Generación de Respuestas:**
    * Si encuentras la información, proporciona una respuesta clara, concisa y relevante. Cita los datos o la sección del JSON de donde provienen si es apropiado o si el usuario lo pide.
    * Si, después de una búsqueda exhaustiva y considerando las relaciones entre tablas, **no encuentras datos específicos**, informa al usuario de manera clara que la información no está disponible. Ofrece sugerir una pregunta diferente o aclarar su búsqueda. **Evita inventar o inferir datos.**
    * Si se te pide analizar tendencias, resumir datos o hacer comparaciones, procesa los datos recuperados de manera inteligente y proporciona un resumen comprensivo.

**Restricciones:**
* **No accedas a ninguna información fuera del archivo JSON adjunto.**
* No inventes respuestas, cifras o datos.
* Mantén un tono profesional, servicial y directo.
```