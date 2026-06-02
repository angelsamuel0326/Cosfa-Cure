from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enfermeria', '0016_estudiante_grado_sin_choices'),
    ]

    operations = [
        migrations.CreateModel(
            name='SesionChatbot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(blank=True, default='Nueva conversación', max_length=120)),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('actualizada', models.DateTimeField(auto_now=True)),
                ('activa', models.BooleanField(default=True)),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sesiones_chatbot',
                    to=settings.AUTH_USER_MODEL,
                    db_index=True,
                )),
            ],
            options={
                'verbose_name': 'Sesión de chatbot',
                'verbose_name_plural': 'Sesiones de chatbot',
                'ordering': ['-actualizada'],
            },
        ),
        migrations.AddField(
            model_name='mensajechatbot',
            name='sesion',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mensajes',
                to='enfermeria.sesionchatbot',
            ),
        ),
    ]
