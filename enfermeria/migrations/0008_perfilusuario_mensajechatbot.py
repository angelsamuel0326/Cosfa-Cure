from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('enfermeria', '0007_medicamento_categoria_remision_nuevos_campos'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cargo', models.CharField(blank=True, default='Enfermera/o', max_length=100, verbose_name='Cargo')),
                ('telefono', models.CharField(blank=True, max_length=20, verbose_name='Teléfono de contacto')),
                ('firma_digital', models.TextField(blank=True, verbose_name='Firma digital (base64 SVG)')),
                ('foto', models.ImageField(blank=True, null=True, upload_to='perfiles/', verbose_name='Foto de perfil')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='perfilusuario',
                    to='auth.user',
                )),
            ],
            options={
                'verbose_name': 'Perfil de usuario',
                'verbose_name_plural': 'Perfiles de usuario',
            },
        ),
        migrations.CreateModel(
            name='MensajeChatbot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'Usuario'), ('assistant', 'CURE-BOT')], max_length=10)),
                ('content', models.TextField()),
                ('modelo_ia', models.CharField(blank=True, max_length=50, verbose_name='Modelo IA usado')),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mensajes_chatbot',
                    to='auth.user',
                )),
            ],
            options={
                'verbose_name': 'Mensaje del chatbot',
                'verbose_name_plural': 'Historial del chatbot',
                'ordering': ['fecha'],
            },
        ),
    ]
