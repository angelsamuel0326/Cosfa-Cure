"""
Management command: alerta_seguimientos
Revisa seguimientos vencidos y próximos a vencer, crea notificaciones
internas en el sistema para todos los usuarios activos.

Uso manual:
    python manage.py alerta_seguimientos

Cron (diariamente a las 7 AM junto con alerta_vencimientos):
    0 7 * * * /ruta/venv/bin/python /ruta/manage.py alerta_seguimientos

Celery Beat (agregar en settings.py):
    CELERY_BEAT_SCHEDULE = {
        'alerta-seguimientos-diaria': {
            'task': 'enfermeria.tasks.alerta_seguimientos_task',
            'schedule': crontab(hour=7, minute=10),
        },
    }
"""
import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea notificaciones internas para seguimientos vencidos y próximos a vencer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se notificaría sin crear registros reales',
        )
        parser.add_argument(
            '--dias', type=int, default=7,
            help='Días de anticipación para alertar seguimientos próximos (default: 7)',
        )

    def handle(self, *args, **options):
        from enfermeria.models import Seguimiento, Notificacion

        dry_run  = options['dry_run']
        dias     = options['dias']
        hoy      = datetime.date.today()
        en_n     = hoy + datetime.timedelta(days=dias)

        vencidos = Seguimiento.objects.filter(
            completado=False, fecha__lt=hoy
        ).select_related('estudiante').order_by('fecha')

        proximos = Seguimiento.objects.filter(
            completado=False, fecha__gte=hoy, fecha__lte=en_n
        ).select_related('estudiante').order_by('fecha')

        self.stdout.write(
            f'📋 Vencidos sin completar: {vencidos.count()} | '
            f'Próximos {dias} días: {proximos.count()}'
        )

        if not vencidos.exists() and not proximos.exists():
            self.stdout.write(self.style.SUCCESS('✅ Sin seguimientos pendientes hoy.'))
            return

        usuarios  = list(User.objects.filter(is_active=True))
        creadas   = 0

        for u in usuarios:
            # ── Notificación: vencidos ─────────────────────────────────────
            if vencidos.exists():
                nombres = ', '.join(s.estudiante.nombre for s in vencidos[:3])
                extra   = f' y {vencidos.count() - 3} más' if vencidos.count() > 3 else ''
                titulo  = f'🔴 {vencidos.count()} seguimiento(s) vencido(s) sin completar'
                mensaje = f'Pendientes: {nombres}{extra}. Revisa el calendario.'

                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] Notif vencidos → {u.username}: {titulo}')
                else:
                    Notificacion.objects.create(
                        usuario=u,
                        tipo='seguimiento',
                        titulo=titulo,
                        mensaje=mensaje,
                        url='/enfermeria/calendario/',
                    )
                    creadas += 1

            # ── Notificación: próximos ─────────────────────────────────────
            if proximos.exists():
                nombres = ', '.join(s.estudiante.nombre for s in proximos[:3])
                extra   = f' y {proximos.count() - 3} más' if proximos.count() > 3 else ''
                titulo  = f'🟡 {proximos.count()} seguimiento(s) en los próximos {dias} días'
                mensaje = f'Próximos: {nombres}{extra}.'

                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] Notif próximos → {u.username}: {titulo}')
                else:
                    Notificacion.objects.create(
                        usuario=u,
                        tipo='seguimiento',
                        titulo=titulo,
                        mensaje=mensaje,
                        url='/enfermeria/calendario/',
                    )
                    creadas += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'🔍 Dry-run: se crearían {(vencidos.exists() + proximos.exists()) * len(usuarios)} notificaciones.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'✅ {creadas} notificación(es) creadas para {len(usuarios)} usuario(s).'
            ))

        # Imprimir detalle de vencidos
        if vencidos.exists():
            self.stdout.write('\n🔴 Seguimientos vencidos:')
            for s in vencidos:
                self.stdout.write(
                    f'   • {s.estudiante.nombre} ({s.estudiante.grado}) — '
                    f'{s.get_tipo_display()} — vencía el {s.fecha}'
                )

        # Imprimir detalle de próximos
        if proximos.exists():
            self.stdout.write(f'\n🟡 Próximos {dias} días:')
            for s in proximos:
                dias_restantes = (s.fecha - hoy).days
                self.stdout.write(
                    f'   • {s.estudiante.nombre} ({s.estudiante.grado}) — '
                    f'{s.get_tipo_display()} — en {dias_restantes} día(s) ({s.fecha})'
                )
