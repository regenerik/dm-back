import logging
import sys

# Configuración básica del logger
logging.basicConfig(level=logging.INFO)

# Crear un logger global
logger = logging.getLogger("my_app_logger")
logger.propagate = False  # Desactiva la propagación al logger raíz

# Verificar si ya hay handlers para evitar duplicados
if not logger.handlers:
    # Crear un manejador de salida que redirige sys.stdout (prints)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)


