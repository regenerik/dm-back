# utils.py

import requests
from bs4 import BeautifulSoup
import re
import tempfile

def obtener_sesskey(html):
    soup = BeautifulSoup(html, 'html.parser')
    sesskey_link = soup.find('a', href=re.compile(r'/login/logout.php\?sesskey='))
    if sesskey_link:
        sesskey_url = sesskey_link['href']
        sesskey = re.search(r'sesskey=([a-zA-Z0-9]+)', sesskey_url)
        if sesskey:
            return sesskey.group(1)
    return None

def exportar_reporte_excel(username, password):
    session = requests.Session()
    print("Utils inciando. Entrando y recuperando token inicial...")
    # Paso 1: Obtener el logintoken
    login_page_url = "https://www.campuscomercialypf.com/login/index.php"
    login_page_response = session.get(login_page_url)
    login_page_soup = BeautifulSoup(login_page_response.text, 'html.parser')
    logintoken_input = login_page_soup.find('input', {'name': 'logintoken'})
    logintoken = logintoken_input['value'] if logintoken_input else None
    print("token recuperado. Iniciando login")
    # Paso 2: Realizar el inicio de sesión
    login_payload = {
        "username": username,
        "password": password,
        "logintoken": logintoken,
        "anchor": ""
    }
    login_headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    login_response = session.post(login_page_url, data=login_payload, headers=login_headers)

    # Verificar si se ha iniciado sesión correctamente
    if login_response.status_code == 200 and "TotaraSession" in session.cookies:
        print("Inicio de sesión exitoso")
    else:
        print("Error en el inicio de sesión")
        return None

    # Paso 3: Obtener el sesskey dinámicamente desde la página
    dashboard_url = "https://www.campuscomercialypf.com/totara/reportbuilder/report.php?id=133"
    dashboard_response = session.get(dashboard_url)
    dashboard_html = dashboard_response.text
    sesskey = obtener_sesskey(dashboard_html)

    # Verificar si se pudo obtener el sesskey
    if not sesskey:
        print("Error: No se pudo obtener el sesskey")
        return None
    print("sESSION KEY - Recuperado, recuperando reporte...")
    # Paso 4: Seleccionar "Excel" como formato de exportación y exportar el archivo
    export_payload = {
        "sesskey": sesskey,
        "_qf__report_builder_export_form": "1",
        "format": "excel",
        "export": "Exportar"
    }
    export_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": dashboard_url
    }

    export_response = session.post(dashboard_url, data=export_payload, headers=export_headers)

    # Verificar la respuesta de la exportación
    if export_response.status_code == 200:
        print("Exportación exitosa")

        # Crear un archivo temporal y escribir el contenido de export_response en él
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(export_response.content)

        return temp_file.name  # Devolver el nombre del archivo temporal
    else:
        print("Error en la exportación")
        return None
