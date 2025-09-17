Para hacer un clon y empezar desde otra carpeta : 

1 - Eliminar carpeta myenv
2 - crearla devuelta : python -m venv myenv
3 - activarla : myenv\Scripts\activate
4 - instalar dependencias : pip install -r requirements.txt
5 - Eliminar carpeta escondida .git
6 - Crearla devuelta git init
7 - Darle origen  : git remote add origin <URL_del_nuevo_repositorio>
8 - Crear repo en github
9 - Agregar y 
    git add .
    git commit -m "Initial commit for new project"
    git branch -M main
    git push -u origin main
10 - test de funcionamiento.