from django.db import migrations


class Migration(migrations.Migration):
    """
    Migración original creaba usuario 'jenifer' automáticamente.
    Reemplazada para que el primer usuario se registre
    por la UI (flujo admin_setup).
    """

    dependencies = [
        ('enfermeria', '0023_perfilusuario_rol'),
    ]

    operations = []
