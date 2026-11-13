# Publicación paso a paso en GitHub y Streamlit Cloud

## A. Repositorio

1. En GitHub crea un **repositorio privado vacío**, por ejemplo `odontologia-agenda-pro`, sin README ni plantilla (este proyecto ya trae esos archivos).
2. Carga los archivos de este proyecto al repositorio, respetando sus carpetas, o utiliza desde la raíz:

```bash
git init
git add .
git commit -m "feat: professional dental appointment management"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/odontologia-agenda-pro.git
git push -u origin main
```

3. **En Windows:** tras descomprimir este ZIP en una carpeta, también puedes ejecutar `PUBLICAR_EN_GITHUB.bat` para publicar automáticamente en `o31942/odontologia-agenda-pro`. Se requiere Git instalado y una sesión autorizada de GitHub. El repositorio debe estar creado y vacío.
4. Si trabajas con ChatGPT conectado a GitHub, también puedes crear el repositorio vacío y solicitar la carga de los archivos mediante el conector.

## B. Base de datos PostgreSQL

1. Crea un proyecto PostgreSQL administrado que ofrezca SSL, backups y control de acceso.
2. Copia la cadena de conexión **del servidor** (no de una cuenta pública o cliente web).
3. Guarda `DATABASE_URL` exclusivamente en los secretos de Streamlit, nunca en `.streamlit/config.toml` ni en el código.
4. Permite conexiones desde la plataforma de alojamiento según las recomendaciones del proveedor de base de datos.

**Importante:** el esquema se inicializa automáticamente con `SQLAlchemy.create_all()` para esta versión inicial; las futuras modificaciones del modelo deben manejarse mediante migraciones controladas (p. ej. Alembic) y copia de seguridad previa.

## C. Acceso seguro

1. Crea una contraseña única de 12 caracteres o más.
2. En tu PC, ejecuta `python scripts/hash_password.py`.
3. Copia el hash generado a `ADMIN_PASSWORD_HASH` y configura `ADMIN_EMAIL`.
4. Nunca publiques ni compartas la cadena de conexión ni el hash por GitHub. La contraseña en texto plano **no se guarda**.
5. Para producción usa HTTPS, revisa permisos del servicio, accesos administrativos y un proveedor con capacidades empresariales si vas a manejar datos personales de pacientes.

## D. Streamlit Community Cloud

1. Abre https://share.streamlit.io e inicia sesión con GitHub.
2. Pulsa **Create app** → **Yup, I have an app**.
3. Selecciona tu repositorio, rama `main` y archivo de entrada `app.py`.
4. En opciones avanzadas ingresa los **Secrets**:

```toml
CLINIC_NAME = "Mi Clínica Odontológica"
ADMIN_EMAIL = "admin@miclinica.com"
ADMIN_PASSWORD_HASH = "scrypt$16384$8$1$..."
DATABASE_URL = "postgresql://..."
DEMO_MODE = "false"
APP_ENV = "production"
```

5. Publica y entra con el correo y la contraseña que definiste.
6. Crea profesionales y pacientes, luego agenda una cita y verifica que persista tras reiniciar la app.

**Nota:** Streamlit Community Cloud admite repositorios privados con permisos apropiados. La visibilidad de un repositorio no sustituye las medidas de seguridad de la aplicación; considera alojamiento dedicado y controles más estrictos para datos reales de pacientes.

## E. Checklist de habilitación

- [ ] Repositorio privado con permisos mínimos
- [ ] PostgreSQL externo con TLS, copias de seguridad y restauración probada
- [ ] Secrets configurados solo en el hosting
- [ ] Modo demo deshabilitado
- [ ] Acceso administrativo robusto
- [ ] Aviso de privacidad y políticas de tratamiento de datos de pacientes
- [ ] Revisión de seguridad, legislación aplicable y permisos operacionales
- [ ] Pruebas de agendamiento, cancelación y reprogramación completas

## F. Consideraciones funcionales de la versión 1.0

- No envía emails, WhatsApp ni SMS automáticos. Requiere configuración del proveedor y consentimiento.
- No incorpora historia clínica, odontogramas, facturación, pagos ni autorizaciones médicas.
- Un administrador maneja todos los pacientes y profesionales; no hay roles por profesional.
- Los horarios recurrentes se administran a nivel de clínica, no por profesional; las excepciones se gestionan con bloqueos individuales.
