from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0015_codigoverificacion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estudiante',
            name='grado',
            field=models.CharField(db_index=True, max_length=10),
        ),
    ]
