from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0012_docente_consultadocente_fk'),
    ]

    operations = [
        # Crear modelo GradoEscolar
        migrations.CreateModel(
            name='GradoEscolar',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=10, unique=True, verbose_name='Nombre del grado')),
                ('orden', models.PositiveSmallIntegerField(default=0, verbose_name='Orden de visualización')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Grado Escolar',
                'verbose_name_plural': 'Grados Escolares',
                'ordering': ['orden', 'nombre'],
            },
        ),
        # Ampliar campo grado de Estudiante (de max_length=5 a 10)
        migrations.AlterField(
            model_name='estudiante',
            name='grado',
            field=models.CharField(
                choices=[
                    ('1A','1A'),('1B','1B'),('2A','2A'),('2B','2B'),
                    ('3A','3A'),('3B','3B'),('4A','4A'),('4B','4B'),
                    ('5A','5A'),('5B','5B'),('6A','6A'),('6B','6B'),
                    ('7A','7A'),('7B','7B'),('8A','8A'),('8B','8B'),
                    ('9A','9A'),('9B','9B'),('10A','10A'),('10B','10B'),
                    ('11A','11A'),('11B','11B'),
                ],
                db_index=True,
                max_length=10,
            ),
        ),
        # Agregar estado_academico
        migrations.AddField(
            model_name='estudiante',
            name='estado_academico',
            field=models.CharField(
                choices=[
                    ('activo', 'Activo'),
                    ('graduado', 'Graduado'),
                    ('retirado', 'Retirado'),
                    ('trasladado', 'Trasladado'),
                ],
                db_index=True,
                default='activo',
                max_length=12,
                verbose_name='Estado académico',
            ),
        ),
        # Agregar anio_lectivo
        migrations.AddField(
            model_name='estudiante',
            name='anio_lectivo',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name='Año lectivo',
                help_text='Año escolar actual del estudiante',
            ),
        ),
        # Poblar grados por defecto
        migrations.RunPython(
            code=lambda apps, schema_editor: _seed_grados(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
    ]


def _seed_grados(apps, schema_editor):
    GradoEscolar = apps.get_model('enfermeria', 'GradoEscolar')
    grados = [
        '1A','1B','2A','2B','3A','3B','4A','4B','5A','5B',
        '6A','6B','7A','7B','8A','8B','9A','9B','10A','10B','11A','11B',
    ]
    for i, g in enumerate(grados):
        GradoEscolar.objects.get_or_create(nombre=g, defaults={'orden': i})
