from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0018_registroaperturacorreo'),
    ]

    operations = [
        migrations.AddField(
            model_name='remision',
            name='numero_eps',
            field=models.CharField(blank=True, max_length=50, verbose_name='Número de carné / póliza EPS'),
        ),
    ]
