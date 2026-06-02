from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enfermeria', '0013_gradoescolar_estudiante_estado_anio'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notificacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(
                    choices=[
                        ('consulta', '🩺 Nueva consulta'),
                        ('remision', '🚑 Remisión'),
                        ('seguimiento', '📋 Seguimiento'),
                        ('inventario', '💊 Inventario bajo'),
                        ('sistema', 'ℹ️ Sistema'),
                    ],
                    default='sistema', max_length=20)),
                ('titulo', models.CharField(max_length=200)),
                ('mensaje', models.TextField()),
                ('url', models.CharField(blank=True, max_length=300)),
                ('leida', models.BooleanField(db_index=True, default=False)),
                ('fecha', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('usuario', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notificaciones',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-fecha'], 'verbose_name': 'Notificación', 'verbose_name_plural': 'Notificaciones'},
        ),
        migrations.CreateModel(
            name='CorreoCoordinador',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('correo_dest', models.EmailField(verbose_name='Correo del coordinador')),
                ('motivo', models.CharField(
                    choices=[
                        ('urgencia', '🚨 Urgencia médica'),
                        ('remision', '🚑 Remisión a centro médico'),
                        ('accidente', '⚠️ Accidente escolar'),
                        ('medicamento', '💊 Solicitud de medicamento'),
                        ('seguimiento', '📋 Informe de seguimiento'),
                        ('inventario', '📦 Inventario crítico'),
                        ('ausentismo', '📅 Ausentismo por salud'),
                        ('otro', '📝 Otro motivo'),
                    ],
                    max_length=30,
                )),
                ('asunto', models.CharField(max_length=200)),
                ('cuerpo', models.TextField(verbose_name='Mensaje')),
                ('enviado', models.BooleanField(default=False)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('error_msg', models.TextField(blank=True)),
                ('remitente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='correos_enviados_coordinador',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-fecha'], 'verbose_name': 'Correo al coordinador', 'verbose_name_plural': 'Correos al coordinador'},
        ),
    ]
