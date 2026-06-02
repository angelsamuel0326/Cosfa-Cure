from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Carga de variables de entorno desde .env (python-decouple) ────────────────
from decouple import config, Csv

SECRET_KEY = config('SECRET_KEY')

# ── Modo DEBUG y hosts ────────────────────────────────────────────────────────
# En producción: DEBUG=False en el .env
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=Csv()
)

# ── Ngrok / proxy headers ─────────────────────────────────────────────────────
# Acepta automáticamente cualquier dominio *.ngrok-free.dev y *.ngrok.io
# para pruebas móviles sin editar .env cada vez que cambia el túnel.
ALLOWED_HOSTS += ['.ngrok-free.dev', '.ngrok.io', '.ngrok.app']

SITE_URL               = config('SITE_URL', default='http://localhost:8000')
USE_X_FORWARDED_HOST   = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'enfermeria.apps.EnfermeriaConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cosfa_cure.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'enfermeria' / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'enfermeria.context_processors.rol_usuario',
    ]},
}]

WSGI_APPLICATION = 'cosfa_cure.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-co'
TIME_ZONE     = 'America/Bogota'
USE_I18N = True
USE_TZ   = True

STATIC_URL  = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'enfermeria' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

# Crear carpetas de media automáticamente si no existen
import os as _os
for _subfolder in ['perfiles', 'estudiantes', 'docentes', 'medicamentos']:
    _os.makedirs(MEDIA_ROOT / _subfolder, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login
SESSION_COOKIE_AGE              = 60 * 60 * 24 * 30
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/inicio/'
LOGOUT_REDIRECT_URL = '/login/'

# ══════════════════════════════════════════════════════════════════════════════
# CORREO ELECTRÓNICO  —  credenciales desde .env
# ══════════════════════════════════════════════════════════════════════════════
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')   # contraseña de aplicación Google
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default='COSFA CURE Enfermería <cosfacure@gmail.com>')

# ══════════════════════════════════════════════════════════════════════════════
# CHATBOT IA — Google Gemini  —  credenciales desde .env
# ══════════════════════════════════════════════════════════════════════════════
GEMINI_API_KEY    = config('GEMINI_API_KEY', default='')
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

# ── NGROK / CSRF ─────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000',
    cast=Csv()
)
# Permite formularios POST desde ngrok sin cambiar el .env
CSRF_TRUSTED_ORIGINS += ['https://*.ngrok-free.dev', 'https://*.ngrok.io', 'https://*.ngrok.app']

# ══════════════════════════════════════════════════════════════════════════════
# CELERY — Tareas automáticas programadas
# ══════════════════════════════════════════════════════════════════════════════
CELERY_BROKER_URL     = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_TIMEZONE       = 'America/Bogota'

try:
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'alerta-vencimientos-diaria': {
            'task':     'enfermeria.tasks.alerta_vencimientos_task',
            'schedule': crontab(hour=7, minute=0),
        },
        'alerta-seguimientos-diaria': {
            'task':     'enfermeria.tasks.alerta_seguimientos_task',
            'schedule': crontab(hour=7, minute=10),
        },
        'limpieza-otp-expirados': {
            'task':     'enfermeria.tasks.limpiar_codigos_otp_task',
            'schedule': crontab(hour=3, minute=0),
        },
    }
except ImportError:
    pass  # Celery no instalado — usar cron del sistema
