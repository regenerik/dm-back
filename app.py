import os # para saber la ruta absoluta de la db si no la encontramos
from flask_bcrypt import Bcrypt  # para encriptar y comparar
from flask import Flask, request, jsonify # Para endpoints
from flask_sqlalchemy import SQLAlchemy  # Para rutas
from flask_jwt_extended import  JWTManager, create_access_token, jwt_required, get_jwt_identity
from routes.admin_bp import admin_bp                       # Acá importamos rutas admin
from public_bp import public_bp                     # Acá importamos rutas public
from routes.data_mentor_bp import data_mentor_bp
from routes.quinto_survey_bp import quinto_survey_bp
from routes.cuarto_survey_bp import cuarto_survey_bp
from routes.form_gestores_bp import form_gestores_bp
from routes.chat_moes_bp import chat_moes_bp
from routes.rescate_actividades_bp import rescate_actividades_bp
from routes.clasifica_topicos_mensual_bp import clasifica_topicos_mensual_bp
from routes.rescate_reportes_bp import rescate_reportes_bp
from routes.encuestas_cursos_bp import encuestas_cursos_bp
from routes.segundo_survey_bp import segundo_survey_bp
from routes.tercer_survey_bp import tercer_survey_bp
from routes.resumen_comentarios_apies_bp import resumen_comentarios_apies_bp
from routes.diarios_clasifica_sentimientos_bp import diarios_clasifica_sentimientos_bp
from routes.clasifica_comentarios_individuales_bp import clasifica_comentarios_individuales_bp
from routes.comentarios_necesidades_bp import comentarios_necesidades_bp
from routes.comentarios_necesidades_final_bp import comentarios_necesidades_final_bp
from routes.data_mentor_cursos_bp import data_mentor_cursos_bp
from initial_data_setup import carga_base_instrucciones_ia_data_mentor # Este es el que funciona para IA DATAMENTOR
from database import db                             # Acá importamos la base de datos inicializada
from flask_cors import CORS                         # Permisos de consumo
from extensions import init_extensions              # Necesario para que funcione el executor en varios archivos en simultaneo
from models import TodosLosReportes, User  # Importamos el modelo para TodosLosReportes
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Inicializa los extensiones
init_extensions(app)

CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# ENCRIPTACION JWT y BCRYPT-------

app.config["JWT_SECRET_KEY"] = "valor-variable"  # clave secreta para firmar los tokens.( y a futuro va en un archivo .env)
jwt = JWTManager(app)  # isntanciamos jwt de JWTManager utilizando app para tener las herramientas de encriptacion.
bcrypt = Bcrypt(app)   # para encriptar password

# por ejemplo en create_app()
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

# REGISTRAR BLUEPRINTS ( POSIBILIDAD DE UTILIZAR EL ENTORNO DE LA app EN OTROS ARCHIVOS Y GENERAR RUTAS EN LOS MISMOS )


app.register_blueprint(admin_bp)  # poder registrarlo como un blueprint ( parte del app )
                                                       # y si queremos podemos darle toda un path base como en el ejemplo '/admin'

app.register_blueprint(public_bp, url_prefix='/public')  # blueprint public_bp

app.register_blueprint(rescate_reportes_bp, url_prefix='/') 

app.register_blueprint(encuestas_cursos_bp, url_prefix='/') 

app.register_blueprint(resumen_comentarios_apies_bp, url_prefix='/') 

app.register_blueprint(clasifica_comentarios_individuales_bp, url_prefix='/')

app.register_blueprint(diarios_clasifica_sentimientos_bp, url_prefix='/')

app.register_blueprint(clasifica_topicos_mensual_bp, url_prefix='/')

app.register_blueprint(segundo_survey_bp, url_prefix='/')

app.register_blueprint(tercer_survey_bp, url_prefix='/')

app.register_blueprint(rescate_actividades_bp, url_prefix='/')

app.register_blueprint(chat_moes_bp, url_prefix='/')

app.register_blueprint(form_gestores_bp, url_prefix='/')

app.register_blueprint(cuarto_survey_bp, url_prefix='/')

app.register_blueprint(quinto_survey_bp, url_prefix='/')

app.register_blueprint(data_mentor_bp, url_prefix='/')

app.register_blueprint(comentarios_necesidades_bp, url_prefix='/')

app.register_blueprint(comentarios_necesidades_final_bp , url_prefix='/')

app.register_blueprint(data_mentor_cursos_bp , url_prefix='/')

# DATABASE---------------
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'mydatabase.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'


print(f"Ruta de la base de datos: {db_path}")


if not os.path.exists(os.path.dirname(db_path)): # Nos aseguramos que se cree carpeta instance automatico para poder tener mydatabase.db dentro.
    os.makedirs(os.path.dirname(db_path))

from logging_config import logger
# Función para recargar los reportes (siempre borra lo anterior y carga lo nuevo)
def cargar_todos_los_reportes_iniciales():
    logger.info("Recargando reportes en tabla...")
    # Lista de reportes que queremos cargar
    reportes_nuevos = [
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=133", "title": "USUARIOS POR ASIGNACION PARA GESTORES"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=302&sid=712", "title": "Clon de CURSADA RETAIL"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=248", "title": "Cursos con detalle"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=130", "title": "VERIFICA USUARIOS PARA GESTORES"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=204", "title": "T2_CURSOS_HV"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=332", "title": "T2_APIES_HV_2"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=261", "title": "T2_FACILITADOR_SEMINAR"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=296&sid=713", "title": "CURSADA NO RETAIL"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=306", "title": "Inscripciones Marketplace"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=210&sid=731", "title": "AVANCE DE PROGRAMAS"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=210&sid=732" ,"title": "AVANCE DE PROGRAMAS"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=210&sid=734" ,"title": "AVANCE DE PROGRAMAS"},
        {"report_url": "https://www.campuscomercialypf.com/mod/perform/reporting/performance/activity.php?activity_id=9&all_activities=true" ,"title":"Todas las actividades - 237099 registro/s"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=249" ,"title": "+YPF 2025 Avance por usuarios"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=330" ,"title": "VERIFICÁ INFORMACIÓN DE TU EQUIPO PBI"},
        {"report_url": "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=205","title":"T2_APIES_HV"}
    ]

    # Borramos todos los reportes actuales
    TodosLosReportes.query.delete()
    db.session.commit()  # Confirmamos el borrado en la base de datos

    # Verificamos si la tabla quedó vacía
    reportes_actuales = TodosLosReportes.query.all()
    if reportes_actuales:
        print("Error: No se pudieron eliminar los reportes anteriores.")
        return  # Salimos de la función si no se eliminaron correctamente

    print("Los reportes anteriores fueron eliminados correctamente.")

    # Cargamos los nuevos reportes
    nuevos_registros = [
        TodosLosReportes(report_url=reporte["report_url"], title=reporte["title"])
        for reporte in reportes_nuevos
    ]
    db.session.bulk_save_objects(nuevos_registros)
    db.session.commit()
    logger.info(f"Los reportes fueron actualizados. Se cargaron {len(nuevos_registros)} reportes nuevos.")





# Función para cargar los usuarios iniciales
def cargar_usuarios_iniciales():
    # Borramos todos los usuarios existentes sin llorar
    User.query.delete()
    db.session.commit()
    print("Usuarios anteriores eliminados. Cargando nuevos usuarios...")

    usuarios_iniciales = [
        {
            "email": os.getenv(f'EMAIL{i}'),
            "name": os.getenv(f'NAME{i}'),
            "password": os.getenv(f'PASSWORD{i}'),
            "dni": os.getenv(f'DNI{i}'),
            "admin": os.getenv(f'ADMIN{i}') == 'True',
            "url_image": os.getenv(f'URL_IMAGE{i}')
        }
        for i in range(1, 14)  # Del 1 al 12 inclusive
        if os.getenv(f'EMAIL{i}')  # Solo si hay mail en el .env
    ]

    for usuario in usuarios_iniciales:
        password_hash = bcrypt.generate_password_hash(usuario['password']).decode('utf-8')
        new_user = User(
            email=usuario['email'],
            name=usuario['name'],
            password=password_hash,
            dni=usuario['dni'],
            admin=usuario['admin'],
            url_image=usuario['url_image']
        )
        db.session.add(new_user)

    db.session.commit()
    print("Usuarios nuevos cargados con éxito, maestro.")


def cargar_topicos_iniciales_si_no_existen():
    """
    Verifica si hay exactamente 24 tópicos en la tabla.
    Si no los hay, borra los existentes y carga los 24 iniciales definidos.
    """
    topicos_requeridos = [
        "MEJORAR_ATENCION_AL_CLIENTE_FULL",
        "MEJORAR_INFRAESTRUCTURA_BAÑOS",
        "BUSQUEDA_DE_DESCUENTOS",
        "LENTITUD_EN_SERVICIO",
        "FALTA_REPOSICION_DE_PRODUCTOS",
        "FALTAS_O_ERRORES_EN_PROCESO_DE_PAGO",
        "PROBLEMAS_EN_CANJE_DE_PRODUCTOS",
        "MEJORAR_APLICACION_SISTEMA",
        "VENCIMIENTO_DE_PUNTOS",
        "INFRAESTRUCTURA_E_INSTALACIONES_FULL",
        "PRECIOS_ALTOS_EN_PRODUCTOS",
        "MEJORAR_SERVICIOS_PLAYA",
        "DESCUENTOS_NO_APLICADOS",
        "LOGISTICA_Y_ADMINISTRACION_DE_PERSONAL",
        "MEJORAR_SEÑALIZACIONES",
        "MEJORAR_ATENCION_AL_CLIENTE_PLAYA",
        "MEJORAR_CALIDAD_O_VARIEDAD_DE_PRODUCTOS_FULL",
        "SUMAR_OPCIONES_DIGITALES",
        "MEJORAR_SISTEMA_DE_PUNTOS",
        "COBROS_INDEBIDOS_O_INESPERADOS_DE_PRODUCTOS_O_SERVICIOS",
        "MEJORAS_EN_SEGURIDAD",
        "MEJORAR_ATENCION_DEFICIENTE_EN_ESPERA",
        "MEJORAR_HIGIENE_EN_MANIPULACION_DE_ALIMENTOS",
        "MEJORAR_PRODUCTOS_O_SERVICIOS_PLAYA"
    ]

    from models import TopicoNecesidad  # ajustá si tu import es distinto

    existentes = TopicoNecesidad.query.count()

    if existentes != len(topicos_requeridos):
        print(f"⚠️  Se detectaron {existentes} tópicos. Se reemplazarán por los 24 requeridos.")

        # Borrar todos
        TopicoNecesidad.query.delete()
        db.session.commit()

        # Insertar los nuevos
        nuevos = [TopicoNecesidad(nombre_topico=nombre) for nombre in topicos_requeridos]
        db.session.bulk_save_objects(nuevos)
        db.session.commit()

        print("✅ Tópicos iniciales cargados correctamente.")
    else:
        print("✅ Ya hay 24 tópicos cargados. No se hizo ningún cambio.")

with app.app_context():
    db.init_app(app)
    db.create_all() # Nos aseguramos que este corriendo en el contexto del proyecto.
    cargar_todos_los_reportes_iniciales()  # Cargamos los reportes iniciales
    cargar_usuarios_iniciales()
    cargar_topicos_iniciales_si_no_existen()
    carga_base_instrucciones_ia_data_mentor()

# -----------------------

# AL FINAL ( detecta que encendimos el servidor desde terminal y nos da detalles de los errores )
if __name__ == '__main__':
    app.run()

# Primera vez creo el environment: python -m venv myenv
# EJECUTO ENV CON : myenv\Scripts\activate
# pRIMERA VEZ INSTALO DEPENDENCIAS : pip install -r requirements.txt
# EJECUTO SERVER CON : waitress-serve --port=5000 app:app
