from flask import Blueprint, send_file, make_response, request, jsonify, render_template, current_app, Response # Blueprint para modularizar y relacionar con app
from flask_bcrypt import Bcrypt                                  # Bcrypt para encriptación
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity   # Jwt para tokens
from models import User, TotalComents, Instructions, ReportesDataMentor, HistoryUserCourses, FormularioGestor                     # importar tabla "User" de models
from database import db                                          # importa la db desde database.py
from datetime import timedelta                                   # importa tiempo especifico para rendimiento de token válido
from logging_config import logger
import os                                                        # Para datos .env
from dotenv import load_dotenv                                   # Para datos .env
load_dotenv()
import pandas as pd
from io import BytesIO
from openai import OpenAI
import json
from sqlalchemy import text
from datetime import datetime, date
import tempfile
from sqlalchemy.exc import SQLAlchemyError




admin_bp = Blueprint('admin', __name__)     # instanciar admin_bp desde clase Blueprint para crear las rutas.
bcrypt = Bcrypt()
jwt = JWTManager()



# Sistema de key base pre rutas ------------------------:

API_KEY = os.getenv('API_KEY')

def check_api_key(api_key):
    return api_key == API_KEY

@admin_bp.before_request
def authorize():
    if request.method == 'OPTIONS':
        return
    if request.path in ['/toggle_user_status','/delete_user','/check_token','/procesar_encuesta','/test_admin_bp','/','/correccion_campos_vacios','/descargar_positividad_corregida','/download_comments_evaluation','/all_comments_evaluation','/download_resume_csv','/create_resumes_of_all','/descargar_excel','/create_resumes', '/reportes_disponibles', '/create_user', '/login', '/users','/update_profile','/update_profile_image','/update_admin']:
        return
    api_key = request.headers.get('Authorization')
    if not api_key or not check_api_key(api_key):
        return jsonify({'message': 'Unauthorized'}), 401
    
#--------------------------------RUTAS SINGLE---------------------------------

# Ruta de prueba time-out-test------------------------------------------------
@admin_bp.route('/test_admin_bp', methods=['GET'])
def test():
    return jsonify({'message': 'test bien sucedido','status':"Si lees esto, tenemos que ver como manejar el timeout porque los archivos llegan..."}),200

# RUTA DOCUMENTACION
@admin_bp.route('/', methods=['GET'])
def show_hello_world():
         return render_template('instructions.html')

# RUTAS DE ADMINISTRACIÓN DE USUARIOS Y ADMINS ---------------------------------------------------------------

    # RUTA CREAR USUARIO
@admin_bp.route('/create_user', methods=['POST'])
def create_user():
    try:
        email = request.json.get('email')
        password = request.json.get('password')
        name = request.json.get('name')
        dni = request.json.get('dni')
        admin = False
        url_image = "base"
        # Después de crear el primer administrador y la consola de agregar y quitar admins borrar este pedazo:

        #-----------------------------------------------------------------------------------------------------
        if not email or not password or not name or not dni:
            return jsonify({'error': 'Email, password, dni and Name are required.'}), 400

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'error': 'Email already exists.'}), 409

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')


        # Ensamblamos el usuario nuevo
        new_user = User(email=email, password=password_hash, name=name , dni=dni, admin=admin, url_image= url_image)

        db.session.add(new_user)
        db.session.commit()

        good_to_share_to_user = {
            'name':new_user.name,
            'email':new_user.email,
            'dni':new_user.dni,
            'admin':new_user.admin,
            'url_image':new_user.url_image
        }

        return jsonify({'message': 'User created successfully.','user_created':good_to_share_to_user}), 201

    except Exception as e:
        return jsonify({'error': 'Error in user creation: ' + str(e)}), 500


    #RUTA LOG-IN ( CON TOKEN DE RESPUESTA )
@admin_bp.route('/login', methods=['POST'])
def get_token():
    try:
        # Primero chequeamos que por el body venga la info necesaria:
        email = request.json.get('email')
        password = request.json.get('password')

        if not email or not password:
            return jsonify({'error': 'Email y password son requeridos.'}), 400
        
        # Buscamos al usuario con ese correo electronico
        login_user = User.query.filter_by(email=email).one_or_none()

        # Si el usuario no existe, o la contraseña es incorrecta, manejamos el error.
        # Es mejor no especificar si es el email o la contraseña lo que falla por seguridad.
        if not login_user or not bcrypt.check_password_hash(login_user.password, password):
            return jsonify({"Error": "Usuario o contraseña incorrecta"}), 401
        
        # --- CAMBIO CLAVE: VERIFICAR EL ESTADO DEL USUARIO ---
        if not login_user.status:
            return jsonify({"Error": "Tu cuenta está inactiva. Por favor, contacta a un administrador."}), 403 # 403 Forbidden
        
        # Si la contraseña es correcta y el usuario está activo, generamos un token
        expires = timedelta(minutes=30)
        user_dni = login_user.dni
        access_token = create_access_token(identity=str(user_dni), expires_delta=expires)
        
        return jsonify({ 
            'access_token': access_token, 
            'name': login_user.name, 
            'admin': login_user.admin, 
            'dni': user_dni, 
            'email': login_user.email, 
            'url_image': login_user.url_image
        }), 200

    except Exception as e:
        # Aquí manejamos errores inesperados, como problemas de conexión a la base de datos
        return {"Error":"Ocurrió un problema en el servidor: " + str(e)}, 500
    

    # EJEMPLO DE RUTA RESTRINGIDA POR TOKEN. ( LA MISMA RECUPERA TODOS LOS USERS Y LO ENVIA PARA QUIEN ESTÉ LOGUEADO )
@admin_bp.route('/users')
@jwt_required()
def show_users():
    current_user_dni = get_jwt_identity()
    if current_user_dni:
        users = User.query.all()
        user_list = []
        for user in users:
            user_dict = {
                'dni': user.dni,
                'email': user.email,
                'name': user.name,
                'admin': user.admin,
                'url_image': user.url_image,
                'status': bool(user.status)  # <- CAMBIO CLAVE: convertimos a booleano
            }
            user_list.append(user_dict)
        return jsonify({"lista_usuarios":user_list , 'cantidad':len(user_list)}), 200
    else:
        return {"Error": "Token inválido o vencido"}, 401

# ACTUALIZAR PERFIL
@admin_bp.route('/update_profile', methods=['PUT'])
def update():
    email = request.json.get('email')
    password = request.json.get('password')
    name = request.json.get('name')
    dni = request.json.get('dni')
    url_image = request.json.get('url_image')

    # Verificar que el email y la contraseña estén presentes para la validación
    if not email or not password:
        return jsonify({"error": "El email y la contraseña son obligatorios"}), 400

    # Buscar al usuario por email
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Validar la contraseña
    if not bcrypt.check_password_hash(user.password, password):
        return jsonify({"error": "Contraseña incorrecta"}), 401 # 401 Unauthorized

    # Si la contraseña es correcta, actualizar los datos
    try:
        if name is not None:
            user.name = name
        if dni is not None:
            user.dni = dni
        if url_image is not None:
            user.url_image = url_image
        
        # Opcional: Si tienes una forma de cambiar la contraseña, podrías añadirla aquí.
        # Por ahora, solo actualizamos los campos que se pasan
        
        db.session.commit()
        return jsonify({"message": "Usuario actualizado con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar el usuario: {str(e)}"}), 500
        

    # ACTUALIZAR IMAGEN DE PERFIL
@admin_bp.route('/update_profile_image', methods=['PUT'])
def update_profile_image():
    email = request.json.get('email')
    url_image = request.json.get('url_image')

    # Verificar que ambos campos estén presentes
    if not email or not url_image:
        return jsonify({"error": "El email y la URL de la imagen son obligatorios"}), 400

    # Buscar al usuario por email
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Actualizar solo la URL de la imagen
    user.url_image = url_image

    try:
        db.session.commit()
        return jsonify({"message": "Imagen de perfil actualizada con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar la imagen: {str(e)}"}), 500
    
    # ACTUALIZAR CONDICIÓN DE ADMIN
@admin_bp.route('/update_admin', methods=['PUT'])
def update_admin():
    email = request.json.get('email')
    admin = request.json.get('admin')

    # Verificar que ambos campos estén presentes
    if email is None or admin is None:
        return jsonify({"error": "El email y la situación admin son obligatorios"}), 400

    # Buscar al usuario por email
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Actualizar estado admin
    user.admin = not user.admin

    try:
        db.session.commit()
        return jsonify({"message": f"Estado admin de {email} ahora es {'admin' if user.admin else 'no admin'}", "admin": user.admin}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar el estado admin: {str(e)}"}), 500
    
    # OBTENER USUARIO POR SU DNI
@admin_bp.route('/get_user/<int:dni>', methods=['GET'])
def get_user(dni):
    try:
        
        login_user = User.query.filter_by(dni=dni).one()

        if login_user:
            return jsonify({'name':login_user.name, 'admin':login_user.admin, 'dni':login_user.dni, 'email':login_user.email, 'url_image':login_user.url_image}), 200 

        else:
            return {"Error":"No se encontró un usuario con ese documento"}
    
    except Exception as e:
        return {"Error":"El dni proporcionado no corresponde a ninguno registrado: " + str(e)}, 500
    

@admin_bp.route('/delete_user', methods=['DELETE'])
@jwt_required()
def delete_user():
    # Obtiene la identidad (DNI del administrador) del token JWT
    current_user_dni = get_jwt_identity()
    
    # 1. Verificar si el usuario que realiza la solicitud es un administrador
    admin_user = User.query.filter_by(dni=current_user_dni).first()
    if not admin_user or not admin_user.admin:
        return jsonify({"error": "Acceso no autorizado"}), 403

    # 2. Obtener el DNI del usuario a eliminar de la solicitud
    dni_to_delete = request.json.get('dni')
    if not dni_to_delete:
        return jsonify({"error": "El DNI del usuario a eliminar es obligatorio"}), 400

    # 3. Buscar y eliminar al usuario
    user_to_delete = User.query.filter_by(dni=dni_to_delete).first()
    if not user_to_delete:
        return jsonify({"error": "Usuario no encontrado"}), 404

    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        return jsonify({"message": f"Usuario con DNI {dni_to_delete} eliminado con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar el usuario: {str(e)}"}), 500
    

@admin_bp.route('/toggle_user_status', methods=['PUT'])
@jwt_required()
def toggle_user_status():
    # Obtiene la identidad (DNI del administrador) del token JWT
    current_user_dni = get_jwt_identity()
    
    # 1. Verificar si el usuario que realiza la solicitud es un administrador
    admin_user = User.query.filter_by(dni=current_user_dni).first()
    if not admin_user or not admin_user.admin:
        return jsonify({"error": "Acceso no autorizado"}), 403

    # 2. Obtener el DNI del usuario del que se va a cambiar el estado
    dni_to_toggle = request.json.get('dni')
    if not dni_to_toggle:
        return jsonify({"error": "El DNI del usuario es obligatorio"}), 400

    # 3. Buscar y cambiar el estado del usuario
    user_to_toggle = User.query.filter_by(dni=dni_to_toggle).first()
    if not user_to_toggle:
        return jsonify({"error": "Usuario no encontrado"}), 404

    try:
        user_to_toggle.status = not user_to_toggle.status
        db.session.commit()
        new_status = "activo" if user_to_toggle.status else "inactivo"
        return jsonify({"message": f"Estado del usuario con DNI {dni_to_toggle} cambiado a {new_status}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al cambiar el estado del usuario: {str(e)}"}), 500

# ADMINISTRACION DE RESUMEN BBDDconcat ( CRUDO ) DE COMENTARIOS DE APIES-----------------------------------/////////////////////////////////////////////////////////

@admin_bp.route('/eliminar_excel_total', methods=['DELETE'])
def eliminar_excel():
    try:
        excel_data = TotalComents.query.first()
        if excel_data:
            db.session.delete(excel_data)
            db.session.commit()
            return jsonify({"message": "Excel eliminado con éxito"}), 200
        else:
            return jsonify({"message": "No hay archivo Excel para eliminar"}), 404
    except Exception as e:
        return jsonify({"message": "Error al eliminar el archivo"}), 500
    

@admin_bp.route('/subir_excel_total', methods=['POST'])
def subir_excel():
    try:
        # Eliminar el registro anterior
        excel_data = TotalComents.query.first()
        if excel_data:
            db.session.delete(excel_data)
            db.session.commit()

        # Guardar el nuevo Excel en binario
        file = request.files['file']
        df = pd.read_excel(file)  # Cargamos el Excel usando pandas
        binary_data = BytesIO()
        df.to_pickle(binary_data)  # Convertimos el DataFrame a binario
        binary_data.seek(0)

        nuevo_excel = TotalComents(data=binary_data.read())
        db.session.add(nuevo_excel)
        db.session.commit()

        return jsonify({"message": "Archivo subido con éxito"}), 200
    except Exception as e:
        return jsonify({"message": f"Error al subir el archivo: {str(e)}"}), 500
    
@admin_bp.route('/descargar_excel', methods=['GET'])
def descargar_excel():
    try:
        logger.info("1 - Entró en la ruta descargar_excel")
        # Obtener el registro más reciente de la base de datos
        excel_data = TotalComents.query.first()

        if not excel_data:
            return jsonify({"message": "No se encontró ningún archivo Excel en la base de datos"}), 404

        logger.info("2 - Encontró el excel en db, traduciendo de binario a dataframe..")
        # Convertir los datos binarios de vuelta a DataFrame
        binary_data = BytesIO(excel_data.data)
        df = pd.read_pickle(binary_data)

        logger.info("3 - De dataframe a excel...")
        # Convertir el DataFrame a un archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='APIES_Data')

        output.seek(0)  # Mover el puntero al inicio del archivo
        
        logger.info("4 - Devolviendo excel. Fin del proceso...")
        # Enviar el archivo Excel como respuesta
        return send_file(output, 
                         download_name='apies_data.xlsx', 
                         as_attachment=True, 
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        return jsonify({"message": f"Error al descargar el archivo: {str(e)}"}), 500
    

@admin_bp.route('/existencia_excel', methods=['GET'])
def existencia_excel():
    try:
        # Obtener el registro más reciente de la base de datos
        excel_data = TotalComents.query.first()

        if not excel_data:
            return jsonify({"message": "No se encontró ningún archivo Excel en la base de datos", "ok": False}), 404
        else:
            # Formatear el timestamp de manera legible (dd/mm/yyyy HH:MM:SS)
            datetime = excel_data.timestamp.strftime('%d/%m/%Y %H:%M:%S')
            return jsonify({"message": f"El archivo se encuentra disponible. Y data del día: {datetime}", "ok": True, "datetime":datetime}), 200
        
    except Exception as e:
        return jsonify({"message": f"Error al confirmar la existencia del archivo: {str(e)}", "ok": False}), 500


@admin_bp.route('/check_token', methods=['GET'])
@jwt_required()
def check_token():
    """
    Verifica la validez del token de acceso JWT.
    Si el token es válido y no ha expirado, esta ruta devuelve un mensaje de éxito.
    Si el token es inválido o expiró, flask_jwt_extended maneja el error automáticamente
    devolviendo un status 401.
    """
    return jsonify({"message": "Token is valid", "status": "success"}), 200


RESTORE_DB_KEY = os.getenv("RESTORE_DB_KEY")

@admin_bp.route("/get_buckup", methods=["GET"])
def get_buckup():
    logger.info("DEBUG: Iniciando el proceso de backup.")
    try:
        # Serializar los datos de las tablas que tienen el método serialize()
        backup_data = {
            "Instructions": [item.serialize() for item in Instructions.query.all()],
            "ReportesDataMentor": [item.serialize() for item in ReportesDataMentor.query.all()],
            "HistoryUserCourses": [item.serialize() for item in HistoryUserCourses.query.all()],
            "User": [],  # Serialización manual
            "FormularioGestor": []  # Serialización manual
        }
        logger.info("DEBUG: Datos de tablas con .serialize() serializados.")

        # Serialización manual de la tabla User (sin método .serialize())
        for user_obj in User.query.all():
            backup_data["User"].append({
                "id": user_obj.id,
                "dni": user_obj.dni,
                "name": user_obj.name,
                "email": user_obj.email,
                "password": user_obj.password,
                "url_image": user_obj.url_image,
                "admin": user_obj.admin,
                "status": user_obj.status,
            })
        logger.info("DEBUG: Serialización de User completada.")
        
        # Serialización manual de FormularioGestor (excluyendo datos binarios)
        for fg_obj in FormularioGestor.query.all():
            backup_data["FormularioGestor"].append({
                "id": fg_obj.id,
                "apies": fg_obj.apies,
                "curso": fg_obj.curso,
                "fecha_usuario": fg_obj.fecha_usuario.isoformat() if fg_obj.fecha_usuario else None,
                "gestor": fg_obj.gestor,
                "duracion_horas": fg_obj.duracion_horas,
                "objetivo": fg_obj.objetivo,
                "contenido_desarrollado": fg_obj.contenido_desarrollado,
                "ausentes": fg_obj.ausentes,
                "presentes": fg_obj.presentes,
                "resultados_logros": fg_obj.resultados_logros,
                "compromiso": fg_obj.compromiso,
                "participacion_actividades": fg_obj.participacion_actividades,
                "concentracion": fg_obj.concentracion,
                "cansancio": fg_obj.cansancio,
                "interes_temas": fg_obj.interes_temas,
                "recomendaciones": fg_obj.recomendaciones,
                "otros_aspectos": fg_obj.otros_aspectos,
                "jornada": fg_obj.jornada,
                "dotacion_real_estacion": fg_obj.dotacion_real_estacion,
                "dotacion_dni_faltantes": fg_obj.dotacion_dni_faltantes,
                "nombre_firma": fg_obj.nombre_firma,
                "email_gestor": fg_obj.email_gestor,
                "creado_en": fg_obj.creado_en.isoformat() if fg_obj.creado_en else None
            })
        logger.info("DEBUG: Serialización de FormularioGestor completada (firma_file excluida).")

        # Guardar el JSON en un archivo temporal
        backup_filename = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        temp_file_path = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
            json.dump(backup_data, temp_file, indent=4, ensure_ascii=False)
            temp_file_path = temp_file.name
        
        logger.info(f"DEBUG: Archivo temporal creado en: {temp_file_path}")

        # Enviar el archivo como respuesta
        try:
            response = send_file(temp_file_path, as_attachment=True, mimetype='application/json', download_name=backup_filename)
            logger.info("DEBUG: Archivo enviado al cliente.")
            return response
        finally:
            os.remove(temp_file_path)
            logger.info(f"DEBUG: Archivo temporal {temp_file_path} eliminado.")

    except Exception as e:
        logger.error(f"ERROR: Fallo inesperado en get_buckup: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Error al generar el backup: {str(e)}"}), 500

@admin_bp.route("/restaurar_db", methods=["POST"])
def restaurar_db():
    logger.info("DEBUG: Iniciando el proceso de restauración.")
    try:
        # 1. Validar la clave secreta
        password = request.form.get("password")
        if not password or password.strip() != RESTORE_DB_KEY:
            logger.error("ERROR: Clave de restauración incorrecta o no proporcionada.")
            return jsonify({"error": "Clave de restauración incorrecta."}), 401
        
        logger.info("DEBUG: Clave de restauración validada.")
        
        # 2. Recibir y cargar el archivo de backup
        file = request.files.get("file")
        if not file:
            logger.error("ERROR: No se recibió ningún archivo.")
            return jsonify({"error": "No se recibió ningún archivo."}), 400
        
        logger.info("DEBUG: Archivo recibido. Cargando datos...")
        backup_data = json.load(file)
        logger.info("DEBUG: Datos del backup cargados con éxito. Vaciando tablas.")

        # 3. Vaciar las tablas existentes para evitar conflictos de IDs
        # Usamos DELETE FROM para eliminar todas las filas. NO reiniciamos la secuencia.
        db.session.execute(text("DELETE FROM instructions"))
        db.session.execute(text("DELETE FROM user"))
        db.session.execute(text("DELETE FROM reportes_data_mentor"))
        db.session.execute(text("DELETE FROM history_user_courses"))
        db.session.execute(text("DELETE FROM formulario_gestor"))
        
        db.session.commit()
        logger.info("DEBUG: Tablas vaciadas. Iniciando restauración de datos con IDs originales.")

        # 4. Función genérica para restaurar datos con IDs originales
        def restore_table(model, data):
            for item_data in data:
                # Se mantiene el 'id' en los datos
                
                # Manejar fechas
                for key, value in item_data.items():
                    if isinstance(value, str):
                        try:
                            # Intenta convertir la cadena a datetime
                            item_data[key] = datetime.fromisoformat(value)
                        except (ValueError, TypeError):
                            try:
                                # Si falla, intenta convertir a date
                                item_data[key] = date.fromisoformat(value)
                            except (ValueError, TypeError):
                                pass

                # Se crea la nueva instancia con todos los datos, incluyendo el ID
                new_item = model(**item_data)
                db.session.add(new_item)
                
        # 5. Restaurar cada tabla
        restore_table(Instructions, backup_data.get("Instructions", []))
        logger.info("DEBUG: Tabla Instructions restaurada.")
        restore_table(User, backup_data.get("User", []))
        logger.info("DEBUG: Tabla User restaurada.")
        restore_table(ReportesDataMentor, backup_data.get("ReportesDataMentor", []))
        logger.info("DEBUG: Tabla ReportesDataMentor restaurada.")
        restore_table(HistoryUserCourses, backup_data.get("HistoryUserCourses", []))
        logger.info("DEBUG: Tabla HistoryUserCourses restaurada.")
        restore_table(FormularioGestor, backup_data.get("FormularioGestor", []))
        logger.info("DEBUG: Tabla FormularioGestor restaurada.")

        # 6. Commit de la sesión
        db.session.commit()
        logger.info("DEBUG: Commit a la base de datos realizado. Proceso completado.")
        return jsonify({"message": "Base de datos restaurada con éxito."}), 200

    except SQLAlchemyError as e:
        logger.error(f"ERROR: Fallo de SQLAlchemy durante la restauración: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Fallo de la base de datos: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"ERROR: Fallo inesperado en restaurar_db: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Fallo inesperado: {str(e)}"}), 500
    
