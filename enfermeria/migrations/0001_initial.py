from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Migración inicial que refleja todas las tablas ya existentes en la BD.
    Se debe correr con:  python manage.py migrate --fake-initial
    Eso le dice a Django que las tablas ya existen y solo registra la migración.
    """

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Estudiante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, verbose_name='Nombre completo')),
                ('numero_documento', models.CharField(max_length=20, unique=True, verbose_name='Número de documento')),
                ('grado', models.CharField(max_length=5, choices=[('1A','1A'),('1B','1B'),('2A','2A'),('2B','2B'),('3A','3A'),('3B','3B'),('4A','4A'),('4B','4B'),('5A','5A'),('5B','5B'),('6A','6A'),('6B','6B'),('7A','7A'),('7B','7B'),('8A','8A'),('8B','8B'),('9A','9A'),('9B','9B'),('10A','10A'),('10B','10B'),('11A','11A'),('11B','11B')])),
                ('fecha_nacimiento', models.DateField(verbose_name='Fecha de nacimiento')),
                ('sexo', models.CharField(blank=True, max_length=1, choices=[('M','Masculino'),('F','Femenino'),('O','Otro')], verbose_name='Sexo biológico')),
                ('tipo_sangre', models.CharField(blank=True, max_length=5, choices=[('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-')], verbose_name='Tipo de sangre')),
                ('peso_kg', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Peso (kg)')),
                ('talla_cm', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Talla (cm)')),
                ('alergias', models.TextField(blank=True, verbose_name='Alergias conocidas')),
                ('condiciones_medicas', models.TextField(blank=True, verbose_name='Condiciones médicas')),
                ('medicamentos_perm', models.TextField(blank=True, verbose_name='Medicamentos de uso permanente')),
                ('discapacidad', models.TextField(blank=True, verbose_name='Discapacidad o necesidad especial')),
                ('eps', models.CharField(blank=True, max_length=100, verbose_name='EPS / Aseguradora')),
                ('regimen', models.CharField(blank=True, max_length=15, choices=[('contributivo','Contributivo'),('subsidiado','Subsidiado'),('especial','Régimen especial'),('ninguno','Sin aseguramiento')], verbose_name='Régimen de salud')),
                ('numero_poliza', models.CharField(blank=True, max_length=50, verbose_name='N.° póliza / carné EPS')),
                ('acudiente', models.CharField(max_length=100, verbose_name='Nombre del acudiente')),
                ('cc_acudiente', models.CharField(blank=True, max_length=20, verbose_name='Cédula del acudiente')),
                ('parentesco_acudiente', models.CharField(blank=True, max_length=10, choices=[('madre','Madre'),('padre','Padre'),('abuelo','Abuelo/a'),('tio','Tío/a'),('hermano','Hermano/a'),('otro','Otro')], verbose_name='Parentesco')),
                ('telefono_acudiente', models.CharField(max_length=20, verbose_name='Teléfono acudiente')),
                ('telefono_alternativo', models.CharField(blank=True, max_length=20, verbose_name='Teléfono alternativo')),
                ('correo_acudiente', models.EmailField(blank=True, verbose_name='Correo del acudiente')),
                ('direccion_residencia', models.CharField(blank=True, max_length=200, verbose_name='Dirección de residencia')),
                ('contacto_emergencia', models.CharField(blank=True, max_length=100, verbose_name='Contacto emergencia adicional')),
                ('tel_emergencia', models.CharField(blank=True, max_length=20, verbose_name='Teléfono emergencia adicional')),
                ('foto', models.ImageField(blank=True, null=True, upload_to='estudiantes/')),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Estudiante', 'verbose_name_plural': 'Estudiantes', 'ordering': ['nombre']},
        ),
        migrations.CreateModel(
            name='Medicamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('descripcion', models.TextField(blank=True)),
                ('cantidad_actual', models.IntegerField()),
                ('cantidad_minima', models.IntegerField(default=5)),
                ('unidad', models.CharField(max_length=20, choices=[('tabletas','Tabletas'),('capsulas','Cápsulas'),('ml','Mililitros (ml)'),('mg','Miligramos (mg)'),('unidades','Unidades'),('sobres','Sobres')])),
                ('fecha_vencimiento', models.DateField()),
                ('imagen', models.ImageField(blank=True, null=True, upload_to='medicamentos/', verbose_name='Imagen del medicamento')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Medicamento', 'verbose_name_plural': 'Medicamentos', 'ordering': ['nombre']},
        ),
        migrations.CreateModel(
            name='HistorialCambio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accion', models.CharField(max_length=10, choices=[('crear','Creado'),('editar','Editado'),('eliminar','Eliminado')])),
                ('modelo', models.CharField(max_length=50)),
                ('descripcion', models.TextField()),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-fecha']},
        ),
        migrations.CreateModel(
            name='Consulta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('motivo', models.CharField(max_length=50, choices=[('dolor_cabeza','Dolor de cabeza'),('dolor_estomago','Dolor de estómago'),('fiebre','Fiebre'),('lesion','Lesión / Golpe'),('mareo','Mareo'),('nauseas','Náuseas / Vómito'),('dolor_garganta','Dolor de garganta'),('alergias','Reacción alérgica'),('otro','Otro')])),
                ('descripcion_sintomas', models.TextField()),
                ('tratamiento', models.TextField()),
                ('cantidad_usada', models.PositiveIntegerField(default=1)),
                ('medicamento_suministrado', models.CharField(blank=True, max_length=100)),
                ('dosis', models.CharField(blank=True, max_length=50)),
                ('estado', models.CharField(max_length=20, choices=[('atendido','Atendido en enfermería'),('regreso_clase','Regreso a clases'),('remitido_casa','Remitido a casa'),('remitido_hospital','Remitido al hospital')])),
                ('observaciones', models.TextField(blank=True)),
                ('temperatura', models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Temperatura (°C)')),
                ('presion_arterial', models.CharField(blank=True, max_length=20, verbose_name='Presión arterial')),
                ('frecuencia_cardiaca', models.PositiveIntegerField(blank=True, null=True, verbose_name='Frec. cardíaca (lpm)')),
                ('frecuencia_respiratoria', models.PositiveIntegerField(blank=True, null=True, verbose_name='Frec. respiratoria (rpm)')),
                ('peso', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Peso (kg)')),
                ('talla', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Talla (cm)')),
                ('acudiente_notificado', models.BooleanField(default=False, verbose_name='Acudiente notificado')),
                ('hora_notificacion', models.TimeField(blank=True, null=True, verbose_name='Hora de notificación')),
                ('quien_atendio_llamada', models.CharField(blank=True, max_length=100, verbose_name='Quién atendió la llamada')),
                ('detalle_notificacion', models.TextField(blank=True, verbose_name='Detalle de la notificación')),
                ('correo_padre_madre', models.EmailField(blank=True, verbose_name='Correo padre/madre (regreso a clase)')),
                ('correo_docente', models.EmailField(blank=True, verbose_name='Correo del docente (regreso a clase)')),
                ('notificacion_clase_enviada', models.BooleanField(default=False, verbose_name='Notificación de clase enviada')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consultas', to='enfermeria.estudiante')),
                ('medicamento', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consultas_usadas', to='enfermeria.medicamento')),
            ],
            options={'verbose_name': 'Consulta', 'verbose_name_plural': 'Consultas', 'ordering': ['-fecha_hora']},
        ),
        migrations.CreateModel(
            name='Remision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('motivo', models.TextField()),
                ('hospital_destino', models.CharField(max_length=150)),
                ('eps', models.CharField(blank=True, max_length=100)),
                ('acompanante', models.CharField(max_length=100)),
                ('hora_salida', models.TimeField()),
                ('estado', models.CharField(default='pendiente', max_length=15, choices=[('pendiente','Pendiente'),('en_proceso','En proceso'),('resuelto','Resuelto')])),
                ('observaciones', models.TextField(blank=True)),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='remisiones', to='enfermeria.estudiante')),
            ],
            options={'verbose_name': 'Remisión', 'verbose_name_plural': 'Remisiones', 'ordering': ['-fecha_hora']},
        ),
        migrations.CreateModel(
            name='Seguimiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(max_length=20, choices=[('control','Control médico'),('vacuna','Vacunación'),('revision','Revisión general'),('otro','Otro')])),
                ('fecha', models.DateField()),
                ('descripcion', models.TextField()),
                ('completado', models.BooleanField(default=False)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguimientos', to='enfermeria.estudiante')),
            ],
            options={'verbose_name': 'Seguimiento', 'verbose_name_plural': 'Seguimientos', 'ordering': ['fecha']},
        ),
        migrations.CreateModel(
            name='MovimientoInventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(max_length=10, choices=[('entrada','Entrada'),('salida','Salida')])),
                ('cantidad', models.IntegerField()),
                ('motivo', models.CharField(max_length=200)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('medicamento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimientos', to='enfermeria.medicamento')),
            ],
            options={'ordering': ['-fecha']},
        ),
        migrations.CreateModel(
            name='MedicamentoConsulta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField(default=1)),
                ('dosis', models.CharField(blank=True, max_length=100)),
                ('consulta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medicamentos_usados', to='enfermeria.consulta')),
                ('medicamento', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='usos_consulta', to='enfermeria.medicamento')),
            ],
        ),
    ]
