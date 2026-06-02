from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0022_estudiante_tel_contacto_eps'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='rol',
            field=models.CharField(
                choices=[('admin', 'Administrador'), ('viewer', 'Solo lectura')],
                default='viewer',
                max_length=10,
                verbose_name='Rol',
            ),
        ),
    ]
