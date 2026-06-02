from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0010_alter_medicamento_options_and_more'),
    ]

    operations = [
        # Agrega hora_atencion a Consulta (obligatorio, default=hora actual para registros existentes)
        migrations.AddField(
            model_name='consulta',
            name='hora_atencion',
            field=models.TimeField(
                default=datetime.time(0, 0),
                verbose_name='Hora de atención',
                help_text='Hora exacta en que se atendió al estudiante',
            ),
            preserve_default=False,
        ),
        # Crea el modelo ConsultaDocente
        migrations.CreateModel(
            name='ConsultaDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_completo', models.CharField(max_length=150, verbose_name='Nombre completo')),
                ('cedula', models.CharField(max_length=20, verbose_name='Cédula')),
                ('edad', models.PositiveIntegerField(blank=True, null=True, verbose_name='Edad')),
                ('fecha_nacimiento', models.DateField(blank=True, null=True, verbose_name='Fecha de nacimiento')),
                ('tipo', models.CharField(default='Docente', editable=False, max_length=30, verbose_name='Tipo')),
                ('area_grado', models.CharField(max_length=150, verbose_name='Área / Grado que atiende')),
                ('eps', models.CharField(blank=True, max_length=100, verbose_name='EPS')),
                ('fecha_hora', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('hora_atencion', models.TimeField(help_text='Hora exacta en que se atendió al docente', verbose_name='Hora de atención')),
                ('motivo', models.CharField(
                    choices=[
                        ('dolor_cabeza', 'Dolor de cabeza'), ('dolor_estomago', 'Dolor de estómago'),
                        ('fiebre', 'Fiebre'), ('lesion', 'Lesión / Golpe'), ('mareo', 'Mareo'),
                        ('nauseas', 'Náuseas / Vómito'), ('dolor_garganta', 'Dolor de garganta'),
                        ('alergias', 'Reacción alérgica'), ('otro', 'Otro'),
                    ],
                    db_index=True, max_length=50,
                )),
                ('descripcion_sintomas', models.TextField(verbose_name='Descripción de síntomas')),
                ('tratamiento', models.TextField(verbose_name='Tratamiento aplicado')),
                ('estado', models.CharField(
                    choices=[
                        ('atendido', 'Atendido en enfermería'),
                        ('regreso_clase', 'Regresa a sus actividades'),
                        ('remitido_casa', 'Remitido a casa'),
                        ('remitido_hospital', 'Remitido al hospital'),
                    ],
                    db_index=True, max_length=20,
                )),
                ('observaciones', models.TextField(blank=True)),
                ('temperatura', models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Temperatura (°C)')),
                ('presion_arterial', models.CharField(blank=True, max_length=20, verbose_name='Presión arterial')),
                ('frecuencia_cardiaca', models.PositiveIntegerField(blank=True, null=True, verbose_name='Frec. cardíaca (lpm)')),
                ('frecuencia_respiratoria', models.PositiveIntegerField(blank=True, null=True, verbose_name='Frec. respiratoria (rpm)')),
                ('peso', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Peso (kg)')),
                ('talla', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Talla (cm)')),
                ('medicamento_suministrado', models.CharField(blank=True, max_length=200)),
            ],
            options={
                'verbose_name': 'Consulta Docente',
                'verbose_name_plural': 'Consultas Docentes',
                'ordering': ['-fecha_hora'],
                'indexes': [
                    models.Index(fields=['-fecha_hora'], name='enfermeria__fecha_h_docente_idx'),
                    models.Index(fields=['cedula'], name='enfermeria__cedula_docente_idx'),
                ],
            },
        ),
    ]
