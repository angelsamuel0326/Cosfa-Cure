from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0017_sesionchatbot_mensajechatbot_sesion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistroAperturaCorreo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(
                    choices=[
                        ('coordinador', '📋 Correo al coordinador'),
                        ('acudiente',   '👨‍👩‍👧 Correo a acudiente'),
                        ('remision',    '🚑 Remisión médica'),
                        ('inventario',  '💊 Alerta de inventario'),
                        ('seguimiento', '📅 Alerta de seguimiento'),
                    ],
                    db_index=True, max_length=20,
                )),
                ('objeto_id',   models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name='ID del objeto relacionado')),
                ('objeto_tipo', models.CharField(blank=True, max_length=50, verbose_name='Tipo de objeto (Consulta, Remision, etc.)')),
                ('destinatario_email',  models.EmailField(verbose_name='Email del destinatario')),
                ('destinatario_nombre', models.CharField(blank=True, max_length=200, verbose_name='Nombre del destinatario')),
                ('token',           models.CharField(db_index=True, max_length=64, unique=True)),
                ('abierto',         models.BooleanField(db_index=True, default=False)),
                ('fecha_envio',     models.DateTimeField(auto_now_add=True)),
                ('fecha_apertura',  models.DateTimeField(blank=True, null=True)),
                ('metodo_apertura', models.CharField(blank=True, choices=[('pixel', 'Píxel automático'), ('confirmacion', 'Enlace de confirmación')], default='', max_length=15)),
                ('ip_apertura',     models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent',      models.TextField(blank=True)),
                ('veces_abierto',   models.PositiveIntegerField(default=0)),
                ('enviado_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='correos_tracking',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Enviado por',
                )),
            ],
            options={
                'verbose_name': 'Registro de apertura de correo',
                'verbose_name_plural': 'Registros de apertura de correos',
                'ordering': ['-fecha_envio'],
            },
        ),
        migrations.AddIndex(
            model_name='registroaperturacorreo',
            index=models.Index(fields=['token'], name='enf_track_token_idx'),
        ),
        migrations.AddIndex(
            model_name='registroaperturacorreo',
            index=models.Index(fields=['abierto', 'tipo'], name='enf_track_abierto_idx'),
        ),
    ]
