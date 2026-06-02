from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0025_remision_acompanante_blank'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estudiante',
            name='fecha_nacimiento',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de nacimiento'),
        ),
    ]
