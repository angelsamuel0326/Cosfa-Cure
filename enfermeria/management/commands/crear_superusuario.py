"""
Comando legacy — ya no es necesario.
El acceso admin ahora se gestiona desde el login con el código secreto.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Comando obsoleto. El rol admin se asigna desde el login con código secreto.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'Este comando ya no es necesario. '
            'Crea tu cuenta normalmente y usa el botón "Ingresar como Administrador" '
            'en el login con el código secreto.'
        ))
