# AulaGest — Sistema académico

Aplicación web inicial para gestionar estudiantes, cursos, matrículas, calificaciones y cuentas con roles `admin` y `user`.

## Requisitos
- Python 3.11 o superior (usa una versión soportada por tu hosting).
- MySQL 8 o MariaDB compatible.
- Entorno virtual de Python.

## Funcionalidades
- Login y logout con contraseñas almacenadas mediante hash.
- Permisos de administrador y usuario normal.
- CRUD de estudiantes y cursos.
- Matrículas por periodo académico.
- Registro y consulta de notas entre 0 y 5.
- Cuentas vinculables a un estudiante.
- Formularios protegidos con CSRF y cookies de sesión configurables.
- Interfaz responsive en español.

## Instalación local en Windows (PowerShell)

1. Instala Python y MySQL, o inicia MySQL desde XAMPP.
2. Crea la base de datos. Desde phpMyAdmin, importa `schema.sql`; alternativamente, en terminal MySQL ejecuta:
   `mysql -u root -p < schema.sql`
3. En la carpeta del proyecto:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```
4. Edita `.env` con la contraseña real de MySQL. Si root no tiene contraseña en XAMPP, la URL local puede ser:
   `mysql+pymysql://root:@127.0.0.1:3306/aulagest?charset=utf8mb4`
5. Inicializa tablas y crea administrador:
   ```powershell
   flask --app app init-db
   flask --app app create-admin
   ```
   Introduce un usuario y una contraseña de al menos 10 caracteres.
6. Ejecuta:
   ```powershell
   python app.py
   ```
7. Abre `http://127.0.0.1:5000`.

Si PowerShell bloquea la activación del entorno virtual, usa:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
y vuelve a activar `.venv`.

## Modelo de datos

- `users`: credenciales, rol y vínculo opcional con estudiante.
- `students`: datos personales académicos.
- `courses`: catálogo de cursos y docente.
- `enrollments`: relación entre estudiante, curso y periodo.
- `grades`: calificación única por matrícula.

`schema.sql` contiene el esquema relacional. Para desarrollo rápido existe también el comando `flask --app app init-db`, que crea tablas a partir de los modelos. En un sistema productivo en evolución se recomienda usar migraciones (por ejemplo, Flask-Migrate/Alembic) en vez de modificar tablas manualmente.

## Recomendación de hosting

Para un proyecto Flask + MySQL, PythonAnywhere es una opción sencilla porque documenta el despliegue de Flask y ofrece MySQL en planes compatibles. Consulta el precio y los límites vigentes antes de pagar: las cuentas gratuitas nuevas no incluyen MySQL. Guía: https://help.pythonanywhere.com/pages/Flask/ y planes: https://www.pythonanywhere.com/pricing/

Hostinger indica que para ejecutar aplicaciones Python con dependencias propias se necesita un VPS; el hosting web/Cloud compartido no ofrece acceso root. Si ya tienes Hostinger, revisa VPS y su administración antes de elegirlo: https://support.hostinger.com/es/articles/3648030-es-python-compatible-con-hostinger

## Despliegue general

1. Contrata un plan que admita aplicación WSGI de Python y una base MySQL accesible desde esa aplicación.
2. Crea la base de datos y el usuario de base de datos desde el panel del hosting.
3. Sube el proyecto (sin `.env`, `.venv`, `__pycache__` ni datos locales).
4. Configura las variables de entorno en el panel:
   - `SECRET_KEY`: valor largo, aleatorio y privado.
   - `DATABASE_URL`: `mysql+pymysql://USUARIO:CLAVE@HOST:PUERTO/BASE?charset=utf8mb4`
   - `COOKIE_SECURE=1` cuando HTTPS esté activo.
   - `FLASK_DEBUG=0`
5. Instala `requirements.txt` en el entorno virtual del hosting.
6. Ejecuta `flask --app app init-db` o importa `schema.sql` en la base de datos vacía.
7. Crea el primer administrador con `flask --app app create-admin`.
8. Configura el WSGI de la plataforma para importar `app` desde `app.py`. No ejecutes `app.run()` en el servidor WSGI.
9. Activa HTTPS, prueba login, roles, creación de registros y permisos; revisa los logs del hosting.
10. Configura copias de seguridad de la base de datos.

### Ejemplo de importación WSGI (PythonAnywhere)
Ajusta las rutas y el nombre de usuario a los de tu cuenta:
```python
import sys
project_path = "/home/TU_USUARIO/AulaGest"
if project_path not in sys.path:
    sys.path.insert(0, project_path)
from app import app as application
```

## Seguridad y límites de esta primera versión
- Cambia la clave secreta antes de publicar.
- No reutilices contraseñas personales; guarda credenciales fuera del repositorio.
- Usa HTTPS y `COOKIE_SECURE=1` en producción.
- Crea cuentas normales solo después de registrar estudiantes.
- La aplicación evita duplicados en campos clave y aplica CSRF en formularios POST.
- Antes de usarla con datos reales de menores o expedientes oficiales, añade políticas de privacidad, auditoría de cambios, copias de seguridad verificadas, recuperación de contraseña, limitación de intentos de login y un proceso formal de autorización de usuarios.
- El usuario normal solo ve las matrículas/notas asociadas a su cuenta vinculada. Los usuarios sin estudiante vinculado ven el catálogo de cursos, pero no expedientes ajenos.
