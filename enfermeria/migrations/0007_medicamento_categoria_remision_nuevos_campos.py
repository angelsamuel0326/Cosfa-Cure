from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0006_remision_consulta_origen'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicamento',
            name='categoria',
            field=models.CharField(
                choices=[
                    ('insumo', 'Insumo / Primeros auxilios'),
                    ('medicamento', 'Medicamento (requiere prescripción)'),
                ],
                default='insumo',
                max_length=20,
                verbose_name='Categoría',
            ),
        ),
        migrations.AddField(
            model_name='remision',
            name='hora_llegada',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora de llegada / regreso'),
        ),
        migrations.AddField(
            model_name='remision',
            name='seguimiento_posterior',
            field=models.TextField(blank=True, verbose_name='Seguimiento posterior / diagnóstico recibido'),
        ),
    ]
