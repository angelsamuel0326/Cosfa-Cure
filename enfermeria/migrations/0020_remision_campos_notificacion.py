from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0019_remision_numero_eps'),
    ]

    operations = [
        migrations.AddField(
            model_name='remision',
            name='numero_contacto_eps',
            field=models.CharField(blank=True, max_length=30, verbose_name='Número de contacto EPS'),
        ),
        migrations.AddField(
            model_name='remision',
            name='acudiente_notificado',
            field=models.BooleanField(default=False, verbose_name='¿Se notificó al acudiente?'),
        ),
        migrations.AddField(
            model_name='remision',
            name='hora_notificacion',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora de notificación'),
        ),
        migrations.AddField(
            model_name='remision',
            name='quien_atendio_llamada',
            field=models.CharField(blank=True, max_length=100, verbose_name='¿Quién atendió la llamada?'),
        ),
        migrations.AddField(
            model_name='remision',
            name='detalle_notificacion',
            field=models.TextField(blank=True, verbose_name='Detalle de lo informado'),
        ),
        migrations.AddField(
            model_name='remision',
            name='correo_padre_madre',
            field=models.EmailField(blank=True, verbose_name='Correo padre / madre / acudiente'),
        ),
        migrations.AddField(
            model_name='remision',
            name='correo_docente',
            field=models.EmailField(blank=True, verbose_name='Correo del docente'),
        ),
    ]
