# 🦷 DentalFlow — Agenda odontológica profesional

![Python](https://img.shields.io/badge/Python-3.12-3776AB) ![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-FF4B4B) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Production-336791)

Aplicación web administrativa en español para gestionar las citas de una clínica odontológica. Diseñada para operación en Colombia (zona horaria `America/Bogota`), con identidad visual propia y un repositorio independiente.

## Funciones

- **Dashboard:** cifras de citas del día, confirmaciones, atenciones, pacientes y tendencias.
- **Agenda visual:** calendario por día/semana/mes; selección de espacios, filtros por odontólogo y lista exportable a CSV.
- **Registro de pacientes:** datos de contacto, documento, búsqueda y edición.
- **Profesionales:** especialidades, activación/desactivación y bloqueos de horarios.
- **Procedimientos:** catálogo de servicios, duración configurable y valores en COP.
- **Citas:** crear, reprogramar, confirmar, marcar en atención, atendida, cancelada o no asistió; historial básico de movimientos.
- **Disponibilidad:** horario por día, duración del procedimiento, bloqueo de permisos y validación de solapamientos.
- **Seguridad:** acceso administrativo con password `scrypt`, credenciales por secrets y base de datos externa fuera del código.
- **Calidad:** pruebas automáticas en `tests/` y GitHub Actions.

**Publicación rápida en Windows:** crea el repositorio privado `o31942/odontologia-agenda-pro` en GitHub, descomprime el proyecto y ejecuta `PUBLICAR_EN_GITHUB.bat`. Ver [guía de despliegue](docs/DEPLOY.md).

## Requisitos

Python 3.12 (recomendado), PostgreSQL gestionado en producción (Supabase, Neon, Render, RDS o similar) y una instancia de Streamlit.

## Inicio rápido (demostración sin datos reales)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Crea `.streamlit/secrets.toml` localmente con:

```toml
DEMO_MODE = "true"
CLINIC_NAME = "Clínica Dental Demo"
```

Luego ejecuta:

```bash
streamlit run app.py
```

⚠️ **Modo demo:** usa SQLite local (`dentalflow_demo.sqlite3`, excluida de Git) y **no tiene autenticación**. No ingresar pacientes reales y nunca exponer datos sensibles en este modo.

## Producción — con persistencia y acceso protegido

1. Crea una base de datos PostgreSQL con SSL/TLS y configura respaldo automático.
2. Genera tu contraseña segura (no se incluye ninguna contraseña en el código):

   ```bash
   python scripts/hash_password.py
   ```

3. En **Streamlit Community Cloud → App settings → Secrets** (o en tu fichero `.streamlit/secrets.toml` local, que está ignorado por Git), configura:

   ```toml
   CLINIC_NAME = "Nombre de tu clínica"
   ADMIN_EMAIL = "admin@tuclinica.com"
   ADMIN_PASSWORD_HASH = "scrypt$16384$8$1$...hash_generado_por_script..."
   DATABASE_URL = "postgresql://usuario:contraseña@host:5432/base?sslmode=require"
   DEMO_MODE = "false"
   APP_ENV = "production"
   ```

4. Ejecuta la aplicación en Streamlit Cloud, apuntando a `app.py`, rama `main`. Las tablas y servicios estándar se crean automáticamente en la primera conexión.
5. Crea primero un **profesional**, luego un **paciente** y finalmente una **cita**.

**Nunca publiques** `ADMIN_PASSWORD_HASH` o `DATABASE_URL` en GitHub. El código está preparado para leer `st.secrets` o variables de entorno; el archivo de ejemplo contiene solo valores ficticios.

> Atención: el usuario y contraseña de esta versión corresponden a **una cuenta administrativa**. Para múltiples recepcionistas, profesionales y sucursales con permisos independientes se debe incorporar autenticación y autorización por roles con auditoría y controles adicionales.

## Estructura

```
app.py                         # Frontend Streamlit
 dentalflow/db.py              # Modelos SQLAlchemy
 dentalflow/services.py        # Reglas de agendamiento
 dentalflow/security.py        # Lectura de secretos + login
 dentalflow/ui.py              # Sistema de diseño
 tests/                        # Pruebas automáticas
 scripts/hash_password.py      # Herramienta para la contraseña
 .streamlit/config.toml        # Tema de la interfaz
 .streamlit/secrets.example.toml
 .github/workflows/quality.yml
 docs/DEPLOY.md                # Instrucciones de despliegue
```

## Privacidad y alcance

Es una **agenda administrativa, no una historia clínica electrónica**. Antes de tratar datos personales de pacientes reales, configura cumplimiento de la normativa colombiana aplicable (Ley 1581 de 2012 y disposiciones relacionadas), políticas de tratamiento y retención, información a titulares, control de accesos, respaldo, recuperación, cifrado en tránsito y proveedor de infraestructura apropiado. No anotes diagnósticos, resultados médicos ni datos clínicos sensibles en los campos libres. Para uso clínico productivo, solicita una revisión de seguridad y privacidad.

**Nota técnica:** En PostgreSQL el agendamiento bloquea la fila del profesional al validar disponibilidad, reduciendo la carrera por dobles reservas. El modo demo SQLite no es apto para concurrencia de múltiples operadores.

## Pruebas

```bash
pip install pytest
python -m pytest -q
```

## Licencia

Código del proyecto preparado para personalización. Revisa los términos de las dependencias utilizadas antes de redistribuir.