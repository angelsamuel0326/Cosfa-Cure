from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0021_remision_signos_vitales'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='tel_contacto_eps',
            field=models.CharField(blank=True, max_length=30, verbose_name='Teléfono de contacto / urgencias EPS'),
        ),
    ]
