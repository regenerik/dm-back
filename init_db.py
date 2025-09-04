from database import db
from app import app
from models import Reporte, User  # Importa todos los modelos necesarios

# Crear las tablas en la base de datos
with app.app_context():
    db.create_all()
    print("Base de datos actualizada.")
