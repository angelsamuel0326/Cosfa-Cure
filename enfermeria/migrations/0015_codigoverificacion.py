from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0014_notificacion_correcoordinador'),
    ]

    operations = [
        migrations.CreateModel(
            name='CodigoVerificacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('username', models.CharField(max_length=150)),
                ('password', models.CharField(max_length=255)),
                ('codigo', models.CharField(max_length=6)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('verificado', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Código de verificación',
                'ordering': ['-creado_en'],
            },
        ),
    ]
