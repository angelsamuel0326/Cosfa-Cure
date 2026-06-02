"""Management command: limpiar_otp — elimina códigos OTP expirados."""
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Elimina códigos OTP expirados (>10 min) de la base de datos'

    def handle(self, *args, **options):
        from enfermeria.models import CodigoVerificacion
        limite = timezone.now() - datetime.timedelta(minutes=10)
        eliminados, _ = CodigoVerificacion.objects.filter(
            creado_en__lt=limite, verificado=False
        ).delete()
        self.stdout.write(self.style.SUCCESS(f'✅ {eliminados} código(s) OTP expirado(s) eliminado(s).'))
