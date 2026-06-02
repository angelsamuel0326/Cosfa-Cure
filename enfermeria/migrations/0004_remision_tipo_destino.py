from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0003_seguimiento_fecha_fin'),
    ]

    operations = [
        migrations.AddField(
            model_name='remision',
            name='tipo_destino',
            field=models.CharField(
                choices=[('hospital', 'Hospital / Centro médico'), ('casa', 'Casa del estudiante')],
                default='hospital',
                max_length=10,
                verbose_name='Tipo de destino',
            ),
        ),
        migrations.AlterField(
            model_name='remision',
            name='hospital_destino',
            field=models.CharField(blank=True, max_length=150, verbose_name='Hospital / Clínica de destino'),
        ),
    ]
