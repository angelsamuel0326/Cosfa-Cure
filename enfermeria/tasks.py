"""
enfermeria/tasks.py — Tareas Celery para COSFA CURE
=====================================================

INSTALACIÓN (si se usa Celery):
    pip install celery redis

CONFIGURACIÓN en cosfa_cure/settings.py:
    CELERY_BROKER_URL    = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
    CELERY_TIMEZONE      = 'America/Bogota'

    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'alerta-vencimientos-diaria': {
            'task': 'enfermeria.tasks.alerta_vencimientos_task',
            'schedule': crontab(hour=7, minute=0),   # cada día a las 7 AM
        },
        'limpieza-otp-expirados': {
            'task': 'enfermeria.tasks.limpiar_codigos_otp_task',
            'schedule': crontab(hour=3, minute=0),   # cada día a las 3 AM
        },
    }

CREAR cosfa_cure/celery.py:
    import os
    from celery import Celery
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cosfa_cure.settings')
    app = Celery('cosfa_cure')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()

AGREGAR en cosfa_cure/__init__.py:
    from .celery import app as celery_app
    __all__ = ('celery_app',)

INICIAR workers:
    celery -A cosfa_cure worker -l info
    celery -A cosfa_cure beat -l info

ALTERNATIVA SIN CELERY (cron del sistema):
    # En crontab (`crontab -e`):
    0 7 * * * /ruta/venv/bin/python /ruta/cosfa_edit/manage.py alerta_vencimientos
    0 3 * * * /ruta/venv/bin/python /ruta/cosfa_edit/manage.py limpiar_otp
"""
import datetime

# Importación condicional de Celery para no romper si no está instalado
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    # Fallback: decorador vacío para que el módulo no falle
    def shared_task(func=None, **kwargs):
        if func:
            return func
        def decorator(f):
            return f
        return decorator
    CELERY_AVAILABLE = False


@shared_task(name='enfermeria.tasks.alerta_vencimientos_task', bind=True, max_retries=3)
def alerta_vencimientos_task(self, dias_anticipacion=30):
    """
    Tarea automática diaria: detecta medicamentos vencidos/próximos a vencer
    y envía notificaciones internas + correos a todos los usuarios activos.
    """
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from enfermeria.models import Medicamento, Notificacion

    hoy  = datetime.date.today()
    en_n = hoy + datetime.timedelta(days=dias_anticipacion)

    vencidos        = list(Medicamento.objects.filter(fecha_vencimiento__lte=hoy))
    proximos_vencer = list(Medicamento.objects.filter(
        fecha_vencimiento__gt=hoy, fecha_vencimiento__lte=en_n))

    if not vencidos and not proximos_vencer:
        return {'status': 'ok', 'mensaje': 'Sin alertas de vencimiento'}

    usuarios = list(User.objects.filter(is_active=True).exclude(email=''))
    enviados = 0
    errores  = []

    partes = []
    if vencidos:
        partes.append(f'{len(vencidos)} medicamento(s) vencido(s)')
    if proximos_vencer:
        partes.append(f'{len(proximos_vencer)} próximo(s) a vencer en {dias_anticipacion} días')
    resumen = ' y '.join(partes)

    for usuario in usuarios:
        # Notificación interna
        Notificacion.objects.create(
            usuario=usuario,
            tipo='inventario',
            titulo='⚠️ Alerta automática de vencimiento',
            mensaje=f'Alerta diaria: {resumen}. Revisa el inventario.',
            url='/inventario/',
        )
        # Correo
        try:
            from django.core.mail import EmailMultiAlternatives
            from email.mime.image import MIMEImage
            import os
            html_msg = render_to_string('enfermeria/emails/alerta_inventario.html', {
                'vencidos':        vencidos,
                'proximos_vencer': proximos_vencer,
                'nombre_enfermera': usuario.get_full_name() or usuario.username,
                'dias': dias_anticipacion,
                'hoy': hoy,
            })
            msg = EmailMultiAlternatives(
                subject=f'COSFA CURE — Alerta de vencimiento ({hoy:%d/%m/%Y})',
                body=strip_tags(html_msg),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[usuario.email],
            )
            msg.attach_alternative(html_msg, 'text/html')
            msg.mixed_subtype = 'related'
            logo_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'static', 'icons', 'logo_cosfa.png'
            )
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo = MIMEImage(f.read(), _subtype='png')
                logo.add_header('Content-ID', '<logo_cosfa>')
                logo.add_header('Content-Disposition', 'inline', filename='logo_cosfa.png')
                msg.attach(logo)
            msg.send(fail_silently=False)
            enviados += 1
        except Exception as exc:
            errores.append(f'{usuario.email}: {exc}')

    return {
        'status': 'ok',
        'vencidos': len(vencidos),
        'proximos': len(proximos_vencer),
        'enviados': enviados,
        'errores': errores,
    }


@shared_task(name='enfermeria.tasks.alerta_seguimientos_task', bind=True, max_retries=3)
def alerta_seguimientos_task(self, dias_anticipacion=7):
    """
    Tarea automática diaria: detecta seguimientos vencidos y próximos a vencer
    y crea notificaciones internas en el sistema para todos los usuarios activos.
    """
    import datetime
    from django.contrib.auth.models import User
    from enfermeria.models import Seguimiento, Notificacion

    hoy    = datetime.date.today()
    en_n   = hoy + datetime.timedelta(days=dias_anticipacion)

    vencidos = list(Seguimiento.objects.filter(
        completado=False, fecha__lt=hoy
    ).select_related('estudiante'))

    proximos = list(Seguimiento.objects.filter(
        completado=False, fecha__gte=hoy, fecha__lte=en_n
    ).select_related('estudiante'))

    if not vencidos and not proximos:
        return {'status': 'ok', 'mensaje': 'Sin seguimientos pendientes'}

    usuarios = list(User.objects.filter(is_active=True))
    creadas  = 0

    for u in usuarios:
        if vencidos:
            nombres = ', '.join(s.estudiante.nombre for s in vencidos[:3])
            extra   = f' y {len(vencidos)-3} más' if len(vencidos) > 3 else ''
            Notificacion.objects.create(
                usuario=u,
                tipo='seguimiento',
                titulo=f'🔴 {len(vencidos)} seguimiento(s) vencido(s) sin completar',
                mensaje=f'Pendientes: {nombres}{extra}. Revisa el calendario.',
                url='/enfermeria/calendario/',
            )
            creadas += 1

        if proximos:
            nombres = ', '.join(s.estudiante.nombre for s in proximos[:3])
            extra   = f' y {len(proximos)-3} más' if len(proximos) > 3 else ''
            Notificacion.objects.create(
                usuario=u,
                tipo='seguimiento',
                titulo=f'🟡 {len(proximos)} seguimiento(s) en los próximos {dias_anticipacion} días',
                mensaje=f'Próximos: {nombres}{extra}.',
                url='/enfermeria/calendario/',
            )
            creadas += 1

    return {
        'status': 'ok',
        'vencidos': len(vencidos),
        'proximos': len(proximos),
        'notificaciones_creadas': creadas,
    }


@shared_task(name='enfermeria.tasks.limpiar_codigos_otp_task')
def limpiar_codigos_otp_task():
    """
    Limpia periódicamente los códigos OTP expirados (> 10 min) y no verificados.
    Ejecutar diariamente para mantener la tabla limpia.
    """
    from django.utils import timezone
    from enfermeria.models import CodigoVerificacion
    limite = timezone.now() - datetime.timedelta(minutes=10)
    eliminados, _ = CodigoVerificacion.objects.filter(
        creado_en__lt=limite, verificado=False
    ).delete()
    return {'eliminados': eliminados}
