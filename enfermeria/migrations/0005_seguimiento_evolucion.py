from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0004_remision_tipo_destino'),
    ]

    operations = [
        migrations.AddField(
            model_name='seguimiento',
            name='continuado',
            field=models.BooleanField(default=False, verbose_name='Continúa en seguimiento'),
        ),
        migrations.AddField(
            model_name='seguimiento',
            name='evolucion',
            field=models.TextField(blank=True, verbose_name='Evolución / Notas de cierre'),
        ),
    ]
