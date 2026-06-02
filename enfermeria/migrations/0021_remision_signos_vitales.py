from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0020_remision_campos_notificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='remision',
            name='temperatura',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Temperatura (°C)'),
        ),
        migrations.AddField(
            model_name='remision',
            name='presion_arterial',
            field=models.CharField(blank=True, max_length=20, verbose_name='Presión arterial'),
        ),
        migrations.AddField(
            model_name='remision',
            name='frecuencia_cardiaca',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Frec. cardíaca (lpm)'),
        ),
        migrations.AddField(
            model_name='remision',
            name='frecuencia_respiratoria',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Frec. respiratoria (rpm)'),
        ),
        migrations.AddField(
            model_name='remision',
            name='peso',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Peso (kg)'),
        ),
        migrations.AddField(
            model_name='remision',
            name='talla',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Talla (cm)'),
        ),
    ]
