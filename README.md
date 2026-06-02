# COSFA CURE — Sistema de Gestión de Enfermería Escolar
Colegio San Francisco de Asís · Cinnamon Code · SENA 2026

## Instalación

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir: http://127.0.0.1:8000/login/

---

## Configuración de variables de entorno

Copia `.env.example` como `.env` y completa los valores:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Mac / Linux
```

Variables requeridas: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `GEMINI_API_KEY`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`.

Ver `.env.example` para descripción de cada variable.

---

## Funcionalidades incluidas

- **Consultas** — Estudiantes y docentes, con historial completo
- **Inventario de medicamentos** — Control de stock, alertas de vencimiento y stock bajo
- **Remisiones** — Gestión de remisiones a hospital o casa, con consentimientos firmados
- **Seguimientos** — Planes de seguimiento médico con fechas de control
- **Chatbot IA (CURE-BOT)** — Asistente médico integrado con Google Gemini
- **Tracking de correos** — Registro de apertura de notificaciones enviadas
- **Backup y Restore** — Descarga y restauración de la base de datos (solo superusuarios)
- **Grados y promoción** — Gestión de grados escolares y promoción anual
- **Reportes y estadísticas** — Exportación a PDF y Excel
- **Notificaciones por correo** — A acudientes, docentes y coordinador
- **Historial de cambios** — Auditoría completa de acciones en el sistema

---

## Configurar correos con Gmail

### Paso 1 — Verificación en dos pasos
Ve a: https://myaccount.google.com/security  
Activa "Verificación en dos pasos"

### Paso 2 — Contraseña de aplicación
Ve a: https://myaccount.google.com/apppasswords  
→ Selecciona "Correo" → "Otro" → Escribe "COSFA CURE" → Generar  
→ Copia la contraseña de 16 caracteres

### Paso 3 — Agrega al .env
```
EMAIL_HOST_USER=tucorreo@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
```

---

## Probar sin Gmail (modo desarrollo)
Cambia en `.env`:
```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```
Los correos aparecerán en la terminal donde corre el servidor.

---

## Tareas programadas (alertas automáticas)

Usando crontab del sistema (recomendado):
```
0 7 * * * /ruta/venv/bin/python /ruta/manage.py alerta_vencimientos
0 7 * * * /ruta/venv/bin/python /ruta/manage.py alerta_seguimientos
0 3 * * * /ruta/venv/bin/python /ruta/manage.py limpiar_otp
```

O con Celery + Redis (ver comentarios en `settings.py`).
