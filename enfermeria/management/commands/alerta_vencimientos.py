"""
Management command: alerta_vencimientos
Envía automáticamente alertas de medicamentos vencidos y próximos a vencer.

Uso manual:
    python manage.py alerta_vencimientos

Cron (diariamente a las 7 AM):
    0 7 * * * /ruta/venv/bin/python /ruta/manage.py alerta_vencimientos

Celery Beat (agregar en settings.py):
    CELERY_BEAT_SCHEDULE = {
        'alerta-vencimientos-diaria': {
            'task': 'enfermeria.tasks.alerta_vencimientos_task',
            'schedule': crontab(hour=7, minute=0),
        },
    }
"""
import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


class Command(BaseCommand):
    help = 'Envía alertas automáticas de vencimiento de medicamentos a todos los usuarios activos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se enviaría sin enviar correos reales'
        )
        parser.add_argument(
            '--dias', type=int, default=30,
            help='Días de anticipación para alertar próximos vencimientos (default: 30)'
        )

    def handle(self, *args, **options):
        from enfermeria.models import Medicamento, Notificacion
        dry_run = options['dry_run']
        dias    = options['dias']
        hoy     = datetime.date.today()
        en_n    = hoy + datetime.timedelta(days=dias)

        vencidos        = list(Medicamento.objects.filter(fecha_vencimiento__lte=hoy))
        proximos_vencer = list(Medicamento.objects.filter(
            fecha_vencimiento__gt=hoy, fecha_vencimiento__lte=en_n))

        if not vencidos and not proximos_vencer:
            self.stdout.write(self.style.SUCCESS('✅ Sin alertas de vencimiento hoy.'))
            return

        # Usuarios activos con email
        usuarios = list(User.objects.filter(is_active=True).exclude(email=''))

        self.stdout.write(f'📋 Vencidos: {len(vencidos)} | Próximos ({dias}d): {len(proximos_vencer)}')
        self.stdout.write(f'👥 Destinatarios: {len(usuarios)}')

        for usuario in usuarios:
            # Crear notificación interna en el sistema
            if not dry_run:
                partes = []
                if vencidos:
                    partes.append(f'{len(vencidos)} medicamento(s) vencido(s)')
                if proximos_vencer:
                    partes.append(f'{len(proximos_vencer)} próximo(s) a vencer en {dias} días')
                Notificacion.objects.create(
                    usuario=usuario,
                    tipo='inventario',
                    titulo='⚠️ Alerta automática de vencimiento',
                    mensaje=f'Alerta diaria: {" y ".join(partes)}. Revisa el inventario.',
                    url='/inventario/',
                )

            # Enviar correo si tiene email
            if usuario.email:
                html_msg = render_to_string('enfermeria/emails/alerta_inventario.html', {
                    'vencidos':        vencidos,
                    'proximos_vencer': proximos_vencer,
                    'nombre_enfermera': usuario.get_full_name() or usuario.username,
                    'dias': dias,
                    'hoy': hoy,
                })
                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] Correo → {usuario.email}')
                else:
                    try:
                        send_mail(
                            subject=f'COSFA CURE — Alerta de vencimiento ({hoy:%d/%m/%Y})',
                            message=strip_tags(html_msg),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[usuario.email],
                            html_message=html_msg,
                            fail_silently=False,
                        )
                        self.stdout.write(f'  ✉️  Correo enviado → {usuario.email}')
                    except Exception as e:
                        self.stderr.write(f'  ❌ Error enviando a {usuario.email}: {e}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Alertas enviadas: {len(usuarios)} usuario(s) notificado(s).'
            ))
        else:
            self.stdout.write(self.style.WARNING('🔍 Dry-run completado. No se enviaron correos reales.'))
