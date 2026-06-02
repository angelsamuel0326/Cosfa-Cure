from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0002_consentimientoremision'),
    ]

    operations = [
        migrations.AddField(
            model_name='seguimiento',
            name='fecha_fin',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha fin (opcional)'),
        ),
    ]
